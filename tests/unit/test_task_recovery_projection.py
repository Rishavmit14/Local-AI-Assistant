import json
from pathlib import Path

import pytest

from local_ai_assistant.autonomy.service import ObjectiveService
from local_ai_assistant.history.models import TaskStatus
from local_ai_assistant.history.service import TaskHistoryService
from local_ai_assistant.history.store import TaskHistoryStore
from local_ai_assistant.interface.task_recovery import TaskRecoveryProjectionService


def setup_task(tmp_path, *, status=TaskStatus.EXECUTING):
    repository = tmp_path / "canonical"
    repository.mkdir(exist_ok=True)
    store = TaskHistoryStore(tmp_path / "tasks.sqlite3")
    history = TaskHistoryService(store)
    task = history.create_task("synthetic recovery fixture", repository, "a" * 40, "main")
    if status is not TaskStatus.CREATED:
        with store.transaction() as connection:
            connection.execute("UPDATE tasks SET status=? WHERE task_id=?", (status.value, task.task_id))
    root = tmp_path / "runtime" / "worktrees"
    repo_id = "a" * 20
    (root / repo_id / task.task_id).mkdir(parents=True)
    metadata = root / repo_id / "metadata" / f"{task.task_id}.json"
    metadata.parent.mkdir(parents=True)
    metadata.write_text(json.dumps({
        "schema_version": 1, "task_id": task.task_id, "repository_id": repo_id,
        "canonical_repository": str(repository.resolve()), "starting_commit": task.starting_commit,
        "plan_hash": task.plan_hash, "state": "executing", "cleanup_status": "pending",
        "worktree": str(root / repo_id / task.task_id),
    }))
    return history, task, root, metadata


@pytest.mark.parametrize(("state", "expected"), [
    ("creating", "interrupted_lifecycle"), ("ready", "interrupted_lifecycle"),
    ("executing", "interrupted_lifecycle"), ("validating", "interrupted_lifecycle"),
    ("rollback_in_progress", "rollback_in_progress"),
    ("recovery_required", "recovery_required"), ("cleanup_pending", "cleanup_pending"),
    ("cleaned", "interrupted_lifecycle"), ("failed", "interrupted_lifecycle"),
    ("rolled_back", "interrupted_lifecycle"), ("cancelled", "interrupted_lifecycle"),
    ("promotion_ready", "interrupted_lifecycle"), ("promoted", "interrupted_lifecycle"),
])
def test_projection_distinguishes_every_worktree_lifecycle(tmp_path, state, expected):
    history, task, root, metadata = setup_task(tmp_path)
    value = json.loads(metadata.read_text())
    value["state"] = state
    metadata.write_text(json.dumps(value))
    result = TaskRecoveryProjectionService(history, root, clock=lambda: 1000).project(task.task_id)
    assert result.overall_status == expected
    assert result.task_id == task.task_id


@pytest.mark.parametrize(("claim_kind", "expires", "expected"), [
    ("planning", 2000, "active"), ("planning", 999, "expired"),
    ("execution", 2000, "active"), ("execution", 999, "expired"),
])
def test_projection_reads_claim_expiry_without_pruning_or_claiming(tmp_path, claim_kind, expires, expected):
    history, task, root, metadata = setup_task(tmp_path)
    table = "task_planning_claims" if claim_kind == "planning" else "task_execution_claims"
    with history.store.transaction() as connection:
        connection.execute(f"INSERT INTO {table}(task_id, claim_id, claimed_at, expires_at) VALUES(?,?,?,?)", (task.task_id, "synthetic-claim", 900, expires))
    before = history.store.task_claims(task.task_id)
    result = TaskRecoveryProjectionService(history, root, clock=lambda: 1000).project(task.task_id)
    after = history.store.task_claims(task.task_id)
    claim = getattr(result, f"{claim_kind}_claim")
    assert claim.state == expected
    assert before == after
    expected_overall = "claim_expired" if expected == "expired" else ("claim_waiting" if claim_kind == "execution" else "interrupted_lifecycle")
    assert result.overall_status == expected_overall


@pytest.mark.parametrize(("worker", "expected_status", "attention"), [
    ({"status": "running"}, "in_progress_known", "wait"),
    ({"status": "completed"}, "interrupted_lifecycle", "inspect"),
    ({"status": "failed"}, "interrupted_lifecycle", "inspect"),
    ({"status": "not_started"}, "interrupted_lifecycle", "inspect"),
    (None, "interrupted_lifecycle", "inspect"),
])
def test_worker_observation_is_separate_from_task_status(tmp_path, worker, expected_status, attention):
    history, task, root, _ = setup_task(tmp_path)
    result = TaskRecoveryProjectionService(history, root, worker_status=(lambda _: worker) if worker else None, clock=lambda: 1000).project(task.task_id)
    assert result.overall_status == expected_status
    assert result.owner_attention == attention
    assert result.worker_liveness == ("running" if worker and worker["status"] == "running" else "not_running" if worker and worker["status"] in {"completed", "failed"} else "unknown")


