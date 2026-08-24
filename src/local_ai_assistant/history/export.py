"""Redacted task report exports."""

from __future__ import annotations

import json
from pathlib import Path

from local_ai_assistant.execution.history import redact

from .service import TaskHistoryService


def export_task(service: TaskHistoryService, task_id: str, destination: Path, format: str) -> Path:
    package = service.summary(task_id)
    package["artifacts"] = service.artifacts(task_id)
    if format == "json":
        content = json.dumps(package, indent=2, ensure_ascii=False, default=str)
    elif format == "markdown":
        task = package["task"]
        lines = [
            f"# Task {task_id}", "", f"- Status: {task['status']}",
            f"- Repository: {task['repository']}", f"- Branch: {task['branch']}",
            f"- Starting commit: {task['starting_commit']}",
            f"- Final commit: {task.get('final_commit') or 'none'}",
            f"- Risk: {task['risk']}", f"- Confidence: {task.get('confidence')}",
            f"- Plan hash: {task.get('plan_hash') or 'none'}", "", "## Request", "",
            task["original_request"], "", "## Summary", "", task.get("summary") or "",
            "", "## Affected files", "",
            *[f"- {item}" for item in package["affected_files"]], "", "## Timeline", "",
            *[f"- {item['timestamp']} — {item['subsystem']}: {item['summary']}" for item in package["timeline"]],
        ]
        content = "\n".join(lines)
    else:
        raise ValueError("Export format must be json or markdown")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(redact(content) + "\n", encoding="utf-8")
    return destination
