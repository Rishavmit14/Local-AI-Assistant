"""Git worktree lifecycle bound to task, repository, commit, and plan."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from .errors import IsolationError, WorktreeIdentityError
from .models import WorktreeIdentity, WorktreeState
from .paths import contained_path, safe_identifier


def repository_id(repository: Path) -> str:
    root = repository.resolve(strict=True)
    common = _git(root, "rev-parse", "--path-format=absolute", "--git-common-dir")
    return hashlib.sha256(f"{root}\0{Path(common).resolve()}".encode()).hexdigest()[:20]


class WorktreeManager:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def create(
        self,
        repository: Path,
        task_id: str,
        starting_commit: str,
        plan_hash: str,
    ) -> WorktreeIdentity:
        safe_identifier(task_id, "task ID")
        repository = repository.resolve(strict=True)
        if _git(repository, "status", "--porcelain"):
            raise IsolationError("Canonical repository must be clean before isolation")
        if _git(repository, "rev-parse", "HEAD") != starting_commit:
            raise WorktreeIdentityError("Canonical HEAD does not match starting commit")
        repo_id = repository_id(repository)
        location = contained_path(self.root, repo_id, task_id)
        if location.exists() or location.is_symlink():
            raise WorktreeIdentityError("Task worktree path already exists")
        branch = f"friday/task/{task_id}"
        existing = subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
            cwd=repository,
        )
        if existing.returncode == 0:
            raise WorktreeIdentityError("Task branch already exists")
        location.parent.mkdir(parents=True, exist_ok=True)
        creating = WorktreeIdentity(
            1,
            task_id,
            repo_id,
            str(repository),
            str(location),
            branch,
            starting_commit,
            plan_hash,
            datetime.now(UTC).isoformat(),
            WorktreeState.CREATING,
        )
        self._persist(creating)
        result = subprocess.run(
            ["git", "worktree", "add", "--no-checkout", "-b", branch, str(location), starting_commit],
            cwd=repository,
            text=True,
            capture_output=True,
        )
        if result.returncode != 0:
            raise IsolationError("Could not create task worktree: " + result.stderr.strip())
        checkout = subprocess.run(
            ["git", "-c", "core.hooksPath=/dev/null", "checkout", "--detach", starting_commit],
            cwd=location,
            text=True,
            capture_output=True,
        )
        if checkout.returncode != 0:
            self.cleanup(creating, delete_branch=True)
            raise IsolationError("Could not populate task worktree: " + checkout.stderr.strip())
        # Reattach HEAD without invoking repository hooks.
        _git(location, "symbolic-ref", "HEAD", f"refs/heads/{branch}")
        ready = replace(creating, state=WorktreeState.READY, current_commit=starting_commit)
        self._persist(ready)
        return ready

    def load(
        self,
        repository: Path,
        task_id: str,
        *,
        starting_commit: str | None = None,
        plan_hash: str | None = None,
    ) -> WorktreeIdentity:
        repo_id = repository_id(repository)
        path = contained_path(self.root, repo_id, safe_identifier(task_id, "task ID"))
        metadata = self._metadata_path(repo_id, task_id)
        try:
            raw = json.loads(metadata.read_text())
            identity = WorktreeIdentity(
                **{**raw, "state": WorktreeState(raw["state"])}
            )
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            raise WorktreeIdentityError(f"Invalid task worktree metadata: {exc}") from exc
        expected = (repo_id, str(repository.resolve()), str(path), task_id)
        actual = (
            identity.repository_id,
            identity.canonical_repository,
            identity.worktree,
            identity.task_id,
        )
        if actual != expected:
            raise WorktreeIdentityError("Task worktree identity mismatch")
        if starting_commit and identity.starting_commit != starting_commit:
            raise WorktreeIdentityError("Task worktree starting commit mismatch")
        if plan_hash and identity.plan_hash != plan_hash:
            raise WorktreeIdentityError("Task worktree plan hash mismatch")
        if identity.state is not WorktreeState.CLEANED:
            if _git(path, "rev-parse", "HEAD") != (identity.current_commit or identity.starting_commit):
                raise WorktreeIdentityError("Task worktree HEAD is stale")
            branch = _git(path, "branch", "--show-current")
            if branch != identity.branch:
                raise WorktreeIdentityError("Task worktree branch mismatch")
        return identity

    def transition(self, identity: WorktreeIdentity, state: WorktreeState) -> WorktreeIdentity:
        current = _git(Path(identity.worktree), "rev-parse", "HEAD")
        updated = replace(identity, state=state, current_commit=current)
        self._persist(updated)
        return updated

    def cleanup(self, identity: WorktreeIdentity, *, delete_branch: bool = False) -> WorktreeIdentity:
        canonical = Path(identity.canonical_repository).resolve(strict=True)
        path = contained_path(self.root, identity.repository_id, identity.task_id)
        if str(path) != identity.worktree:
            raise WorktreeIdentityError("Refusing cleanup outside bound task worktree")
        metadata_path = self._metadata_path(identity.repository_id, identity.task_id)
        if not path.exists():
            try:
                persisted = json.loads(metadata_path.read_text())
                if persisted.get("state") == WorktreeState.CLEANED.value:
                    return replace(identity, state=WorktreeState.CLEANED, cleanup_status="cleaned")
            except (OSError, ValueError, json.JSONDecodeError):
                pass
            raise WorktreeIdentityError("Active task worktree is missing")
        self.load(
            canonical,
            identity.task_id,
            starting_commit=identity.starting_commit,
            plan_hash=identity.plan_hash,
        )
        if path.exists():
            result = subprocess.run(
                ["git", "worktree", "remove", "--force", str(path)],
                cwd=canonical,
                text=True,
                capture_output=True,
            )
            if result.returncode != 0:
                raise IsolationError("Worktree cleanup failed: " + result.stderr.strip())
        if delete_branch:
            deleted = subprocess.run(
                ["git", "branch", "-D", identity.branch],
                cwd=canonical,
                text=True,
                capture_output=True,
            )
            if deleted.returncode != 0:
                raise IsolationError("Task branch cleanup failed: " + deleted.stderr.strip())
        cleaned = replace(identity, state=WorktreeState.CLEANED, cleanup_status="cleaned")
        self._persist(cleaned)
        return cleaned

    def _persist(self, identity: WorktreeIdentity) -> None:
        target = self._metadata_path(identity.repository_id, identity.task_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(identity.to_dict(), sort_keys=True, indent=2) + "\n")
        with temporary.open("rb") as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, target)

    def _metadata_path(self, repo_id: str, task_id: str) -> Path:
        return contained_path(self.root, repo_id, "metadata", task_id).with_suffix(".json")


def _git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=repository, text=True, capture_output=True
    )
    if result.returncode != 0:
        raise IsolationError("Git isolation operation failed: " + result.stderr.strip())
    return result.stdout.strip()
