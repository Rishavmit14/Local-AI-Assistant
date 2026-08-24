"""Task-path validation shared by worktree and sandbox code."""

from __future__ import annotations

import re
from pathlib import Path

from .errors import IsolationError

SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def safe_identifier(value: str, label: str = "identifier") -> str:
    if (
        not SAFE_ID.fullmatch(value)
        or value in {".", ".."}
        or ".." in value
        or value.endswith(".")
    ):
        raise IsolationError(f"Unsafe {label}: {value!r}")
    return value


def contained_path(root: Path, *parts: str, must_exist: bool = False) -> Path:
    root = root.resolve()
    for part in parts:
        safe_identifier(part, "path component")
    candidate = root.joinpath(*parts)
    try:
        resolved = candidate.resolve(strict=must_exist)
    except OSError as exc:
        raise IsolationError(f"Cannot resolve isolated path: {exc}") from exc
    if resolved == root or root not in resolved.parents:
        raise IsolationError("Isolated path escapes configured runtime root")
    return resolved
