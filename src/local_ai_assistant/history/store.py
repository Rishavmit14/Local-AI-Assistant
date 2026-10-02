"""Transactional SQLite store for local task history."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from local_ai_assistant.execution.history import redact, redact_data

from .errors import HistoryDatabaseError, InvalidStatusTransition
from .migrations import MIGRATIONS, SCHEMA_VERSION
from .models import (
    ALLOWED_TRANSITIONS,
    TaskFilter,
    TaskRecord,
    TaskStatus,
    TimelineEvent,
    utc_now,
)


def _json(value) -> str:
    return json.dumps(redact_data(value), ensure_ascii=False, sort_keys=True)


def execution_implementation_fingerprint() -> str:
    """Identify the execution/recovery implementation behind a failed retry."""
    package_root = Path(__file__).resolve().parents[1]
    relevant = (
        "agent/code_agent.py",
        "execution/loop.py",
        "execution/registry.py",
        "gateway/execution_service.py",
        "gateway/recovery.py",
        "history/store.py",
        "isolation/gitops.py",
        "isolation/worktrees.py",
        "planning/analysis.py",
        "planning/patch_scope.py",
        "validation/repair.py",
        "validation/tests.py",
    )
    digest = hashlib.sha256()
    for relative in relevant:
        path = package_root / relative
        digest.update(relative.encode())
        digest.update(b"\0")
        try:
            digest.update(path.read_bytes())
        except OSError as exc:
            digest.update(f"unavailable:{type(exc).__name__}".encode())
        digest.update(b"\0")
    return digest.hexdigest()


class TaskHistoryStore:
    def __init__(self, path: Path) -> None:
        self.path = path.resolve()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._connect() as connection:
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)"
                )
                rows = connection.execute("SELECT version FROM schema_version").fetchall()
                if len(rows) > 1:
                    raise HistoryDatabaseError("History schema-version table is corrupt")
                row = rows[0] if rows else None
                current = int(row[0]) if row else 0
                if current > SCHEMA_VERSION:
                    raise HistoryDatabaseError(
                        f"History schema {current} is newer than supported {SCHEMA_VERSION}"
                    )
                for version in range(current + 1, SCHEMA_VERSION + 1):
                    connection.execute("BEGIN IMMEDIATE")
                    try:
                        for statement in MIGRATIONS[version]:
                            connection.execute(statement)
                        if row is None and version == 1:
                            connection.execute("INSERT INTO schema_version(version) VALUES (?)", (version,))
                        else:
                            connection.execute("UPDATE schema_version SET version = ?", (version,))
                        connection.commit()
                    except Exception:
                        connection.rollback()
                        raise
                required_tables = {
                    "tasks", "task_status_events", "plans", "executions", "tool_events",
                    "validations", "reviews", "approvals", "affected_files",
                    "affected_symbols", "metrics_summary", "artifact_imports",
                    "external_idempotency",
                    "external_publications", "external_ci_checks",
                    "task_planning_claims",
                    "task_execution_claims",
                    "task_execution_attempts",
                    "rollback_operations",
                }
                actual_tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                event_columns = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(task_status_events)")
                }
                metrics_columns = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(metrics_summary)")
                }
                required_metrics_columns = {
                    "plan_validation_success", "patch_preflight_success",
                    "first_targeted_test_pass", "first_full_suite_pass",
                    "repeated_failures", "review_blocking_findings", "commit_success",
                }
                if (
                    not required_tables <= actual_tables
                    or "sequence" not in event_columns
                    or not required_metrics_columns <= metrics_columns
                ):
                    raise HistoryDatabaseError(
                        "History schema metadata does not match the supported schema"
                    )
                integrity = connection.execute("PRAGMA quick_check").fetchone()[0]
                if integrity != "ok":
                    raise HistoryDatabaseError(f"History database integrity check failed: {integrity}")
        except HistoryDatabaseError:
            raise
        except (sqlite3.DatabaseError, TypeError, ValueError) as exc:
            raise HistoryDatabaseError(f"Cannot initialize history database: {exc}") from exc

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                try:
                    yield connection
                    connection.commit()
                except Exception:
                    connection.rollback()
                    raise
        except sqlite3.DatabaseError as exc:
            raise HistoryDatabaseError(f"History transaction failed: {exc}") from exc

    def claim_planning(self, task_id: str, claim_id: str, *, lease_seconds: int = 3600) -> bool:
        """Atomically admit one bounded planner; a crash recovers after its lease."""
        if not task_id or not claim_id or not 1 <= lease_seconds <= 86_400:
            raise HistoryDatabaseError("Invalid planning claim")
        now = int(time.time())
        with self.transaction() as connection:
            if connection.execute("SELECT 1 FROM tasks WHERE task_id=?", (task_id,)).fetchone() is None:
                raise HistoryDatabaseError(f"Task not found: {task_id}")
            connection.execute(
                "DELETE FROM task_planning_claims WHERE task_id=? AND expires_at <= ?",
                (task_id, now),
            )
            try:
                connection.execute(
                    "INSERT INTO task_planning_claims(task_id, claim_id, claimed_at, expires_at) VALUES(?,?,?,?)",
                    (task_id, claim_id, now, now + lease_seconds),
                )
            except sqlite3.IntegrityError:
                return False
        return True

    def release_planning_claim(self, task_id: str, claim_id: str) -> None:
        """Only the holder may release its task-local planner admission."""
        with self.transaction() as connection:
            connection.execute(
                "DELETE FROM task_planning_claims WHERE task_id=? AND claim_id=?",
                (task_id, claim_id),
            )

    def claim_execution(self, task_id: str, claim_id: str, *, lease_seconds: int = 86_400) -> bool:
        if not task_id or not claim_id or not 1 <= lease_seconds <= 86_400:
            raise HistoryDatabaseError("Invalid execution claim")
        now = int(time.time())
        with self.transaction() as connection:
            if connection.execute("SELECT 1 FROM tasks WHERE task_id=?", (task_id,)).fetchone() is None:
                raise HistoryDatabaseError(f"Task not found: {task_id}")
            connection.execute("DELETE FROM task_execution_claims WHERE task_id=? AND expires_at <= ?", (task_id, now))
            try:
                connection.execute("INSERT INTO task_execution_claims(task_id, claim_id, claimed_at, expires_at) VALUES(?,?,?,?)", (task_id, claim_id, now, now + lease_seconds))
            except sqlite3.IntegrityError:
                return False
        return True

    def release_execution_claim(self, task_id: str, claim_id: str) -> None:
        with self.transaction() as connection:
            connection.execute("DELETE FROM task_execution_claims WHERE task_id=? AND claim_id=?", (task_id, claim_id))

    def create_execution_attempt(self, task_id: str, plan_hash: str, attempt_id: str) -> None:
        now = utc_now()
        with self.transaction() as connection:
            task = connection.execute("SELECT status, plan_hash FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            claim = connection.execute("SELECT 1 FROM task_execution_claims WHERE task_id=? AND claim_id=?", (task_id, attempt_id)).fetchone()
            if task is None or task["status"] != TaskStatus.APPROVED.value or task["plan_hash"] != plan_hash or claim is None:
                raise HistoryDatabaseError("Exact approved execution claim is required")
            connection.execute(
                "INSERT INTO task_execution_attempts VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (attempt_id, task_id, plan_hash, None, "initial", "running", attempt_id, now, now, None, "{}", None),
            )
            self._insert_event(connection, task_id, now, "execution", "execution_attempt_started",
                "Execution attempt admitted for the exact approved plan", artifact_id=attempt_id,
                status="running", metadata={"attempt_id": attempt_id, "plan_hash": plan_hash, "attempt_kind": "initial"})

    def task_claims(self, task_id: str) -> dict[str, dict[str, int] | None]:
        """Read admission lease timestamps without pruning expired claims."""
        with self._connect() as connection:
            result = {}
            for kind, table in (
                ("planning", "task_planning_claims"),
                ("execution", "task_execution_claims"),
            ):
                row = connection.execute(
                    f"SELECT claimed_at, expires_at FROM {table} WHERE task_id=?",
                    (task_id,),
                ).fetchone()
                result[kind] = (
                    {"claimed_at": int(row["claimed_at"]), "expires_at": int(row["expires_at"])}
                    if row else None
                )
        return result

    def begin_recovery_attempt(
        self, task_id: str, plan_hash: str, attempt_id: str, idempotency_key: str,
        *, principal: str, lease_seconds: int = 86_400,
    ) -> tuple[dict, bool]:
        """Atomically bind one exact-plan recovery attempt to the execution claim."""
        if not all((task_id, plan_hash, attempt_id, idempotency_key)) or not 1 <= lease_seconds <= 86_400:
            raise HistoryDatabaseError("Invalid recovery attempt identity")
        now = int(time.time())
        timestamp = utc_now()
        with self.transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM task_execution_attempts WHERE task_id=? AND idempotency_key=?",
                (task_id, idempotency_key),
            ).fetchone()
            if existing is not None:
                return dict(existing), False
            task = connection.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            if task is None or task["status"] != TaskStatus.RECOVERY_REQUIRED.value or task["plan_hash"] != plan_hash:
                raise HistoryDatabaseError("Exact interrupted task is not recoverable")
            if task["approval_state"] != "explicitly_approved":
                raise HistoryDatabaseError("Current exact-plan approval is unavailable")
            approval = connection.execute(
                "SELECT approval_id,state FROM approvals WHERE task_id=? AND plan_hash=? ORDER BY timestamp DESC, approval_id DESC LIMIT 1",
                (task_id, plan_hash),
            ).fetchone()
            if approval is None or approval["state"] != "explicitly_approved":
                raise HistoryDatabaseError("Current exact-plan approval is unavailable")
            connection.execute("DELETE FROM task_execution_claims WHERE task_id=? AND expires_at<=?", (task_id, now))
            try:
                connection.execute(
                    "INSERT INTO task_execution_claims(task_id,claim_id,claimed_at,expires_at) VALUES(?,?,?,?)",
                    (task_id, attempt_id, now, now + lease_seconds),
                )
            except sqlite3.IntegrityError as exc:
                raise HistoryDatabaseError("Task execution is already claimed") from exc
            parent = connection.execute(
                "SELECT attempt_id FROM task_execution_attempts WHERE task_id=? ORDER BY created_at DESC, attempt_id DESC LIMIT 1",
                (task_id,),
            ).fetchone()
            connection.execute(
                "INSERT INTO task_execution_attempts VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (attempt_id, task_id, plan_hash, parent[0] if parent else None, "recovery", "running", idempotency_key, timestamp, timestamp, None, _json({"principal": principal}), None),
            )
            connection.execute(
                "UPDATE tasks SET status=?,updated_at=? WHERE task_id=?",
                (TaskStatus.EXECUTING.value, timestamp, task_id),
            )
            self._insert_event(
                connection, task_id, timestamp, "recovery", "execution_recovery_started",
                "Owner-authorized recovery attempt started for the unchanged approved plan",
                artifact_id=attempt_id, status="executing",
                metadata={"attempt_id": attempt_id, "parent_attempt_id": parent[0] if parent else None,
                    "plan_hash": plan_hash, "approval_id": approval[0], "principal": principal,
                    "decision": "authorized"},
            )
            row = connection.execute("SELECT * FROM task_execution_attempts WHERE attempt_id=?", (attempt_id,)).fetchone()
        return dict(row), True

    def begin_rolled_back_retry(
        self, task_id: str, plan_hash: str, attempt_id: str, idempotency_key: str,
        *, principal: str, workspace_fingerprint: str, worker_state: str, reason: str,
        lease_seconds: int = 86_400,
    ) -> tuple[dict, bool]:
        """Atomically audit stale-claim reconciliation and admit one explicit retry."""
        if (not all((task_id, plan_hash, attempt_id, idempotency_key, principal,
                     workspace_fingerprint, reason)) or worker_state not in {"completed", "failed", "cancelled", "process_replaced"}
                or not 1 <= lease_seconds <= 86_400):
            raise HistoryDatabaseError("Verified terminal worker and workspace are required")
        now, timestamp = int(time.time()), utc_now()
        with self.transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM task_execution_attempts WHERE task_id=? AND idempotency_key=?",
                (task_id, idempotency_key),
            ).fetchone()
            if existing is not None:
                if existing["attempt_kind"] != "retry" or existing["plan_hash"] != plan_hash:
                    raise HistoryDatabaseError("Idempotency key is bound to another attempt")
                return dict(existing), False
            task = connection.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            if (task is None or task["status"] != TaskStatus.ROLLED_BACK.value
                    or task["plan_hash"] != plan_hash
                    or task["approval_state"] != "explicitly_approved"):
                raise HistoryDatabaseError("Exact explicitly approved rolled-back task is required")
            approval = connection.execute(
                "SELECT approval_id,state FROM approvals WHERE task_id=? AND plan_hash=? ORDER BY timestamp DESC,approval_id DESC LIMIT 1",
                (task_id, plan_hash),
            ).fetchone()
            if approval is None or approval["state"] != "explicitly_approved":
                raise HistoryDatabaseError("Current exact-plan approval is unavailable")
            previous = connection.execute(
                "SELECT * FROM task_execution_attempts WHERE task_id=? ORDER BY created_at DESC,attempt_id DESC LIMIT 1",
                (task_id,),
            ).fetchone()
            if previous is None or previous["state"] not in {"completed", "failed"}:
                raise HistoryDatabaseError("Latest execution attempt is not terminal")
            artifact = connection.execute(
                "SELECT status FROM executions WHERE task_id=? AND run_id=? ORDER BY rowid DESC LIMIT 1",
                (task_id, previous["attempt_id"]),
            ).fetchone()
            if artifact is None and previous["state"] == "failed" and previous["artifact_id"] is None:
                prior_attempts = connection.execute(
                    "SELECT attempt_id FROM task_execution_attempts WHERE task_id=? AND attempt_id<>?",
                    (task_id, previous["attempt_id"]),
                ).fetchall()
                prior_ids = {item["attempt_id"] for item in prior_attempts}
                executions = connection.execute(
                    "SELECT artifact_id,run_id,status FROM executions WHERE task_id=?", (task_id,),
                ).fetchall()
                latest_restore = None
                for item in connection.execute(
                    "SELECT event_type,metadata_json FROM task_status_events WHERE task_id=? AND event_type IN ('validation_failure_checkpoint_rollback_completed','failed_retry_setup_reconciled') ORDER BY timestamp DESC",
                    (task_id,),
                ).fetchall():
                    try:
                        metadata = json.loads(item["metadata_json"] or "{}")
                    except (TypeError, ValueError):
                        continue
                    exact_rollback = (
                        item["event_type"] == "validation_failure_checkpoint_rollback_completed"
                        and metadata.get("attempt_id") == previous["attempt_id"]
                    ) or (
                        item["event_type"] == "failed_retry_setup_reconciled"
                        and metadata.get("attempt_id") == previous["attempt_id"]
                        and metadata.get("worker_state") in {"failed", "process_replaced"}
                        and bool(metadata.get("workspace_fingerprint"))
                    )
                    if exact_rollback and metadata.get("plan_hash") == plan_hash:
                        latest_restore = metadata
                        break
                operation = connection.execute(
                    "SELECT task_id,checkpoint_id,plan_hash,state,fingerprint FROM rollback_operations WHERE operation_id=?",
                    (latest_restore.get("operation_id") if latest_restore else "",),
                ).fetchone()
                orphan_tools = connection.execute(
                    "SELECT 1 FROM tool_events WHERE task_id=? AND run_id NOT IN (SELECT artifact_id FROM executions WHERE task_id=? AND status='rolled_back') LIMIT 1",
                    (task_id, task_id),
                ).fetchone()
                if (not latest_restore or not latest_restore.get("checkpoint_id")
                        or operation is None or operation["task_id"] != task_id
                        or operation["checkpoint_id"] != latest_restore["checkpoint_id"]
                        or operation["plan_hash"] != plan_hash or operation["state"] != "succeeded"
                        or not operation["fingerprint"]
                        or any(row["run_id"] not in prior_ids or row["status"] != "rolled_back"
                               for row in executions)
                        or orphan_tools):
                    raise HistoryDatabaseError("Canonical rolled-back execution evidence is required")
            elif artifact is None or artifact["status"] != "rolled_back":
                raise HistoryDatabaseError("Canonical rolled-back execution evidence is required")
            if connection.execute(
                "SELECT 1 FROM executions WHERE task_id=? AND status IN ('complete','committed','merged','no_changes') LIMIT 1",
                (task_id,),
            ).fetchone():
                raise HistoryDatabaseError("A successful terminal execution already exists")
            claims = connection.execute(
                "SELECT claim_id,claimed_at,expires_at FROM task_execution_claims WHERE task_id=?",
                (task_id,),
            ).fetchall()
            if len(claims) > 1:
                raise HistoryDatabaseError("Competing execution claims prevent retry")
            if claims:
                claim = claims[0]
                if claim["claim_id"] != previous["attempt_id"]:
                    raise HistoryDatabaseError("A competing execution claim prevents retry")
                connection.execute("DELETE FROM task_execution_claims WHERE task_id=? AND claim_id=?",
                                   (task_id, previous["attempt_id"]))
                self._insert_event(
                    connection, task_id, timestamp, "recovery", "terminal_execution_claim_reconciled",
                    "Execution claim reconciled after its owning worker and attempt terminated",
                    artifact_id=previous["attempt_id"], status="reconciled",
                    metadata={"attempt_id": previous["attempt_id"], "plan_hash": plan_hash,
                              "claim_expires_at": claim["expires_at"], "worker_state": worker_state,
                              "workspace_fingerprint": workspace_fingerprint,
                              "decision": "reconciled_for_explicit_retry"},
                )
            try:
                connection.execute(
                    "INSERT INTO task_execution_claims(task_id,claim_id,claimed_at,expires_at) VALUES(?,?,?,?)",
                    (task_id, attempt_id, now, now + lease_seconds),
                )
            except sqlite3.IntegrityError as exc:
                raise HistoryDatabaseError("Task execution is already claimed") from exc
            connection.execute(
                "INSERT INTO task_execution_attempts VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (attempt_id, task_id, plan_hash, previous["attempt_id"], "retry", "running",
                 idempotency_key, timestamp, timestamp, None,
                 _json({"principal": principal, "retry_reason": reason[:500],
                        "workspace_fingerprint": workspace_fingerprint,
                        "previous_failure_type": previous["failure_type"]}), None),
            )
            connection.execute("UPDATE tasks SET status=?,updated_at=? WHERE task_id=? AND status=?",
                               (TaskStatus.RETRY_REQUESTED.value, timestamp, task_id, TaskStatus.ROLLED_BACK.value))
            if connection.execute("SELECT changes()").fetchone()[0] != 1:
                raise HistoryDatabaseError("Task changed while retry was being admitted")
            self._insert_event(
                connection, task_id, timestamp, "recovery", "task_retry_requested",
                "Owner explicitly requested a retry: " + reason[:500],
                artifact_id=attempt_id, status=TaskStatus.RETRY_REQUESTED.value,
                metadata={"attempt_id": attempt_id, "parent_attempt_id": previous["attempt_id"],
                          "plan_hash": plan_hash, "approval_id": approval["approval_id"],
                          "principal": principal, "workspace_fingerprint": workspace_fingerprint,
                          "gateway_scope": "REQUEST_EXECUTION",
                          "old_state": TaskStatus.ROLLED_BACK.value,
                          "new_state": TaskStatus.RETRY_REQUESTED.value,
                          "decision": "authorized"},
            )
            connection.execute("UPDATE tasks SET status=?,updated_at=? WHERE task_id=? AND status=?",
                               (TaskStatus.EXECUTING.value, timestamp, task_id, TaskStatus.RETRY_REQUESTED.value))
            if connection.execute("SELECT changes()").fetchone()[0] != 1:
                raise HistoryDatabaseError("Task changed while retry was being admitted")
            self._insert_event(
                connection, task_id, timestamp, "recovery", "task_retry_execution_started",
                "New retry attempt entered the existing isolated execution pipeline",
                artifact_id=attempt_id, status=TaskStatus.EXECUTING.value,
                metadata={"attempt_id": attempt_id, "plan_hash": plan_hash,
                          "old_state": TaskStatus.RETRY_REQUESTED.value,
                          "new_state": TaskStatus.EXECUTING.value},
            )
            row = connection.execute("SELECT * FROM task_execution_attempts WHERE attempt_id=?", (attempt_id,)).fetchone()
        return dict(row), True

    def attach_execution_artifact(self, task_id: str, attempt_id: str, plan_hash: str, artifact_id: str) -> None:
        """Attach artifact identity without racing ahead of the worker's terminal callback."""
        with self.transaction() as connection:
            connection.execute(
                "UPDATE task_execution_attempts SET artifact_id=?,updated_at=? WHERE attempt_id=? AND task_id=? AND plan_hash=? AND state='running'",
                (artifact_id, utc_now(), attempt_id, task_id, plan_hash),
            )

    def mark_recovery_required(self, task_id: str, plan_hash: str, *, worker_state: str, workspace_fingerprint: str, failure_type: str | None = None, idempotency_key: str | None = None) -> dict:
        """Persist an observed interruption only after current DB facts are rechecked."""
        if worker_state not in {"failed", "process_replaced"} or not workspace_fingerprint:
            raise HistoryDatabaseError("Worker failure and verified workspace are required")
        timestamp = utc_now()
        now = int(time.time())
        with self.transaction() as connection:
            task = connection.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            if task is None or task["status"] not in {
                TaskStatus.EXECUTING.value, TaskStatus.VALIDATING.value,
                TaskStatus.RECOVERY_REQUIRED.value,
            } or task["plan_hash"] != plan_hash:
                raise HistoryDatabaseError("Task is not the exact interrupted execution")
            if task["approval_state"] != "explicitly_approved":
                raise HistoryDatabaseError("Exact-plan approval is not valid")
            connection.execute("DELETE FROM task_execution_claims WHERE task_id=? AND expires_at<=?", (task_id, now))
            if connection.execute("SELECT 1 FROM task_execution_claims WHERE task_id=?", (task_id,)).fetchone():
                existing = connection.execute(
                    "SELECT * FROM task_execution_attempts WHERE task_id=? AND idempotency_key=? AND plan_hash=?",
                    (task_id, idempotency_key, plan_hash),
                ).fetchone() if idempotency_key else None
                if existing is not None:
                    return dict(existing)
                raise HistoryDatabaseError("Task execution still has an active claim")
            attempts = connection.execute(
                "SELECT * FROM task_execution_attempts WHERE task_id=? ORDER BY created_at,attempt_id",
                (task_id,),
            ).fetchall()
            latest_attempt = attempts[-1] if attempts else None
            has_history = any(
                connection.execute(f"SELECT 1 FROM {table} WHERE task_id=? LIMIT 1", (task_id,)).fetchone()
                for table in ("executions", "validations", "tool_events")
            )
            if has_history and not self._only_terminal_prior_attempt_history(
                connection, task_id, attempts, latest_attempt
            ):
                raise HistoryDatabaseError("Execution has side effects or terminal evidence requiring inspection")
            if connection.execute("SELECT 1 FROM rollback_operations WHERE task_id=? LIMIT 1", (task_id,)).fetchone():
                raise HistoryDatabaseError("Rollback evidence requires inspection")
            approval = connection.execute(
                "SELECT approval_id,state FROM approvals WHERE task_id=? AND plan_hash=? ORDER BY timestamp DESC, approval_id DESC LIMIT 1",
                (task_id, plan_hash),
            ).fetchone()
            if approval is None or approval["state"] != "explicitly_approved":
                raise HistoryDatabaseError("Exact-plan approval is unavailable")
            attempt = latest_attempt
            if attempt is None:
                attempt_id = "attempt_legacy_" + hashlib.sha256(task_id.encode()).hexdigest()[:20]
                connection.execute(
                    "INSERT INTO task_execution_attempts VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (attempt_id, task_id, plan_hash, None, "interrupted", "interrupted", "legacy-interruption", timestamp, timestamp, failure_type or "WorkerLost", _json({"run_id": "run_" + task_id, "workspace_fingerprint": workspace_fingerprint}), None),
                )
            else:
                attempt_id = attempt["attempt_id"]
            if task["status"] in {TaskStatus.EXECUTING.value, TaskStatus.VALIDATING.value}:
                connection.execute("UPDATE tasks SET status=?,updated_at=? WHERE task_id=?", (TaskStatus.RECOVERY_REQUIRED.value, timestamp, task_id))
                self._insert_event(
                    connection, task_id, timestamp, "recovery", "execution_interruption_detected",
                    "Execution or validation worker failed; clean task workspace and canonical records permit owner recovery review",
                    artifact_id=attempt_id, status=TaskStatus.RECOVERY_REQUIRED.value,
                    metadata={"attempt_id": attempt_id, "plan_hash": plan_hash, "approval_id": approval[0],
                        "worker_state": worker_state, "failure_type": failure_type,
                        "workspace_fingerprint": workspace_fingerprint,
                        "decision": "recovery_required"},
                )
            row = connection.execute("SELECT * FROM task_execution_attempts WHERE attempt_id=?", (attempt_id,)).fetchone()
        return dict(row)

    @staticmethod
    def _only_terminal_prior_attempt_history(connection, task_id, attempts, latest_attempt) -> bool:
        """Permit a clean retry after a failed artifactless attempt with only terminal prior evidence."""
        if latest_attempt is None or latest_attempt["state"] != "failed" or latest_attempt["artifact_id"] is not None:
            return False
        prior = [row for row in attempts if row["attempt_id"] != latest_attempt["attempt_id"]]
        if any(row["state"] not in {"failed", "rolled_back", "cancelled", "interrupted"} for row in prior):
            return False
        prior_ids = {row["attempt_id"] for row in prior}
        executions = connection.execute(
            "SELECT artifact_id,run_id,status FROM executions WHERE task_id=?", (task_id,),
        ).fetchall()
        if any(row["run_id"] not in prior_ids or row["status"] not in {"failed", "rolled_back"} for row in executions):
            return False
        execution_artifacts = {row["artifact_id"] for row in executions}
        for row in connection.execute(
            "SELECT artifact_path,decision FROM validations WHERE task_id=?", (task_id,),
        ).fetchall():
            if Path(row["artifact_path"]).stem not in prior_ids or row["decision"] != "failed":
                return False
        for row in connection.execute(
            "SELECT run_id FROM tool_events WHERE task_id=?", (task_id,),
        ).fetchall():
            if row["run_id"] not in execution_artifacts:
                return False
        return True

    def finish_execution_attempt(self, attempt_id: str, *, failure_type: str | None = None) -> None:
        now = utc_now()
        with self.transaction() as connection:
            row = connection.execute("SELECT * FROM task_execution_attempts WHERE attempt_id=?", (attempt_id,)).fetchone()
            if row is None or row["state"] not in {"running", "interrupted"}:
                return
            task_id = row["task_id"]
            state = "failed" if failure_type else "completed"
            metadata = json.loads(row["metadata_json"] or "{}")
            if failure_type and row["attempt_kind"] == "retry":
                execution = connection.execute("SELECT status FROM executions WHERE task_id=? AND run_id=? ORDER BY rowid DESC LIMIT 1", (task_id, attempt_id)).fetchone()
                tools = [item[0] for item in connection.execute("SELECT tool_name FROM tool_events WHERE task_id=? AND run_id IN (SELECT artifact_id FROM executions WHERE task_id=? AND run_id=?) ORDER BY timestamp", (task_id, task_id, attempt_id))]
                implementation = execution_implementation_fingerprint()
                material = json.dumps({
                    "failure_type": failure_type,
                    "execution_status": execution[0] if execution else None,
                    "tools": tools,
                    "implementation_fingerprint": implementation,
                }, sort_keys=True)
                metadata["implementation_fingerprint"] = implementation
                metadata["failure_signature"] = hashlib.sha256(material.encode()).hexdigest()
            connection.execute("UPDATE task_execution_attempts SET state=?,updated_at=?,failure_type=?,metadata_json=? WHERE attempt_id=?", (state, now, failure_type, _json(metadata), attempt_id))
            connection.execute("DELETE FROM task_execution_claims WHERE task_id=? AND claim_id=?", (task_id, attempt_id))
            self._insert_event(
                connection, task_id, now, "recovery" if row["attempt_kind"] in {"recovery", "retry"} else "execution",
                "execution_attempt_failed" if failure_type else "execution_attempt_completed",
                "Execution worker ended with a recorded failure" if failure_type else "Execution attempt worker completed",
                artifact_id=attempt_id, status=state,
                metadata={"attempt_id": attempt_id, "failure_type": failure_type, "plan_hash": row["plan_hash"]},
            )

    def execution_attempts(self, task_id: str) -> tuple[dict, ...]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM task_execution_attempts WHERE task_id=? ORDER BY created_at, attempt_id", (task_id,)).fetchall()
        return tuple(dict(row) for row in rows)

    def execution_attempt_is_claimed(self, task_id: str, attempt_id: str, plan_hash: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT 1 FROM task_execution_attempts a
                   JOIN task_execution_claims c ON c.task_id=a.task_id AND c.claim_id=a.attempt_id
                   WHERE a.task_id=? AND a.attempt_id=? AND a.plan_hash=?
                     AND a.attempt_kind IN ('recovery','retry') AND a.state='running' AND c.expires_at>?""",
                (task_id, attempt_id, plan_hash, int(time.time())),
            ).fetchone()
        return row is not None

    def execution_attempt_by_key(self, task_id: str, idempotency_key: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT attempt_id,state,attempt_kind,parent_attempt_id,plan_hash FROM task_execution_attempts WHERE task_id=? AND idempotency_key=?",
                (task_id, idempotency_key),
            ).fetchone()
        return dict(row) if row is not None else None

    def task_rollback_operations(self, task_id: str, *, limit: int = 20) -> tuple[dict, ...]:
        """Read bounded rollback ledger facts; omit principal, fingerprint and key."""
        if not 1 <= limit <= 100:
            raise HistoryDatabaseError("Rollback operation limit must be between 1 and 100")
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT operation_id, checkpoint_id, state, created_at, expires_at, result_json "
                "FROM rollback_operations WHERE task_id=? ORDER BY created_at DESC LIMIT ?",
                (task_id, limit),
            ).fetchall()
        return tuple(dict(row) for row in rows)

    def create_task(self, task: TaskRecord) -> TaskRecord:
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO tasks VALUES (
                    :task_id, :original_request, :repository, :starting_commit, :final_commit,
                    :branch, :created_at, :updated_at, :status, :classification, :risk,
                    :confidence, :approval_state, :plan_hash, :final_decision, :outcome,
                    :failure_reason, :human_review_state, :duration_seconds, :summary,
                    :metadata_json
                )""",
                {**task.to_dict(), "metadata_json": _json(task.metadata)},
            )
            self._insert_event(
                connection,
                task.task_id,
                task.created_at,
                "history",
                "task_created",
                "Task created",
                status=task.status.value,
            )
            connection.execute(
                "INSERT INTO metrics_summary(task_id) VALUES (?)", (task.task_id,)
            )
            row = connection.execute(
                "SELECT * FROM tasks WHERE task_id = ?", (task.task_id,)
            ).fetchone()
        return self._task(row)

    def create_external_task(self, task: TaskRecord, *, source: str, event_id: str) -> TaskRecord:
        """Atomically claim an external delivery and create its task.

        The idempotency key and task row share the history transaction, so a
        concurrent/restarted gateway cannot leave an orphan task behind.
        """
        if not source or not event_id or len(source) > 100 or len(event_id) > 256:
            raise HistoryDatabaseError("Invalid external idempotency identity")
        with self.transaction() as connection:
            existing = connection.execute(
                "SELECT task_id FROM external_idempotency WHERE source=? AND event_id=? AND repository=?",
                (source, event_id, task.repository),
            ).fetchone()
            if existing:
                row = connection.execute("SELECT * FROM tasks WHERE task_id=?", (existing[0],)).fetchone()
                return self._task(row)
            connection.execute(
                """INSERT INTO tasks VALUES (:task_id, :original_request, :repository, :starting_commit, :final_commit,
                   :branch, :created_at, :updated_at, :status, :classification, :risk, :confidence,
                   :approval_state, :plan_hash, :final_decision, :outcome, :failure_reason,
                   :human_review_state, :duration_seconds, :summary, :metadata_json)""",
                {**task.to_dict(), "metadata_json": _json(task.metadata)},
            )
            self._insert_event(connection, task.task_id, task.created_at, "history", "task_created", "Task created", status=task.status.value)
            connection.execute("INSERT INTO metrics_summary(task_id) VALUES (?)", (task.task_id,))
            connection.execute(
                "INSERT INTO external_idempotency VALUES (?, ?, ?, ?, ?)",
                (source, event_id, task.repository, task.task_id, task.created_at),
            )
            row = connection.execute("SELECT * FROM tasks WHERE task_id=?", (task.task_id,)).fetchone()
        return self._task(row)

    def get_task(self, task_id: str) -> TaskRecord | None:
        try:
            with self._connect() as connection:
                row = connection.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
                return self._task(row) if row else None
        except sqlite3.DatabaseError as exc:
            raise HistoryDatabaseError(f"Cannot read task history: {exc}") from exc

    def upsert_publication(self, task_id: str, repository_id: str, state: str, **values) -> dict:
        task = self.get_task(task_id)
        if task is None or task.repository != str(Path(values.get("repository", task.repository)).resolve()):
            raise HistoryDatabaseError("Publication task identity mismatch")
        import json as _json_module
        timestamp = utc_now()
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO external_publications(task_id,repository_id,state,branch,commit_sha,pr_id,pr_number,pr_url,last_error,attempts,updated_at,metadata_json)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(task_id) DO UPDATE SET state=excluded.state, branch=excluded.branch, commit_sha=excluded.commit_sha, pr_id=excluded.pr_id, pr_number=excluded.pr_number, pr_url=excluded.pr_url, last_error=excluded.last_error, attempts=excluded.attempts, updated_at=excluded.updated_at, metadata_json=excluded.metadata_json""",
                (task_id, repository_id, state, values.get("branch"), values.get("commit_sha"), values.get("pr_id"), values.get("pr_number"), values.get("pr_url"), redact(values.get("last_error", "")), values.get("attempts", 0), timestamp, _json_module.dumps(redact_data(values.get("metadata", {})), sort_keys=True)),
            )
            row = connection.execute("SELECT * FROM external_publications WHERE task_id=?", (task_id,)).fetchone()
        return dict(row)

    def publication(self, task_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM external_publications WHERE task_id=?", (task_id,)).fetchone()
        return dict(row) if row else None

    def claim_publication(self, task_id: str, repository_id: str, *, branch: str, commit_sha: str) -> int | None:
        """Atomically claim an external publication for one task."""
        with self.transaction() as connection:
            row = connection.execute("SELECT state, repository_id, branch, commit_sha FROM external_publications WHERE task_id=?", (task_id,)).fetchone()
            if row is not None:
                if row["repository_id"] != repository_id or row["branch"] not in {None, branch} or row["commit_sha"] not in {None, commit_sha}:
                    raise HistoryDatabaseError("publication identity mismatch")
                if row["state"] not in {"not_requested", "ready", "retryable_failure", "reconciliation_required"}:
                    return None
            connection.execute(
                """INSERT INTO external_publications(task_id,repository_id,state,branch,commit_sha,attempts,updated_at,metadata_json)
                   VALUES(?,?,?,?,?,1,?,?)
                   ON CONFLICT(task_id) DO UPDATE SET state='pushing', branch=excluded.branch, commit_sha=excluded.commit_sha, attempts=external_publications.attempts+1, updated_at=excluded.updated_at""",
                (task_id, repository_id, "pushing", branch, commit_sha, utc_now(), "{}"),
            )
            value = connection.execute("SELECT attempts FROM external_publications WHERE task_id=?", (task_id,)).fetchone()
        return int(value[0])

    def add_ci_check(self, task_id: str, values: dict) -> dict:
        with self.transaction() as connection:
            connection.execute("INSERT OR REPLACE INTO external_ci_checks VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", tuple(values.get(key, "") for key in ("check_id","task_id","repository_id","external_repository","pr_id","commit_sha","name","status","conclusion","url","timestamp","metadata_json")))
            row = connection.execute("SELECT * FROM external_ci_checks WHERE check_id=?", (values["check_id"],)).fetchone()
        return dict(row)

    def ci_checks(self, task_id: str, limit: int = 100) -> tuple[dict, ...]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM external_ci_checks WHERE task_id=? ORDER BY timestamp DESC LIMIT ?", (task_id, min(max(limit, 1), 1000))).fetchall()
        return tuple(dict(row) for row in rows)

    def artifact_records(self, task_id: str, table: str, limit: int = 100) -> tuple[dict, ...]:
        if table not in {"plans", "executions", "validations", "reviews"}:
            raise HistoryDatabaseError("Unsupported artifact table")
        with self._connect() as connection:
            rows = connection.execute(f"SELECT * FROM {table} WHERE task_id=? ORDER BY rowid DESC LIMIT ?", (task_id, min(max(limit, 1), 100))).fetchall()
        return tuple(dict(row) for row in rows)

    def events_after_rowid(self, rowid: int, limit: int = 200) -> tuple[dict, ...]:
        with self._connect() as connection:
            rows = connection.execute("SELECT rowid, * FROM task_status_events WHERE rowid > ? ORDER BY rowid LIMIT ?", (rowid, min(max(limit, 1), 1000))).fetchall()
        return tuple(dict(row) for row in rows)

    def event_rowid(self, event_id: str) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT rowid FROM task_status_events WHERE event_id=?", (event_id,)).fetchone()
        if row is None:
            raise HistoryDatabaseError("event not found")
        return int(row[0])

    def reconcile_failed_retry_setup(
        self, task_id: str, plan_hash: str, attempt_id: str, *,
        checkpoint_id: str, operation_id: str, workspace_fingerprint: str,
        worker_state: str,
    ) -> TaskRecord:
        """Return an artifactless failed retry to its verified prior rollback."""
        if worker_state not in {"failed", "process_replaced"} or not workspace_fingerprint:
            raise HistoryDatabaseError("Terminated worker and verified workspace are required")
        timestamp, now = utc_now(), int(time.time())
        with self.transaction() as connection:
            task = connection.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            latest = connection.execute(
                "SELECT * FROM task_execution_attempts WHERE task_id=? ORDER BY created_at DESC,attempt_id DESC LIMIT 1",
                (task_id,),
            ).fetchone()
            if (task is None or task["status"] != TaskStatus.EXECUTING.value
                    or task["plan_hash"] != plan_hash
                    or task["approval_state"] != "explicitly_approved"
                    or latest is None or latest["attempt_id"] != attempt_id
                    or latest["plan_hash"] != plan_hash or latest["state"] != "failed"
                    or latest["artifact_id"] is not None or not latest["failure_type"]):
                raise HistoryDatabaseError("Latest exact-plan retry is not an artifactless failed setup")
            connection.execute("DELETE FROM task_execution_claims WHERE task_id=? AND expires_at<=?", (task_id, now))
            if connection.execute("SELECT 1 FROM task_execution_claims WHERE task_id=?", (task_id,)).fetchone():
                raise HistoryDatabaseError("Task still has an active execution claim")
            attempts = connection.execute(
                "SELECT attempt_id,state FROM task_execution_attempts WHERE task_id=? AND attempt_id<>?",
                (task_id, attempt_id),
            ).fetchall()
            prior_ids = {row["attempt_id"] for row in attempts}
            if any(row["state"] not in {"failed", "rolled_back", "cancelled", "interrupted"} for row in attempts):
                raise HistoryDatabaseError("A prior execution attempt is not terminal")
            execution_rows = connection.execute(
                "SELECT artifact_id,run_id,status FROM executions WHERE task_id=?", (task_id,),
            ).fetchall()
            if any(row["run_id"] not in prior_ids or row["status"] != "rolled_back" for row in execution_rows):
                raise HistoryDatabaseError("Prior execution evidence is not exclusively rolled back")
            if connection.execute(
                "SELECT 1 FROM tool_events WHERE task_id=? AND (run_id IS NULL OR run_id NOT IN (SELECT artifact_id FROM executions WHERE task_id=? AND status='rolled_back')) LIMIT 1",
                (task_id, task_id),
            ).fetchone():
                raise HistoryDatabaseError("Unbound tool evidence prevents rollback reconciliation")
            completed = None
            for row in connection.execute(
                "SELECT metadata_json FROM task_status_events WHERE task_id=? AND event_type='validation_failure_checkpoint_rollback_completed' ORDER BY timestamp DESC",
                (task_id,),
            ).fetchall():
                try:
                    metadata = json.loads(row["metadata_json"] or "{}")
                except (TypeError, ValueError):
                    continue
                if metadata.get("plan_hash") == plan_hash and metadata.get("checkpoint_id") == checkpoint_id:
                    completed = metadata
                    break
            operation = connection.execute(
                "SELECT task_id,checkpoint_id,plan_hash,state,fingerprint FROM rollback_operations WHERE operation_id=?",
                (operation_id,),
            ).fetchone()
            if (completed is None or completed.get("attempt_id") not in prior_ids
                    or completed.get("operation_id") != operation_id
                    or operation is None or operation["task_id"] != task_id
                    or operation["checkpoint_id"] != checkpoint_id
                    or operation["plan_hash"] != plan_hash or operation["state"] != "succeeded"
                    or not operation["fingerprint"]):
                raise HistoryDatabaseError("Verified baseline rollback evidence is unavailable")
            connection.execute(
                "UPDATE tasks SET status=?,updated_at=? WHERE task_id=? AND status=? AND plan_hash=?",
                (TaskStatus.ROLLED_BACK.value, timestamp, task_id, TaskStatus.EXECUTING.value, plan_hash),
            )
            if connection.execute("SELECT changes()").fetchone()[0] != 1:
                raise HistoryDatabaseError("Task changed during failed retry reconciliation")
            self._insert_event(
                connection, task_id, timestamp, "recovery", "failed_retry_setup_reconciled",
                "Artifactless retry setup failure reconciled to the verified prior baseline rollback",
                artifact_id=attempt_id, status=TaskStatus.ROLLED_BACK.value,
                metadata={"attempt_id": attempt_id, "plan_hash": plan_hash,
                          "checkpoint_id": checkpoint_id, "operation_id": operation_id,
                          "workspace_fingerprint": workspace_fingerprint,
                          "worker_state": worker_state},
            )
            row = connection.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        return self._task(row)

    def transition(self, task_id: str, status: TaskStatus, reason: str, *, subsystem: str = "history") -> TaskRecord:
        with self.transaction() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            if row is None:
                raise HistoryDatabaseError(f"Task not found: {task_id}")
            current = TaskStatus(row["status"])
            if status not in ALLOWED_TRANSITIONS[current]:
                raise InvalidStatusTransition(f"Invalid task transition: {current.value} -> {status.value}")
            if (
                current in {TaskStatus.AWAITING_APPROVAL, TaskStatus.REAPPROVAL_REQUIRED}
                and status is TaskStatus.APPROVED
            ):
                approval = connection.execute(
                    """SELECT 1 FROM approvals WHERE task_id = ? AND plan_hash = ?
                       AND state IN ('explicitly_approved', 'historical_execution_evidence')
                       ORDER BY timestamp DESC LIMIT 1""",
                    (task_id, row["plan_hash"]),
                ).fetchone()
                if approval is None:
                    raise InvalidStatusTransition(
                        "Exact-plan approval evidence is required before execution"
                    )
            timestamp = utc_now()
            connection.execute(
                "UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ?",
                (status.value, timestamp, task_id),
            )
            if status is TaskStatus.REAPPROVAL_REQUIRED:
                connection.execute(
                    "UPDATE metrics_summary SET reapprovals = reapprovals + 1 WHERE task_id = ?",
                    (task_id,),
                )
            if status is TaskStatus.ROLLED_BACK:
                connection.execute(
                    "UPDATE metrics_summary SET rollbacks = rollbacks + 1 WHERE task_id = ?",
                    (task_id,),
                )
            self._insert_event(
                connection,
                task_id,
                timestamp,
                subsystem,
                "status_changed",
                reason,
                status=status.value,
                metadata={
                    "old_state": current.value,
                    "new_state": status.value,
                    "source": subsystem,
                },
            )
            updated = connection.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        return self._task(updated)

    def finalize_task(
        self,
        task_id: str,
        repository: str,
        status: TaskStatus,
        *,
        final_commit: str | None = None,
        decision: str | None = None,
        outcome: str | None = None,
        failure_reason: str | None = None,
        duration_seconds: float | None = None,
    ) -> TaskRecord:
        """Atomically persist terminal details and the terminal transition."""
        with self.transaction() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            if row is None or Path(row["repository"]).resolve() != Path(repository).resolve():
                raise HistoryDatabaseError("Task/repository identity mismatch")
            current = TaskStatus(row["status"])
            if status not in ALLOWED_TRANSITIONS[current]:
                raise InvalidStatusTransition(
                    f"Invalid task transition: {current.value} -> {status.value}"
                )
            timestamp = utc_now()
            redacted_outcome = redact(outcome) if outcome else outcome
            redacted_failure = redact(failure_reason) if failure_reason else failure_reason
            connection.execute(
                """UPDATE tasks SET status = ?, updated_at = ?, final_commit = ?,
                   final_decision = ?, outcome = ?, failure_reason = ?, duration_seconds = ?
                   WHERE task_id = ?""",
                (
                    status.value, timestamp, final_commit, decision, redacted_outcome,
                    redacted_failure, duration_seconds, task_id,
                ),
            )
            if status is TaskStatus.ROLLED_BACK:
                connection.execute(
                    "UPDATE metrics_summary SET rollbacks = rollbacks + 1 WHERE task_id = ?",
                    (task_id,),
                )
            self._insert_event(
                connection,
                task_id,
                timestamp,
                "history",
                "status_changed",
                redacted_outcome or redacted_failure or status.value,
                status=status.value,
                metadata={
                    "old_state": current.value,
                    "new_state": status.value,
                    "source": "history",
                },
            )
            updated = connection.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        return self._task(updated)

    def update_task(self, task_id: str, repository: str, **changes) -> TaskRecord:
        allowed = {
            "final_commit", "classification", "risk", "confidence", "approval_state",
            "plan_hash", "final_decision", "outcome", "failure_reason",
            "human_review_state", "duration_seconds", "summary", "metadata", "branch",
        }
        if not changes or set(changes) - allowed:
            raise HistoryDatabaseError("Invalid task update fields")
        task = self.get_task(task_id)
        if task is None or str(Path(task.repository).resolve()) != str(Path(repository).resolve()):
            raise HistoryDatabaseError("Task/repository identity mismatch")
        values = dict(changes)
        for name in ("summary", "failure_reason", "outcome"):
            if isinstance(values.get(name), str):
                values[name] = redact(values[name])
        if "metadata" in values:
            values["metadata_json"] = _json(values.pop("metadata"))
        values["updated_at"] = utc_now()
        assignments = ", ".join(f"{name} = ?" for name in values)
        with self.transaction() as connection:
            connection.execute(
                f"UPDATE tasks SET {assignments} WHERE task_id = ?",  # noqa: S608 - fixed allowlist
                (*values.values(), task_id),
            )
            row = connection.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        return self._task(row)

    def record_reviewed_task_commit(
        self, task_id: str, repository: str, plan_hash: str,
        attempt_id: str, commit_sha: str,
    ) -> TaskRecord:
        """Bind a reviewed isolated commit to the exact completed task once."""
        if not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
            raise HistoryDatabaseError("Promoted commit must be a full Git SHA")
        with self.transaction() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            if (row is None or str(Path(row["repository"]).resolve()) != str(Path(repository).resolve())
                    or row["status"] != TaskStatus.SUCCEEDED.value or row["plan_hash"] != plan_hash):
                raise HistoryDatabaseError("Reviewed task identity or lifecycle changed")
            if row["final_commit"]:
                if row["final_commit"] != commit_sha:
                    raise HistoryDatabaseError("Task is bound to a different commit")
                return self._task(row)
            attempt = connection.execute(
                "SELECT state,artifact_id FROM task_execution_attempts WHERE task_id=? AND attempt_id=? AND plan_hash=?",
                (task_id, attempt_id, plan_hash),
            ).fetchone()
            if attempt is None or attempt["state"] != "completed" or not attempt["artifact_id"]:
                raise HistoryDatabaseError("Completed execution attempt is unavailable")
            timestamp = utc_now()
            connection.execute(
                "UPDATE tasks SET final_commit=?,updated_at=?,outcome=? WHERE task_id=? AND final_commit IS NULL",
                (commit_sha, timestamp, "Reviewed isolated task commit recorded.", task_id),
            )
            self._insert_event(
                connection, task_id, timestamp, "promotion", "reviewed_commit_recorded",
                "Reviewed isolated task commit recorded", artifact_id=attempt["artifact_id"],
                status="succeeded", metadata={"attempt_id": attempt_id, "commit_sha": commit_sha},
            )
            updated = connection.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        return self._task(updated)

    def add_event(
        self,
        task_id: str,
        subsystem: str,
        event_type: str,
        summary: str,
        **details,
    ) -> TimelineEvent:
        timestamp = details.pop("timestamp", utc_now())
        with self.transaction() as connection:
            if not connection.execute("SELECT 1 FROM tasks WHERE task_id = ?", (task_id,)).fetchone():
                raise HistoryDatabaseError(f"Task not found: {task_id}")
            return self._insert_event(
                connection, task_id, timestamp, subsystem, event_type, summary, **details
            )

    def timeline(self, task_id: str) -> tuple[TimelineEvent, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM task_status_events WHERE task_id = ?
                   ORDER BY timestamp, sequence, event_id""",
                (task_id,),
            ).fetchall()
        return tuple(self._event(row) for row in rows)

    def approvals_for(self, task_id: str, plan_hash: str) -> tuple[dict, ...]:
        """Return exact-plan approval evidence in canonical order."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT approval_id, task_id, plan_hash, state, timestamp, actor, reason "
                "FROM approvals WHERE task_id=? AND plan_hash=? ORDER BY timestamp, approval_id",
                (task_id, plan_hash),
            ).fetchall()
        return tuple(dict(row) for row in rows)

    def list_tasks(self, filters: TaskFilter | None = None) -> tuple[TaskRecord, ...]:
        filters = filters or TaskFilter()
        clauses: list[str] = []
        values: list[object] = []
        for column, value in (
            ("t.task_id", filters.task_id), ("t.repository", filters.repository),
            ("t.branch", filters.branch), ("t.status", filters.status),
            ("t.classification", filters.classification), ("t.risk", filters.risk),
            ("t.outcome", filters.outcome),
        ):
            if value:
                clauses.append(f"{column} = ?")
                values.append(value)
        if filters.date_from:
            clauses.append("t.created_at >= ?")
            values.append(filters.date_from)
        if filters.date_to:
            clauses.append("t.created_at <= ?")
            values.append(filters.date_to)
        if filters.text:
            clauses.append("(t.original_request LIKE ? OR t.summary LIKE ?)")
            values.extend((f"%{filters.text}%", f"%{filters.text}%"))
        joins = ""
        for table, alias, condition, value in (
            ("affected_files", "f", "f.path = ?", filters.affected_file),
            ("affected_symbols", "s", "(s.symbol_id = ? OR s.qualified_name = ?)", filters.affected_symbol),
        ):
            if value:
                joins += f" JOIN {table} {alias} ON {alias}.task_id = t.task_id"
                clauses.append(condition)
                values.extend((value, value) if alias == "s" else (value,))
        if filters.language:
            joins += " LEFT JOIN affected_files lf ON lf.task_id = t.task_id LEFT JOIN affected_symbols ls ON ls.task_id = t.task_id"
            clauses.append("(lf.language = ? OR ls.language = ?)")
            values.extend((filters.language, filters.language))
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        values.append(max(1, min(filters.limit, 1000)))
        query = f"SELECT DISTINCT t.* FROM tasks t{joins}{where} ORDER BY t.created_at DESC LIMIT ?"
        try:
            with self._connect() as connection:
                rows = connection.execute(query, values).fetchall()
            return tuple(self._task(row) for row in rows)
        except sqlite3.DatabaseError as exc:
            raise HistoryDatabaseError(f"Task search failed: {exc}") from exc

    def attach_artifact(
        self,
        table: str,
        task_id: str,
        artifact_id: str,
        path: str,
        digest: str,
        values: dict,
    ) -> bool:
        specs = {
            "plans": ("version, plan_hash, created_at", (values.get("version", 1), values.get("plan_hash"), values.get("created_at", utc_now()))),
            "executions": ("run_id, status, duration_seconds, repairs, replans, final_commit", (values.get("run_id", artifact_id), values.get("status"), values.get("duration_seconds"), values.get("repairs", 0), values.get("replans", 0), values.get("final_commit"))),
            "validations": ("validation_id, decision, duration_seconds, required_passed, failure_count, tests_run", (values.get("validation_id"), values.get("decision"), values.get("duration_seconds"), values.get("required_passed"), values.get("failure_count", 0), values.get("tests_run", 0))),
            "reviews": ("review_id, blocking_findings, security_findings, model_assisted", (values.get("review_id"), values.get("blocking_findings", 0), values.get("security_findings", 0), values.get("model_assisted", 0))),
        }
        if table not in specs:
            raise HistoryDatabaseError(f"Unsupported artifact table: {table}")
        columns, specific = specs[table]
        placeholders = ", ".join("?" for _ in specific)
        try:
            with self.transaction() as connection:
                before = connection.total_changes
                connection.execute(
                    f"INSERT OR IGNORE INTO {table} (artifact_id, task_id, artifact_path, artifact_hash, {columns}, metadata_json) VALUES (?, ?, ?, ?, {placeholders}, ?)",
                    (artifact_id, task_id, path, digest, *specific, _json(values.get("metadata", {}))),
                )
                return connection.total_changes > before
        except HistoryDatabaseError:
            raise

    def add_affected_file(self, task_id: str, path: str, role: str, language=None, change_type=None) -> None:
        with self.transaction() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO affected_files VALUES (?, ?, ?, ?, ?)",
                (task_id, path, role, language, change_type),
            )

    def add_affected_symbol(self, task_id: str, symbol_id: str, qualified_name: str | None, path: str | None, language: str | None, role: str) -> None:
        with self.transaction() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO affected_symbols VALUES (?, ?, ?, ?, ?, ?)",
                (task_id, symbol_id, qualified_name, path, language, role),
            )

    def status(self) -> dict:
        self.initialize()
        with self._connect() as connection:
            version = connection.execute("SELECT version FROM schema_version").fetchone()[0]
            tasks = connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            integrity = connection.execute("PRAGMA quick_check").fetchone()[0]
        return {"path": str(self.path), "schema_version": version, "tasks": tasks, "integrity": integrity, "size_bytes": self.path.stat().st_size}

    def vacuum(self) -> None:
        with self._connect() as connection:
            connection.execute("VACUUM")

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 5000")
            connection.execute("PRAGMA journal_mode = WAL")
            yield connection
        finally:
            connection.close()

    @staticmethod
    def _task(row: sqlite3.Row) -> TaskRecord:
        return TaskRecord(
            **{key: row[key] for key in TaskRecord.__dataclass_fields__ if key not in {"status", "metadata"}},
            status=TaskStatus(row["status"]),
            metadata=json.loads(row["metadata_json"]),
        )

    @staticmethod
    def _event(row: sqlite3.Row) -> TimelineEvent:
        return TimelineEvent(
            row["event_id"], row["task_id"], row["timestamp"], row["subsystem"],
            row["event_type"], row["summary"], row["artifact_id"], row["artifact_path"],
            row["status"], row["risk_or_severity"], json.loads(row["metadata_json"]),
        )

    @staticmethod
    def _insert_event(connection, task_id, timestamp, subsystem, event_type, summary, *, artifact_id=None, artifact_path=None, status=None, risk_or_severity=None, metadata=None):
        sequence = connection.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 FROM task_status_events WHERE task_id = ?",
            (task_id,),
        ).fetchone()[0]
        seed = "\0".join((task_id, timestamp, subsystem, event_type, summary, str(sequence)))
        event_id = "evt_" + hashlib.sha256(seed.encode()).hexdigest()[:20]
        safe_metadata = json.loads(_json(metadata or {}))
        connection.execute(
            """INSERT INTO task_status_events
               (event_id, task_id, timestamp, subsystem, event_type, summary,
                artifact_id, artifact_path, status, risk_or_severity, metadata_json, sequence)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event_id, task_id, timestamp, subsystem, event_type, redact(summary),
                artifact_id, artifact_path, status, risk_or_severity,
                json.dumps(safe_metadata, ensure_ascii=False, sort_keys=True), sequence,
            ),
        )
        return TimelineEvent(
            event_id, task_id, timestamp, subsystem, event_type, redact(summary), artifact_id,
            artifact_path, status, risk_or_severity, safe_metadata,
        )
