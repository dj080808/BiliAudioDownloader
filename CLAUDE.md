# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Bilibili Audio Downloader — a web app where users paste a Bilibili video URL, see metadata (title/cover/duration), and download the audio track. Backend is Python FastAPI; frontend is a single `static/index.html` with embedded CSS/JS.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Development server (with hot reload)
uvicorn main:app --reload

# Or equivalently:
python main.py

# Production server
uvicorn main:app --host 0.0.0.0 --port 8000
```

There is no test suite or linter configured yet for this project.

## Architecture

### Flow

```
Browser (index.html) ──POST /api/prepare──▶ FastAPI (main.py)
                            {url}                 │
                                                  ├─► downloader.get_video_info(url)
                                                  │     yt-dlp --dump-json → {title, thumbnail, duration, formats}
                                                  │
                                                  ├─► downloader.download_audio(url, path, cb)
                                                  │     yt-dlp -f bestaudio -o <path>
                                                  │     cb(pct) called via file-size polling every 0.5s
                                                  │
                     ◀──GET /api/task/{id}─────── task_manager.get(task_id)
                     ◀──GET /api/download/{id}─── FileResponse + BackgroundTask cleanup
```

### Key modules

| Module | Role |
|---|---|
| `main.py` | FastAPI app, route handlers, CORS, startup cleanup loop, background task orchestration |
| `downloader.py` | yt-dlp subprocess wrapper: `get_video_info()` (metadata) and `download_audio()` (with progress callback) |
| `task_manager.py` | In-memory async-safe `Task` store (`create`/`get`/`update`/`delete`/`cleanup_stale`) |
| `models.py` | Pydantic schemas: `TaskStatus` enum, request/response models |
| `config.py` | All settings with `os.environ.get()` overrides (temp dir, TTLs, size limits) |
| `static/index.html` | Single-page frontend — embedded CSS (Bilibili-pink theme) + vanilla JS polling loop |

### State machine

```
preparing → downloading → ready → (file served → BackgroundTask deletes file + task)
                ↓
              error
```

Tasks live in memory (`task_manager._tasks: dict`). A periodic coroutine (every 10 min) removes tasks older than 30 min. Temp files are deleted when the task is deleted.

### API endpoints

- `POST /api/prepare` — accepts `{url}`, returns `{task_id, status}` immediately (202)
- `GET /api/task/{task_id}` — returns full task status including progress, metadata, download_url when ready
- `GET /api/download/{task_id}` — serves the audio file with `Content-Disposition: attachment`, auto-cleans up afterward
- `GET /` — serves `static/index.html`

## Dependencies

- `fastapi` — web framework
- `uvicorn` — ASGI server
- `yt-dlp` — Bilibili video/audio extraction (called via subprocess, not Python API)
- No database, no Redis, no ffmpeg required

## Configuration

All config lives in `config.py` and reads from environment variables with sensible defaults:

- `DOWNLOADTOOL_TEMP_DIR` — where temp audio files are stored
- `DOWNLOADTOOL_MAX_TASK_AGE` — seconds before stale task is cleaned up (default 1800)
- `DOWNLOADTOOL_CLEANUP_INTERVAL` — seconds between cleanup sweeps (default 600)
- `DOWNLOADTOOL_MAX_FILE_SIZE` — bytes, abort downloads exceeding this (default 200 MB)

## Key design decisions

- **yt-dlp via subprocess**, not Python API — most reliable interface, handles all Bilibili URL formats (BV, b23.tv short links)
- **Download-then-serve** (not streaming from stdout) — enables `Content-Length` header so browser shows download progress; BackgroundTask auto-cleans temp files
- **In-memory task store** — simpler than Redis/SQLite, fine for single-server deployment
- **No ffmpeg / no audio conversion** — serves native `bestaudio` stream (usually m4a), avoids extra dependency
- **File-size polling for progress** — checks `os.path.getsize(output_path)` every 0.5s, simpler than parsing yt-dlp stderr
- **Same-origin static + API** — FastAPI serves both, no CORS issues in normal use (CORS middleware still included for flexibility)
