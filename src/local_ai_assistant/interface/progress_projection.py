"""Shared bounded read projection for canonical task isolation recovery."""

from __future__ import annotations

import json
from pathlib import Path

from local_ai_assistant.isolation.models import WorktreeState
from local_ai_assistant.isolation.recovery import inspect_task_recovery


def task_recovery_projection(root_path: Path | None, task_id: str) -> dict[str, str | None]:
    if root_path is None:
        return {"status": "unavailable", "summary": "Isolation recovery evidence is unavailable."}
    try:
        root = root_path.resolve()
        matches = sorted(root.glob(f"*/metadata/{task_id}.json")) if root.exists() else []
        if len(matches) > 1:
            return {"status": "identity_collision", "summary": "Multiple isolation records match this task; inspection is required."}
        if not matches:
            return {"status": "no_isolation_record", "summary": "No task isolation record was found; recovery health is unknown."}
        path = matches[0].resolve(strict=True)
        if root not in path.parents:
            return {"status": "path_rejected", "summary": "Isolation metadata failed its containment check."}
        metadata = json.loads(path.read_text(encoding="utf-8"))
        state = WorktreeState(str(metadata.get("state", ""))).value
        cleanup = str(metadata.get("cleanup_status", ""))
        findings = inspect_task_recovery(root, task_id)
        if state == WorktreeState.RECOVERY_REQUIRED.value:
            return {"status": "recovery_required", "summary": "Recovery inspection is required."}
        if state == WorktreeState.CLEANUP_PENDING.value or cleanup == WorktreeState.CLEANUP_PENDING.value:
            return {"status": "cleanup_pending", "summary": "Canonical isolation metadata records pending cleanup; inspection is required."}
        if findings:
            return {"status": "recovery_required", "summary": "Recovery inspection is required."}
        if state == "cleaned" or cleanup == "cleaned":
            return {"status": "cleaned", "summary": "Canonical isolation metadata records cleanup as complete."}
        if state:
            return {"status": "known_isolation_state", "isolation_state": state,
                    "cleanup_state": cleanup or None,
                    "summary": "Canonical isolation metadata is available; no recovery conclusion is inferred."}
        return {"status": "unavailable", "summary": "Isolation metadata has no recognized state."}
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return {"status": "unavailable", "summary": "Isolation recovery evidence could not be read."}
