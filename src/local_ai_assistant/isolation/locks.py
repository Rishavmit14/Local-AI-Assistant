"""Single-host advisory locks for task lifecycle operations."""

from __future__ import annotations

import fcntl
from contextlib import contextmanager
from pathlib import Path

from .errors import IsolationError
from .paths import contained_path, safe_identifier


@contextmanager
def task_lock(root: Path, repository_id: str, task_id: str, *, blocking: bool = False):
    path = contained_path(
        root.resolve(),
        safe_identifier(repository_id, "repository ID"),
        "locks",
        safe_identifier(task_id, "task ID"),
    ).with_suffix(".lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open("a+")
    flags = fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB)
    try:
        try:
            fcntl.flock(stream.fileno(), flags)
        except BlockingIOError as exc:
            raise IsolationError("Task isolation lock is already held") from exc
        yield
    finally:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        finally:
            stream.close()