@pytest.mark.parametrize("mutation,expected", [
    ("missing_worktree", "missing_worktree"), ("corrupt", "corrupt"),
    ("path_rejected", "path_rejected"), ("identity_mismatch", "identity_mismatch"),
])
def test_projection_fails_closed_for_untrustworthy_or_missing_isolation(tmp_path, mutation, expected):
    history, task, root, metadata = setup_task(tmp_path)
    if mutation == "missing_worktree":
        import shutil
        shutil.rmtree(root / ("a" * 20) / task.task_id)
    elif mutation == "corrupt":
        metadata.write_text("{")
    else:
        value = json.loads(metadata.read_text())
        if mutation == "path_rejected":
            value["worktree"] = str(tmp_path / "outside")
        else:
            value["starting_commit"] = "b" * 40
        metadata.write_text(json.dumps(value))
    result = TaskRecoveryProjectionService(history, root, clock=lambda: 1000).project(task.task_id)
    assert result.overall_status == expected
    assert result.owner_attention == "inspect"


def test_projection_serialization_contains_no_paths_requests_or_claim_secrets(tmp_path):
    history, task, root, _ = setup_task(tmp_path)
    with history.store.transaction() as connection:
        connection.execute("INSERT INTO task_execution_claims(task_id, claim_id, claimed_at, expires_at) VALUES(?,?,?,?)", (task.task_id, "private-claim-secret", 900, 2000))
    result = TaskRecoveryProjectionService(history, root, clock=lambda: 1000).project(task.task_id).to_dict()
    serialized = json.dumps(result)
    assert str(tmp_path) not in serialized
    assert "synthetic recovery fixture" not in serialized
    assert "private-claim-secret" not in serialized
    assert result["task_id"] == task.task_id


@pytest.mark.parametrize("status", [TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.BLOCKED, TaskStatus.ROLLED_BACK, TaskStatus.CANCELLED])
def test_terminal_history_and_cleaned_isolation_are_reported_without_inference(tmp_path, status):
    history, task, root, metadata = setup_task(tmp_path)
    value = json.loads(metadata.read_text())
    value.update(state="cleaned", cleanup_status="cleaned")
    metadata.write_text(json.dumps(value))
    with history.store.transaction() as connection:
        connection.execute("UPDATE tasks SET status=? WHERE task_id=?", (status.value, task.task_id))
    import shutil
    shutil.rmtree(root / ("a" * 20) / task.task_id)
    result = TaskRecoveryProjectionService(history, root, clock=lambda: 1000).project(task.task_id)
    assert result.task_status == status.value
    assert result.overall_status == "terminal_consistent"
    assert result.cleanup.state == "complete"


def test_objective_plan_disagreement_is_preserved_as_owner_inspection(tmp_path):
    history, task, root, metadata = setup_task(tmp_path)
    with history.store.transaction() as connection:
        connection.execute("UPDATE tasks SET plan_hash=? WHERE task_id=?", ("a" * 64, task.task_id))
    value = json.loads(metadata.read_text())
    value["plan_hash"] = "a" * 64
    metadata.write_text(json.dumps(value))
    objectives = ObjectiveService(
        tmp_path / "objectives.sqlite3",
        plan_hash_for_task=lambda _: "b" * 64,
        task_state_for_task=lambda _: "executing",
    )
    objective = objectives.create("synthetic linked objective")
    objectives.bind_plan(objective.objective_id, task.task_id)
    result = TaskRecoveryProjectionService(history, root, objectives, clock=lambda: 1000).project(task.task_id)
    assert result.overall_status == "objective_task_mismatch"
    assert result.owner_attention == "inspect"
    assert result.objective_links[0].plan_matches_task is False


def test_corrupt_objective_identity_is_not_emitted(tmp_path):
    history, task, root, _ = setup_task(tmp_path)
    objectives = ObjectiveService(tmp_path / "objectives.sqlite3")
    with objectives._db() as connection:
        connection.execute(
            "INSERT INTO objectives(objective_id,text,state,created_at,updated_at,plan_hash,task_id) VALUES(?,?,?,?,?,?,?)",
            ("private-owner-path", "private objective text", "planned", "2026-09-28T00:00:00+00:00", "2026-09-28T00:00:00+00:00", None, task.task_id),
        )
    result = TaskRecoveryProjectionService(history, root, objectives, clock=lambda: 1000).project(task.task_id)
    assert result.overall_status == "objective_unavailable"
    assert result.objective_links[0].objective_id is None
    assert result.objective_links[0].state == "unavailable"
    assert "private-owner-path" not in json.dumps(result.to_dict())
    assert "private objective text" not in json.dumps(result.to_dict())


