from __future__ import annotations

import json
import sqlite3
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from local_ai_assistant.common.config import AppConfig, PathConfig
from local_ai_assistant.history.cli import main as history_main
from local_ai_assistant.history.errors import (
    ArtifactImportError,
    HistoryDatabaseError,
    InvalidStatusTransition,
)
from local_ai_assistant.history.export import export_task
from local_ai_assistant.history.importer import ArtifactImporter
from local_ai_assistant.history.metrics import aggregate_metrics
from local_ai_assistant.history.models import TaskFilter, TaskStatus
from local_ai_assistant.history.service import TaskHistoryService
from local_ai_assistant.history.store import TaskHistoryStore
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
from local_ai_assistant.ui.coding import CodingUIService


@pytest.fixture
def history(tmp_path):
    store = TaskHistoryStore(tmp_path / "history.sqlite3")
    return TaskHistoryService(store)


def create(service, tmp_path, request="Fix parser", **kwargs):
    repo = tmp_path / kwargs.pop("repo", "repo")
    repo.mkdir(exist_ok=True)
    return service.create_task(request, repo, "a" * 40, kwargs.pop("branch", "main"), **kwargs)


def test_task_creation_has_stable_persisted_identity(history, tmp_path):
    task = create(history, tmp_path, created_at="2026-01-01T00:00:00+00:00")
    same_inputs = create(
        TaskHistoryService(TaskHistoryStore(tmp_path / "other.sqlite3")),
        tmp_path,
        created_at="2026-01-01T00:00:00+00:00",
    )

    assert task.task_id == same_inputs.task_id
    assert history.get(task.task_id) == task
    assert history.timeline(task.task_id)[0].event_type == "task_created"


def test_status_lifecycle_and_invalid_transition(history, tmp_path):
    task = create(history, tmp_path)
    history.transition(task.task_id, TaskStatus.PLANNING, "planning")
    history.transition(task.task_id, TaskStatus.AWAITING_APPROVAL, "review")
    history.transition(task.task_id, TaskStatus.APPROVED, "approved")
    history.transition(task.task_id, TaskStatus.EXECUTING, "execute")
    history.transition(task.task_id, TaskStatus.VALIDATING, "validate")
    history.transition(task.task_id, TaskStatus.REVIEWING, "review")
    final = history.finalize(
        task.task_id, Path(task.repository), TaskStatus.SUCCEEDED,
        final_commit="b" * 40, decision="pass", outcome="committed", duration_seconds=2.5,
    )

    assert final.status is TaskStatus.SUCCEEDED
    assert [event.status for event in history.timeline(task.task_id) if event.status][-1] == "succeeded"
    with pytest.raises(InvalidStatusTransition):
        history.transition(task.task_id, TaskStatus.EXECUTING, "invalid")


def test_reapproval_rollback_repair_timeline_is_chronological(history, tmp_path):
    task = create(history, tmp_path)
    for status in (TaskStatus.PLANNING, TaskStatus.APPROVED, TaskStatus.EXECUTING):
        history.transition(task.task_id, status, status.value)
    history.store.add_event(task.task_id, "repair", "repair_attempt", "Repair 1")
    history.transition(task.task_id, TaskStatus.REAPPROVAL_REQUIRED, "scope increased")
    history.transition(task.task_id, TaskStatus.APPROVED, "renewed")
    history.transition(task.task_id, TaskStatus.EXECUTING, "resumed")
    rolled_back = history.finalize(
        task.task_id, Path(task.repository), TaskStatus.ROLLED_BACK,
        outcome="rolled back", failure_reason="validation failed",
    )

    events = history.timeline(task.task_id)
    assert rolled_back.status is TaskStatus.ROLLED_BACK
    assert [item.timestamp for item in events] == sorted(item.timestamp for item in events)
    assert {item.event_type for item in events} >= {"repair_attempt", "status_changed"}


