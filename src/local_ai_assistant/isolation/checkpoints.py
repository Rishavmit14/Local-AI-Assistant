"""Exact task-worktree checkpoints using Git patches plus an untracked archive."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tarfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from .errors import CheckpointError
from .models import CheckpointRecord
from .paths import contained_path, safe_identifier


class CheckpointManager:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def create(
        self, repository: Path, task_id: str, plan_hash: str, label: str
    ) -> CheckpointRecord:
        repository = repository.resolve(strict=True)
        safe_identifier(task_id, "task ID")
        safe_identifier(label, "checkpoint label")
        head = _git(repository, "rev-parse", "HEAD")
        staged = _git_bytes(repository, "diff", "--cached", "--binary", "--full-index", "HEAD")
        unstaged = _git_bytes(repository, "diff", "--binary", "--full-index")
        untracked = tuple(
            item
            for item in _git(repository, "ls-files", "--others").splitlines()
            if item
        )
        base = contained_path(self.root, task_id, label)
        if base.exists() or base.is_symlink():
            raise CheckpointError("Checkpoint already exists")
        base.mkdir(parents=True)
        (base / "staged.patch").write_bytes(staged)
        (base / "unstaged.patch").write_bytes(unstaged)
        archive = base / "untracked.tar"
        with tarfile.open(archive, "w") as bundle:
            for relative in untracked:
                path = _safe_repo_path(repository, relative)
                bundle.add(path, arcname=relative, recursive=False)
        archive_hash = _sha256(archive.read_bytes())
        checkpoint_id = _sha256(
            f"{task_id}\0{plan_hash}\0{head}\0{label}\0{_sha256(staged)}\0{_sha256(unstaged)}\0{archive_hash}".encode()
        )[:24]
        record = CheckpointRecord(
            1,
            checkpoint_id,
            task_id,
            plan_hash,
            head,
            _sha256(staged),
            _sha256(unstaged),
            _sha256("\n".join(untracked).encode()),
            archive_hash,
            datetime.now(UTC).isoformat(),
            base,
        )
        metadata = {
            "schema_version": 1,
            "checkpoint_id": checkpoint_id,
            "task_id": task_id,
            "plan_hash": plan_hash,
            "head": head,
            "staged_diff_hash": record.staged_diff_hash,
            "unstaged_diff_hash": record.unstaged_diff_hash,
            "untracked_hash": record.untracked_hash,
            "untracked": untracked,
            "archive_hash": archive_hash,
            "created_at": record.created_at,
        }
        _atomic_json(base / "checkpoint.json", metadata)
        return record

    def load(self, task_id: str, label: str, plan_hash: str | None = None) -> CheckpointRecord:
        base = contained_path(
            self.root,
            safe_identifier(task_id, "task ID"),
            safe_identifier(label, "checkpoint label"),
            must_exist=True,
        )
        try:
            value = json.loads((base / "checkpoint.json").read_text())
            if value["schema_version"] != 1 or value["task_id"] != task_id:
                raise ValueError("identity mismatch")
            if plan_hash is not None and value["plan_hash"] != plan_hash:
                raise ValueError("plan mismatch")
            for filename, expected in (
                ("staged.patch", value["staged_diff_hash"]),
                ("unstaged.patch", value["unstaged_diff_hash"]),
                ("untracked.tar", value["archive_hash"]),
            ):
                if _sha256((base / filename).read_bytes()) != expected:
                    raise ValueError(f"{filename} hash mismatch")
            return CheckpointRecord(
                1,
                value["checkpoint_id"],
                task_id,
                value["plan_hash"],
                value["head"],
                value["staged_diff_hash"],
                value["unstaged_diff_hash"],
                value["untracked_hash"],
                value["archive_hash"],
                value["created_at"],
                base,
            )
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise CheckpointError(f"Invalid checkpoint: {exc}") from exc

    def restore(self, repository: Path, record: CheckpointRecord) -> None:
        repository = repository.resolve(strict=True)
        if _git(repository, "rev-parse", "HEAD") != record.head:
            raise CheckpointError("Checkpoint HEAD no longer matches worktree HEAD")
        _run_git(repository, "reset", "--hard", record.head)
        _run_git(repository, "clean", "-fdx")
        staged = record.path / "staged.patch"
        unstaged = record.path / "unstaged.patch"
        if staged.stat().st_size:
            _run_git(repository, "apply", "--index", "--binary", str(staged))
        if unstaged.stat().st_size:
            _run_git(repository, "apply", "--binary", str(unstaged))
        archive = record.path / "untracked.tar"
        with tarfile.open(archive, "r") as bundle:
            for member in bundle.getmembers():
                _validate_tar_member(member)
            bundle.extractall(repository, members=bundle.getmembers())


def _safe_repo_path(repository: Path, relative: str) -> Path:
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts:
        raise CheckpointError("Unsafe untracked path")
    candidate = repository.joinpath(*path.parts)
    if candidate.is_symlink():
        # The link itself belongs to the repository; tar records it without following.
        return candidate
    resolved = candidate.resolve(strict=True)
    if resolved != repository and repository not in resolved.parents:
        raise CheckpointError("Untracked path escapes worktree")
    return candidate


def _validate_tar_member(member: tarfile.TarInfo) -> None:
    path = PurePosixPath(member.name)
    if path.is_absolute() or ".." in path.parts or member.isdev():
        raise CheckpointError("Unsafe checkpoint archive member")
    if (member.issym() or member.islnk()) and (
        PurePosixPath(member.linkname).is_absolute()
        or ".." in PurePosixPath(member.linkname).parts
    ):
        raise CheckpointError("Checkpoint symlink escapes worktree")


def _run_git(repository: Path, *arguments: str) -> None:
    result = subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", *arguments],
        cwd=repository,
        text=True,
        capture_output=True,
    )
    if result.returncode:
        raise CheckpointError("Git checkpoint operation failed: " + result.stderr.strip())


def _git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(["git", *arguments], cwd=repository, text=True, capture_output=True)
    if result.returncode:
        raise CheckpointError("Git checkpoint inspection failed: " + result.stderr.strip())
    return result.stdout.strip()


def _git_bytes(repository: Path, *arguments: str) -> bytes:
    result = subprocess.run(["git", *arguments], cwd=repository, capture_output=True)
    if result.returncode:
        raise CheckpointError("Git checkpoint inspection failed")
    return result.stdout


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    with temporary.open("rb") as stream:
        os.fsync(stream.fileno())
    os.replace(temporary, path)