@pytest.mark.parametrize(("state", "result_json", "expected"), [
    ("executing", None, "rollback_in_progress"),
    ("failed_recovered", '{"status":"failed_recovered"}', "rollback_failed_recovered"),
    ("recovery_required", '{"status":"recovery_required"}', "recovery_required"),
    ("succeeded", '{"status":"restored"}', "rollback_completed"),
])
def test_rollback_ledger_is_projected_by_exact_task_and_never_retried(tmp_path, state, result_json, expected):
    history, task, root, _ = setup_task(tmp_path)
    with history.store.transaction() as connection:
        connection.execute(
            "INSERT INTO rollback_operations(operation_id,task_id,checkpoint_id,plan_hash,principal,state,fingerprint,created_at,expires_at,idempotency_key,result_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            ("c" * 32, task.task_id, "d" * 24, "a" * 64, "private-principal", state, "private-fingerprint", "2026-09-28T10:00:00+00:00", "2026-09-28T10:10:00+00:00", "private-key", result_json),
        )
    result = TaskRecoveryProjectionService(history, root, clock=lambda: 1000).project(task.task_id)
    assert result.overall_status == expected
    assert result.rollback.operation_id == "c" * 32
    assert result.rollback.checkpoint_id == "d" * 24
    assert "private-principal" not in json.dumps(result.to_dict())
    assert "private-fingerprint" not in json.dumps(result.to_dict())
    assert "private-key" not in json.dumps(result.to_dict())


@pytest.mark.parametrize("artifact_status", ["complete", "committed", "rolled_back", "failed_validation"])
def test_terminal_execution_artifact_is_not_implicitly_reconciled(tmp_path, artifact_status):
    history, task, root, _ = setup_task(tmp_path)
    with history.store.transaction() as connection:
        connection.execute(
            "INSERT INTO executions(artifact_id,task_id,run_id,artifact_path,artifact_hash,status,duration_seconds,repairs,replans,final_commit,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            ("artifact-synthetic", task.task_id, "run-synthetic", str(tmp_path / "private-artifact.json"), "d" * 64, artifact_status, 1.0, 0, 0, None, "{}"),
        )
    result = TaskRecoveryProjectionService(history, root, clock=lambda: 1000).project(task.task_id)
    assert result.overall_status == "terminal_evidence_unreconciled"
    assert result.reconciliation.state == "terminal_evidence_unreconciled"
    assert history.get(task.task_id).status is TaskStatus.EXECUTING
    assert str(tmp_path) not in json.dumps(result.to_dict())


def test_terminal_task_with_recovery_required_isolation_keeps_both_sources_visible(tmp_path):
    history, task, root, metadata = setup_task(tmp_path)
    with history.store.transaction() as connection:
        connection.execute("UPDATE tasks SET status=? WHERE task_id=?", (TaskStatus.SUCCEEDED.value, task.task_id))
    result = json.loads(metadata.read_text())
    result["state"] = "recovery_required"
    metadata.write_text(json.dumps(result))
    projection = TaskRecoveryProjectionService(history, root, clock=lambda: 1000).project(task.task_id)
    assert projection.task_status == "succeeded"
    assert projection.isolation.state == "recovery_required"
    assert projection.overall_status == "recovery_required"
    assert projection.owner_attention == "inspect"
    assert "TaskHistory records a terminal state" in projection.summary


def test_projection_is_scoped_to_the_exact_requested_task(tmp_path):
    history, first, root, _ = setup_task(tmp_path)
    second = history.create_task("unrelated synthetic task", Path(first.repository), "b" * 40, "main")
    (root / ("b" * 20) / second.task_id).mkdir(parents=True)
    second_meta = root / ("b" * 20) / "metadata" / f"{second.task_id}.json"
    second_meta.parent.mkdir(parents=True)
    second_meta.write_text(json.dumps({
        "schema_version": 1, "task_id": second.task_id, "repository_id": "b" * 20,
        "canonical_repository": str(first.repository), "starting_commit": second.starting_commit,
        "plan_hash": second.plan_hash, "state": "recovery_required", "cleanup_status": "pending",
        "worktree": str(root / ("b" * 20) / second.task_id),
    }))
    first_projection = TaskRecoveryProjectionService(history, root, clock=lambda: 1000).project(first.task_id)
    second_projection = TaskRecoveryProjectionService(history, root, clock=lambda: 1000).project(second.task_id)
    assert first_projection.overall_status == "interrupted_lifecycle"
    assert second_projection.overall_status == "recovery_required"
    assert first_projection.task_id != second_projection.task_id
