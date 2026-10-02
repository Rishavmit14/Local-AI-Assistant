from __future__ import annotations

import hashlib
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock
from types import SimpleNamespace
from uuid import uuid4

import pytest

from local_ai_assistant.gateway import execution_service
from local_ai_assistant.gateway import recovery as recovery_module
from local_ai_assistant.gateway.execution_service import ExecutionHandle
from local_ai_assistant.gateway.recovery import (
    TaskExecutionRecoveryService,
    TaskExecutionRetryService,
)
from local_ai_assistant.history import store as history_store
from local_ai_assistant.history.models import TaskStatus
from local_ai_assistant.history.service import TaskHistoryService
from local_ai_assistant.history.store import TaskHistoryStore
from local_ai_assistant.interface.task_recovery import TaskRecoveryProjectionService
from local_ai_assistant.isolation.checkpoints import CheckpointManager
from local_ai_assistant.isolation.models import WorktreeState
from local_ai_assistant.isolation.owner_rollback import OwnerRollbackService
from local_ai_assistant.isolation.transactional_rollback import TransactionalRollbackService
from local_ai_assistant.isolation.worktrees import WorktreeManager
from local_ai_assistant.planning.models import (
    ApprovalDecision,
    ApprovalStatus,
    ConfidenceAssessment,
    ImplementationPlan,
    PlanningArtifact,
    RiskAssessment,
    RiskLevel,
    ScopeCandidate,
    ScopeRole,
    TaskCategory,
    TaskClassification,
    plan_approval_token,
)


class ObjectiveAuthority:
    def __init__(self, objective_id, task_id, plan_hash):
        self.objective = SimpleNamespace(objective_id=objective_id, task_id=task_id,
                                         plan_hash=plan_hash, state="planned")

    def get(self, _objective_id):
        return self.objective

    def linked_to_task(self, task_id):
        from local_ai_assistant.autonomy.service import ObjectiveTaskLink
        return (ObjectiveTaskLink(self.objective.objective_id, "planned",
                                  self.objective.plan_hash, task_id),)


class Executor:
    def __init__(self, history, *, status="failed"):
        self.history = history
        self.status = status
        self.started_at = datetime.now(UTC) + timedelta(seconds=1)
        self.calls = []
        self.callbacks = []
        self.lock = Lock()

    def get_status(self, task_id):
        return {"task_id": task_id, "status": self.status, "failure_type": "RuntimeError"}

    def execute_task(self, task, *, attempt_id, recovery=False, retry=False):
        assert recovery or retry
        with self.lock:
            self.calls.append((task.task_id, task.plan_hash, attempt_id))
        return ExecutionHandle(task.task_id, f"run_{task.task_id}_{attempt_id}")

    def on_completion(self, _task_id, callback):
        self.callbacks.append(callback)
        return True


def _git(path, *args):
    return subprocess.run(["git", *args], cwd=path, check=True, capture_output=True, text=True).stdout.strip()


def test_execution_worker_logs_traceback_and_preserves_failure(monkeypatch, caplog):
    def fail(_argv):
        raise TypeError("bounded worker failure")

    monkeypatch.setattr(execution_service.code_agent, "main", fail)
    with pytest.raises(TypeError, match="bounded worker failure"):
        execution_service._run_code_agent(["task"])
    assert "code-agent execution worker failed" in caplog.text
    assert "TypeError: bounded worker failure" in caplog.text


def test_failed_validation_worker_uses_checkpoint_rollback_and_reconciles_all_state(recovery_fixture):
    f = recovery_fixture
    f.history.store.add_event(
        f.task.task_id, "isolation", "rollback_restore_succeeded",
        "Earlier completed attempt was restored", status="rollback_restore_succeeded",
        metadata={"owner_operation_id": "historical-operation"},
    )
    attempt_id = uuid4().hex
    f.history.store.add_event(
        f.task.task_id, "execution", "execution_attempt_started",
        "Execution attempt started", artifact_id=attempt_id, status="running",
        metadata={"attempt_id": attempt_id, "plan_hash": f.plan_hash},
    )
    now = datetime.now(UTC).isoformat()
    with f.history.store.transaction() as connection:
        connection.execute(
            "INSERT INTO task_execution_attempts VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (attempt_id, f.task.task_id, f.plan_hash, None, "initial", "failed",
             attempt_id, now, now, "LLMError", "{}", None),
        )
    f.history.transition(
        f.task.task_id, TaskStatus.VALIDATING, "validation started",
        subsystem="validation",
    )
    f.history.transition(
        f.task.task_id, TaskStatus.REVIEWING, "validation review indexed",
        subsystem="review",
    )
    f.history.store.add_event(
        f.task.task_id, "execution", "execution_attempt_failed",
        "Execution worker ended with a recorded failure", artifact_id=attempt_id,
        status="failed", metadata={"attempt_id": attempt_id, "failure_type": "LLMError"},
    )
    checkpoints = CheckpointManager(f.history.store.path.parent / "checkpoints")
    baseline = checkpoints.create(f.worktree, f.task.task_id, f.plan_hash, "baseline")
    (f.worktree / "README.md").write_text("malformed generated mutation\n")
    def worker(_task_id):
        return {"status": "failed", "failure_type": "LLMError"}
    worktrees = WorktreeManager(f.history.store.path.parent / "worktrees")
    service = OwnerRollbackService(
        f.history, worktrees, checkpoints,
        TransactionalRollbackService(worktrees, checkpoints, f.history),
        worker_status=worker,
    )

    key = str(uuid4())
    result = service.reconcile_validation_failure(
        f.task.task_id, f.plan_hash, key, "local-owner"
    )

    assert result["status"] == "rolled_back"
    assert result["checkpoint_id"] == baseline.checkpoint_id
    assert f.history.get(f.task.task_id).status is TaskStatus.ROLLED_BACK
    assert f.history.get(f.task.task_id).failure_reason == "LLMError during validation/repair"
    assert f.history.store.execution_attempts(f.task.task_id)[-1]["state"] == "failed"
    assert f.history.store.task_claims(f.task.task_id)["execution"] is None
    assert not f.history.artifacts(f.task.task_id)["executions"]
    assert not f.history.artifacts(f.task.task_id)["validations"]
    assert not f.history.artifacts(f.task.task_id)["reviews"]
    assert not f.worktree.exists()
    assert _git(f.repo, "status", "--porcelain") == ""
    assert _git(f.repo, "rev-parse", "HEAD") == f.head
    identity = worktrees.load(f.repo, f.task.task_id, starting_commit=f.head,
                              plan_hash=f.plan_hash)
    assert identity.state is WorktreeState.CLEANED
    projection = TaskRecoveryProjectionService(f.history, worktrees.root).project(f.task.task_id)
    assert projection.overall_status == "terminal_consistent"
    rollback_rows = f.history.store.task_rollback_operations(f.task.task_id)
    assert len(rollback_rows) == 1
    assert rollback_rows[0]["state"] == "succeeded"
    assert rollback_rows[0]["checkpoint_id"] == baseline.checkpoint_id
    assert json.loads(rollback_rows[0]["result_json"])["status"] == "restored"

    restarted_history = TaskHistoryService(TaskHistoryStore(f.history.store.path))
    restarted_worktrees = WorktreeManager(f.history.store.path.parent / "worktrees")
    restarted_checkpoints = CheckpointManager(f.history.store.path.parent / "checkpoints")
    restarted_service = OwnerRollbackService(
        restarted_history, restarted_worktrees, restarted_checkpoints,
        TransactionalRollbackService(restarted_worktrees, restarted_checkpoints, restarted_history),
        worker_status=lambda _task_id: {"status": "not_started"},
    )
    restarted_projection = TaskRecoveryProjectionService(
        restarted_history, restarted_worktrees.root,
    ).project(f.task.task_id)
    assert restarted_projection.overall_status == "terminal_consistent"
    assert restarted_projection.rollback.state == "succeeded"
    repeated = restarted_service.reconcile_validation_failure(
        f.task.task_id, f.plan_hash, key, "local-owner"
    )
    assert repeated["duplicate"] is True
    assert sum(
        event.event_type == "validation_failure_checkpoint_rollback_completed"
        for event in f.history.timeline(f.task.task_id)
    ) == 1


