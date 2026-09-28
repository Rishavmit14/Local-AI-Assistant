"""Task-scoped transactional orchestration for checkpoint restoration."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from local_ai_assistant.history.models import TERMINAL_STATUSES, TaskStatus
from local_ai_assistant.history.service import TaskHistoryService

from .checkpoints import CheckpointManager, _git, _git_bytes
from .errors import CheckpointError, IsolationError
from .locks import task_lock
from .models import WorktreeState
from .worktrees import WorktreeManager


@dataclass(frozen=True, slots=True)
class RollbackResult:
    status: str
    task_id: str
    target_checkpoint_id: str
    safety_checkpoint_id: str | None = None
    detail: str | None = None


class TransactionalRollbackService:
    """Restore one exact task checkpoint, compensating if target restore fails.

    The per-task advisory lock is shared with WorktreeManager lifecycle writes.
    Execution code marks the worktree EXECUTING under this same lock before it
    mutates files; rollback rechecks lifecycle while holding the lock.
    """

    _ALLOWED_WORKTREE_STATES = {WorktreeState.READY, WorktreeState.FAILED}
    _ACTIVE_TASK_STATES = {
        TaskStatus.PLANNING, TaskStatus.EXECUTING, TaskStatus.VALIDATING,
        TaskStatus.REVIEWING,
    }

    def __init__(
        self,
        worktrees: WorktreeManager,
        checkpoints: CheckpointManager,
        history: TaskHistoryService,
    ) -> None:
        self.worktrees = worktrees
        self.checkpoints = checkpoints
        self.history = history

    def restore(
        self,
        canonical_repository: Path,
        task_id: str,
        plan_hash: str,
        label: str,
        *,
        expected_current_state: str | None = None,
        operation_id: str | None = None,
    ) -> RollbackResult:
        identity = self.worktrees.load(canonical_repository, task_id, plan_hash=plan_hash)
        canonical = canonical_repository.resolve(strict=True)
        worktree = Path(identity.worktree).resolve(strict=True)
        if worktree == canonical:
            raise IsolationError("Refusing rollback of a canonical or active integration repository")
        protected = {
            Path("/AI/projects/Local-AI-Assistant").resolve(),
            Path("/AI/projects/Local-AI-Assistant-terra-integration").resolve(),
        }
        if canonical in protected:
            raise IsolationError("Refusing rollback against a protected Friday checkout")
        task = self.history.get(task_id)
        if (
            task is None
            or Path(task.repository).resolve() != canonical
            or task.plan_hash != plan_hash
            or task.starting_commit != identity.starting_commit
            or task.status in self._ACTIVE_TASK_STATES
            or task.status in TERMINAL_STATUSES
        ):
            raise IsolationError("Canonical task history does not match an inactive isolated task")

        with task_lock(self.worktrees.root, identity.repository_id, task_id):
            # Revalidate metadata and lifecycle after acquiring the lock.
            identity = self.worktrees.load(canonical, task_id, plan_hash=plan_hash)
            if identity.state not in self._ALLOWED_WORKTREE_STATES:
                raise IsolationError("Task worktree lifecycle does not permit checkpoint restore")
            worktree = Path(identity.worktree).resolve(strict=True)
            if worktree == canonical:
                raise IsolationError("Task worktree resolves to the canonical repository")
            if expected_current_state is not None and worktree_fingerprint(worktree) != expected_current_state:
                raise CheckpointError("Reviewed worktree state is stale")
            target = self.checkpoints.load(task_id, label, plan_hash)
            if target.schema_version < 2:
                raise CheckpointError("Checkpoint predates transactional restore verification; create a fresh checkpoint")
            if target.head != _git_head(worktree):
                raise CheckpointError("Target checkpoint HEAD is stale")
            safety_label = "safety-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid4().hex[:12]
            safety = self.checkpoints.create(worktree, task_id, plan_hash, safety_label)
            if not self.checkpoints.verify(worktree, safety):
                raise CheckpointError("Pre-restore safety checkpoint does not match the current worktree")
            self._event(task_id, "rollback_started", "Task checkpoint restore started", {
                "target_checkpoint_id": target.checkpoint_id,
                "safety_checkpoint_id": safety.checkpoint_id,
            }, operation_id=operation_id)
            original_state = identity.state
            identity = self.worktrees.persist_state_under_lock(
                identity, WorktreeState.ROLLBACK_IN_PROGRESS
            )

            try:
                self.checkpoints.restore(worktree, target)
                if not self.checkpoints.verify(worktree, target):
                    raise CheckpointError("Target checkpoint state verification failed")
            except Exception as target_error:
                self._event(task_id, "rollback_target_failed", "Target restore failed; compensation started", {
                    "target_checkpoint_id": target.checkpoint_id,
                    "safety_checkpoint_id": safety.checkpoint_id,
                    "error_type": type(target_error).__name__,
                }, severity="warning", operation_id=operation_id)
                try:
                    self.checkpoints.restore(worktree, safety)
                    if not self.checkpoints.verify(worktree, safety):
                        raise CheckpointError("Safety checkpoint state verification failed")
                except Exception as recovery_error:
                    self.worktrees.mark_recovery_required(identity)
                    self._event(task_id, "rollback_recovery_required", "Target and compensating restore failed; manual recovery required", {
                        "target_checkpoint_id": target.checkpoint_id,
                        "safety_checkpoint_id": safety.checkpoint_id,
                        "error_type": type(recovery_error).__name__,
                    }, severity="critical", operation_id=operation_id)
                    return RollbackResult("recovery_required", task_id, target.checkpoint_id, safety.checkpoint_id, type(recovery_error).__name__)
                self._event(task_id, "rollback_failed_recovered", "Target restore failed; pre-restore worktree state was recovered", {
                    "target_checkpoint_id": target.checkpoint_id,
                    "safety_checkpoint_id": safety.checkpoint_id,
                    "error_type": type(target_error).__name__,
                }, severity="warning", operation_id=operation_id)
                self.worktrees.persist_state_under_lock(identity, original_state)
                return RollbackResult("failed_recovered", task_id, target.checkpoint_id, safety.checkpoint_id, type(target_error).__name__)

            self._event(task_id, "rollback_restore_succeeded", "Task worktree restored to the exact checkpoint", {
                "target_checkpoint_id": target.checkpoint_id,
                "safety_checkpoint_id": safety.checkpoint_id,
            }, operation_id=operation_id)
            self.worktrees.persist_state_under_lock(identity, original_state)
            return RollbackResult("restored", task_id, target.checkpoint_id, safety.checkpoint_id)

    def _event(self, task_id: str, kind: str, summary: str, metadata: dict, severity: str | None = None, operation_id: str | None = None) -> None:
        if operation_id:
            metadata["owner_operation_id"] = operation_id
        self.history.record_isolation_event(
            task_id, kind, summary, status=kind, severity=severity, metadata=metadata
        )


def _git_head(repository: Path) -> str:
    from .checkpoints import _git

    return _git(repository, "rev-parse", "HEAD")


def worktree_fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    for args in (("rev-parse", "HEAD"), ("status", "--porcelain=v1", "--untracked-files=all")):
        digest.update(_git(path, *args).encode())
        digest.update(b"\0")
    digest.update(_git_bytes(path, "diff", "--binary", "HEAD"))
    for name in _git(path, "ls-files", "--others", "--exclude-standard").splitlines():
        file = path / name
        if not file.resolve(strict=True).is_relative_to(path.resolve()):
            raise CheckpointError("Untracked file escapes the task worktree")
        digest.update(name.encode())
        if file.is_symlink():
            digest.update(os.readlink(file).encode())
        elif file.is_file():
            digest.update(hashlib.sha256(file.read_bytes()).digest())
    digest.update(str(path.resolve()).encode())
    return digest.hexdigest()