def test_cooperative_cancel_request_is_auditable(history, tmp_path):
    task = create(history, tmp_path)
    history.transition(task.task_id, TaskStatus.PLANNING, "planning")
    history.request_cancel(task.task_id, Path(task.repository), "user requested stop")

    assert history.cancel_requested(task.task_id)
    assert history.timeline(task.task_id)[-1].event_type == "cancel_requested"


def test_repository_identity_isolation_and_exact_approval_binding(history, tmp_path):
    task = create(history, tmp_path)
    history.store.update_task(task.task_id, task.repository, plan_hash="hash-one")
    with pytest.raises(HistoryDatabaseError, match="exact current plan"):
        history.attach_approval(task.task_id, "hash-two", "approved")
    with pytest.raises(HistoryDatabaseError, match="identity"):
        history.store.update_task(task.task_id, str(tmp_path / "other"), summary="bad")
    approval = history.attach_approval(task.task_id, "hash-one", "approved")
    assert approval.startswith("approval_")


def test_search_filters_files_symbols_languages_and_text(history, tmp_path):
    first = create(history, tmp_path, "Fix Rust parser", repo="rust", branch="feature")
    second = create(history, tmp_path, "Document Python API", repo="python")
    history.store.update_task(first.task_id, first.repository, classification="bug_fix", risk="medium", outcome="fixed")
    history.store.update_task(second.task_id, second.repository, classification="documentation", risk="low")
    history.store.add_affected_file(first.task_id, "src/lib.rs", "direct", "rust", "modify")
    history.store.add_affected_symbol(first.task_id, "rs:1", "crate::run", "src/lib.rs", "rust", "direct")

    assert history.search("Rust")[0].task_id == first.task_id
    assert history.list(TaskFilter(repository=first.repository))[0].task_id == first.task_id
    assert history.list(TaskFilter(branch="feature", classification="bug_fix", risk="medium", outcome="fixed"))[0].task_id == first.task_id
    assert history.list(TaskFilter(affected_file="src/lib.rs", language="rust"))[0].task_id == first.task_id
    assert history.list(TaskFilter(affected_symbol="crate::run"))[0].task_id == first.task_id


