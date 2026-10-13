# YouTube Media Downloader

A local Flask web app for downloading one YouTube video as MP4 or its audio as MP3. Video downloads can be limited to a maximum resolution to reduce their size.

Use the app only for content you own or are authorized to save. Follow YouTube's terms and applicable copyright law.

## Features

- Accepts YouTube watch, short-link (`youtu.be`), embed, Shorts, and Live URLs.
- Downloads one video at a time; playlists are disabled.
- Produces MP3 audio at 192 kbps.
- Produces MP4 video at the best available quality or up to 1080p, 720p, 480p, or 360p.
- Merges separate video and audio streams and converts audio using FFmpeg.
- Runs locally and listens only on `127.0.0.1:5000` by default.

The video quality setting caps the selected resolution. It does not re-encode a video to a lower bitrate, so the final file size varies by video and selected stream. A lower maximum resolution usually yields a smaller file.

## Requirements

### Required software

- **Python 3.10 or newer** and `pip`.
- **Node.js 22 or newer**, with `node` available on `PATH`. yt-dlp uses a JavaScript runtime to handle YouTube player challenges. The app detects Node automatically; if Node is absent, some videos may fail.
- Internet access to YouTube and permission to download the chosen content.

You do not need to install FFmpeg separately on supported platforms. The `imageio-ffmpeg` Python package supplies an FFmpeg binary used for MP3 conversion and MP4 stream merging. If the bundled binary is unavailable on your platform, install FFmpeg and adjust `ffmpeg_location` in `app.py` to point to it.

### Python libraries

The full list is in [`requirements.txt`](requirements.txt):

- **Flask** — local web server and form handling.
- **yt-dlp[default]** — media format selection and downloading, plus yt-dlp's default dependencies and JavaScript challenge scripts.
- **imageio-ffmpeg** — provides the FFmpeg executable used by yt-dlp post-processing.

The remaining imports (`os`, `pathlib`, `shutil`, `tempfile`, and `urllib`) are part of Python's standard library.

## Install and run on Windows

Open PowerShell in the folder containing `app.py` and run:

```powershell
# Create an isolated Python environment
py -3 -m venv .venv

# Activate it
.\.venv\Scripts\Activate.ps1

# Install Python dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Confirm Node is available (install Node.js 22+ if this prints no version)
node --version

# Start the app
python app.py
```

If PowerShell blocks activation, either allow activation for the current terminal with `Set-ExecutionPolicy -Scope Process RemoteSigned`, or use the environment's Python directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000). Keep the terminal open while using the app; press `Ctrl+C` there to stop the server.

## Install and run on macOS or Linux

Install Python 3.10+, Node.js 22+, and `pip` using your operating system's package manager or installers. In the app folder, run:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
node --version
python app.py
```

Then open [http://127.0.0.1:5000](http://127.0.0.1:5000). On macOS/Linux, the same Python environment, yt-dlp, Node, and FFmpeg requirements apply.

## Use

1. Paste a supported YouTube URL.
2. Choose **Audio (MP3)** or **Video (MP4)**.
3. For video, choose **Best available** or a maximum resolution.
4. Select **Download** and save the file offered by your browser.

Audio ignores the video quality selection. The app normalizes supported URL forms to a YouTube watch URL and asks yt-dlp to download one item, not a playlist.

## Network and proxy configuration

The app sets yt-dlp's proxy explicitly. By default it connects directly and does not inherit `HTTP_PROXY`, `HTTPS_PROXY`, or `ALL_PROXY` environment settings. This avoids failures from stale proxy values such as an unavailable proxy on `127.0.0.1:9`.

If your network requires a working proxy, set `YTDLP_PROXY` before starting the app.

PowerShell:

```powershell
$env:YTDLP_PROXY = "http://proxy.example:8080"
python app.py
```

macOS/Linux:

```bash
export YTDLP_PROXY="http://proxy.example:8080"
python app.py
```

Replace the example with your authorized proxy URL. The variable must be set in the same terminal that starts the app. Do not put proxy credentials in a file that will be shared or committed.

## How the app works

- `app.py` serves the HTML form at `/` and handles form submissions at `POST /download`.
- URL validation permits YouTube hosts and extracts a video ID from watch, `youtu.be`, embed, Shorts, and Live links.
- Audio selection uses yt-dlp's best audio stream and FFmpeg to produce a 192 kbps MP3.
- Video selection asks yt-dlp for MP4 video and M4A audio streams, merges them as MP4, and applies the selected maximum-height filter when one is chosen.
- Each request downloads into a temporary directory. The file is streamed to the browser as an attachment, and the temporary directory is removed after the response closes.
- yt-dlp's cache is kept in the app's `.cache` directory. Downloads are not kept in the project folder.

## Project files

```text
youtube-downloader/
├── app.py            # Flask routes, form UI, validation, and yt-dlp options
├── requirements.txt  # Python package dependencies
├── README.md         # Setup and replication guide
├── .venv/            # Local virtual environment (created during setup)
├── .cache/           # yt-dlp cache (created during use)
└── downloads/        # Optional folder for manually saved output; app uses temp folders
```

You can recreate the app from `app.py` and `requirements.txt`; `.venv`, `.cache`, and `downloads` are local runtime folders and do not contain required source code.

## Troubleshooting

### `Unable to connect to proxy` or `127.0.0.1:9`

This indicates a network proxy issue, before the resolution choice is applied. The app uses direct network access by default. If a proxy is required, set `YTDLP_PROXY` to its reachable address and restart the app.

### `node` is missing or JavaScript challenge errors appear

Install Node.js 22 or newer, make sure `node --version` works in the same terminal, then stop and restart the app. Reinstall dependencies with `python -m pip install -r requirements.txt` so yt-dlp's default challenge scripts are installed.

### FFmpeg conversion or merging fails

Reinstall or upgrade the bundled binary package with `python -m pip install --upgrade imageio-ffmpeg`. If your platform does not have a compatible bundled FFmpeg binary, install FFmpeg separately and configure its location in `app.py`.

### A video is unavailable or a chosen quality is missing

Availability and formats vary by video, region, and time. Try **Best available** or another maximum resolution. The app cannot download videos that yt-dlp cannot access from the current network or that require access the app does not have.

### Port 5000 is already in use

Stop the existing copy of the app in its terminal with `Ctrl+C`, then start one instance. Alternatively, change the `port=5000` value in the `app.run(...)` call and open the corresponding local URL.

## Security and deployment

This is a small local development app. It binds to `127.0.0.1` and has no authentication, job queue, rate limiting, or production server. Do not expose it to the public internet or change the host to `0.0.0.0` without adding appropriate security controls. Keep Python and the packages in `requirements.txt` updated.
