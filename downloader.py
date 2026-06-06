"""yt-dlp wrapper: extract video metadata and download best-quality audio."""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import os
import re
import shutil
import subprocess
from typing import Any, Callable, Awaitable

from config import MAX_FILE_SIZE_BYTES, NATIVE_AUDIO_FORMATS

ProgressCallback = Callable[[int], Awaitable[None]]

# Bilibili requires browser-like headers; without them it returns HTTP 412.
_DEFAULT_HEADERS: list[str] = [
    "--add-header",
    "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    " (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "--add-header",
    "Referer: https://www.bilibili.com/",
]

# Shared thread pool for subprocess calls (avoids asyncio subprocess issues on Windows).
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)


def _run_yt_dlp(*args: str) -> subprocess.CompletedProcess:
    """Run yt-dlp synchronously in a thread."""
    cmd = ["yt-dlp", *args]
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def _popen_yt_dlp(*args: str) -> subprocess.Popen:
    """Start yt-dlp as a background subprocess (for streaming progress)."""
    cmd = ["yt-dlp", *args]
    return subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


# Cached ffmpeg availability check (lazy, runs once per process)
_ffmpeg_available: bool | None = None


def is_ffmpeg_available() -> bool:
    """Check whether ffmpeg is on PATH. Result is cached after first call."""
    global _ffmpeg_available
    if _ffmpeg_available is None:
        _ffmpeg_available = shutil.which("ffmpeg") is not None
    return _ffmpeg_available


def _format_is_native(fmt: str) -> bool:
    """Return True if *fmt* is served natively by Bilibili (no ffmpeg needed)."""
    return fmt in NATIVE_AUDIO_FORMATS


def _build_yt_dlp_args(
    url: str,
    output_path: str,
    audio_format: str,
    headers: list[str],
) -> list[str]:
    """Build the yt-dlp argument list for a given audio format.

    Native formats (m4a, opus) are downloaded directly.
    Other formats (mp3, flac, wav, aac) require ffmpeg post-processing.

    Raises ``ValueError`` if ffmpeg is needed but not available.
    """
    if _format_is_native(audio_format):
        return [
            "-f", f"bestaudio[ext={audio_format}]",
            "--no-playlist",
            "-o", output_path,
            *headers,
            url,
        ]
    else:
        if not is_ffmpeg_available():
            raise ValueError(
                f"Format '{audio_format}' requires ffmpeg for audio conversion. "
                f"Please install ffmpeg or choose a native format: {', '.join(NATIVE_AUDIO_FORMATS)}."
            )
        return [
            "-f", "bestaudio",
            "-x",
            "--audio-format", audio_format,
            "--no-playlist",
            "-o", output_path,
            *headers,
            url,
        ]


async def get_video_info(url: str) -> dict[str, Any]:
    """Run ``yt-dlp --dump-json`` and return parsed metadata.

    Raises ``ValueError`` when yt-dlp cannot process the URL.
    """
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        _executor,
        _run_yt_dlp,
        "--dump-json",
        "--no-playlist",
        "--no-download",
        *_DEFAULT_HEADERS,
        url,
    )

    if result.returncode != 0:
        err = (result.stderr or "").strip()
        for line in err.splitlines():
            if "ERROR:" in line:
                raise ValueError(line.split("ERROR:", 1)[-1].strip())
        raise ValueError(err.splitlines()[-1] if err else f"yt-dlp exited with code {result.returncode}")

    try:
        return json.loads((result.stdout or "").strip())
    except json.JSONDecodeError:
        raise ValueError("Failed to parse video info from yt-dlp")


