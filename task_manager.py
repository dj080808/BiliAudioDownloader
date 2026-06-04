"""In-memory task store with async-safe operations and stale cleanup."""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from models import TaskStatus


@dataclass
class Task:
    task_id: str
    url: str
    status: TaskStatus = TaskStatus.PREPARING
    title: Optional[str] = None
    cover: Optional[str] = None
    duration: Optional[int] = None
    progress: int = 0
    filesize_mb: Optional[float] = None
    filename: Optional[str] = None
    filepath: Optional[str] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)


class TaskManager:
    """Thread-safe (async) in-memory store for download tasks."""

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._lock = asyncio.Lock()

    async def create(self, url: str) -> Task:
        """Create a new task and return it."""
        task_id = uuid.uuid4().hex
        task = Task(task_id=task_id, url=url)
        async with self._lock:
            self._tasks[task_id] = task
        return task

    async def get(self, task_id: str) -> Optional[Task]:
        """Return a task by id, or None."""
        async with self._lock:
            return self._tasks.get(task_id)

    async def update(self, task_id: str, **kwargs: object) -> None:
        """Merge keyword arguments into an existing task."""
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return
            for key, value in kwargs.items():
                if hasattr(task, key):
                    setattr(task, key, value)

    async def delete(self, task_id: str) -> None:
        """Remove a task and delete its temp file (if any)."""
        async with self._lock:
            task = self._tasks.pop(task_id, None)
        if task and task.filepath:
            try:
                os.remove(task.filepath)
            except FileNotFoundError:
                pass

    async def cleanup_stale(self, max_age_seconds: int) -> int:
        """Delete tasks older than *max_age_seconds* and their temp files. Returns count removed."""
        now = time.time()
        stale_ids: list[str] = []
        async with self._lock:
            for task_id, task in self._tasks.items():
                if now - task.created_at > max_age_seconds:
                    stale_ids.append(task_id)
            for task_id in stale_ids:
                task = self._tasks.pop(task_id, None)
                if task and task.filepath:
                    try:
                        os.remove(task.filepath)
                    except FileNotFoundError:
                        pass
        return len(stale_ids)