def test_execution_artifact_import_is_idempotent_and_redacted(history, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    artifact = tmp_path / "execution.json"
    artifact.write_text(
        json.dumps(
            {
                "schema_version": 1, "task_id": "imported", "plan_hash": "plan",
                "repository": str(repo), "starting_commit": "a" * 40, "status": "complete",
                "plan_versions": ["plan"], "repairs": 1, "replans": 0,
                "events": [{"task_id": "imported", "plan_hash": "plan", "repository": str(repo), "starting_commit": "a" * 40, "tool_name": "run_tests", "arguments": {"token": "secret-value"}, "timestamp": "2026-01-01T00:00:00+00:00", "duration_seconds": 1.0, "success": True, "output_summary": "token=secret-value", "mutation_summary": "", "affected_files": ["a.py"], "risk": "low", "approval": "approved"}],
            }
        )
    )
    importer = ArtifactImporter(history)
    first = importer.import_path(artifact, repository=repo)
    second = importer.import_path(artifact, repository=repo)

    assert first["imported"] is True and second["duplicate"] is True
    with history.store._connect() as connection:
        summary = connection.execute("SELECT summary FROM tool_events").fetchone()[0]
    assert "secret-value" not in summary


def test_plan_validation_and_review_artifacts_attach_without_large_blob_duplication(history, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    task = history.create_task("Fix parser", repo, "a" * 40, "main", task_id="artifact-task")
    classification = TaskClassification(TaskCategory.BUG_FIX, 0.9, ("bug",), "Fix parser")
    plan = ImplementationPlan(
        task_id=task.task_id,
        original_request=task.original_request,
        classification=classification,
        summary="Fix parser safely",
        assumptions=(), direct_scope=(), dependent_scope=(), files_to_inspect=(),
        files_to_modify=(), files_to_create=(), files_to_delete_or_rename=(),
        symbols_to_modify=(), symbols_to_create=(), steps=(), relevant_tests=(),
        validation_commands=(), dependency_changes=(), migration_implications=(),
        security_implications=(), rollback_considerations=(), unresolved_questions=(),
        confidence=ConfidenceAssessment(0.8, {"exact": 1.0}, ("heuristic",)),
        risk=RiskAssessment(RiskLevel.MEDIUM, ("logic",)),
        approval=ApprovalDecision(ApprovalStatus.AUTOMATIC, ("bounded",)),
    )
    artifact = PlanningArtifact(
        "2026-01-01T00:00:00+00:00", str(repo), "a" * 40, task.original_request,
        classification, (), plan,
    )
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(artifact.to_dict()))
    assert history.attach_plan(task.task_id, artifact, plan_path)
    assert not history.attach_plan(task.task_id, artifact, plan_path)

    validation_path = tmp_path / "validation.json"
    validation_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "plan": {
                    "schema_version": 1, "validation_id": "validation-1",
                    "task_id": task.task_id, "plan_hash": history.get(task.task_id).plan_hash,
                    "repository": str(repo), "starting_commit": "a" * 40,
                    "risk_level": "medium", "affected_files": [], "affected_symbols": [],
                    "targeted_steps": [], "final_steps": [], "expected_coverage": "configured",
                    "timeout_policy": {}, "failure_policy": "required", "configuration_identity": "config",
                },
                "results": [], "failures": [],
                "review": {"plan_hash": "plan", "diff_hash": "diff", "findings": [{"category": "security", "blocking": True}], "model_summary": None},
                "decision": {"status": "blocked", "reasons": ["security"], "evidence": []},
                "metadata": {"original_request": task.original_request},
            }
        )
    )
    imported = ArtifactImporter(history).import_path(validation_path, repository=repo)
    artifacts = history.artifacts(task.task_id)
    assert imported["type"] == "validation"
    assert len(artifacts["plans"]) == len(artifacts["validations"]) == len(artifacts["reviews"]) == 1
    assert "Fix parser safely" not in json.dumps(artifacts["plans"])


def test_corrupt_and_cross_repository_artifacts_fail(history, tmp_path):
    corrupt = tmp_path / "bad.json"
    corrupt.write_text("{")
    with pytest.raises(ArtifactImportError):
        ArtifactImporter(history).import_path(corrupt)
    unknown = tmp_path / "unknown.json"
    unknown.write_text('{"schema_version": 1}')
    with pytest.raises(ArtifactImportError, match="Unrecognized"):
        ArtifactImporter(history).import_path(unknown)


def test_metrics_handle_empty_and_aggregate_quality_counts(history, tmp_path):
    empty = aggregate_metrics(history.store)
    assert empty.total_tasks == 0 and empty.success_rate == 0 and empty.first_pass_success_rate == 0
    task = create(history, tmp_path)
    with history.store.transaction() as connection:
        connection.execute(
            "UPDATE tasks SET status='succeeded', outcome='committed', duration_seconds=4 WHERE task_id=?",
            (task.task_id,),
        )
        connection.execute(
            """UPDATE metrics_summary SET repairs=2, first_pass_success=0,
               scope_violations=1, reapprovals=1, tests_run=3, tool_calls=5,
               validation_failures=1, security_blocking_findings=1 WHERE task_id=?""",
            (task.task_id,),
        )
    metrics = aggregate_metrics(history.store)
    assert metrics.success_rate == 1
    assert metrics.average_repairs == 2
    assert metrics.scope_violations == metrics.reapprovals == metrics.validation_failures == 1
    assert metrics.tests_run == 3 and metrics.tool_calls == 5