async def download_audio(
    url: str,
    output_path: str,
    audio_format: str = "mp3",
    progress_callback: ProgressCallback | None = None,
    expected_size: int | None = None,
) -> None:
    """Download audio in the requested *audio_format* to *output_path*.

    Native formats (m4a, opus) are downloaded directly.  Other formats (mp3,
    flac, wav, aac) trigger ffmpeg post-processing via ``--extract-audio``.

    yt-dlp writes DASH fragments to ``<output_path>.part`` and renames on
    completion — progress is tracked by polling the part-file size against
    *expected_size*.  If *expected_size* is not provided it is estimated from
    the metadata.

    Raises ``ValueError`` on failure, if the download exceeds
    ``MAX_FILE_SIZE_BYTES``, or if ffmpeg is required but unavailable.
    """
    # If expected_size unknown, estimate from metadata
    if expected_size is None:
        try:
            info = await get_video_info(url)
            formats = info.get("formats") or []
            best = _pick_best_audio_format(formats)
            if best:
                expected_size = best.get("filesize") or best.get("filesize_approx")
        except Exception:
            pass

    part_path = output_path + ".part"
    # yt-dlp may also use a .ytdl suffix for DASH fragment downloads
    ytdl_path = output_path + ".ytdl"

    loop = asyncio.get_running_loop()
    args = _build_yt_dlp_args(url, output_path, audio_format, _DEFAULT_HEADERS)
    proc = await loop.run_in_executor(
        _executor,
        _popen_yt_dlp,
        *args,
    )

    last_pct = -1
    error_lines: list[str] = []

    async def _poll_progress() -> None:
        nonlocal last_pct
        current_size = 0
        # yt-dlp writes to .part (regular) or .ytdl (DASH fragments) during download
        if os.path.exists(part_path):
            target = part_path
        elif os.path.exists(ytdl_path):
            target = ytdl_path
        else:
            target = output_path
        if os.path.exists(target):
            current_size = os.path.getsize(target)

        if current_size > MAX_FILE_SIZE_BYTES:
            proc.kill()
            raise ValueError(
                f"File exceeds maximum size of {MAX_FILE_SIZE_BYTES // 1_000_000} MB"
            )

        if expected_size and expected_size > 0 and progress_callback:
            pct = min(int(current_size / expected_size * 100), 99)
            if pct != last_pct:
                await progress_callback(pct)
                last_pct = pct

    # Poll loop: check file size every 0.5s while process runs
    while proc.poll() is None:
        try:
            await _poll_progress()
        except ValueError:
            proc.kill()
            raise
        except Exception:
            pass

        # Drain stderr lines (non-blocking)
        if proc.stderr:
            for _ in range(10):
                line = proc.stderr.readline()
                if not line:
                    break
                text = line.strip()
                if text and "ERROR:" in text:
                    error_lines.append(text.split("ERROR:", 1)[-1].strip())

        await asyncio.sleep(0.5)

    # Final poll
    try:
        await _poll_progress()
    except Exception:
        pass

    # Drain remaining stderr
    if proc.stderr:
        for line in proc.stderr.readlines():
            text = line.strip()
            if text and "ERROR:" in text:
                error_lines.append(text.split("ERROR:", 1)[-1].strip())

    if proc.returncode != 0:
        if error_lines:
            raise ValueError(error_lines[-1])
        raise ValueError(f"yt-dlp exited with code {proc.returncode}")

    # Final progress → 100%
    if progress_callback:
        await progress_callback(100)

    # Verify final file
    if not os.path.exists(output_path):
        raise ValueError("Download completed but output file not found")
    actual_size = os.path.getsize(output_path)
    if actual_size > MAX_FILE_SIZE_BYTES:
        os.remove(output_path)
        raise ValueError(
            f"File exceeds maximum size of {MAX_FILE_SIZE_BYTES // 1_000_000} MB"
        )


def _pick_best_audio_format(formats: list[dict[str, Any]]) -> dict[str, Any] | None:
    """From yt-dlp's format list, pick the best audio-only format."""
    audio = [
        f for f in formats
        if f.get("acodec") != "none" and f.get("vcodec") == "none"
        and f.get("format_note") != "storyboard"
    ]
    if not audio:
        audio = [f for f in formats if f.get("acodec") != "none"]
    audio.sort(
        key=lambda f: f.get("filesize") or f.get("filesize_approx") or 0,
        reverse=True,
    )
    return audio[0] if audio else None


def sanitize_filename(title: str) -> str:
    """Remove characters that are invalid in filenames and truncate."""
    name = re.sub(r'[\\/:*?"<>|]', "", title)
    name = re.sub(r"\s+", "_", name)
    if len(name) > 100:
        name = name[:100]
    return name.strip("._")
