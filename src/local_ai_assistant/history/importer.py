"""Idempotent indexing of existing Stage 3-5 JSON artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from local_ai_assistant.execution.history import load_report, redact
from local_ai_assistant.planning.service import PlannerService
from local_ai_assistant.validation.service import load_validation_report

from .errors import ArtifactImportError
from .models import TaskStatus, utc_now
from .service import TaskHistoryService


class ArtifactImporter:
    def __init__(self, service: TaskHistoryService) -> None:
        self.service = service

    def import_path(self, path: Path, *, repository: Path | None = None) -> dict:
        path = path.resolve()
        try:
            raw = path.read_bytes()
            value = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            raise ArtifactImportError(f"Invalid artifact {path}: {exc}") from exc
        digest = hashlib.sha256(raw).hexdigest()
        with self.service.store._connect() as connection:
            duplicate = connection.execute(
                "SELECT task_id, artifact_type FROM artifact_imports WHERE artifact_hash = ?",
                (digest,),
            ).fetchone()
        if duplicate:
            return {"imported": False, "duplicate": True, "task_id": duplicate[0], "type": duplicate[1]}
        artifact_type = self._type(value)
        try:
            if artifact_type == "plan":
                artifact = PlannerService.load(path)
                task_id = artifact.plan.task_id
                repo = Path(artifact.repository).resolve()
                self._verify_requested_repository(repo, repository)
                self._ensure_task(
                    task_id, artifact.request, repo, artifact.starting_commit,
                    value.get("branch", "unknown"), artifact.timestamp,
                )
                self.service.attach_plan(task_id, artifact, path)
                schema = artifact.schema_version
            elif artifact_type == "execution":
                report = load_report(path)
                task_id = report["task_id"]
                repo = Path(report["repository"]).resolve()
                self._verify_requested_repository(repo, repository)
                self._ensure_task(task_id, value.get("request", "Imported execution"), repo, report["starting_commit"], value.get("branch", "unknown"), value.get("timestamp", utc_now()))
                self._execution(task_id, path, digest, report)
                schema = int(report["schema_version"])
            else:
                report = load_validation_report(path)
                plan = report["plan"]
                task_id = plan["task_id"]
                repo = Path(plan["repository"]).resolve()
                self._verify_requested_repository(repo, repository)
                self._ensure_task(task_id, report.get("metadata", {}).get("original_request", "Imported validation"), repo, plan["starting_commit"], value.get("branch", "unknown"), value.get("timestamp", utc_now()))
                self._validation(task_id, path, digest, report)
                schema = int(report["schema_version"])
        except ArtifactImportError:
            raise
        except Exception as exc:
            raise ArtifactImportError(f"Cannot import {artifact_type} artifact {path}: {exc}") from exc
        with self.service.store.transaction() as connection:
            connection.execute(
                "INSERT INTO artifact_imports VALUES (?, ?, ?, ?, ?, ?)",
                (digest, task_id, artifact_type, str(path), utc_now(), schema),
            )
        return {"imported": True, "duplicate": False, "task_id": task_id, "type": artifact_type, "hash": digest}

    @staticmethod
    def _type(value: dict) -> str:
        if not isinstance(value, dict):
            raise ArtifactImportError("Artifact root must be an object")
        if "plan" in value and "scope_candidates" in value and "classification" in value:
            return "plan"
        if "events" in value and "plan_versions" in value and "status" in value:
            return "execution"
        if "results" in value and "review" in value and "decision" in value:
            return "validation"
        raise ArtifactImportError("Unrecognized Stage 3-5 artifact schema")

    @staticmethod
    def _verify_requested_repository(actual: Path, expected: Path | None) -> None:
        if expected is not None and actual != expected.resolve():
            raise ArtifactImportError("Artifact repository identity does not match requested repository")

    def _ensure_task(self, task_id, request, repo, commit, branch, timestamp):
        existing = self.service.get(task_id)
        if existing:
            if Path(existing.repository).resolve() != repo or existing.starting_commit != commit:
                raise ArtifactImportError("Artifact task identity conflicts with existing history")
            return
        self.service.create_task(
            request, repo, commit, branch, task_id=task_id, created_at=timestamp,
            metadata={"imported": True},
        )

    def _execution(self, task_id, path, digest, report):
        self._advance(task_id, TaskStatus.EXECUTING, report.get("plan_hash"))
        inserted = self.service.store.attach_artifact(
            "executions", task_id, "execution_" + digest[:20], str(path), digest,
            {"run_id": "execution_" + digest[:20], "status": report.get("status"), "repairs": report.get("repairs", 0), "replans": report.get("replans", 0), "final_commit": report.get("final_commit"), "metadata": {"schema_version": report["schema_version"]}},
        )
        if not inserted:
            return
        with self.service.store.transaction() as connection:
            for number, event in enumerate(report.get("events", [])):
                event_id = "tool_" + hashlib.sha256(f"{digest}:{number}".encode()).hexdigest()[:20]
                connection.execute(
                    "INSERT INTO tool_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (event_id, task_id, "execution_" + digest[:20], event.get("timestamp", utc_now()), event.get("tool_name", "unknown"), int(bool(event.get("success"))), event.get("duration_seconds"), json.dumps(event.get("affected_files", [])), redact(event.get("output_summary", ""))[:1000], event.get("approval"), "{}"),
                )
            connection.execute(
                "UPDATE metrics_summary SET repairs = ?, reapprovals = ?, tool_calls = ?, commit_success = ? WHERE task_id = ?",
                (
                    report.get("repairs", 0), report.get("replans", 0),
                    len(report.get("events", [])),
                    int(report.get("status") in {"committed", "merged", "no_changes"}), task_id,
                ),
            )
        self.service.store.add_event(task_id, "execution", "execution_imported", f"Execution status: {report.get('status')}", artifact_id="execution_" + digest[:20], artifact_path=str(path), status=report.get("status"))
        outcome = report.get("status")
        terminal = (
            TaskStatus.SUCCEEDED
            if outcome in {"complete", "committed", "merged", "no_changes"}
            else TaskStatus.ROLLED_BACK
            if outcome == "rolled_back"
            else TaskStatus.FAILED
            if outcome and outcome.startswith("failed")
            else None
        )
        task = self.service.get(task_id)
        if terminal and task and task.status not in {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.ROLLED_BACK}:
            if terminal is TaskStatus.SUCCEEDED and task.status is TaskStatus.EXECUTING:
                self.service.transition(task_id, TaskStatus.VALIDATING, "Imported validation phase", subsystem="validation")
                self.service.transition(task_id, TaskStatus.REVIEWING, "Imported review phase", subsystem="review")
            self.service.finalize(
                task_id, Path(task.repository), terminal,
                final_commit=report.get("final_commit"), outcome=outcome,
            )

    def _validation(self, task_id, path, digest, report):
        self._advance(task_id, TaskStatus.VALIDATING, report["plan"].get("plan_hash"))
        results = report.get("results", [])
        failures = report.get("failures", [])
        decision = report.get("decision", {}).get("status")
        tests_run = sum(1 for result in results if "test" in result.get("step_id", "").lower())
        required_passed = not any(not item.get("success") and not item.get("skipped") for item in results)
        review = report.get("review", {})
        findings = review.get("findings", [])
        blocking = sum(bool(item.get("blocking")) for item in findings)
        security = sum(item.get("category") == "security" and item.get("blocking") for item in findings)
        targeted_ids = {item.get("step_id") for item in report["plan"].get("targeted_steps", [])}
        final_ids = {item.get("step_id") for item in report["plan"].get("final_steps", [])}
        targeted_results = [item for item in results if item.get("step_id") in targeted_ids]
        final_results = [item for item in results if item.get("step_id") in final_ids]
        self.service.store.attach_artifact(
            "validations", task_id, "validation_" + digest[:20], str(path), digest,
            {"validation_id": report["plan"].get("validation_id"), "decision": decision, "required_passed": required_passed, "failure_count": len(failures), "tests_run": tests_run, "metadata": {"schema_version": report["schema_version"]}},
        )
        review_digest = hashlib.sha256(json.dumps(review, sort_keys=True).encode()).hexdigest()
        self.service.store.attach_artifact(
            "reviews", task_id, "review_" + review_digest[:20], str(path), review_digest,
            {"review_id": "review_" + review_digest[:20], "blocking_findings": blocking, "security_findings": security, "model_assisted": bool(review.get("model_summary")), "metadata": {"embedded_in_validation": True}},
        )
        with self.service.store.transaction() as connection:
            connection.execute(
                """UPDATE metrics_summary SET validation_failures = ?,
                   security_blocking_findings = ?, tests_run = ?, first_pass_success = ?,
                   first_targeted_test_pass = ?, first_full_suite_pass = ?,
                   review_blocking_findings = ? WHERE task_id = ?""",
                (
                    len(failures), security, tests_run, int(required_passed and not failures),
                    int(all(item.get("success") for item in targeted_results)) if targeted_results else None,
                    int(all(item.get("success") for item in final_results)) if final_results else None,
                    blocking, task_id,
                ),
            )
        self.service.store.add_event(task_id, "validation", "validation_imported", f"Validation decision: {decision}", artifact_id="validation_" + digest[:20], artifact_path=str(path), status=decision)
        task = self.service.get(task_id)
        if task and task.status is TaskStatus.VALIDATING:
            self.service.transition(task_id, TaskStatus.REVIEWING, "Validation review indexed", subsystem="review")

    def _advance(self, task_id: str, target: TaskStatus, plan_hash: str | None) -> None:
        task = self.service.get(task_id)
        if task is None or task.status in {
            TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.BLOCKED,
            TaskStatus.ROLLED_BACK, TaskStatus.CANCELLED,
        }:
            return
        if plan_hash:
            if task.plan_hash and task.plan_hash != plan_hash:
                raise ArtifactImportError("Artifact plan hash conflicts with current task plan")
            if not task.plan_hash:
                task = self.service.store.update_task(
                    task_id, task.repository, plan_hash=plan_hash
                )
        if task.status is TaskStatus.CREATED:
            self.service.transition(task_id, TaskStatus.PLANNING, "Imported plan phase", subsystem="planning")
            task = self.service.get(task_id)
        if task.status is TaskStatus.PLANNING:
            self.service.transition(task_id, TaskStatus.APPROVED, "Imported approved plan", subsystem="approval")
            task = self.service.get(task_id)
        if task.status in {TaskStatus.AWAITING_APPROVAL, TaskStatus.REAPPROVAL_REQUIRED}:
            if task.plan_hash and plan_hash == task.plan_hash:
                self.service.attach_approval(
                    task_id, task.plan_hash, "explicitly_approved", actor="artifact_import",
                    reason="Execution/validation artifact is bound to this exact plan hash",
                )
            self.service.transition(task_id, TaskStatus.APPROVED, "Imported exact-plan approval", subsystem="approval")
            task = self.service.get(task_id)
        if target in {TaskStatus.EXECUTING, TaskStatus.VALIDATING} and task.status is TaskStatus.APPROVED:
            self.service.transition(task_id, TaskStatus.EXECUTING, "Execution artifact indexed", subsystem="execution")
            task = self.service.get(task_id)
        if target is TaskStatus.VALIDATING and task.status is TaskStatus.EXECUTING:
            self.service.transition(task_id, TaskStatus.VALIDATING, "Validation artifact indexed", subsystem="validation")
