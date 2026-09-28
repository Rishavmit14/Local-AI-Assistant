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
                WorktreeState.CLEANUP_PENDING,
                WorktreeState.RECOVERY_REQUIRED,
            } or (state is not WorktreeState.CLEANED and not worktree.exists()):
                findings.append(RecoveryFinding(task_id, WorktreeState.RECOVERY_REQUIRED.value,
                    "interrupted lifecycle requires operator inspection", str(resolved.relative_to(root))))
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            findings.append(RecoveryFinding(task_id, "corrupt", "isolation metadata is unavailable", ""))
    return tuple(findings)
