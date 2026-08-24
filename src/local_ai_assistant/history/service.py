"""Repository-bound service API for task history and audit records."""

from __future__ import annotations

import hashlib
from pathlib import Path

from local_ai_assistant.code_index.languages import build_language_registry
from local_ai_assistant.execution.history import redact
from local_ai_assistant.planning.models import PlanningArtifact, plan_approval_token

from .errors import HistoryDatabaseError
from .models import TaskFilter, TaskRecord, TaskStatus, stable_task_id, utc_now
from .store import TaskHistoryStore


class TaskHistoryService:
    def __init__(
        self,
        store: TaskHistoryStore,
        *,
        artifact_roots: tuple[Path, ...] | None = None,
    ) -> None:
        self.store = store
        self.artifact_roots = tuple(
            root.resolve() for root in (artifact_roots or (store.path.parent,))
        )
        self.store.initialize()

    def create_task(
        self,
        request: str,
        repository: Path,
        starting_commit: str,
        branch: str,
        *,
        task_id: str | None = None,
        created_at: str | None = None,
        metadata: dict | None = None,
    ) -> TaskRecord:
        timestamp = created_at or utc_now()
        repository_id = str(repository.resolve())
        return self.store.create_task(
            TaskRecord(
                task_id or stable_task_id(repository_id, starting_commit, request, timestamp),
                redact(request),
                repository_id,
                starting_commit,
                branch,
                timestamp,
                timestamp,
                metadata=metadata or {},
            )
        )

    def create_external_task(
        self, request: str, repository: Path, starting_commit: str, branch: str,
        *, source: str, event_id: str, metadata: dict | None = None,
    ) -> TaskRecord:
        """Create an externally-originated task and idempotency claim atomically."""
        timestamp = utc_now()
        repository_id = str(repository.resolve())
        task = TaskRecord(
            stable_task_id(repository_id, starting_commit, request, timestamp),
            redact(request), repository_id, starting_commit, branch, timestamp, timestamp,
            metadata=metadata or {},
        )
        return self.store.create_external_task(task, source=source, event_id=event_id)

    def transition(self, task_id: str, status: TaskStatus, reason: str, *, subsystem="history"):
        return self.store.transition(task_id, status, reason, subsystem=subsystem)

    def attach_plan(self, task_id: str, artifact: PlanningArtifact, path: Path) -> bool:
        task = self._identity(task_id, artifact.repository, artifact.starting_commit)
        if task.status in {
            TaskStatus.EXECUTING,
            TaskStatus.VALIDATING,
            TaskStatus.REVIEWING,
            TaskStatus.SUCCEEDED,
            TaskStatus.FAILED,
            TaskStatus.BLOCKED,
            TaskStatus.ROLLED_BACK,
            TaskStatus.CANCELLED,
        }:
            raise HistoryDatabaseError("Cannot replace a plan after execution has started")
        path = self.validate_artifact_path(path)
        digest = _sha256(path)
        plan_hash = plan_approval_token(artifact.plan)
        with self.store._connect() as connection:
            version = 1 + connection.execute(
                "SELECT COUNT(*) FROM plans WHERE task_id = ?", (task_id,)
            ).fetchone()[0]
        attached = self.store.attach_artifact(
            "plans",
            task_id,
            "plan_" + digest[:20],
            str(path.resolve()),
            digest,
            {
                "version": version,
                "plan_hash": plan_hash,
                "created_at": artifact.timestamp,
                "metadata": {"schema_version": artifact.schema_version},
            },
        )
        if attached:
            requires_reapproval = task.status is TaskStatus.APPROVED
            registry = build_language_registry()
            self.store.update_task(
                task_id,
                task.repository,
                classification=artifact.classification.category.value,
                risk=artifact.plan.risk.level.value,
                confidence=artifact.plan.confidence.score,
                approval_state=artifact.plan.approval.status.value,
                plan_hash=plan_hash,
                summary=artifact.plan.summary,
            )
            if requires_reapproval:
                self.store.update_task(
                    task_id, task.repository, approval_state="stale_plan_replaced"
                )
                self.store.transition(
                    task_id,
                    TaskStatus.REAPPROVAL_REQUIRED,
                    "Plan content changed after approval",
                    subsystem="approval",
                )
            for candidate in artifact.scope_candidates:
                self.store.add_affected_file(
                    task_id,
                    candidate.path,
                    candidate.role.value,
                    registry.detect(candidate.path),
                    change_type="inspect",
                )
                if candidate.symbol_id:
                    symbol_language = candidate.provenance.get("language") or registry.detect(
                        candidate.path
                    )
                    self.store.add_affected_symbol(
                        task_id,
                        candidate.symbol_id,
                        candidate.qualified_name,
                        candidate.path,
                        symbol_language,
                        candidate.role.value,
                    )
            with self.store.transaction() as connection:
                connection.execute(
                    "UPDATE metrics_summary SET model_calls = model_calls + 1, plan_validation_success = ? WHERE task_id = ?",
                    (
                        int(not any(issue.severity.value == "error" for issue in artifact.validation_issues)),
                        task_id,
                    ),
                )
            self.store.add_event(
                task_id,
                "planning",
                "plan_attached",
                f"Plan {plan_hash[:12]} attached",
                artifact_id="plan_" + digest[:20],
                artifact_path=str(path.resolve()),
                risk_or_severity=artifact.plan.risk.level.value,
            )
        return attached

    def attach_approval(self, task_id: str, plan_hash: str, state: str, *, actor="human", reason="") -> str:
        if state not in {"explicitly_approved", "historical_execution_evidence"}:
            raise HistoryDatabaseError("Unsupported approval evidence state")
        timestamp = utc_now()
        approval_id = "approval_" + hashlib.sha256(
            f"{task_id}\0{plan_hash}\0{timestamp}\0{actor}".encode()
        ).hexdigest()[:20]
        with self.store.transaction() as connection:
            task = connection.execute(
                "SELECT status, plan_hash FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            if task is None or task["plan_hash"] != plan_hash:
                raise HistoryDatabaseError(
                    "Approval does not match the task's exact current plan hash"
                )
            if TaskStatus(task["status"]) not in {
                TaskStatus.AWAITING_APPROVAL,
                TaskStatus.REAPPROVAL_REQUIRED,
            }:
                raise HistoryDatabaseError("Task is not awaiting exact-plan approval")
            connection.execute(
                "INSERT INTO approvals VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (approval_id, task_id, plan_hash, state, timestamp, actor, redact(reason), "{}"),
            )
            connection.execute(
                "UPDATE tasks SET approval_state = ?, updated_at = ? WHERE task_id = ?",
                (state, timestamp, task_id),
            )
            self.store._insert_event(
                connection,
                task_id,
                timestamp,
                "approval",
                "approval_recorded",
                f"Approval state: {state}",
                artifact_id=approval_id,
                status=state,
            )
        return approval_id

    def finalize(
        self,
        task_id: str,
        repository: Path,
        status: TaskStatus,
        *,
        final_commit: str | None = None,
        decision: str | None = None,
        outcome: str | None = None,
        failure_reason: str | None = None,
        duration_seconds: float | None = None,
    ) -> TaskRecord:
        task = self._identity(task_id, str(repository.resolve()), None)
        if status not in {
            TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.BLOCKED,
            TaskStatus.ROLLED_BACK, TaskStatus.CANCELLED,
        }:
            raise HistoryDatabaseError("Final status must be terminal")
        return self.store.finalize_task(
            task_id,
            task.repository,
            status,
            final_commit=final_commit,
            decision=decision,
            outcome=outcome,
            failure_reason=failure_reason,
            duration_seconds=duration_seconds,
        )

    def validate_artifact_path(self, path: Path) -> Path:
        try:
            resolved = path.resolve(strict=True)
        except OSError as exc:
            raise HistoryDatabaseError(f"Artifact is unavailable: {exc}") from exc
        if not resolved.is_file() or not any(
            resolved == root or root in resolved.parents for root in self.artifact_roots
        ):
            raise HistoryDatabaseError("Artifact is outside configured runtime roots")
        return resolved

    def get(self, task_id: str) -> TaskRecord | None:
        return self.store.get_task(task_id)

    def list(self, filters: TaskFilter | None = None):
        return self.store.list_tasks(filters)

    def search(self, text: str, **filters):
        return self.store.list_tasks(TaskFilter(text=text, **filters))

    def timeline(self, task_id: str):
        return self.store.timeline(task_id)

    def request_cancel(self, task_id: str, repository: Path, reason: str) -> TaskRecord:
        task = self._identity(task_id, str(repository.resolve()), None)
        if task.status not in {
            TaskStatus.PLANNING, TaskStatus.AWAITING_APPROVAL, TaskStatus.APPROVED,
            TaskStatus.EXECUTING, TaskStatus.VALIDATING, TaskStatus.REVIEWING,
            TaskStatus.REAPPROVAL_REQUIRED,
        }:
            raise HistoryDatabaseError("Task is not in a cancellable state")
        metadata = {**task.metadata, "cancel_requested": True, "cancel_reason": reason}
        updated = self.store.update_task(task_id, task.repository, metadata=metadata)
        self.store.add_event(
            task_id, "control", "cancel_requested", reason,
            status="cancel_requested", risk_or_severity="warning",
        )
        if task.status in {
            TaskStatus.PLANNING,
            TaskStatus.AWAITING_APPROVAL,
            TaskStatus.APPROVED,
            TaskStatus.REAPPROVAL_REQUIRED,
        }:
            return self.store.transition(
                task_id,
                TaskStatus.CANCELLED,
                "Cancelled before execution",
                subsystem="control",
            )
        return updated

    def cancel_requested(self, task_id: str) -> bool:
        task = self.store.get_task(task_id)
        return bool(task and task.metadata.get("cancel_requested"))

    def record_isolation_event(
        self,
        task_id: str,
        event_type: str,
        summary: str,
        *,
        status: str | None = None,
        severity: str | None = None,
        metadata: dict | None = None,
    ):
        """Persist bounded isolation evidence without granting execution authority."""
        return self.store.add_event(
            task_id,
            "isolation",
            event_type,
            summary,
            status=status,
            risk_or_severity=severity,
            metadata=metadata or {},
        )

    def summary(self, task_id: str) -> dict:
        task = self.store.get_task(task_id)
        if task is None:
            raise HistoryDatabaseError(f"Task not found: {task_id}")
        with self.store._connect() as connection:
            counts = {
                table: connection.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE task_id = ?", (task_id,)
                ).fetchone()[0]
                for table in ("plans", "executions", "tool_events", "validations", "reviews", "approvals")
            }
            files = [row[0] for row in connection.execute("SELECT path FROM affected_files WHERE task_id = ? ORDER BY path", (task_id,))]
            symbols = [row[0] for row in connection.execute("SELECT qualified_name FROM affected_symbols WHERE task_id = ? ORDER BY qualified_name", (task_id,))]
        return {"task": task.to_dict(), "counts": counts, "affected_files": files, "affected_symbols": symbols, "timeline": [event.__dict__ if hasattr(event, "__dict__") else {name: getattr(event, name) for name in event.__dataclass_fields__} for event in self.timeline(task_id)]}

    def artifacts(self, task_id: str) -> dict[str, list[dict]]:
        with self.store._connect() as connection:
            return {
                table: [dict(row) for row in connection.execute(f"SELECT * FROM {table} WHERE task_id = ?", (task_id,))]
                for table in ("plans", "executions", "validations", "reviews", "approvals")
            }

    def incidents(
        self, *, subsystem: str | None = None, severity: str | None = None, limit: int = 100
    ) -> tuple[dict, ...]:
        clauses = ["(event_type LIKE '%failed%' OR event_type LIKE '%error%' OR status IN ('failed', 'blocked', 'rolled_back'))"]
        values: list[object] = []
        if subsystem:
            clauses.append("subsystem = ?")
            values.append(subsystem)
        if severity:
            clauses.append("risk_or_severity = ?")
            values.append(severity)
        values.append(max(1, min(limit, 1000)))
        with self.store._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM task_status_events WHERE " + " AND ".join(clauses)
                + " ORDER BY timestamp DESC LIMIT ?",
                values,
            ).fetchall()
        return tuple(dict(row) for row in rows)

    def _identity(self, task_id: str, repository: str, starting_commit: str | None):
        task = self.store.get_task(task_id)
        if task is None:
            raise HistoryDatabaseError(f"Task not found: {task_id}")
        if Path(task.repository).resolve() != Path(repository).resolve():
            raise HistoryDatabaseError("Task/repository identity mismatch")
        if starting_commit is not None and task.starting_commit != starting_commit:
            raise HistoryDatabaseError("Task starting-commit identity mismatch")
        return task


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
