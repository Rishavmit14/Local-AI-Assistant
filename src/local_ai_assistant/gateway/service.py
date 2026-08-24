"""Thin gateway service delegating task state to Stage 7 history."""
from __future__ import annotations

import subprocess
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from local_ai_assistant.history.models import TaskFilter
from local_ai_assistant.history.service import TaskHistoryService
from local_ai_assistant.isolation.gitops import git_argv, safe_git_environment

from .events import BoundedEventBus
from .github import map_repository, validate_mappings
from .models import ExternalProvenance, GatewayEvent, RepositoryMapping


class IntegrationGatewayService:
    def __init__(self, history: TaskHistoryService, mappings: tuple[RepositoryMapping, ...] = (), *, max_events: int = 1000):
        self.history = history
        self.mappings = mappings
        validate_mappings(mappings)
        self.events = BoundedEventBus(max_events)

    def _repo(self, repository_id: str) -> Path:
        for mapping in self.mappings:
            if mapping.repository_id == repository_id:
                path = Path(mapping.local_path).resolve()
                if not path.is_dir():
                    raise ValueError("configured repository is unavailable")
                return path
        raise ValueError("unknown configured repository")

    def create_task(self, repository_id: str, request: str, *, plan_only: bool = False, provenance: ExternalProvenance | None = None, branch: str = "main"):
        if not request.strip():
            raise ValueError("task request must not be empty")
        if len(request) > 20_000:
            raise ValueError("task request exceeds the configured character limit")
        repository = self._repo(repository_id)
        head = _git_head(repository)
        key = (provenance.source, provenance.event_id, repository_id) if provenance else None
        if key:
            task = self.history.create_external_task(
                request, repository, head, branch, source=key[0], event_id=key[1],
                metadata={"plan_only": plan_only, "external_provenance": asdict(provenance)},
            )
        else:
            task = self.history.create_task(
                request, repository, head, branch,
                metadata={"plan_only": plan_only, "external_provenance": None},
            )
        self.events.publish(GatewayEvent("", 0, task.task_id, "TASK_CREATED", datetime.now(UTC).isoformat(), "Task created from gateway request"))
        return task

    def intake_issue(self, owner: str, repo: str, number: int, issue: dict, provenance: ExternalProvenance):
        if number < 1 or number > 10_000_000:
            raise ValueError("invalid issue number")
        mapping = map_repository(self.mappings, owner, repo)
        title = str(issue.get("title", ""))[:500]
        body = str(issue.get("body", ""))[:19_000]
        return self.create_task(mapping.repository_id, f"GitHub issue #{number}: {title}\n\n{body}", provenance=provenance)

    def get_task(self, task_id: str): return self.history.get(task_id)
    def list_tasks(self, filters: TaskFilter | None = None): return self.history.list(filters)
    def timeline(self, task_id: str): return self.history.timeline(task_id)
    def cancel(self, task_id: str, repository_id: str, reason: str): return self.history.request_cancel(task_id, self._repo(repository_id), reason[:2000])

    def events_since(self, sequence: int = 0, limit: int = 100): return self.events.since(sequence, min(limit, 1000))


def _git_head(repository: Path) -> str:
    result = subprocess.run(
        git_argv("rev-parse", "HEAD"), cwd=repository, env=safe_git_environment(),
        check=True, capture_output=True, text=True, timeout=5,
    )
    return result.stdout.strip()
