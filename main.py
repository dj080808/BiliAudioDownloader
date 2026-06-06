"""FastAPI application: Bilibili Audio Downloader."""

from __future__ import annotations

import asyncio
import os
import sys
from urllib.parse import urlparse

# Windows: must use ProactorEventLoop for asyncio subprocess support.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask

from config import ALLOWED_DOMAINS, AUDIO_MIME_TYPES, CLEANUP_INTERVAL_SECONDS, MAX_TASK_AGE_SECONDS, TEMP_DIR
from downloader import download_audio, get_video_info, sanitize_filename
from models import PrepareRequest, PrepareResponse, TaskStatus, TaskStatusResponse
from task_manager import TaskManager

app = FastAPI(title="Bilibili Audio Downloader")
task_manager = TaskManager()

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Startup / shutdown
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def startup() -> None:
    os.makedirs(TEMP_DIR, exist_ok=True)
    asyncio.create_task(_periodic_cleanup())


# ---------------------------------------------------------------------------
# Static files (served on / by default, but we also mount /static)
# ---------------------------------------------------------------------------
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def root() -> FileResponse:
    """Serve the single-page frontend."""
    return FileResponse(os.path.join(static_dir, "index.html"))


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------
@app.post("/api/prepare", response_model=PrepareResponse, status_code=202)
async def prepare(request: PrepareRequest) -> PrepareResponse:
    """Submit a Bilibili URL and get back a task ID immediately."""
    url = _normalize_url(request.url)
    _validate_url(url)

    task = await task_manager.create(url, audio_format=request.format)
    asyncio.create_task(_process_download(task.task_id))
    return PrepareResponse(task_id=task.task_id, status=task.status)


@app.get("/api/task/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str) -> TaskStatusResponse:
    """Poll for the current state of a download task."""
    task = await task_manager.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    return TaskStatusResponse(
        task_id=task.task_id,
        status=task.status,
        title=task.title,
        cover=task.cover,
        duration=task.duration,
        progress=task.progress,
        filesize_mb=task.filesize_mb,
        download_url=f"/api/download/{task.task_id}" if task.status == TaskStatus.READY else None,
        filename=task.filename,
        error=task.error,
    )


@app.get("/api/download/{task_id}")
async def download_file(task_id: str) -> FileResponse:
    """Serve the downloaded audio file, then clean up."""
    task = await task_manager.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != TaskStatus.READY:
        raise HTTPException(
            status_code=409,
            detail=f"Task not ready. Current status: {task.status.value}",
        )
    if not task.filepath or not os.path.exists(task.filepath):
        raise HTTPException(status_code=404, detail="File no longer available")

    cleanup = BackgroundTask(_cleanup_after_download, task_id)
    mime_type = AUDIO_MIME_TYPES.get(task.audio_format, "audio/mpeg")
    fallback_name = f"audio.{task.audio_format}" if task.audio_format else "audio.mp3"
    return FileResponse(
        path=task.filepath,
        filename=task.filename or fallback_name,
        media_type=mime_type,
        background=cleanup,
    )


# ---------------------------------------------------------------------------
# Background helpers
# ---------------------------------------------------------------------------
async def _process_download(task_id: str) -> None:
    """Background coroutine: extract info → download audio → mark ready."""
    task = await task_manager.get(task_id)
    if task is None:
        return

    try:
        # -- Extract metadata --
        print(f"[task:{task_id[:8]}] Fetching video info for: {task.url}")
        await task_manager.update(task_id, status=TaskStatus.PREPARING)
        info = await get_video_info(task.url)

        title = info.get("title") or "Unknown"
        cover = info.get("thumbnail") or ""
        duration = info.get("duration")
        print(f"[task:{task_id[:8]}] Title: {title[:50]}")

        # Output format comes from the user's choice (default mp3)
        ext = task.audio_format
        formats = info.get("formats") or []

        # Estimate expected file size from best audio format (source, not converted)
        expected_size: int | None = None
        audio_fmts = [
            f for f in formats
            if f.get("acodec") != "none" and f.get("vcodec") == "none"
        ]
        if audio_fmts:
            audio_fmts.sort(
                key=lambda f: f.get("filesize") or f.get("filesize_approx") or 0,
                reverse=True,
            )
            expected_size = audio_fmts[0].get("filesize") or audio_fmts[0].get("filesize_approx")

        filename = sanitize_filename(title) + f".{ext}"
        filepath = os.path.join(TEMP_DIR, f"{task_id}.{ext}")

        print(f"[task:{task_id[:8]}] Downloading audio ({ext}, ~{expected_size / 1024 / 1024:.1f} MB)...")
        await task_manager.update(
            task_id,
            status=TaskStatus.DOWNLOADING,
            title=title,
            cover=cover,
            duration=int(duration) if duration else None,
            filename=filename,
            filepath=filepath,
        )

        # -- Download audio --
        async def _on_progress(pct: int) -> None:
            await task_manager.update(task_id, progress=pct)

        await download_audio(
            task.url, filepath,
            audio_format=task.audio_format,
            progress_callback=_on_progress,
            expected_size=expected_size,
        )

        # -- Mark ready --
        file_size = os.path.getsize(filepath)
        print(f"[task:{task_id[:8]}] Done! {file_size / 1024 / 1024:.1f} MB")
        await task_manager.update(
            task_id,
            status=TaskStatus.READY,
            filesize_mb=round(file_size / (1024 * 1024), 1),
            progress=100,
        )

    except Exception as exc:
        import traceback
        print(f"[task:{task_id[:8]}] FAILED: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        await task_manager.update(
            task_id,
            status=TaskStatus.ERROR,
            error=f"{type(exc).__name__}: {exc}" or "Unknown error",
        )


async def _cleanup_after_download(task_id: str) -> None:
    """Delete the task and its temp file (called as Starlette BackgroundTask)."""
    await task_manager.delete(task_id)


async def _periodic_cleanup() -> None:
    """Remove stale tasks on a fixed interval."""
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
        try:
            count = await task_manager.cleanup_stale(MAX_TASK_AGE_SECONDS)
            if count > 0:
                print(f"[cleanup] Removed {count} stale task(s)")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _normalize_url(url: str) -> str:
    """Prepend https:// if the URL has no scheme, so users can paste bare domains."""
    url = url.strip()
    if not url:
        return url
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def _validate_url(url: str) -> None:
    """Raise 400 if *url* does not look like a Bilibili URL."""
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    parsed = urlparse(url)
    if not parsed.netloc or not any(domain in parsed.netloc for domain in ALLOWED_DOMAINS):
        raise HTTPException(
            status_code=400,
            detail="Invalid URL: must be a bilibili.com or b23.tv link",
        )


# ---------------------------------------------------------------------------
# Entry point (for ``python main.py``)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
