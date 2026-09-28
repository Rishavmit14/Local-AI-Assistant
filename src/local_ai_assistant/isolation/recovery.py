"""Read-only crash-recovery classification; never resumes tasks automatically."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .models import WorktreeState


@dataclass(frozen=True, slots=True)
class RecoveryFinding:
    task_id: str
    state: str
    reason: str
    metadata_path: str


@dataclass(frozen=True, slots=True)
class TaskIsolationEvidence:
    """Path-free exact-task view of one canonical worktree metadata record."""

    status: str
    state: str | None = None
    cleanup_state: str | None = None
    worktree_present: bool | None = None
    summary: str = "Isolation recovery evidence is unavailable."


def inspect_task_isolation(
    root: Path,
    task_id: str,
    *,
    canonical_repository: Path | None = None,
    starting_commit: str | None = None,
    plan_hash: str | None = None,
) -> TaskIsolationEvidence:
    """Read one task's isolation record, failing closed without exposing paths."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", task_id):
        return TaskIsolationEvidence("path_rejected", summary="Recovery evidence was rejected by task-identity policy.")
    try:
        root = root.resolve()
        if not root.exists():
            return TaskIsolationEvidence("no_isolation_record", summary="No task isolation record was found; recovery health is unknown.")
        matches = sorted(root.glob(f"*/metadata/{task_id}.json"))
        if len(matches) > 1:
            return TaskIsolationEvidence("identity_collision", summary="Multiple isolation records match this task; inspection is required.")
        if not matches:
            return TaskIsolationEvidence("no_isolation_record", summary="No task isolation record was found; recovery health is unknown.")
        metadata_path = matches[0]
        if metadata_path.is_symlink():
            return TaskIsolationEvidence("path_rejected", summary="Recovery metadata was rejected by containment policy.")
        resolved = metadata_path.resolve(strict=True)
        if root not in resolved.parents:
            return TaskIsolationEvidence("path_rejected", summary="Recovery metadata was rejected by containment policy.")
        value = json.loads(resolved.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("schema_version") != 1 or value.get("task_id") != task_id:
            return TaskIsolationEvidence("corrupt", summary="Recovery metadata is corrupt or does not match this task.")
        repo_id = value.get("repository_id")
        if not isinstance(repo_id, str) or not re.fullmatch(r"[a-f0-9]{20}", repo_id):
            return TaskIsolationEvidence("corrupt", summary="Recovery metadata is corrupt or does not match this task.")
        expected_metadata = root / repo_id / "metadata" / f"{task_id}.json"
        if resolved != expected_metadata:
            return TaskIsolationEvidence("path_rejected", summary="Recovery metadata was rejected by containment policy.")
        metadata_repository = value.get("canonical_repository")
        if not isinstance(metadata_repository, str) or not Path(metadata_repository).is_absolute():
            return TaskIsolationEvidence("corrupt", summary="Recovery metadata is corrupt or does not match this task.")
        if (
            (canonical_repository is not None and Path(metadata_repository).resolve() != canonical_repository.resolve())
            or (starting_commit is not None and value.get("starting_commit") != starting_commit)
            or (plan_hash is not None and value.get("plan_hash") != plan_hash)
        ):
            return TaskIsolationEvidence("identity_mismatch", summary="Isolation metadata does not match the canonical task identity; inspection is required.")
        state = WorktreeState(value["state"]).value
        cleanup = value.get("cleanup_status", "pending")
        if cleanup not in {"pending", "cleaned"}:
            return TaskIsolationEvidence("corrupt", state, summary="Recovery metadata is corrupt or does not match this task.")
        worktree_value = value.get("worktree")
        if not isinstance(worktree_value, str) or not Path(worktree_value).is_absolute():
            return TaskIsolationEvidence("path_rejected", state, cleanup, summary="Recovery worktree was rejected by containment policy.")
        worktree = Path(worktree_value)
        expected_worktree = root / repo_id / task_id
        resolved_worktree = worktree.resolve(strict=False)
        if resolved_worktree != expected_worktree or root not in resolved_worktree.parents:
            return TaskIsolationEvidence("path_rejected", state, cleanup, summary="Recovery worktree was rejected by containment policy.")
        present = worktree.is_dir()
        if state == WorktreeState.RECOVERY_REQUIRED.value:
            return TaskIsolationEvidence("recovery_required", state, cleanup, present, "Isolation metadata records recovery_required; owner inspection is required.")
        if state == WorktreeState.CLEANUP_PENDING.value:
            return TaskIsolationEvidence("cleanup_pending", state, cleanup, present, "Worktree cleanup is pending; the canonical task outcome is unchanged.")
        if state != WorktreeState.CLEANED.value and not present:
            return TaskIsolationEvidence("missing_worktree", state, cleanup, False, "Active isolation metadata remains but its worktree is missing; recovery inspection is required.")
        if state in {
            WorktreeState.CREATING.value, WorktreeState.EXECUTING.value,
            WorktreeState.VALIDATING.value, WorktreeState.ROLLBACK_IN_PROGRESS.value,
        }:
            return TaskIsolationEvidence("interrupted_lifecycle", state, cleanup, present, "Isolation metadata records an in-progress lifecycle; recovery inspection is required.")
        return TaskIsolationEvidence("known_state", state, cleanup, present, "Canonical isolation metadata is available; no recovery conclusion is inferred.")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return TaskIsolationEvidence("corrupt", summary="Recovery metadata is corrupt or unavailable.")


def inspect_recovery(root: Path) -> tuple[RecoveryFinding, ...]:
    root = root.resolve()
    if not root.exists():
        return ()
    findings: list[RecoveryFinding] = []
    for metadata in sorted(root.glob("*/metadata/*.json")):
        try:
            resolved = metadata.resolve(strict=True)
            if root not in resolved.parents:
                continue
            value = json.loads(resolved.read_text())
            state = WorktreeState(value["state"])
            worktree = Path(value["worktree"])
            if state in {
                WorktreeState.CREATING,
                WorktreeState.EXECUTING,
                WorktreeState.VALIDATING,
                WorktreeState.ROLLBACK_IN_PROGRESS,
                WorktreeState.RECOVERY_REQUIRED,
                WorktreeState.CLEANUP_PENDING,
            }:
                reason = "interrupted lifecycle requires operator inspection"
            elif state is not WorktreeState.CLEANED and not worktree.exists():
                reason = "worktree missing while metadata remains active"
            else:
                continue
            findings.append(
                RecoveryFinding(
                    str(value.get("task_id", "unknown")),
                    WorktreeState.RECOVERY_REQUIRED.value,
                    reason,
                    str(resolved.relative_to(root)),
                )
            )
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            findings.append(
                RecoveryFinding("unknown", "corrupt", str(exc), str(metadata))
            )
    return tuple(findings)


def inspect_task_recovery(root: Path, task_id: str) -> tuple[RecoveryFinding, ...]:
    """Inspect only one task's metadata; findings remain read-only and path-free at presentation."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", task_id):
        return (RecoveryFinding(task_id, "path_rejected", "invalid task identity", ""),)
    root = root.resolve()
    if not root.exists():
        return ()
    findings: list[RecoveryFinding] = []
    for metadata in sorted(root.glob(f"*/metadata/{task_id}.json")):
        try:
            resolved = metadata.resolve(strict=True)
            if root not in resolved.parents:
                findings.append(RecoveryFinding(task_id, "path_rejected", "metadata escaped the configured root", ""))
                continue
            value = json.loads(resolved.read_text())
            state = WorktreeState(value["state"])
            worktree = Path(value["worktree"])
            resolved_worktree = worktree.resolve(strict=False)
            if root not in resolved_worktree.parents:
                findings.append(RecoveryFinding(task_id, "path_rejected", "worktree escaped the configured root", ""))
            elif state in {
                WorktreeState.CREATING,
                WorktreeState.EXECUTING,
                WorktreeState.VALIDATING,
                WorktreeState.ROLLBACK_IN_PROGRESS,
                WorktreeState.CLEANUP_PENDING,
                WorktreeState.RECOVERY_REQUIRED,
            } or (state is not WorktreeState.CLEANED and not worktree.exists()):
                findings.append(RecoveryFinding(task_id, WorktreeState.RECOVERY_REQUIRED.value,
                    "interrupted lifecycle requires operator inspection", str(resolved.relative_to(root))))
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            findings.append(RecoveryFinding(task_id, "corrupt", "isolation metadata is unavailable", ""))
    return tuple(findings)