def test_json_markdown_exports_redact_secrets(history, tmp_path):
    task = create(history, tmp_path, "Use token=super-secret safely")
    json_path = export_task(history, task.task_id, tmp_path / "task.json", "json")
    markdown = export_task(history, task.task_id, tmp_path / "task.md", "markdown")

    assert "super-secret" not in json_path.read_text()
    assert "super-secret" not in markdown.read_text()
    assert "[REDACTED]" in json_path.read_text()


def test_safe_concurrent_reads_during_writes_and_transaction_rollback(history, tmp_path):
    task = create(history, tmp_path)

    def read():
        return history.get(task.task_id).task_id

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(read) for _ in range(20)]
        history.store.add_event(task.task_id, "test", "concurrent", "write")
    assert {future.result() for future in futures} == {task.task_id}
    with pytest.raises(RuntimeError):
        with history.store.transaction() as connection:
            connection.execute("UPDATE tasks SET summary='wrong' WHERE task_id=?", (task.task_id,))
            raise RuntimeError("rollback")
    assert history.get(task.task_id).summary == ""


def test_corrupt_database_fails_explicitly(tmp_path):
    path = tmp_path / "bad.sqlite3"
    path.write_bytes(b"not sqlite")
    with pytest.raises(HistoryDatabaseError):
        TaskHistoryStore(path).initialize()


def test_schema_migration_is_ordered_and_newer_schema_is_rejected(tmp_path):
    path = tmp_path / "migration.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE schema_version(version INTEGER NOT NULL)")
        connection.execute("INSERT INTO schema_version VALUES (0)")
    store = TaskHistoryStore(path)
    store.initialize()
    assert store.status()["schema_version"] == 1
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE schema_version SET version = 999")
    with pytest.raises(HistoryDatabaseError, match="newer"):
        store.initialize()


def test_ui_service_lists_only_configured_git_repositories(tmp_path):
    roots = tmp_path / "repos"
    repo = roots / "demo"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repo, check=True)
    (repo / "main.rs").write_text("fn main() {}\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "base"], cwd=repo, check=True, capture_output=True)
    paths = PathConfig(
        var_dir=tmp_path / "var", document_dir=tmp_path / "docs", rag_data_dir=tmp_path / "rag",
        code_repo_dir=roots, code_index_dir=tmp_path / "index", patch_dir=tmp_path / "patches",
        task_history_db=tmp_path / "var/history/tasks.sqlite3",
    )
    service = CodingUIService(AppConfig(paths=paths))

    snapshot = service.repositories()[0]
    assert snapshot.name == "demo" and snapshot.clean and snapshot.languages == ("rust",)
    with pytest.raises(ValueError):
        service.repository("../outside")

    outside = tmp_path / "outside.json"
    outside.write_text('{"password": "do-not-display"}')
    preview = service.artifact_preview({"artifact_path": str(outside)})
    assert preview["available"] is False
    assert "do-not-display" not in json.dumps(preview)


def test_history_cli_create_list_search_status_metrics_and_export(tmp_path, capsys):
    database = tmp_path / "history.sqlite3"
    repo = tmp_path / "repo"
    repo.mkdir()
    prefix = ["--database", str(database)]
    assert history_main([*prefix, "status"]) == 0
    capsys.readouterr()
    assert history_main(
        [*prefix, "create", str(repo), "Fix parser", "--branch", "main", "--starting-commit", "a" * 40]
    ) == 0
    created = json.loads(capsys.readouterr().out)
    assert history_main([*prefix, "list", "--risk", "unknown"]) == 0
    assert history_main([*prefix, "search", "parser"]) == 0
    assert history_main([*prefix, "timeline", created["task_id"]]) == 0
    assert history_main([*prefix, "metrics"]) == 0
    destination = tmp_path / "export.json"
    assert history_main([*prefix, "export", created["task_id"], str(destination)]) == 0
    assert destination.is_file()
    archive = tmp_path / "task.zip"
    assert history_main([*prefix, "archive", created["task_id"], str(archive)]) == 0
    assert archive.is_file()
