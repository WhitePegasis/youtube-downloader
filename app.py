from __future__ import annotations

import shutil
import os
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from flask import Flask, jsonify, render_template_string, request, send_file
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
    :root { color-scheme: light; --ink:#182238; --muted:#68748a; --line:#e2e7ef; --blue:#536dfe; }
    * { box-sizing: border-box; }
    body { min-height:100vh; margin:0; padding:42px 18px; display:grid; place-items:center; font:15px/1.5 Inter, ui-sans-serif, system-ui, sans-serif; color:var(--ink); background:radial-gradient(ellipse at 15% 12%,#dce5ff 0,transparent 38%),radial-gradient(ellipse at 90% 88%,#e8ddff 0,transparent 34%),#f7f8fc; }
    main { width:min(100%,620px); padding:clamp(24px,5vw,42px); background:#ffffffed; border:1px solid #fff; border-radius:24px; box-shadow:0 24px 80px #29365c1a,0 2px 8px #29365c0a; }
    .brand { display:flex; align-items:center; gap:12px; margin-bottom:28px; }
    .brand-icon { display:grid; place-items:center; width:44px; height:44px; border-radius:14px; color:white; background:linear-gradient(145deg,#ff5964,#e62745); box-shadow:0 8px 18px #e6274533; }
    .brand-icon svg { width:22px; height:22px; }
    .eyebrow { margin:0; color:var(--muted); font-size:.72rem; font-weight:750; letter-spacing:.12em; text-transform:uppercase; }
    h1 { margin:2px 0 0; font-size:1.18rem; letter-spacing:-.025em; }
    .intro { margin:0 0 25px; color:var(--muted); }
    label { display:block; margin:18px 0 7px; font-weight:700; font-size:.88rem; }
    input,select,button { width:100%; min-height:48px; padding:12px 14px; font:inherit; border-radius:11px; }
    input,select { color:var(--ink); background:#fff; border:1px solid var(--line); outline:none; transition:border-color .15s,box-shadow .15s; }
    input:focus,select:focus { border-color:var(--blue); box-shadow:0 0 0 4px #536dfe1c; }
    .url-wrap { position:relative; }
    .url-wrap input { padding-right:100px; }
    .paste-hint { position:absolute; right:12px; top:50%; transform:translateY(-50%); color:var(--blue); font-size:.78rem; font-weight:700; pointer-events:none; }
    .preview { display:none; align-items:center; gap:14px; margin-top:14px; padding:10px; border:1px solid var(--line); border-radius:13px; background:#fafbff; }
    .preview.visible { display:flex; }
    .preview img { width:108px; aspect-ratio:16/9; object-fit:cover; border-radius:8px; background:#e7eaf2; }
    .preview-copy { min-width:0; }
    .video-title { margin:0; font-weight:700; line-height:1.35; overflow-wrap:anywhere; }
    .preview-status,.hint { display:block; margin-top:4px; color:var(--muted); font-size:.8rem; }
    .options { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
    .options label { margin-top:18px; }
    button { display:flex; justify-content:center; align-items:center; gap:9px; margin-top:25px; border:0; color:white; background:linear-gradient(110deg,#536dfe,#7357ed); box-shadow:0 9px 20px #536dfe30; font-weight:750; cursor:pointer; transition:transform .15s,box-shadow .15s; }
    button:hover { transform:translateY(-1px); box-shadow:0 12px 24px #536dfe42; }
    button:disabled { opacity:.65; cursor:wait; transform:none; }
    button svg { width:18px; height:18px; }
    .error { margin:18px 0 0; padding:13px 15px; color:#8c2936; background:#fff1f2; border:1px solid #ffd8dd; border-radius:11px; white-space:pre-wrap; font-size:.88rem; }
    .note { margin:22px 0 0; padding-top:17px; color:var(--muted); border-top:1px solid var(--line); font-size:.8rem; }
    [hidden] { display:none !important; }
    @media(max-width:520px) { body { padding:20px 12px; } main { border-radius:18px; } .options { grid-template-columns:1fr; gap:0; } .preview img { width:88px; } }
  </style>
</head>
<body><main>
  <div class="brand"><div class="brand-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M23.5 6.2a3 3 0 0 0-2.1-2.1C19.6 3.6 12 3.6 12 3.6s-7.6 0-9.4.5A3 3 0 0 0 .5 6.2 31 31 0 0 0 0 12a31 31 0 0 0 .5 5.8 3 3 0 0 0 2.1 2.1c1.8.5 9.4.5 9.4.5s7.6 0 9.4-.5a3 3 0 0 0 2.1-2.1A31 31 0 0 0 24 12a31 31 0 0 0-.5-5.8ZM9.6 15.6V8.4l6.3 3.6-6.3 3.6Z"/></svg></div><div><p class="eyebrow">Quick and simple</p><h1>YouTube Media Downloader</h1></div></div>
  <p class="intro">Save a video as MP4 or extract its audio as MP3.</p>
  <form method="post" action="/download">
    <label for="url">YouTube URL</label>
    <div class="url-wrap"><input id="url" name="url" type="url" placeholder="Paste a YouTube link here" required value="{{ url|default('', true) }}"><span class="paste-hint">Paste link</span></div>
    <div class="preview" id="preview" aria-live="polite"><img id="thumbnail" alt="Video thumbnail"><div class="preview-copy"><p class="video-title" id="video-title"></p><span class="preview-status" id="preview-status">Getting video details…</span></div></div>
    <div class="options"><div><label for="format">Download type</label>
    <select id="format" name="format">
      <option value="audio" {% if media_format == 'audio' %}selected{% endif %}>Audio (MP3)</option>
      <option value="video" {% if media_format == 'video' %}selected{% endif %}>Video (MP4)</option>
    </select></div>
    <div id="audio-group" {% if media_format == 'video' %}hidden{% endif %}>
      <label for="audio-bitrate">MP3 bitrate</label>
      <select id="audio-bitrate" name="audio_bitrate">
        <option value="64" {% if audio_bitrate == '64' %}selected{% endif %}>64 kbps · smallest</option>
        <option value="96" {% if audio_bitrate == '96' %}selected{% endif %}>96 kbps</option>
        <option value="128" {% if audio_bitrate == '128' %}selected{% endif %}>128 kbps</option>
        <option value="192" {% if audio_bitrate == '192' %}selected{% endif %}>192 kbps · balanced</option>
        <option value="320" {% if audio_bitrate == '320' %}selected{% endif %}>320 kbps · highest</option>
      </select>
      <small class="hint">Lower bitrate means a smaller MP3 file.</small>
    </div>
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
    </div></div>
    <button id="download-button" type="submit"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5M12 15V3"/></svg><span>Download media</span></button>
  </form>
  <div class="error" id="download-error" role="alert" {% if not error %}hidden{% endif %}>{{ error or '' }}</div>
  <p class="note">Only download content you own or are authorized to save. Follow YouTube’s terms and applicable copyright law.</p>
</main>
<script>
  const formatSelect = document.getElementById("format");
  const qualityGroup = document.getElementById("quality-group");
  const audioGroup = document.getElementById("audio-group");
  formatSelect.addEventListener("change", () => {
    qualityGroup.hidden = formatSelect.value !== "video";
    audioGroup.hidden = formatSelect.value !== "audio";
  });
  const urlInput = document.getElementById("url");
  const preview = document.getElementById("preview");
  const titleNode = document.getElementById("video-title");
  const statusNode = document.getElementById("preview-status");
  const thumb = document.getElementById("thumbnail");
  let lookupTimer;
  let activeController;
  async function lookupVideo() {
    const url = urlInput.value.trim();
    if (!url) { preview.classList.remove("visible"); return; }
    if (activeController) activeController.abort();
    activeController = new AbortController();
    preview.classList.add("visible");
    titleNode.textContent = "";
    statusNode.textContent = "Getting video details…";
    thumb.hidden = true;
    try {
      const response = await fetch("/info", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({url}), signal:activeController.signal});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Could not read this link.");
      titleNode.textContent = data.title;
      statusNode.textContent = "Video title detected";
      if (data.thumbnail) { thumb.src = data.thumbnail; thumb.hidden = false; }
    } catch (error) {
      if (error.name !== "AbortError") { titleNode.textContent = ""; statusNode.textContent = error.message || "Could not load video details."; }
    }
  }
  urlInput.addEventListener("input", () => { clearTimeout(lookupTimer); lookupTimer = setTimeout(lookupVideo, 650); });
  if (urlInput.value) lookupVideo();
  const form = document.querySelector("form");
  const downloadError = document.getElementById("download-error");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = document.getElementById("download-button");
    const buttonLabel = button.querySelector("span");
    button.disabled = true;
    buttonLabel.textContent = "Preparing your download…";
    downloadError.hidden = true;
    downloadError.textContent = "";
    try {
      const response = await fetch(form.action, {method:"POST", body:new FormData(form)});
      if (!response.ok) {
        const page = new DOMParser().parseFromString(await response.text(), "text/html");
        throw new Error(page.querySelector(".error")?.textContent || "Download failed. Please try again.");
      }
      const blob = await response.blob();
      const disposition = response.headers.get("Content-Disposition") || "";
      const encodedName = disposition.match(/filename\*=UTF-8''([^;]+)/i);
      const regularName = disposition.match(/filename="?([^";]+)"?/i);
      const fileName = encodedName ? decodeURIComponent(encodedName[1]) : (regularName?.[1] || "youtube_media");
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = fileName;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(objectUrl), 60000);
    } catch (error) {
      downloadError.textContent = error.message || "Download failed. Please try again.";
      downloadError.hidden = false;
    } finally {
      button.disabled = false;
      buttonLabel.textContent = "Download media";
    }
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
    return render_template_string(PAGE, error=None, media_format="audio", quality="best", audio_bitrate="192")


@app.post("/info")
def video_info():
    payload = request.get_json(silent=True) or {}
    url = normalize_youtube_url(str(payload.get("url", "")))
    if not url:
        return jsonify(error="Enter a valid YouTube URL."), 400
    try:
        with yt_dlp.YoutubeDL({
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
            "proxy": os.environ.get("YTDLP_PROXY", ""),
            "cachedir": str(Path(__file__).parent / ".cache"),
            "js_runtimes": {"node": {"path": shutil.which("node")}} if shutil.which("node") else None,
        }) as ydl:
            info = ydl.extract_info(url, download=False)
        return jsonify(title=info.get("title") or "YouTube video", thumbnail=info.get("thumbnail"))
    except Exception:
        return jsonify(error="Could not retrieve this video's details. Check the link and try again."), 422


@app.post("/download")
def download():
    url = request.form.get("url", "").strip()
    media_format = request.form.get("format", "audio")
    quality = request.form.get("quality", "best")
    audio_bitrate = request.form.get("audio_bitrate", "192")
    valid_qualities = {"best", "1080", "720", "480", "360"}
    valid_audio_bitrates = {"64", "96", "128", "192", "320"}
    download_url = normalize_youtube_url(url)
    if not download_url:
        return render_template_string(PAGE, error="Enter a valid YouTube URL.", url=url, media_format=media_format, quality=quality, audio_bitrate=audio_bitrate), 400
    if media_format not in {"audio", "video"}:
        return render_template_string(PAGE, error="Choose audio or video format.", url=url, media_format="audio", quality=quality, audio_bitrate=audio_bitrate), 400
    if quality not in valid_qualities:
        return render_template_string(PAGE, error="Choose a valid video resolution.", url=url, media_format=media_format, quality="best", audio_bitrate=audio_bitrate), 400
    if audio_bitrate not in valid_audio_bitrates:
        return render_template_string(PAGE, error="Choose a valid MP3 bitrate.", url=url, media_format=media_format, quality=quality, audio_bitrate="192"), 400

    temp_dir = Path(tempfile.mkdtemp(prefix="youtube-downloader-"))
    output_template = str(temp_dir / "%(title).160B.%(ext)s")
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
                "preferredquality": audio_bitrate,
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
        response = send_file(files[0], as_attachment=True, download_name=files[0].name)
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
        return render_template_string(PAGE, error=f"Download failed: {message}", url=url, media_format=media_format, quality=quality, audio_bitrate=audio_bitrate), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)