@pytest.fixture

def recovery_fixture(tmp_path):
    repo = tmp_path / "canonical"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("fixture\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-qm", "fixture")
    head = _git(repo, "rev-parse", "HEAD")
    history = TaskHistoryService(TaskHistoryStore(tmp_path / "history.sqlite3"))
    task = history.create_task("Implement safe fixture", repo, head, "main")
    history.transition(task.task_id, TaskStatus.PLANNING, "fixture plan")
    classification = TaskClassification(TaskCategory.BUG_FIX, 0.9, ("bug",), task.original_request)
    plan = ImplementationPlan(
        task_id=task.task_id, original_request=task.original_request,
        classification=classification, summary="Implement bounded fixture behavior",
        assumptions=(), direct_scope=(ScopeCandidate(
            path="README.md", symbol_id="py:fixture", qualified_name="fixture.assess",
            reason="fixture symbol", relationship="exact_symbol", retrieval_score=1.0,
            provenance={}, confidence=0.95, role=ScopeRole.DIRECT,
        ), ScopeCandidate(
            path="test_sample.py", symbol_id="py:fixture.test_case", qualified_name="fixture.test_case",
            reason="approved file-level test", relationship="exact_symbol", retrieval_score=1.0,
            provenance={}, confidence=0.95, role=ScopeRole.DIRECT,
        )), dependent_scope=(), files_to_inspect=(),
        files_to_modify=("README.md", "test_sample.py"), files_to_create=("MODEL_CARD.md",), files_to_delete_or_rename=(),
        symbols_to_modify=("fixture.assess",), symbols_to_create=(), steps=(), relevant_tests=(),
        validation_commands=("python -m pytest",), dependency_changes=(), migration_implications=(),
        security_implications=(), rollback_considerations=(), unresolved_questions=(),
        confidence=ConfidenceAssessment(0.9, {"bounded": 1.0}, ("test",)),
        risk=RiskAssessment(RiskLevel.MEDIUM, ("bounded",)),
        approval=ApprovalDecision(ApprovalStatus.REVIEW, ("review",)),
    )
    artifact = PlanningArtifact(datetime.now(UTC).isoformat(), str(repo), head,
                                task.original_request, classification, (), plan)
    plan_hash = plan_approval_token(plan)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(__import__("json").dumps(artifact.to_dict(), sort_keys=True))
    history.attach_plan(task.task_id, artifact, plan_path)
    history.transition(task.task_id, TaskStatus.AWAITING_APPROVAL, "plan ready")
    history.attach_approval(task.task_id, plan_hash, "explicitly_approved", actor="owner")
    history.transition(task.task_id, TaskStatus.APPROVED, "exact plan approved")
    history.transition(task.task_id, TaskStatus.EXECUTING, "execution started")
    manager = WorktreeManager(tmp_path / "worktrees")
    identity = manager.create(repo, task.task_id, head, plan_hash)
    manager.transition(identity, WorktreeState.EXECUTING)
    objective_id = "a" * 32
    objectives = ObjectiveAuthority(objective_id, task.task_id, plan_hash)
    executor = Executor(history)
    service = TaskExecutionRecoveryService(history, executor, objectives, tmp_path / "worktrees")
    return SimpleNamespace(history=history, task=task, repo=repo, head=head,
                           plan_hash=plan_hash, worktree=Path(identity.worktree),
                           objective_id=objective_id, objectives=objectives,
                           executor=executor, service=service)


def _recover(fixture, key=None):
    return fixture.service.recover(
        objective_id=fixture.objective_id, task_id=fixture.task.task_id,
        plan_hash=fixture.plan_hash, idempotency_key=key or str(uuid4()),
        principal="browser-owner",
    )


def test_failed_validation_worker_can_recover_exact_clean_approved_task(recovery_fixture):
    f = recovery_fixture
    f.history.transition(f.task.task_id, TaskStatus.VALIDATING, "validation started",
                         subsystem="validation")
    manager = WorktreeManager(f.history.store.path.parent / "worktrees")
    identity = manager.load(f.repo, f.task.task_id, starting_commit=f.head,
                            plan_hash=f.plan_hash)
    manager.transition(identity, WorktreeState.VALIDATING)

    result = _recover(f)

    assert result["status"] == "running"
    assert f.history.get(f.task.task_id).status is TaskStatus.EXECUTING
    assert f.executor.calls[-1][0] == f.task.task_id
    attempts = f.history.store.execution_attempts(f.task.task_id)
    assert attempts[-1]["attempt_kind"] == "recovery"
    assert attempts[-1]["plan_hash"] == f.plan_hash


def _rolled_back_retry_fixture(f):
    manager = WorktreeManager(f.history.store.path.parent / "worktrees")
    identity = manager.load(f.repo, f.task.task_id, starting_commit=f.head, plan_hash=f.plan_hash)
    manager.cleanup(identity, delete_branch=True, allow_active=True)
    attempt_id = "rolled-back-attempt"
    now = datetime.now(UTC).isoformat()
    with f.history.store.transaction() as connection:
        connection.execute(
            "INSERT INTO task_execution_attempts VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (attempt_id, f.task.task_id, f.plan_hash, None, "recovery", "completed",
             "prior-execution", now, now, None, "{}", "execution-rolled-back"),
        )
        connection.execute(
            "INSERT INTO task_execution_claims VALUES (?,?,?,?)",
            (f.task.task_id, attempt_id, int(datetime.now().timestamp()), int(datetime.now().timestamp()) + 86400),
        )
    report_path = f.history.store.path.parent / "execution-rolled-back.json"
    report_path.write_text(json.dumps({
        "schema_version": 1, "task_id": f.task.task_id, "plan_hash": f.plan_hash,
        "repository": str(f.worktree), "starting_commit": f.head, "status": "rolled_back",
        "plan_versions": [], "events": [{"tool_name": "read_file", "success": True,
                                           "affected_files": ["README.md"]}],
        "final_diff": "", "final_commit": None, "repairs": 0, "replans": 0,
        "attempt_id": attempt_id,
    }))
    f.history.store.attach_artifact(
        "executions", f.task.task_id, "execution-rolled-back", str(report_path),
        hashlib.sha256(report_path.read_bytes()).hexdigest(),
        {"run_id": attempt_id, "status": "rolled_back"},
    )
    f.history.transition(f.task.task_id, TaskStatus.ROLLED_BACK, "verified rollback")
    f.executor.status = "failed"
    f.retry_service = TaskExecutionRetryService(
        f.history, f.executor, f.objectives, f.history.store.path.parent / "worktrees",
    )
    return f


