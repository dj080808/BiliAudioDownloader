"""Configuration constants. All values can be overridden via environment variables."""

import os
import tempfile

# Directory for temporary downloaded audio files
TEMP_DIR = os.environ.get(
    "DOWNLOADTOOL_TEMP_DIR",
    os.path.join(tempfile.gettempdir(), "downloadtool"),
)

# Tasks older than this (seconds) are cleaned up by the periodic sweep
MAX_TASK_AGE_SECONDS = int(os.environ.get("DOWNLOADTOOL_MAX_TASK_AGE", "1800"))  # 30 min

# How often the periodic cleanup runs (seconds)
CLEANUP_INTERVAL_SECONDS = int(os.environ.get("DOWNLOADTOOL_CLEANUP_INTERVAL", "600"))  # 10 min

# Safety limit: abort downloads that exceed this size (bytes)
MAX_FILE_SIZE_BYTES = int(os.environ.get("DOWNLOADTOOL_MAX_FILE_SIZE", "200_000_000"))  # 200 MB

# Domains accepted as valid Bilibili URLs
ALLOWED_DOMAINS = [
    "bilibili.com",
    "www.bilibili.com",
    "b23.tv",
    "b22.tv",
]

# ---------------------------------------------------------------------------
# Audio format settings
# ---------------------------------------------------------------------------

# Default output audio format (can be overridden via env var)
DEFAULT_AUDIO_FORMAT = os.environ.get("DOWNLOADTOOL_DEFAULT_AUDIO_FORMAT", "mp3")

# All audio formats the user is allowed to request
ALLOWED_AUDIO_FORMATS = [
    "mp3",
    "m4a",
    "opus",
    "flac",
    "wav",
    "aac",
]

# Formats Bilibili serves natively (no ffmpeg post-processing needed)
NATIVE_AUDIO_FORMATS = ["m4a", "opus"]

# Mapping from audio format to MIME type for FileResponse
AUDIO_MIME_TYPES: dict[str, str] = {
    "mp3": "audio/mpeg",
    "m4a": "audio/mp4",
    "opus": "audio/opus",
    "flac": "audio/flac",
    "wav": "audio/wav",
    "aac": "audio/aac",
}
