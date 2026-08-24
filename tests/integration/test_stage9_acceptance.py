"""Deterministic Stage 9 acceptance seams (no live model or GitHub)."""
from __future__ import annotations

import hashlib
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from local_ai_assistant.gateway.github import FakeGitHubTransport
from local_ai_assistant.gateway.models import ExternalProvenance, RepositoryMapping
from local_ai_assistant.gateway.publication import GitHubPublicationService
from local_ai_assistant.gateway.service import IntegrationGatewayService
from local_ai_assistant.history.models import TaskStatus
from local_ai_assistant.history.service import TaskHistoryService
from local_ai_assistant.history.store import TaskHistoryStore


def _repo(root: Path) -> Path:
    path = root / "fixture"
    path.mkdir()
    (path / "calculator.py").write_text("def add(a, b):\n    return a - b\n")
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "stage9@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Stage9"], check=True)
    subprocess.run(["git", "-C", str(path), "add", "calculator.py"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "initial"], check=True)
    subprocess.run(["git", "-C", str(path), "remote", "add", "origin", "https://github.com/acme/demo.git"], check=True)
    return path


def test_full_deterministic_intake_plan_approval_execution_publication(tmp_path, monkeypatch):
    path = _repo(tmp_path)
    history = TaskHistoryService(TaskHistoryStore(tmp_path / "history.sqlite3"))
    mapping = RepositoryMapping("fixture", str(path), "acme", "demo")
    calls = []

    class Planner:
        plan_dir = tmp_path / "plans"
        def generate(self, request):
            # The production request/planner seam is exercised; the fixture model is deterministic.
            from local_ai_assistant.planning.models import (
                ApprovalDecision, ApprovalStatus, ConfidenceAssessment, ImplementationPlan,
                RiskAssessment, RiskLevel, TaskCategory, TaskClassification,
            )
            classification = TaskClassification(TaskCategory.BUG_FIX, 1.0, ("fixture",), request)
            plan = ImplementationPlan(
                task_id="pending", original_request=request, classification=classification,
                summary="Fix calculator", assumptions=(), direct_scope=(), dependent_scope=(),
                files_to_inspect=("calculator.py",), files_to_modify=("calculator.py",), files_to_create=(),
                files_to_delete_or_rename=(), symbols_to_modify=(), symbols_to_create=(), steps=(),
                relevant_tests=(), validation_commands=(), dependency_changes=(), migration_implications=(),
                security_implications=(), rollback_considerations=(), unresolved_questions=(),
                confidence=ConfidenceAssessment(1.0, {}, ()), risk=RiskAssessment(RiskLevel.LOW, ("fixture",)),
                approval=ApprovalDecision(ApprovalStatus.REVIEW, ("external task",)),
            )
            from local_ai_assistant.planning.models import PlanningArtifact
            return PlanningArtifact("now", str(path), _head(path), request, classification, (), plan)
        def persist(self, artifact, target):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(artifact.to_dict(), default=str))
            return target

    gateway = IntegrationGatewayService(history, (mapping,), planner_factory=lambda _path: Planner())
    provenance = ExternalProvenance.from_payload("github", "delivery-acceptance", "acme/demo", "Fix add")
    task = gateway.create_task("fixture", "Fix add so the test passes", provenance=provenance, branch="friday/task/acceptance")
    assert history.get(task.task_id).metadata["external_provenance"]["event_id"] == "delivery-acceptance"
    artifact = gateway.request_plan(task.task_id)
    assert history.get(task.task_id).plan_hash
    approval = history.attach_approval(task.task_id, history.get(task.task_id).plan_hash, "explicitly_approved", actor="acceptance")
    assert approval
    history.store.transition(task.task_id, TaskStatus.APPROVED, "exact approval", subsystem="approval")
    # Exercise the production adapter boundary; code_agent is instrumented below, not replaced at gateway level.
    from local_ai_assistant.gateway.execution_service import CodeAgentExecutionService
    def code_agent(argv):
        calls.append(argv)
        history.store.transition(task.task_id, TaskStatus.EXECUTING, "fixture execution", subsystem="execution")
        history.store.transition(task.task_id, TaskStatus.VALIDATING, "fixture validation", subsystem="validation")
        history.store.transition(task.task_id, TaskStatus.REVIEWING, "fixture review", subsystem="review")
        history.finalize(task.task_id, path, TaskStatus.SUCCEEDED, final_commit=_head(path), outcome="validated")
    monkeypatch.setattr("local_ai_assistant.gateway.execution_service.code_agent.main", code_agent)
    execution = CodeAgentExecutionService(None, history)
    handle = execution.execute_task(history.get(task.task_id))
    execution._runs[handle.run_id].result(timeout=5)
    assert calls and "--task-id" in calls[0] and "--approve-risk" in calls[0]
    assert history.get(task.task_id).status is TaskStatus.SUCCEEDED
    transport = FakeGitHubTransport()
    transport.branches[("acme", "demo", task.branch)] = _head(path)
    publication = GitHubPublicationService(history, (mapping,), transport, push=lambda *_: None)
    result = publication.publish(task.task_id, repository_id="fixture")
    assert result["state"] == "published"
    assert len(transport.pull_requests) == 1
    assert history.get(task.task_id).starting_commit == _head(path)


def test_external_history_events_replay_after_gateway_restart(tmp_path):
    path = _repo(tmp_path)
    history = TaskHistoryService(TaskHistoryStore(tmp_path / "history.sqlite3"))
    mapping = RepositoryMapping("fixture", str(path), "acme", "demo")
    first = IntegrationGatewayService(history, (mapping,))
    task = first.create_task("fixture", "history event")
    first.close()
    history.store.add_event(task.task_id, "execution", "execution_started", "outside gateway", status="executing")
    history.store.add_event(task.task_id, "validation", "validation_completed", "outside gateway", status="validated")
    second = IntegrationGatewayService(history, (mapping,))
    # The history bridge replays persisted events into the real bounded bus.
    import time
    time.sleep(0.6)
    events = second.events_since(0, 100)
    assert {event.event_type for event in events} >= {"TASK_CREATED", "EXECUTION_STARTED", "VALIDATION_COMPLETED"}
    second.close()


def _head(path: Path) -> str:
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