def _retry(f, key=None):
    return f.retry_service.retry(
        objective_id=f.objective_id, task_id=f.task.task_id, plan_hash=f.plan_hash,
        idempotency_key=key or str(uuid4()), principal="browser-owner",
        reason="Owner explicitly retries after reviewing the rolled-back result.",
    )


def _attach_failed_validation_from_latest_attempt(
    f, *, decision="failed", embedded_review=True, validation_path=None
):
    """Create the same failed validation/embedded summary emitted on rollback."""
    previous = f.history.store.execution_attempts(f.task.task_id)[-1]
    execution = f.history.artifacts(f.task.task_id)["executions"][0]
    execution_report = json.loads(Path(execution["artifact_path"]).read_text())
    validation_id = "validation-from-rolled-back-attempt"
    review = {"findings": [], "model_summary": None}
    report = {
        "schema_version": 1,
        "plan": {"task_id": f.task.task_id, "plan_hash": f.plan_hash,
                 "starting_commit": f.head, "repository": execution_report["repository"],
                 "validation_id": validation_id},
        "results": [], "decision": {"status": decision},
        "review": review,
    }
    validation_path = validation_path or f.history.store.path.parent / "validation-from-rollback.json"
    validation_path.write_text(json.dumps(report))
    validation_digest = hashlib.sha256(validation_path.read_bytes()).hexdigest()
    f.history.store.attach_artifact(
        "validations", f.task.task_id, "validation-from-rollback", str(validation_path),
        validation_digest, {"validation_id": validation_id, "decision": decision},
    )
    if embedded_review:
        review_digest = hashlib.sha256(json.dumps(review, sort_keys=True).encode()).hexdigest()
        f.history.store.attach_artifact(
            "reviews", f.task.task_id, "review_" + review_digest[:20], str(validation_path),
            review_digest, {"review_id": "review_" + review_digest[:20],
                            "metadata": {"embedded_in_validation": True}},
        )
    with f.history.store.transaction() as connection:
        connection.execute(
            "INSERT INTO artifact_imports VALUES (?,?,?,?,?,?)",
            (validation_digest, f.task.task_id, "validation", str(validation_path),
             previous["updated_at"], 1),
        )


def test_failed_artifactless_attempt_validation_can_be_reconciled_without_accepting_unrelated_reports(recovery_fixture):
    f = _rolled_back_retry_fixture(recovery_fixture)
    _attach_failed_validation_from_latest_attempt(f)
    prior = f.history.store.execution_attempts(f.task.task_id)[-1]
    latest_id = uuid4().hex
    start = (datetime.fromisoformat(prior["updated_at"]) + timedelta(seconds=1)).isoformat()
    end = (datetime.fromisoformat(prior["updated_at"]) + timedelta(seconds=3)).isoformat()
    with f.history.store.transaction() as connection:
        connection.execute(
            "INSERT INTO task_execution_attempts VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (latest_id, f.task.task_id, f.plan_hash, prior["attempt_id"], "retry", "failed",
             latest_id, start, end, "PatchValidationError", "{}", None),
        )
    prior_report = json.loads((f.history.store.path.parent / "validation-from-rollback.json").read_text())
    prior_report["plan"]["validation_id"] = "validation-from-current-attempt"
    current_path = f.history.store.path.parent / f"{latest_id}.json"
    current_path.write_text(json.dumps(prior_report))
    digest = hashlib.sha256(current_path.read_bytes()).hexdigest()
    f.history.store.attach_artifact(
        "validations", f.task.task_id, "validation-from-current-attempt", str(current_path),
        digest, {"validation_id": "validation-from-current-attempt", "decision": "failed"},
    )
    with f.history.store.transaction() as connection:
        connection.execute(
            "INSERT INTO artifact_imports VALUES (?,?,?,?,?,?)",
            (digest, f.task.task_id, "validation", str(current_path),
             (datetime.fromisoformat(start) + timedelta(seconds=1)).isoformat(), 1),
        )
    artifacts = f.history.artifacts(f.task.task_id)
    f.retry_service._allow_only_failed_rollback_validation(
        f.history.get(f.task.task_id), prior, artifacts,
        additional_failed_attempt=f.history.store.execution_attempts(f.task.task_id)[-1],
    )
    unrelated = f.history.store.execution_attempts(f.task.task_id)[-1].copy()
    unrelated["attempt_id"] = uuid4().hex
    with pytest.raises(ValueError, match="outside the rolled-back attempt interval"):
        f.retry_service._allow_only_failed_rollback_validation(
            f.history.get(f.task.task_id), prior, artifacts,
            additional_failed_attempt=unrelated,
        )


def test_rolled_back_retry_preserves_attempts_and_audits_atomic_claim_reconciliation(recovery_fixture):
    f = _rolled_back_retry_fixture(recovery_fixture)
    prior = f.history.store.execution_attempts(f.task.task_id)
    result = _retry(f)
    attempts = f.history.store.execution_attempts(f.task.task_id)
    assert result["task_id"] == f.task.task_id
    assert result["plan_hash"] == f.plan_hash
    assert result["parent_attempt_id"] == "rolled-back-attempt"
    assert attempts[:-1] == prior
    assert attempts[-1]["attempt_kind"] == "retry"
    assert attempts[-1]["attempt_id"] != "rolled-back-attempt"
    assert f.history.get(f.task.task_id).status is TaskStatus.EXECUTING
    assert f.history.store.task_claims(f.task.task_id)["execution"] is not None
    assert sum(item.event_type == "terminal_execution_claim_reconciled" for item in f.history.timeline(f.task.task_id)) == 1
    assert sum(item.event_type == "task_retry_requested" for item in f.history.timeline(f.task.task_id)) == 1


