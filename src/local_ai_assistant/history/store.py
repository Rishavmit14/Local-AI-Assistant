"""Transactional SQLite store for local task history."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from local_ai_assistant.execution.history import redact

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
    return redact(json.dumps(value, ensure_ascii=False, sort_keys=True))


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
                row = connection.execute("SELECT version FROM schema_version").fetchone()
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
                integrity = connection.execute("PRAGMA quick_check").fetchone()[0]
                if integrity != "ok":
                    raise HistoryDatabaseError(f"History database integrity check failed: {integrity}")
        except HistoryDatabaseError:
            raise
        except sqlite3.DatabaseError as exc:
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
        return task

    def get_task(self, task_id: str) -> TaskRecord | None:
        try:
            with self._connect() as connection:
                row = connection.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
                return self._task(row) if row else None
        except sqlite3.DatabaseError as exc:
            raise HistoryDatabaseError(f"Cannot read task history: {exc}") from exc

    def transition(self, task_id: str, status: TaskStatus, reason: str, *, subsystem: str = "history") -> TaskRecord:
        with self.transaction() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            if row is None:
                raise HistoryDatabaseError(f"Task not found: {task_id}")
            current = TaskStatus(row["status"])
            if status not in ALLOWED_TRANSITIONS[current]:
                raise InvalidStatusTransition(f"Invalid task transition: {current.value} -> {status.value}")
            timestamp = utc_now()
            connection.execute(
                "UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ?",
                (status.value, timestamp, task_id),
            )
            self._insert_event(
                connection, task_id, timestamp, subsystem, "status_changed", reason, status=status.value
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
                "SELECT * FROM task_status_events WHERE task_id = ? ORDER BY timestamp, event_id",
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
            "SELECT COUNT(*) FROM task_status_events WHERE task_id = ?", (task_id,)
        ).fetchone()[0]
        seed = "\0".join((task_id, timestamp, subsystem, event_type, summary, str(sequence)))
        event_id = "evt_" + hashlib.sha256(seed.encode()).hexdigest()[:20]
        connection.execute(
            "INSERT INTO task_status_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (event_id, task_id, timestamp, subsystem, event_type, redact(summary), artifact_id, artifact_path, status, risk_or_severity, _json(metadata or {})),
        )
        return TimelineEvent(event_id, task_id, timestamp, subsystem, event_type, redact(summary), artifact_id, artifact_path, status, risk_or_severity, metadata or {})
