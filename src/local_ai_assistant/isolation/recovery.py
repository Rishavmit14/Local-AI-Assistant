"""Read-only crash-recovery classification; never resumes tasks automatically."""

from __future__ import annotations

import json
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