def test_retry_validates_rolled_back_artifact_against_recorded_task_worktree(recovery_fixture):
    f = _rolled_back_retry_fixture(recovery_fixture)
    row = next(row for row in f.history.artifacts(f.task.task_id)["executions"]
               if row["run_id"] == "rolled-back-attempt")
    report_path = Path(row["artifact_path"])
    report = json.loads(report_path.read_text())
    report["repository"] = str(f.repo)  # Canonical checkout is not the isolated attempt workspace.
    report_path.write_text(json.dumps(report))
    digest = hashlib.sha256(report_path.read_bytes()).hexdigest()
    with f.history.store.transaction() as connection:
        connection.execute(
            "UPDATE executions SET artifact_hash=? WHERE task_id=? AND run_id=?",
            (digest, f.task.task_id, "rolled-back-attempt"),
        )

    with pytest.raises(ValueError, match="artifact identity or outcome is inconsistent"):
        _retry(f)


def test_same_retry_key_is_idempotent_and_concurrent_retry_creates_one_attempt(recovery_fixture):
    f = _rolled_back_retry_fixture(recovery_fixture)
    key = str(uuid4())
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: _retry(f, key), range(2)))
    assert len({item["attempt_id"] for item in outcomes}) == 1
    assert sum(not item.get("duplicate", False) for item in outcomes) == 1
    assert len(f.executor.calls) == 1
    assert len(f.history.store.execution_attempts(f.task.task_id)) == 2


def test_terminal_attempt_after_api_process_replacement_can_be_retried(recovery_fixture):
    f = _rolled_back_retry_fixture(recovery_fixture)
    f.executor.status = "process_replaced"
    result = _retry(f)
    assert result["status"] == "running"
    assert f.history.store.execution_attempts(f.task.task_id)[-1]["attempt_kind"] == "retry"


def test_changed_plan_live_worker_and_competing_claim_block_retry(recovery_fixture):
    f = _rolled_back_retry_fixture(recovery_fixture)
    with pytest.raises(ValueError, match="exact rolled-back task"):
        f.retry_service.retry(objective_id=f.objective_id, task_id=f.task.task_id,
            plan_hash="0" * 64, idempotency_key=str(uuid4()), principal="owner",
            reason="Owner retry after reviewing the prior rollback.")
    f.executor.status = "running"
    with pytest.raises(ValueError, match="live or ambiguous"):
        _retry(f)
    f.executor.status = "failed"
    with f.history.store.transaction() as connection:
        connection.execute("UPDATE task_execution_claims SET claim_id='other-worker' WHERE task_id=?", (f.task.task_id,))
    with pytest.raises(Exception, match="competing execution claim"):
        _retry(f)


def test_ambiguous_workspace_and_revoked_approval_block_retry(recovery_fixture):
    f = _rolled_back_retry_fixture(recovery_fixture)
    (f.repo / "partial-change.txt").write_text("unreconciled")
    with pytest.raises(ValueError, match="ambiguous side effects"):
        _retry(f)
    (f.repo / "partial-change.txt").unlink()
    with f.history.store.transaction() as connection:
        connection.execute("INSERT INTO approvals VALUES (?,?,?,?,?,?,?,?)",
            ("approval-revoked", f.task.task_id, f.plan_hash, "revoked",
             datetime.now(UTC).isoformat(), "owner", "revoked", "{}"))
    with pytest.raises(ValueError, match="approval"):
        _retry(f)


def test_successful_artifact_career_forge_evidence_and_mutating_tool_journal_block_retry(recovery_fixture):
    f = _rolled_back_retry_fixture(recovery_fixture)
    before_claim = f.history.store.task_claims(f.task.task_id)["execution"]
    f.history.store.attach_artifact(
        "executions", f.task.task_id, "execution-success", str(f.repo / "README.md"),
        "0" * 64, {"run_id": "unrelated-success", "status": "complete"},
    )
    with pytest.raises(Exception, match="successful terminal execution"):
        _retry(f)
    assert f.history.store.task_claims(f.task.task_id)["execution"] == before_claim

    # The Career Forge adapter is queried before admission; any evidence bound
    # to the rolled-back attempt is a fail-closed retry blocker.
    f.retry_service.career_forge = SimpleNamespace(evidence_for_attempt=lambda _attempt: "evidence-1")
    with pytest.raises(ValueError, match="Career Forge evidence"):
        _retry(f)


def test_retry_blocks_mutating_or_invalid_execution_artifact_events(recovery_fixture):
    f = _rolled_back_retry_fixture(recovery_fixture)
    import json
    execution = f.history.artifacts(f.task.task_id)["executions"][0]
    report_path = Path(execution["artifact_path"])
    report = json.loads(report_path.read_text())
    report["events"].append({"tool_name": "apply_patch", "success": True, "affected_files": ["README.md"]})
    report_path.write_text(json.dumps(report))
    import hashlib
    with f.history.store.transaction() as connection:
        connection.execute("UPDATE executions SET artifact_hash=? WHERE artifact_id=?",
            (hashlib.sha256(report_path.read_bytes()).hexdigest(), execution["artifact_id"]))
    with pytest.raises(ValueError, match="side effects are ambiguous"):
        _retry(f)


def test_retry_allows_only_failed_approved_replace_after_verified_rollback(recovery_fixture):
    f = _rolled_back_retry_fixture(recovery_fixture)
    import hashlib
    import json

    execution = f.history.artifacts(f.task.task_id)["executions"][0]
    report_path = Path(execution["artifact_path"])
    report = json.loads(report_path.read_text())
    report["events"].append({
        "tool_name": "replace_file", "success": False,
        "arguments": {"path": "README.md", "_mutation_intended": True},
    })
    report_path.write_text(json.dumps(report))
    digest = hashlib.sha256(report_path.read_bytes()).hexdigest()
    with f.history.store.transaction() as connection:
        connection.execute("UPDATE executions SET artifact_hash=? WHERE artifact_id=?",
                           (digest, execution["artifact_id"]))

    result = _retry(f)
    assert result["status"] == "running"
    assert f.history.store.execution_attempts(f.task.task_id)[-1]["parent_attempt_id"] == "rolled-back-attempt"


def test_retry_allows_only_failed_approved_symbol_edit_after_verified_rollback(recovery_fixture):
    f = _rolled_back_retry_fixture(recovery_fixture)
    execution = f.history.artifacts(f.task.task_id)["executions"][0]
    report_path = Path(execution["artifact_path"])
    report = json.loads(report_path.read_text())
    report["events"].append({
        "tool_name": "replace_symbol_body", "success": False,
        "arguments": {"symbol": "fixture.assess", "_mutation_intended": True},
    })
    report_path.write_text(json.dumps(report))
    digest = hashlib.sha256(report_path.read_bytes()).hexdigest()
    with f.history.store.transaction() as connection:
        connection.execute(
            "UPDATE executions SET artifact_hash=? WHERE artifact_id=?",
            (digest, execution["artifact_id"]),
        )

    result = _retry(f)

    assert result["status"] == "running"
    assert f.history.store.execution_attempts(f.task.task_id)[-1]["parent_attempt_id"] == "rolled-back-attempt"


