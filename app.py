from __future__ import annotations

import shutil
import os
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from flask import Flask, after_this_request, render_template_string, request, send_file
import yt_dlp
import imageio_ffmpeg

app = Flask(__name__)


class DownloadLogger:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def debug(self, message: str) -> None:
        self.messages.append(message)

    def info(self, message: str) -> None:
        self.messages.append(message)

    def warning(self, message: str) -> None:
        self.messages.append(f"WARNING: {message}")

    def error(self, message: str) -> None:
        self.messages.append(f"ERROR: {message}")

PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>YouTube Media Downloader</title>
  <style>
    body { font: 16px system-ui, sans-serif; background: #f3f5f8; color: #18202b; margin: 0; }
    main { max-width: 560px; margin: 10vh auto; padding: 30px; background: white; border-radius: 14px; box-shadow: 0 8px 30px #18202b18; }
    h1 { margin-top: 0; font-size: 1.55rem; }
    label { display: block; margin: 18px 0 6px; font-weight: 600; }
    input, select, button { box-sizing: border-box; width: 100%; padding: 11px 12px; font: inherit; border: 1px solid #c8d0da; border-radius: 7px; }
    button { margin-top: 20px; border: 0; background: #1769e0; color: white; font-weight: 650; cursor: pointer; }
    button:hover { background: #0e56c4; }
    .error { margin: 18px 0 0; padding: 12px; color: #842029; background: #f8d7da; border-radius: 7px; }
    .error { white-space: pre-wrap; }
    .note { color: #596575; font-size: .9rem; margin-bottom: 0; }
    .hint { color: #596575; display: block; font-size: .85rem; margin-top: 6px; }
  </style>
</head>
<body><main>
  <h1>YouTube Media Downloader</h1>
  <p>Download one video as MP4 or its audio as MP3.</p>
  <form method="post" action="/download">
    <label for="url">YouTube URL</label>
    <input id="url" name="url" type="url" placeholder="https://www.youtube.com/watch?v=…" required value="{{ url|default('', true) }}">
    <label for="format">Format</label>
    <select id="format" name="format">
      <option value="audio" {% if media_format == 'audio' %}selected{% endif %}>Audio (MP3)</option>
      <option value="video" {% if media_format == 'video' %}selected{% endif %}>Video (MP4)</option>
    </select>
    <div id="quality-group" {% if media_format != 'video' %}hidden{% endif %}>
      <label for="quality">Maximum video resolution</label>
      <select id="quality" name="quality">
        <option value="best" {% if quality == 'best' %}selected{% endif %}>Best available</option>
        <option value="1080" {% if quality == '1080' %}selected{% endif %}>Up to 1080p</option>
        <option value="720" {% if quality == '720' %}selected{% endif %}>Up to 720p</option>
        <option value="480" {% if quality == '480' %}selected{% endif %}>Up to 480p</option>
        <option value="360" {% if quality == '360' %}selected{% endif %}>Up to 360p</option>
      </select>
      <small class="hint">Lower resolution usually means a smaller download.</small>
    </div>
    <button type="submit">Download</button>
  </form>
  {% if error %}<div class="error">{{ error }}</div>{% endif %}
  <p class="note">Only download content you own or are authorized to save. Follow YouTube’s terms and applicable copyright law.</p>
</main>
<script>
  const formatSelect = document.getElementById("format");
  const qualityGroup = document.getElementById("quality-group");
  formatSelect.addEventListener("change", () => {
    qualityGroup.hidden = formatSelect.value !== "video";
  });
</script>
</body></html>"""


def normalize_youtube_url(value: str) -> str | None:
    try:
        parsed = urlparse(value.strip())
    except ValueError:
        return None
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme not in {"http", "https"} or not (
        host == "youtu.be" or host == "youtube.com" or host.endswith(".youtube.com")
    ):
        return None

    parts = [part for part in parsed.path.split("/") if part]
    video_id = None
    if host == "youtu.be" and parts:
        video_id = parts[0]
    elif parts and parts[0] in {"embed", "shorts", "live"} and len(parts) > 1:
        video_id = parts[1]
    elif parsed.path.rstrip("/") == "/watch":
        video_id = parse_qs(parsed.query).get("v", [None])[0]

    if not video_id or len(video_id) != 11 or not all(ch.isalnum() or ch in "_-" for ch in video_id):
        return None
    return f"https://www.youtube.com/watch?v={video_id}"


@app.get("/")
def home():
    return render_template_string(PAGE, error=None, media_format="audio", quality="best")


@app.post("/download")
def download():
    url = request.form.get("url", "").strip()
    media_format = request.form.get("format", "audio")
    quality = request.form.get("quality", "best")
    valid_qualities = {"best", "1080", "720", "480", "360"}
    download_url = normalize_youtube_url(url)
    if not download_url:
        return render_template_string(PAGE, error="Enter a valid YouTube URL.", url=url, media_format=media_format, quality=quality), 400
    if media_format not in {"audio", "video"}:
        return render_template_string(PAGE, error="Choose audio or video format.", url=url, media_format="audio", quality=quality), 400
    if quality not in valid_qualities:
        return render_template_string(PAGE, error="Choose a valid video resolution.", url=url, media_format=media_format, quality="best"), 400

    temp_dir = Path(tempfile.mkdtemp(prefix="youtube-downloader-"))
    output_template = str(temp_dir / "%(title).160B [%(id)s].%(ext)s")
    ytdlp_logger = DownloadLogger()
    options = {
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": True,
        "verbose": True,
        "logger": ytdlp_logger,
        "windowsfilenames": True,
        "cachedir": str(Path(__file__).parent / ".cache"),
        "ffmpeg_location": imageio_ffmpeg.get_ffmpeg_exe(),
        # Avoid inheriting stale HTTP_PROXY/HTTPS_PROXY values (for example,
        # a dead localhost proxy). Set YTDLP_PROXY when a working proxy is needed.
        "proxy": os.environ.get("YTDLP_PROXY", ""),
        "js_runtimes": {"node": {"path": shutil.which("node")}} if shutil.which("node") else None,
    }
    if media_format == "audio":
        options.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })
        extension = "mp3"
    else:
        if quality == "best":
            video_format = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        else:
            video_format = (
                f"bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/"
                f"best[height<={quality}][ext=mp4]/best[height<={quality}]"
            )
        options.update({
            "format": video_format,
            "merge_output_format": "mp4",
        })
        extension = "mp4"

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([download_url])
        files = list(temp_dir.glob(f"*.{extension}"))
        if not files:
            raise FileNotFoundError("The converted download file was not created.")
        response = send_file(files[0], as_attachment=True, download_name=f"youtube_media.{extension}")
        response.call_on_close(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
        return response
    except Exception as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        message = str(exc)
        proxy_unreachable = "unable to connect to proxy" in message.lower() or "proxyerror" in message.lower()
        if proxy_unreachable:
            message = (
                "The configured network proxy is unreachable (the log shows 127.0.0.1:9). "
                "Check your HTTP_PROXY, HTTPS_PROXY, or ALL_PROXY settings, then restart the app. "
                "This is a network connection issue, not a video-quality setting."
            )
        elif "ffmpeg" in message.lower():
            message = "The bundled FFmpeg could not process this media. Try another video or check the server output."
        diagnostics = "\n".join(ytdlp_logger.messages[-30:])
        if diagnostics and not proxy_unreachable:
            message = f"{message}\n\nDownloader details:\n{diagnostics}"
        return render_template_string(PAGE, error=f"Download failed: {message}", url=url, media_format=media_format, quality=quality), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)


