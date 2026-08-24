"""Thin gateway service delegating task state to Stage 7 history."""
from __future__ import annotations

import subprocess
from dataclasses import asdict
from pathlib import Path
from threading import Event, Thread

from local_ai_assistant.history.models import TaskFilter, TaskStatus
from local_ai_assistant.history.service import TaskHistoryService
from local_ai_assistant.isolation.gitops import git_argv, safe_git_environment

from .events import BoundedEventBus
from .github import map_repository, validate_mappings
from .models import ExternalProvenance, GatewayEvent, RepositoryMapping


class IntegrationGatewayService:
    def __init__(self, history: TaskHistoryService, mappings: tuple[RepositoryMapping, ...] = (), *, max_events: int = 1000, planner_factory=None, executor=None):
        self.history = history
        self.mappings = mappings
        validate_mappings(mappings)
        self.events = BoundedEventBus(max_events)
        self.planner_factory = planner_factory
        self.executor = executor
        self._bridge_stop = Event()
        self._bridge = Thread(target=self._history_bridge, name="friday-history-events", daemon=True)
        self._bridge.start()

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
        self._emit(task.task_id, "TASK_CREATED", "Task created from gateway request")
        return task

    def intake_issue(self, owner: str, repo: str, number: int, issue: dict, provenance: ExternalProvenance):
        if number < 1 or number > 10_000_000:
            raise ValueError("invalid issue number")
        mapping = map_repository(self.mappings, owner, repo)
        title = str(issue.get("title", ""))[:500]
        body = str(issue.get("body", ""))[:19_000]
        return self.create_task(mapping.repository_id, f"GitHub issue #{number}: {title}\n\n{body}", provenance=provenance)

    def request_plan(self, task_id: str):
        if self.planner_factory is None:
            raise RuntimeError("planner service is not configured for this gateway process")
        task = self.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        if task.status.value not in {"created", "planning", "reapproval_required"}:
            raise ValueError("task is not in a planable state")
        if task.status is TaskStatus.CREATED:
            self.history.transition(task_id, TaskStatus.PLANNING, "Plan request accepted", subsystem="planning")
        planner = self.planner_factory(Path(task.repository))
        artifact = planner.generate(task.original_request)
        from dataclasses import replace
        artifact = replace(artifact, plan=replace(artifact.plan, task_id=task_id))
        path = planner.persist(artifact, planner.plan_dir / f"{task_id}.json")
        self.history.attach_plan(task_id, artifact, path)
        refreshed = self.history.get(task_id)
        if refreshed and refreshed.status.value == "planning":
            target = TaskStatus.APPROVED if artifact.plan.approval.status.value == "automatic" else TaskStatus.AWAITING_APPROVAL
            self.history.transition(task_id, target, "Plan generated", subsystem="planning")
        self._emit(task_id, "PLAN_READY", "Plan generated")
        return artifact

    def _emit(self, task_id: str, event_type: str, summary: str, *, critical: bool = False) -> None:
        persisted = self.history.store.add_event(task_id, "gateway", event_type.lower(), summary, status=event_type)
        timeline = self.history.timeline(task_id)
        self.events.publish(GatewayEvent(persisted.event_id, self.history.store.event_rowid(persisted.event_id), task_id, event_type, persisted.timestamp, summary, critical=critical))

    def _history_bridge(self) -> None:
        cursor = 0
        while not self._bridge_stop.wait(0.25):
            try:
                for row in self.history.store.events_after_rowid(cursor, 200):
                    cursor = max(cursor, int(row["rowid"]))
                    self.events.publish(GatewayEvent(row["event_id"], cursor, row["task_id"], row["event_type"].upper(), row["timestamp"], row["summary"], critical=row["status"] in {"failed", "blocked", "cancelled"}))
            except Exception:
                continue

    def close(self) -> None:
        self._bridge_stop.set()

    def request_execution(self, task_id: str):
        if self.executor is None:
            raise RuntimeError("execution service is not configured for this gateway process")
        task = self.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        if task.status is not TaskStatus.APPROVED or not task.plan_hash:
            raise ValueError("exact approved plan is required before execution")
        return self.executor(task)

    def get_task(self, task_id: str): return self.history.get(task_id)
    def list_tasks(self, filters: TaskFilter | None = None): return self.history.list(filters)
    def timeline(self, task_id: str): return self.history.timeline(task_id)
    def cancel(self, task_id: str, repository_id: str, reason: str): return self.history.request_cancel(task_id, self._repo(repository_id), reason[:2000])

    def events_since(self, sequence: int = 0, limit: int = 100): return self.events.since(sequence, min(limit, 1000))

    def persisted_events_since(self, cursor: int = 0, limit: int = 100):
        rows = self.history.store.events_after_rowid(max(0, cursor), min(limit, 1000))
        return [GatewayEvent(str(row["event_id"]), int(row["rowid"]), row["task_id"], str(row["event_type"]).upper(), row["timestamp"], row["summary"], critical=row.get("status") in {"failed", "blocked", "cancelled"}) for row in rows]

    def ingest_ci(self, task_id: str, *, repository_id: str, external_repository: str, pr_id: str | None, status, expected_commit: str) -> dict:
        task = self.get_task(task_id)
        mapping = next((item for item in self.mappings if item.repository_id == repository_id), None)
        if task is None or mapping is None or status.commit_sha != expected_commit or external_repository.casefold() != f"{mapping.github_owner}/{mapping.github_name}".casefold():
            raise ValueError("CI evidence is not bound to this task, repository, and commit")
        from dataclasses import asdict
        values = asdict(status)
        values.update({"check_id": f"ci_{task_id}_{status.name}_{status.commit_sha}"[:200], "task_id": task_id, "repository_id": repository_id, "external_repository": external_repository, "pr_id": pr_id, "metadata_json": "{}"})
        return self.history.store.add_ci_check(task_id, values)


def _git_head(repository: Path) -> str:
    result = subprocess.run(
        git_argv("rev-parse", "HEAD"), cwd=repository, env=safe_git_environment(),
        check=True, capture_output=True, text=True, timeout=5,
    )
    return result.stdout.strip()