def test_retry_allows_scoped_successful_patch_after_verified_rollback(recovery_fixture):
    f = _rolled_back_retry_fixture(recovery_fixture)
    execution = f.history.artifacts(f.task.task_id)["executions"][0]
    report_path = Path(execution["artifact_path"])
    report = json.loads(report_path.read_text())
    report["events"].append({
        "tool_name": "apply_patch", "success": True,
        "arguments": {"_mutation_intended": True},
        "affected_files": ["README.md"],
    })
    report["final_diff"] = (
        "diff --git a/README.md b/README.md\n"
        "index 1111111..2222222 100644\n"
        "--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@\n-old\n+new\n"
    )
    report_path.write_text(json.dumps(report))
    with f.history.store.transaction() as connection:
        connection.execute(
            "UPDATE executions SET artifact_hash=? WHERE artifact_id=?",
            (hashlib.sha256(report_path.read_bytes()).hexdigest(), execution["artifact_id"]),
        )

    assert _retry(f)["status"] == "running"


def test_retry_allows_failed_existing_symbol_edit_in_approved_file_level_scope(recovery_fixture):
    f = _rolled_back_retry_fixture(recovery_fixture)
    execution = f.history.artifacts(f.task.task_id)["executions"][0]
    report_path = Path(execution["artifact_path"])
    report = json.loads(report_path.read_text())
    report["events"].append({
        "tool_name": "replace_symbol_body", "success": False,
        "arguments": {"symbol": "py:fixture.test_case", "_mutation_intended": True},
        "output_summary": "ToolArgumentError: Python mutation rejected before writing: syntax error at line 5",
        "affected_files": [],
    })
    report_path.write_text(json.dumps(report))
    with f.history.store.transaction() as connection:
        connection.execute(
            "UPDATE executions SET artifact_hash=? WHERE artifact_id=?",
            (hashlib.sha256(report_path.read_bytes()).hexdigest(), execution["artifact_id"]),
        )

    assert _retry(f)["status"] == "running"


def test_retry_reconciles_rolled_back_approved_symbol_edits_and_rejected_module_edit(recovery_fixture):
    f = _rolled_back_retry_fixture(recovery_fixture)
    execution = f.history.artifacts(f.task.task_id)["executions"][0]
    report_path = Path(execution["artifact_path"])
    report = json.loads(report_path.read_text())
    report["events"].extend([
        {"tool_name": "replace_symbol_body", "success": True,
         "arguments": {"symbol": "fixture.assess", "_mutation_intended": True},
         "affected_files": ["README.md"]},
        {"tool_name": "replace_symbol_body", "success": False,
         "arguments": {"symbol": "py:unapproved-module", "_mutation_intended": True},
         "output_summary": "ToolPermissionError: Symbol is outside approved scope: py:unapproved-module",
         "affected_files": []},
    ])
    report_path.write_text(json.dumps(report))
    with f.history.store.transaction() as connection:
        connection.execute(
            "UPDATE executions SET artifact_hash=? WHERE artifact_id=?",
            (hashlib.sha256(report_path.read_bytes()).hexdigest(), execution["artifact_id"]),
        )

    result = _retry(f)

    assert result["status"] == "running"
    assert f.history.store.execution_attempts(f.task.task_id)[-1]["parent_attempt_id"] == "rolled-back-attempt"


def test_retry_rejects_successful_symbol_edit_outside_approved_scope(recovery_fixture):
    f = _rolled_back_retry_fixture(recovery_fixture)
    execution = f.history.artifacts(f.task.task_id)["executions"][0]
    report_path = Path(execution["artifact_path"])
    report = json.loads(report_path.read_text())
    report["events"].append({
        "tool_name": "replace_symbol_body", "success": True,
        "arguments": {"symbol": "fixture.unapproved", "_mutation_intended": True},
        "affected_files": ["README.md"],
    })
    report_path.write_text(json.dumps(report))
    with f.history.store.transaction() as connection:
        connection.execute(
            "UPDATE executions SET artifact_hash=? WHERE artifact_id=?",
            (hashlib.sha256(report_path.read_bytes()).hexdigest(), execution["artifact_id"]),
        )

    with pytest.raises(ValueError, match="side effects are ambiguous"):
        _retry(f)


def test_retry_allows_failed_validation_and_embedded_summary_from_same_rollback(recovery_fixture):
    f = _rolled_back_retry_fixture(recovery_fixture)
    _attach_failed_validation_from_latest_attempt(f)
    execution = f.history.artifacts(f.task.task_id)["executions"][0]
    report_path = Path(execution["artifact_path"])
    report = json.loads(report_path.read_text())
    report["events"].append({
        "tool_name": "run_tests", "success": False,
        "arguments": {"command": "python -m pytest", "_mutation_intended": False},
        "affected_files": [],
    })
    report["events"].append({
        "tool_name": "create_file", "success": True,
        "arguments": {"path": "MODEL_CARD.md", "_mutation_intended": True},
        "affected_files": ["MODEL_CARD.md"],
    })
    report["final_diff"] = (
        "diff --git a/MODEL_CARD.md b/MODEL_CARD.md\n"
        "new file mode 100644\n--- /dev/null\n+++ b/MODEL_CARD.md\n"
        "@@ -0,0 +1 @@\n+# FraudShield model card\n"
    )
    report_path.write_text(json.dumps(report))
    with f.history.store.transaction() as connection:
        connection.execute(
            "UPDATE executions SET artifact_hash=? WHERE artifact_id=?",
            (hashlib.sha256(report_path.read_bytes()).hexdigest(), execution["artifact_id"]),
        )

    result = _retry(f)

    assert result["status"] == "running"
    attempts = f.history.store.execution_attempts(f.task.task_id)
    assert attempts[-1]["attempt_kind"] == "retry"
    assert attempts[-1]["parent_attempt_id"] == "rolled-back-attempt"


def test_retry_uses_latest_validation_when_attempt_scoped_report_path_is_replaced(recovery_fixture):
    f = _rolled_back_retry_fixture(recovery_fixture)
    _attach_failed_validation_from_latest_attempt(f)
    previous = f.history.store.execution_attempts(f.task.task_id)[-1]
    validation_path = f.history.artifacts(f.task.task_id)["validations"][0]["artifact_path"]
    report = json.loads(Path(validation_path).read_text())
    report["generation"] = 2
    report["review"] = {"findings": [], "model_summary": "second failed validation"}
    Path(validation_path).write_text(json.dumps(report))
    digest = hashlib.sha256(Path(validation_path).read_bytes()).hexdigest()
    imported_at = (datetime.fromisoformat(previous["updated_at"]) + timedelta(seconds=1)).isoformat()
    with f.history.store.transaction() as connection:
        connection.execute(
            "UPDATE task_execution_attempts SET updated_at=? WHERE attempt_id=?",
            (imported_at, previous["attempt_id"]),
        )
    f.history.store.attach_artifact(
        "validations", f.task.task_id, "validation-replaced-snapshot", validation_path,
        digest, {"validation_id": "validation-from-rolled-back-attempt", "decision": "failed"},
    )
    review_digest = hashlib.sha256(json.dumps(report["review"], sort_keys=True).encode()).hexdigest()
    f.history.store.attach_artifact(
        "reviews", f.task.task_id, "review_" + review_digest[:20], validation_path,
        review_digest, {"review_id": "review_" + review_digest[:20],
                        "metadata": {"embedded_in_validation": True}},
    )
    with f.history.store.transaction() as connection:
        connection.execute(
            "INSERT INTO artifact_imports VALUES (?,?,?,?,?,?)",
            (digest, f.task.task_id, "validation", validation_path, imported_at, 1),
        )

    assert _retry(f)["status"] == "running"


