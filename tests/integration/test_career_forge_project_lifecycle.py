from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from local_ai_assistant.autonomy import ObjectiveService
from local_ai_assistant.career_forge import CareerForgeService, MasteryLevel, PracticeLabService
from local_ai_assistant.gateway.auth import GatewayAuth
from local_ai_assistant.gateway.execution_service import CodeAgentExecutionService
from local_ai_assistant.gateway.github import FakeGitHubTransport
from local_ai_assistant.gateway.models import GatewayScope, RepositoryMapping
from local_ai_assistant.gateway.publication import GitHubPublicationService
from local_ai_assistant.gateway.service import IntegrationGatewayService
from local_ai_assistant.history.errors import HistoryDatabaseError
from local_ai_assistant.history.models import TaskStatus
from local_ai_assistant.history.service import TaskHistoryService
from local_ai_assistant.history.store import TaskHistoryStore
from local_ai_assistant.interface.api import create_presentation_app
from local_ai_assistant.interface.conversation import FridayConversationService
from local_ai_assistant.interface.runtime import FridayRuntime
from local_ai_assistant.isolation.owner_rollback import OwnerRollbackSessions
from local_ai_assistant.planning.models import (
    ApprovalDecision,
    ApprovalStatus,
    ConfidenceAssessment,
    ImplementationPlan,
    PlanningArtifact,
    RiskAssessment,
    RiskLevel,
    TaskCategory,
    TaskClassification,
)


class _LLM:
    def stream_chat(self, *_args, **_kwargs):
        yield "bounded response"


def _git(path: Path, *args: str) -> str:
    return subprocess.check_output(("git", "-C", str(path), *args), text=True).strip()


class _Planner:
    def __init__(self, repository: Path, target: Path) -> None:
        self.repository, self.plan_dir = repository, target

    def generate(self, request: str) -> PlanningArtifact:
        classification = TaskClassification(TaskCategory.FEATURE, 1.0, ("project",), request)
        plan = ImplementationPlan(
            task_id="pending", original_request=request, classification=classification,
            summary="Build validated Career Forge project artifact", assumptions=(),
            direct_scope=(), dependent_scope=(), files_to_inspect=("README.md",),
            files_to_modify=(), files_to_create=("artifacts/model_card.md",),
            files_to_delete_or_rename=(), symbols_to_modify=(), symbols_to_create=(),
            steps=(), relevant_tests=(), validation_commands=("test -s artifacts/model_card.md",),
            dependency_changes=(), migration_implications=(), security_implications=(),
            rollback_considerations=(), unresolved_questions=(),
            confidence=ConfidenceAssessment(1.0, {}, ()),
            risk=RiskAssessment(RiskLevel.LOW, ("bounded fixture",)),
            approval=ApprovalDecision(ApprovalStatus.REVIEW, ("owner publication",)),
        )
        return PlanningArtifact(
            "now", str(self.repository), _git(self.repository, "rev-parse", "HEAD"),
            request, classification, (), plan,
        )

    def persist(self, artifact: PlanningArtifact, target: Path) -> Path:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(artifact.to_dict(), default=str))
        return target


