"""Pydantic models for API request/response schemas."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, field_validator

from config import ALLOWED_AUDIO_FORMATS, DEFAULT_AUDIO_FORMAT


class TaskStatus(str, Enum):
    PREPARING = "preparing"
    DOWNLOADING = "downloading"
    READY = "ready"
    ERROR = "error"


class PrepareRequest(BaseModel):
    """Incoming request to start processing a Bilibili URL."""

    url: str
    format: str = DEFAULT_AUDIO_FORMAT

    @field_validator("format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in ALLOWED_AUDIO_FORMATS:
            allowed = ", ".join(ALLOWED_AUDIO_FORMATS)
            raise ValueError(f"Unsupported format '{v}'. Allowed: {allowed}")
        return v


class PrepareResponse(BaseModel):
    """Immediate response after accepting a URL."""

    task_id: str
    status: TaskStatus


class TaskStatusResponse(BaseModel):
    """Full task status returned when polling."""

    task_id: str
    status: TaskStatus
    title: Optional[str] = None
    cover: Optional[str] = None
    duration: Optional[int] = None  # seconds
    progress: Optional[int] = None  # 0-100
    filesize_mb: Optional[float] = None
    download_url: Optional[str] = None  # relative path, e.g. /api/download/{task_id}
    filename: Optional[str] = None
    error: Optional[str] = None