def test_retry_rejects_unapproved_failed_validation_event(recovery_fixture):
    f = _rolled_back_retry_fixture(recovery_fixture)
    execution = f.history.artifacts(f.task.task_id)["executions"][0]
    report_path = Path(execution["artifact_path"])
    report = json.loads(report_path.read_text())
    report["events"].append({
        "tool_name": "run_tests", "success": False,
        "arguments": {"command": "python -m pytest --disable-warnings", "_mutation_intended": False},
        "affected_files": [],
    })
    report_path.write_text(json.dumps(report))
    with f.history.store.transaction() as connection:
        connection.execute(
            "UPDATE executions SET artifact_hash=? WHERE artifact_id=?",
            (hashlib.sha256(report_path.read_bytes()).hexdigest(), execution["artifact_id"]),
        )

    with pytest.raises(ValueError, match="side effects are ambiguous"):
        _retry(f)


def test_retry_reconciles_scoped_audited_diff_after_clean_rollback(recovery_fixture):
    f = _rolled_back_retry_fixture(recovery_fixture)
    _attach_failed_validation_from_latest_attempt(f)
    execution = f.history.artifacts(f.task.task_id)["executions"][0]
    report_path = Path(execution["artifact_path"])
    report = json.loads(report_path.read_text())
    report["events"].append({
        "tool_name": "replace_symbol_body", "success": True,
        "arguments": {"symbol": "fixture.assess", "_mutation_intended": True},
        "affected_files": ["README.md"],
    })
    report["final_diff"] = (
        "diff --git a/README.md b/README.md\n"
        "index 1111111..2222222 100644\n"
        "--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@\n-old\n+new\n"
    )
    report_path.write_text(json.dumps(report))
    with f.history.store.transaction() as connection:
        connection.execute(
            "UPDATE executions SET artifact_hash=? WHERE artifact_id=?",
            (hashlib.sha256(report_path.read_bytes()).hexdigest(), execution["artifact_id"]),
        )

    result = _retry(f)

    assert result["status"] == "running"
    assert f.history.store.execution_attempts(f.task.task_id)[-1]["parent_attempt_id"] == "rolled-back-attempt"


def test_retry_rejects_audited_diff_outside_approved_files(recovery_fixture):
    f = _rolled_back_retry_fixture(recovery_fixture)
    execution = f.history.artifacts(f.task.task_id)["executions"][0]
    report_path = Path(execution["artifact_path"])
    report = json.loads(report_path.read_text())
    report["events"].append({
        "tool_name": "replace_symbol_body", "success": True,
        "arguments": {"symbol": "fixture.assess", "_mutation_intended": True},
        "affected_files": ["README.md"],
    })
    report["final_diff"] = "diff --git a/other.py b/other.py\n--- a/other.py\n+++ b/other.py\n"
    report_path.write_text(json.dumps(report))
    with f.history.store.transaction() as connection:
        connection.execute(
            "UPDATE executions SET artifact_hash=? WHERE artifact_id=?",
            (hashlib.sha256(report_path.read_bytes()).hexdigest(), execution["artifact_id"]),
        )

    with pytest.raises(ValueError, match="unscoped or unaudited diff"):
        _retry(f)


def test_retry_ignores_superseded_failed_validation_file_from_earlier_attempt(recovery_fixture):
    f = _rolled_back_retry_fixture(recovery_fixture)
    previous = f.history.store.execution_attempts(f.task.task_id)[-1]
    shared_path = f.history.store.path.parent / "validation-shared-path.json"
    old_report = {
        "plan": {"task_id": f.task.task_id, "plan_hash": f.plan_hash},
        "decision": {"status": "failed"},
    }
    shared_path.write_text(json.dumps(old_report))
    old_digest = hashlib.sha256(shared_path.read_bytes()).hexdigest()
    f.history.store.attach_artifact(
        "validations", f.task.task_id, "old-validation", str(shared_path), old_digest,
        {"validation_id": "validation-from-rolled-back-attempt", "decision": "failed"},
    )
    old_import = (
        datetime.fromisoformat(previous["created_at"]) - timedelta(seconds=1)
    ).isoformat()
    with f.history.store.transaction() as connection:
        connection.execute(
            "INSERT INTO artifact_imports VALUES (?,?,?,?,?,?)",
            (old_digest, f.task.task_id, "validation", str(shared_path), old_import, 1),
        )
    _attach_failed_validation_from_latest_attempt(f, validation_path=shared_path)

    result = _retry(f)

    assert result["status"] == "running"
    attempts = f.history.store.execution_attempts(f.task.task_id)
    assert attempts[-1]["attempt_kind"] == "retry"
    assert attempts[-1]["parent_attempt_id"] == "rolled-back-attempt"


def test_retry_still_blocks_superseded_successful_validation_history(recovery_fixture):
    f = _rolled_back_retry_fixture(recovery_fixture)
    previous = f.history.store.execution_attempts(f.task.task_id)[-1]
    shared_path = f.history.store.path.parent / "validation-shared-path.json"
    shared_path.write_text(json.dumps({"decision": {"status": "pass"}}))
    old_digest = hashlib.sha256(shared_path.read_bytes()).hexdigest()
    f.history.store.attach_artifact(
        "validations", f.task.task_id, "old-successful-validation", str(shared_path), old_digest,
        {"validation_id": "validation-from-rolled-back-attempt", "decision": "pass"},
    )
    old_import = (
        datetime.fromisoformat(previous["created_at"]) - timedelta(seconds=1)
    ).isoformat()
    with f.history.store.transaction() as connection:
        connection.execute(
            "INSERT INTO artifact_imports VALUES (?,?,?,?,?,?)",
            (old_digest, f.task.task_id, "validation", str(shared_path), old_import, 1),
        )
    _attach_failed_validation_from_latest_attempt(f, validation_path=shared_path)

    with pytest.raises(ValueError, match="successful validation evidence"):
        _retry(f)


def test_retry_still_blocks_successful_validation_and_independent_review(recovery_fixture):
    f = _rolled_back_retry_fixture(recovery_fixture)
    _attach_failed_validation_from_latest_attempt(f, decision="pass", embedded_review=False)
    with pytest.raises(ValueError, match="successful validation"):
        _retry(f)


