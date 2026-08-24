"""Transactional SQLite store for local task history."""

from __future__ import annotations

import hashlib
import json
import sqlite3
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
                if not required_tables <= actual_tables or "sequence" not in event_columns:
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
            "human_review_state", "duration_seconds", "summary", "metadata",
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

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

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