def test_real_bounded_project_lifecycle_recovers_exact_publication(tmp_path, monkeypatch):
    repository = tmp_path / "project"
    repository.mkdir()
    subprocess.run(("git", "init", "-q", str(repository)), check=True)
    subprocess.run(("git", "-C", str(repository), "remote", "add", "origin", "https://github.com/acme/career-project.git"), check=True)
    (repository / "README.md").write_text("Career project\n")
    subprocess.run(("git", "-C", str(repository), "add", "README.md"), check=True)
    subprocess.run(("git", "-C", str(repository), "-c", "user.name=Friday", "-c", "user.email=friday@example.invalid", "commit", "-qm", "initial"), check=True)

    learner_db, objective_db = tmp_path / "learner.sqlite3", tmp_path / "objectives.sqlite3"
    history_db = tmp_path / "history.sqlite3"
    forge = CareerForgeService(learner_db)
    first = forge.start_mission("se.python", "Verify Python")
    lab = PracticeLabService(forge, tmp_path / "lab")
    opened = lab.open(first.mission_id)
    assert lab.submit(first.mission_id).attempt.evidence_type is None
    fixed = opened.draft_code.replace("bucket=[]", "bucket=None").replace(
        "    bucket.append(item)", "    if bucket is None:\n        bucket = []\n    bucket.append(item)",
    )
    lab.save_draft(first.mission_id, fixed)
    lab.submit(first.mission_id)
    evidence = next(
        item for item in forge.evidence_history()
        if item.mission_id == first.mission_id and item.evidence_type == "practice_lab_bounded_test"
    )
    forge.advance_mastery("se.python", MasteryLevel.RECOGNIZE, evidence_id=evidence.evidence_id)
    while forge.next_competency() and forge.next_competency().competency_id != "ml.classical":
        competency = forge.next_competency()
        mission = forge.start_mission(competency.competency_id, f"Verify {competency.title}")
        evidence_id = forge.record_evidence(mission.mission_id, "independent_solution", "Independent verified work")
        forge.advance_mastery(competency.competency_id, MasteryLevel.RECOGNIZE, evidence_id=evidence_id)

    mission = forge.start_mission("ml.classical", "Build bounded FraudShield evidence")
    forge.link_project(mission.mission_id)
    blocked = forge.create_public_evidence_candidate(
        mission.mission_id, "artifacts/model_card.md", genuine_work=True,
        validation_passed=True, secret_scan_passed=True, privacy_review_passed=True,
        documentation_complete=True, artifact_quality_passed=True,
    )
    assert blocked.state == "blocked" and forge.career_readiness().published_artifacts == 0

    history = TaskHistoryService(TaskHistoryStore(history_db))
    mapping = RepositoryMapping("career-project", str(repository), "acme", "career-project")
    execution = CodeAgentExecutionService(None, history, SimpleNamespace(
        list_profiles=lambda: (SimpleNamespace(canonical_root=str(repository), repository_id="career-project"),),
        assert_ready_for_mutation=lambda *_args, **_kwargs: None,
    ))
    gateway = IntegrationGatewayService(
        history, (mapping,), planner_factory=lambda path: _Planner(path, tmp_path / "plans"),
        executor=execution,
    )

    def run_agent(argv):
        task_id = argv[argv.index("--task-id") + 1]
        task = history.get(task_id)
        worktree = tmp_path / "worktree"
        subprocess.run(("git", "-C", str(repository), "worktree", "add", "-q", "-b", task.branch, str(worktree), task.starting_commit), check=True)
        artifact = worktree / "artifacts" / "model_card.md"
        artifact.parent.mkdir()
        artifact.write_text("# Validated bounded model card\n")
        subprocess.run(("git", "-C", str(worktree), "add", "artifacts/model_card.md"), check=True)
        subprocess.run(("git", "-C", str(worktree), "-c", "user.name=Friday", "-c", "user.email=friday@example.invalid", "commit", "-qm", "project artifact"), check=True)
        history.store.transition(task_id, TaskStatus.EXECUTING, "isolated execution", subsystem="execution")
        history.store.transition(task_id, TaskStatus.VALIDATING, "artifact validated", subsystem="validation")
        history.store.transition(task_id, TaskStatus.REVIEWING, "artifact reviewed", subsystem="review")
        history.finalize(task_id, repository, TaskStatus.SUCCEEDED, final_commit=_git(worktree, "rev-parse", "HEAD"), outcome="validated and reviewed")

    monkeypatch.setattr("local_ai_assistant.gateway.execution_service.code_agent.main", run_agent)
    def states(task_id):
        task = history.get(task_id)
        return task.status.value if task else None
    autonomy = ObjectiveService(
        objective_db, plan_hash_for_task=lambda task_id: history.get(task_id).plan_hash if history.get(task_id) else None,
        create_task_for_objective=lambda text, repo, task: gateway.reserve_objective_task(repo, text, task).task_id,
        request_plan_for_task=gateway.request_plan, validate_repository=gateway.validate_repository,
        execute_task=lambda task, token: gateway.request_execution(task, expected_plan_hash=token),
        task_state_for_task=states,
    )
    objective = autonomy.resume(autonomy.create("Build and validate the model card").objective_id)
    forge.link_mission_objective(mission.mission_id, objective.objective_id)
    objective = autonomy.request_plan(objective.objective_id, "career-project")
    gateway_token = "server-only-project-execution-token"
    owner_token = "separate-owner-session-credential"
    browser_auth = GatewayAuth(
        hashlib.sha256(gateway_token.encode()).hexdigest(),
        frozenset({GatewayScope.REQUEST_EXECUTION, GatewayScope.SUBMIT_APPROVAL}),
    )
    browser_runtime = FridayRuntime("project-browser-authorization")
    browser_client = TestClient(create_presentation_app(
        browser_runtime, FridayConversationService(_LLM(), browser_runtime),
        autonomy=autonomy, task_history=history, objective_execution_auth=browser_auth,
        project_execution_sessions=OwnerRollbackSessions(hashlib.sha256(owner_token.encode()).hexdigest()),
        project_execution_allowed_origins=("http://127.0.0.1:5191",),
    ), base_url="http://127.0.0.1:8766")
    origin = {"Origin": "http://127.0.0.1:5191"}
    execution_path = f"/api/v1/objectives/{objective.objective_id}/execute"
    approval_path = f"/api/v1/objectives/{objective.objective_id}/approval"
    assert browser_client.post(execution_path, headers=origin).status_code == 401
    assert browser_client.post(approval_path, json={}, headers={**origin, "X-Friday-CSRF": "missing"}).status_code == 401
    assert browser_client.post("/api/v1/project-execution/unlock", json={"token": owner_token}, headers={"Origin": "http://evil.test"}).status_code == 403
    unlocked = browser_client.post("/api/v1/project-execution/unlock", json={"token": owner_token}, headers=origin)
    assert unlocked.status_code == 200
    assert "HttpOnly" in unlocked.headers["set-cookie"] and "SameSite=strict" in unlocked.headers["set-cookie"]
    assert gateway_token not in unlocked.text
    csrf = unlocked.json()["csrf_token"]
    browser_headers = {**origin, "X-Friday-CSRF": csrf}
    assert browser_client.post(execution_path, headers={"Origin": "http://evil.test", "X-Friday-CSRF": csrf}).status_code == 403
    assert browser_client.post(execution_path, headers=browser_headers).status_code == 409
    approval_body = {"task_id": objective.task_id, "starting_commit": history.get(objective.task_id).starting_commit,
        "plan_hash": objective.plan_hash}
    assert browser_client.post(approval_path, json={**approval_body, "plan_hash": "0" * 64}, headers=browser_headers).status_code == 409
    browser_auth._scopes = frozenset({GatewayScope.REQUEST_EXECUTION})
    assert browser_client.post(approval_path, json=approval_body, headers=browser_headers).status_code == 403
    browser_auth._scopes = frozenset({GatewayScope.SUBMIT_APPROVAL})
    assert browser_client.post(execution_path, headers=browser_headers).status_code == 403
    browser_auth._scopes = frozenset({GatewayScope.REQUEST_EXECUTION, GatewayScope.SUBMIT_APPROVAL})
    approved = browser_client.post(approval_path, json=approval_body, headers=browser_headers)
    assert approved.status_code == 200 and approved.json()["plan_hash"] == objective.plan_hash
    assert history.get(objective.task_id).status is TaskStatus.APPROVED
    history.store.update_task(objective.task_id, str(repository), plan_hash="b" * 64)
    assert browser_client.post(execution_path, headers=browser_headers).status_code == 409
    history.store.update_task(objective.task_id, str(repository), plan_hash=objective.plan_hash)
    started = browser_client.post(execution_path, headers=browser_headers)
    assert started.status_code == 202
    assert browser_client.post(execution_path, headers=browser_headers).status_code == 409
    handle = execution._runs[started.json()["execution"]["run_id"]]
    handle.result(timeout=10)
    assert history.get(objective.task_id).status is TaskStatus.SUCCEEDED
    browser_events = [event for event in history.timeline(objective.task_id) if event.event_type in {"browser_execution_approved", "browser_execution_authorized"}]
    assert {event.event_type for event in browser_events} == {"browser_execution_approved", "browser_execution_authorized"}
    authorized_event = next(event for event in browser_events if event.event_type == "browser_execution_authorized")
    assert authorized_event.metadata["principal"] == "local-owner"
    assert authorized_event.metadata["objective_id"] == objective.objective_id
    assert authorized_event.metadata["task_id"] == objective.task_id
    assert authorized_event.metadata["plan_hash"] == objective.plan_hash
    assert authorized_event.metadata["approval_id"] == approved.json()["approval_id"]
    assert authorized_event.metadata["gateway_scope"] == GatewayScope.REQUEST_EXECUTION.value
    assert gateway_token not in repr(browser_events)
    completed_task = history.get(objective.task_id)
    assert completed_task.status is TaskStatus.SUCCEEDED
    assert completed_task.branch == f"friday/task/{objective.task_id}"
    assert _git(repository, "show", f"{completed_task.final_commit}:artifacts/model_card.md").startswith(
        "# Validated bounded model card"
    )

    project_evidence = forge.record_evidence(mission.mission_id, "validated_project", "Governed task produced validated model card", artifact_ref="artifacts/model_card.md")
    assert project_evidence
    candidate = forge.create_public_evidence_candidate(
        mission.mission_id, "artifacts/model_card.md", genuine_work=True,
        validation_passed=True, secret_scan_passed=True, privacy_review_passed=True,
        documentation_complete=True, artifact_quality_passed=True,
    )
    transport = FakeGitHubTransport()
    def fake_push(_repo, branch, commit):
        transport.branches[("acme", "career-project", branch)] = commit
        if branch.startswith("friday/task/"):
            transport.branches[("acme", "career-project", "main")] = completed_task.starting_commit
            transport.files[("acme", "career-project", branch, "artifacts/model_card.md")] = _git(
                repository, "rev-parse", f"{commit}:artifacts/model_card.md",
            )
    publication = GitHubPublicationService(
        history, (mapping,), transport, push=fake_push,
    )
    commit_sha, blob_sha = publication.validate_artifact_identity(
        objective.task_id, repository_id="career-project", artifact_ref="artifacts/model_card.md",
    )
    assert commit_sha == completed_task.final_commit
    assert blob_sha == _git(repository, "rev-parse", f"{commit_sha}:artifacts/model_card.md").strip()
    with pytest.raises(HistoryDatabaseError, match="invalid"):
        publication.validate_artifact_identity(
            objective.task_id, repository_id="career-project", artifact_ref="../README.md",
        )
    with pytest.raises(HistoryDatabaseError, match="absent"):
        publication.validate_artifact_identity(
            objective.task_id, repository_id="career-project", artifact_ref="artifacts/missing.md",
        )
    token = "bounded-publication-token"
    auth = GatewayAuth(hashlib.sha256(token.encode()).hexdigest(), frozenset({GatewayScope.GITHUB_WRITE}))
    owner_token = "separate-project-owner-session"
    runtime = FridayRuntime("career-project-lifecycle")
    client = TestClient(create_presentation_app(
        runtime, FridayConversationService(_LLM(), runtime), career_forge=forge,
        autonomy=autonomy, career_publication=publication, objective_execution_auth=auth,
        project_execution_sessions=OwnerRollbackSessions(hashlib.sha256(owner_token.encode()).hexdigest()),
        project_execution_allowed_origins=("http://127.0.0.1:5191",),
    ), base_url="http://127.0.0.1:8766")
    path = f"/api/v1/career-forge/public-evidence/{candidate.candidate_id}/publish"
    body = {"task_id": objective.task_id, "repository_id": "career-project", "base": "main"}
    origin = {"Origin": "http://127.0.0.1:5191"}
    assert client.post(path, json=body, headers=origin).status_code == 401
    unlocked = client.post("/api/v1/project-execution/unlock", json={"token": owner_token}, headers=origin)
    assert unlocked.status_code == 200 and "HttpOnly" in unlocked.headers["set-cookie"]
    assert token not in unlocked.text
    owner_headers = {**origin, "X-Friday-CSRF": unlocked.json()["csrf_token"]}
    approve_path = f"/api/v1/career-forge/public-evidence/{candidate.candidate_id}/approve"
    assert client.post(approve_path, headers=origin).status_code == 401
    plan_response = client.get(
        f"/api/v1/career-forge/public-evidence/{candidate.candidate_id}/publication-plan"
        f"?task_id={objective.task_id}&repository_id=career-project&base=main",
        headers=origin,
    )
    assert plan_response.status_code == 200
    plan = plan_response.json()["plan"]
    assert plan["github_owner"] == "acme" and plan["github_repository"] == "career-project"
    assert client.post(approve_path, json=plan, headers=owner_headers).status_code == 200
    auth._scopes = frozenset()
    assert client.post(path, json=body, headers=owner_headers).status_code == 403
    auth._scopes = frozenset({GatewayScope.GITHUB_WRITE})
    assert client.post(path, json={**body, "task_id": "task_" + "b" * 20}, headers=owner_headers).status_code == 409
    published = client.post(path, json=body, headers=owner_headers)
    assert published.status_code == 200
    assert len(transport.pull_requests) == 1
    replay = client.post(path, json=body, headers=owner_headers)
    assert replay.status_code == 200 and len(transport.pull_requests) == 1

    recovered_forge = CareerForgeService(learner_db)
    recovered = recovered_forge.public_evidence_candidate(candidate.candidate_id)
    assert (recovered.mission_id, recovered.task_id, recovered.repository_id) == (
        mission.mission_id, objective.task_id, "career-project",
    )
    assert recovered.state == recovered.publication_state == "published"
    assert recovered.publication_url and recovered.published_at
    assert (recovered.publication_commit_sha, recovered.artifact_blob_sha) == (commit_sha, blob_sha)
    assert recovered_forge.project_link(mission.mission_id).project_name == "FraudShield"
    assert recovered_forge.mission_objective(mission.mission_id).objective_id == objective.objective_id
    assert recovered_forge.career_readiness().published_artifacts == 1
    assert recovered_forge.progress().next_action
    recovered_history = TaskHistoryService(TaskHistoryStore(history_db))
    recovered_autonomy = ObjectiveService(
        objective_db,
        task_state_for_task=lambda task_id: recovered_history.get(task_id).status.value,
    )
    recovered_runtime = FridayRuntime("career-project-recovery")
    recovered_client = TestClient(create_presentation_app(
        recovered_runtime, FridayConversationService(_LLM(), recovered_runtime),
        career_forge=recovered_forge, autonomy=recovered_autonomy,
    ))
    objective_state = recovered_client.get(
        f"/api/v1/career-forge/missions/{mission.mission_id}/objective"
    ).json()
    candidates = recovered_client.get(
        f"/api/v1/career-forge/missions/{mission.mission_id}/public-evidence"
    ).json()["candidates"]
    assert objective_state["objective"]["task_state"] == "succeeded"
    assert candidates[0]["candidate_id"] == candidate.candidate_id
    assert candidates[0]["publication_url"] == recovered.publication_url
    assert recovered_history.store.publication(objective.task_id)["state"] == "published"
    gateway.close()