def test_retry_allows_warning_validation_only_after_failed_verified_rollback(recovery_fixture):
    f = _rolled_back_retry_fixture(recovery_fixture)
    with f.history.store.transaction() as connection:
        connection.execute(
            "UPDATE task_execution_attempts SET state='failed' WHERE attempt_id='rolled-back-attempt'"
        )
    _attach_failed_validation_from_latest_attempt(f, decision="pass_with_warnings")

    result = _retry(f)

    assert result["status"] == "running"
    assert f.history.store.execution_attempts(f.task.task_id)[-1]["parent_attempt_id"] == "rolled-back-attempt"


def test_retry_blocks_independent_reviewer_evidence(recovery_fixture):
    f = _rolled_back_retry_fixture(recovery_fixture)
    _attach_failed_validation_from_latest_attempt(f, embedded_review=False)
    row = f.history.artifacts(f.task.task_id)["validations"][0]
    f.history.store.attach_artifact(
        "reviews", f.task.task_id, "independent-review", row["artifact_path"], "1" * 64,
        {"review_id": "independent-review", "blocking_findings": 0,
         "security_findings": 0, "model_assisted": True},
    )
    with pytest.raises(ValueError, match="independent Reviewer"):
        _retry(f)


def test_retry_rejects_failed_replace_outside_approved_files(recovery_fixture):
    f = _rolled_back_retry_fixture(recovery_fixture)
    import hashlib
    import json

    execution = f.history.artifacts(f.task.task_id)["executions"][0]
    report_path = Path(execution["artifact_path"])
    report = json.loads(report_path.read_text())
    report["events"].append({
        "tool_name": "replace_file", "success": False,
        "arguments": {"path": "outside.py", "_mutation_intended": True},
    })
    report_path.write_text(json.dumps(report))
    digest = hashlib.sha256(report_path.read_bytes()).hexdigest()
    with f.history.store.transaction() as connection:
        connection.execute("UPDATE executions SET artifact_hash=? WHERE artifact_id=?",
                           (digest, execution["artifact_id"]))

    with pytest.raises(ValueError, match="side effects are ambiguous"):
        _retry(f)


def test_retry_rejects_failed_symbol_edit_outside_approved_symbols(recovery_fixture):
    f = _rolled_back_retry_fixture(recovery_fixture)
    execution = f.history.artifacts(f.task.task_id)["executions"][0]
    report_path = Path(execution["artifact_path"])
    report = json.loads(report_path.read_text())
    report["events"].append({
        "tool_name": "replace_symbol_body", "success": False,
        "arguments": {"symbol": "fixture.unapproved", "_mutation_intended": True},
    })
    report_path.write_text(json.dumps(report))
    digest = hashlib.sha256(report_path.read_bytes()).hexdigest()
    with f.history.store.transaction() as connection:
        connection.execute(
            "UPDATE executions SET artifact_hash=? WHERE artifact_id=?",
            (digest, execution["artifact_id"]),
        )

    with pytest.raises(ValueError, match="side effects are ambiguous"):
        _retry(f)


def test_two_identical_deterministic_retry_failures_block_another_retry(recovery_fixture):
    f = _rolled_back_retry_fixture(recovery_fixture)
    import hashlib
    import json

    def finish_as_same_rollback(result):
        attempt_id = result["attempt_id"]
        path = f.history.store.path.parent / f"{attempt_id}.json"
        report = json.loads((f.history.store.path.parent / "execution-rolled-back.json").read_text())
        report["attempt_id"] = attempt_id
        path.write_text(json.dumps(report))
        f.history.store.attach_artifact(
            "executions", f.task.task_id, "execution-" + attempt_id, str(path),
            hashlib.sha256(path.read_bytes()).hexdigest(),
            {"run_id": attempt_id, "status": "rolled_back"},
        )
        f.history.store.finish_execution_attempt(attempt_id, failure_type="SystemExit")
        f.history.transition(f.task.task_id, TaskStatus.ROLLED_BACK, "same deterministic worker failure")

    first = _retry(f)
    finish_as_same_rollback(first)
    second = _retry(f)
    finish_as_same_rollback(second)
    with pytest.raises(ValueError, match="same deterministic retry failure has repeated"):
        _retry(f)


def test_retry_guard_migrates_legacy_repeated_failures_once(recovery_fixture):
    f = _rolled_back_retry_fixture(recovery_fixture)

    def finish_as_legacy_failure(result):
        attempt_id = result["attempt_id"]
        path = f.history.store.path.parent / f"{attempt_id}.json"
        report = json.loads(
            (f.history.store.path.parent / "execution-rolled-back.json").read_text()
        )
        report["attempt_id"] = attempt_id
        path.write_text(json.dumps(report))
        f.history.store.attach_artifact(
            "executions", f.task.task_id, "execution-" + attempt_id, str(path),
            hashlib.sha256(path.read_bytes()).hexdigest(),
            {"run_id": attempt_id, "status": "rolled_back"},
        )
        f.history.store.finish_execution_attempt(attempt_id, failure_type="SystemExit")
        f.history.transition(
            f.task.task_id, TaskStatus.ROLLED_BACK, "legacy deterministic failure"
        )
        with f.history.store.transaction() as connection:
            row = connection.execute(
                "SELECT metadata_json FROM task_execution_attempts WHERE attempt_id=?",
                (attempt_id,),
            ).fetchone()
            metadata = json.loads(row[0])
            metadata.pop("implementation_fingerprint", None)
            connection.execute(
                "UPDATE task_execution_attempts SET metadata_json=? WHERE attempt_id=?",
                (json.dumps(metadata, sort_keys=True), attempt_id),
            )

    first = _retry(f)
    finish_as_legacy_failure(first)
    second = _retry(f)
    finish_as_legacy_failure(second)

    third = _retry(f)

    assert third["status"] == "running"
    assert third["parent_attempt_id"] == second["attempt_id"]


