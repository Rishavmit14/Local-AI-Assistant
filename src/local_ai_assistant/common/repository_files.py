"""Contained, bounded reads of untrusted repository-controlled files."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RepositoryBytesRead:
    data: bytes | None
    reason: str | None = None
    size: int = 0

    @property
    def readable(self) -> bool:
        return self.data is not None


@dataclass(frozen=True, slots=True)
class RepositoryFileRead:
    text: str | None
    reason: str | None = None
    size: int = 0

    @property
    def readable(self) -> bool:
        return self.text is not None


def read_repo_bytes_bounded(
    repository: Path, candidate: Path, *, max_bytes: int
) -> RepositoryBytesRead:
    """Read bounded bytes from a regular in-repository file without following symlinks."""
    root = repository.resolve(strict=True)
    try:
        relative = candidate.relative_to(root)
    except ValueError:
        return RepositoryBytesRead(None, "outside_repository")
    if relative.is_absolute() or ".." in relative.parts:
        return RepositoryBytesRead(None, "outside_repository")

    try:
        metadata = candidate.lstat()
    except OSError:
        return RepositoryBytesRead(None, "unavailable")

    if stat.S_ISLNK(metadata.st_mode):
        return RepositoryBytesRead(None, "symlink")
    if not stat.S_ISREG(metadata.st_mode):
        return RepositoryBytesRead(None, "not_regular")
    if metadata.st_size > max_bytes:
        return RepositoryBytesRead(None, "oversized", metadata.st_size)

    try:
        resolved = candidate.resolve(strict=True)
    except OSError:
        return RepositoryBytesRead(None, "unavailable", metadata.st_size)

    if resolved != root and root not in resolved.parents:
        return RepositoryBytesRead(
            None, "outside_repository", metadata.st_size
        )

    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )

    try:
        descriptor = os.open(candidate, flags)
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())

            if not stat.S_ISREG(opened.st_mode):
                return RepositoryBytesRead(
                    None, "not_regular", opened.st_size
                )
            if opened.st_size > max_bytes:
                return RepositoryBytesRead(
                    None, "oversized", opened.st_size
                )

            payload = stream.read(max_bytes + 1)
    except OSError:
        return RepositoryBytesRead(
            None, "unavailable", metadata.st_size
        )

    if len(payload) > max_bytes:
        return RepositoryBytesRead(None, "oversized", len(payload))

    return RepositoryBytesRead(payload, size=len(payload))


def read_repo_file_bounded(
    repository: Path, candidate: Path, *, max_bytes: int
) -> RepositoryFileRead:
    """Read bounded text from a regular in-repository file without following symlinks."""
    result = read_repo_bytes_bounded(
        repository, candidate, max_bytes=max_bytes
    )

    if not result.readable:
        return RepositoryFileRead(
            None, result.reason, result.size
        )

    return RepositoryFileRead(
        (result.data or b"").decode("utf-8", errors="replace"),
        size=result.size,
    )


__all__ = [
    "RepositoryBytesRead",
    "RepositoryFileRead",
    "read_repo_bytes_bounded",
    "read_repo_file_bounded",
]