def test_retry_failure_guard_allows_one_attempt_after_execution_implementation_changes(
    recovery_fixture, monkeypatch
):
    f = _rolled_back_retry_fixture(recovery_fixture)
    implementation = {"value": "before-fix"}
    monkeypatch.setattr(
        history_store,
        "execution_implementation_fingerprint",
        lambda: implementation["value"],
    )
    monkeypatch.setattr(
        recovery_module,
        "execution_implementation_fingerprint",
        lambda: implementation["value"],
    )

    def finish_as_same_rollback(result):
        attempt_id = result["attempt_id"]
        path = f.history.store.path.parent / f"{attempt_id}.json"
        report = json.loads(
            (f.history.store.path.parent / "execution-rolled-back.json").read_text()
        )
        report["attempt_id"] = attempt_id
        path.write_text(json.dumps(report))
        f.history.store.attach_artifact(
            "executions", f.task.task_id, "execution-" + attempt_id, str(path),
            hashlib.sha256(path.read_bytes()).hexdigest(),
            {"run_id": attempt_id, "status": "rolled_back"},
        )
        f.history.store.finish_execution_attempt(attempt_id, failure_type="SystemExit")
        metadata = json.loads(f.history.store.execution_attempts(f.task.task_id)[-1]["metadata_json"])
        f.history.transition(
            f.task.task_id, TaskStatus.ROLLED_BACK, "same deterministic worker failure"
        )
        return metadata["failure_signature"]

    first = _retry(f)
    first_signature = finish_as_same_rollback(first)
    implementation["value"] = "after-bounded-fix"
    second = _retry(f)
    second_signature = finish_as_same_rollback(second)

    assert second_signature != first_signature
    third = _retry(f)
    third_signature = finish_as_same_rollback(third)
    assert third_signature == second_signature
    with pytest.raises(ValueError, match="same deterministic retry failure has repeated"):
        _retry(f)


def test_clean_worker_failure_recovers_same_task_plan_and_existing_worktree(recovery_fixture):
    f = recovery_fixture
    original = f.task.task_id
    result = _recover(f)
    assert result["task_id"] == original
    assert result["plan_hash"] == f.plan_hash
    assert result["status"] == "running"
    assert f.history.get(original).status is TaskStatus.EXECUTING
    attempts = f.history.store.execution_attempts(original)
    assert [item["attempt_kind"] for item in attempts] == ["interrupted", "recovery"]
    assert attempts[1]["parent_attempt_id"] == attempts[0]["attempt_id"]
    assert len(f.executor.calls) == 1
    assert f.worktree.is_dir()
    assert any(event.event_type == "execution_interruption_detected" for event in f.history.timeline(original))
    assert any(event.event_type == "execution_recovery_started" for event in f.history.timeline(original))


def test_same_idempotency_key_never_dispatches_twice(recovery_fixture):
    f = recovery_fixture
    key = str(uuid4())
    first = _recover(f, key)
    second = _recover(f, key)
    assert second["duplicate"] is True
    assert second["attempt_id"] == first["attempt_id"]
    assert len(f.executor.calls) == 1


def test_simultaneous_same_key_recovery_has_one_attempt_and_worker(recovery_fixture):
    f = recovery_fixture
    key = str(uuid4())
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: _recover(f, key), range(2)))
    assert len(f.executor.calls) == 1
    assert len({item["attempt_id"] for item in outcomes}) == 1
    assert sum(not item["duplicate"] for item in outcomes) == 1


def test_active_worker_and_claim_block_recovery(recovery_fixture):
    f = recovery_fixture
    f.executor.status = "running"
    with pytest.raises(ValueError, match="live execution worker"):
        _recover(f)
    f.executor.status = "failed"
    assert f.history.store.claim_execution(f.task.task_id, "active-claim")
    with pytest.raises(Exception, match="active execution claim"):
        _recover(f)
    assert not f.executor.calls


def test_unknown_worker_and_ambiguous_objective_link_block(recovery_fixture):
    f = recovery_fixture
    f.executor.status = "unknown"
    with pytest.raises(ValueError, match="ambiguous"):
        _recover(f)
    f.executor.status = "failed"
    f.objectives.objective.plan_hash = "f" * 64
    with pytest.raises(ValueError, match="exact active Objective binding"):
        _recover(f)
    assert not f.executor.calls


def test_changed_plan_hash_and_revoked_latest_approval_block(recovery_fixture):
    f = recovery_fixture
    with pytest.raises(ValueError, match="exact interrupted task"):
        f.service.recover(objective_id=f.objective_id, task_id=f.task.task_id,
                          plan_hash="0" * 64, idempotency_key=str(uuid4()), principal="owner")
    with f.history.store.transaction() as connection:
        connection.execute(
            "INSERT INTO approvals VALUES (?,?,?,?,?,?,?,?)",
            ("approval_revoked", f.task.task_id, f.plan_hash, "revoked",
             datetime.now(UTC).isoformat(), "owner", "revoked", "{}"),
        )
    with pytest.raises(ValueError, match="approval"):
        _recover(f)
    assert not f.executor.calls


def test_dirty_workspace_and_tool_journal_block_recovery(recovery_fixture):
    f = recovery_fixture
    (f.worktree / "partial.txt").write_text("partial side effect")
    with pytest.raises(ValueError, match="unverified side effects"):
        _recover(f)
    (f.worktree / "partial.txt").unlink()
    (f.repo / ".git" / "info" / "exclude").write_text("ignored-local\n")
    (f.worktree / "ignored-local").write_text("ignored side effect")
    with pytest.raises(ValueError, match="unverified side effects"):
        _recover(f)
    (f.worktree / "ignored-local").unlink()
    with f.history.store.transaction() as connection:
        connection.execute(
            "INSERT INTO tool_events VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ("tool-partial", f.task.task_id, "run-old", datetime.now(UTC).isoformat(),
             "write_file", 1, 0.1, "[]", "partial tool effect", None, "{}"),
        )
    with pytest.raises(Exception, match="side effects"):
        _recover(f)
    assert not f.executor.calls


def test_terminal_execution_artifact_blocks_recovery(recovery_fixture):
    f = recovery_fixture
    with f.history.store.transaction() as connection:
        connection.execute(
            "INSERT INTO executions VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ("execution-terminal", f.task.task_id, "run-old", "artifact.json", "a" * 64,
             "complete", 1.0, 0, 0, f.head, "{}"),
        )
    with pytest.raises(Exception, match="side effects or terminal evidence"):
        _recover(f)
    assert not f.executor.calls


def test_rollback_history_blocks_recovery(recovery_fixture):
    f = recovery_fixture
    with f.history.store.transaction() as connection:
        connection.execute(
            "INSERT INTO rollback_operations VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ("rollback-1", f.task.task_id, "checkpoint-1", f.plan_hash,
             "owner", "executed", "fingerprint", datetime.now(UTC).isoformat(),
             datetime.now(UTC).isoformat(), "rollback-key", "{}"),
        )
    with pytest.raises(Exception, match="Rollback evidence"):
        _recover(f)
    assert not f.executor.calls


def test_recovery_cli_plan_load_requires_live_claim(recovery_fixture):
    f = recovery_fixture
    with pytest.raises(ValueError, match="exact canonical approved plan"):
        f.history.load_approved_plan(f.task.task_id, f.plan_hash,
                                     execution_attempt_id="invented-attempt")


def test_missing_completion_tracking_does_not_release_recovery_claim(recovery_fixture):
    f = recovery_fixture
    f.executor.on_completion = None
    with pytest.raises(RuntimeError, match="completion could not be tracked"):
        _recover(f)
    attempts = f.history.store.execution_attempts(f.task.task_id)
    recovery = attempts[-1]
    assert recovery["state"] == "running"
    assert f.history.store.task_claims(f.task.task_id)["execution"] is not None
