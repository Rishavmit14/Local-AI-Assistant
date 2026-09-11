"""Durable objective lifecycle; it intentionally does not execute tools."""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class Objective:
    objective_id: str
    text: str
    state: str
    created_at: str
    updated_at: str
    plan_hash: str | None = None
    task_id: str | None = None
    task_state: str | None = None


class ObjectiveService:
    """Persist bounded owner objectives before planning or execution begins."""

    def __init__(
        self,
        database: Path,
        *,
        plan_hash_for_task: Callable[[str], str | None] | None = None,
        create_task_for_objective: Callable[[str, str], str] | None = None,
        request_plan_for_task: Callable[[str], None] | None = None,
        cancel_task: Callable[[str], None] | None = None,
        task_state_for_task: Callable[[str], str | None] | None = None,
    ) -> None:
        self.database = database.resolve()
        self.plan_hash_for_task = plan_hash_for_task
        self.create_task_for_objective = create_task_for_objective
        self.request_plan_for_task = request_plan_for_task
        self.cancel_task = cancel_task
        self.task_state_for_task = task_state_for_task

    def _db(self) -> sqlite3.Connection:
        self.database.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.database)
        db.execute("CREATE TABLE IF NOT EXISTS objectives (objective_id TEXT PRIMARY KEY, text TEXT NOT NULL, state TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, plan_hash TEXT, task_id TEXT)")
        columns = {row[1] for row in db.execute("PRAGMA table_info(objectives)")}
        if "plan_hash" not in columns:
            db.execute("ALTER TABLE objectives ADD COLUMN plan_hash TEXT")
        if "task_id" not in columns:
            db.execute("ALTER TABLE objectives ADD COLUMN task_id TEXT")
        return db

    def create(self, text: str) -> Objective:
        text = text.strip()
        if not text or len(text) > 4000:
            raise ValueError("objective text must be between 1 and 4000 characters")
        now = datetime.now(UTC).isoformat()
        item = Objective(uuid4().hex, text, "created", now, now)
        with self._db() as db:
            db.execute("INSERT INTO objectives VALUES(?,?,?,?,?,?,?)", (item.objective_id, item.text, item.state, item.created_at, item.updated_at, item.plan_hash, item.task_id))
        return item

    def resume(self, objective_id: str) -> Objective:
        item = self.get(objective_id)
        if item.state == "cancelled":
            raise ValueError("cancelled objective cannot resume")
        return self._transition(objective_id, "planning")

    def cancel(self, objective_id: str) -> Objective:
        item = self.get(objective_id)
        if item.state == "completed":
            raise ValueError("completed objective cannot cancel")
        if item.task_id is not None:
            if self.cancel_task is None:
                raise ValueError("canonical task cancellation is unavailable")
            self.cancel_task(item.task_id)
        return self._transition(objective_id, "cancelled")

    def bind_plan(self, objective_id: str, task_id: str) -> Objective:
        if not re.fullmatch(r"task_[a-f0-9]{20}", task_id):
            raise ValueError("canonical planned task ID is required")
        if self.plan_hash_for_task is None:
            raise ValueError("canonical task history is unavailable")
        plan_hash = self.plan_hash_for_task(task_id)
        if not isinstance(plan_hash, str) or not re.fullmatch(r"[a-f0-9]{64}", plan_hash):
            raise ValueError("task has no canonical plan ready for binding")
        item = self.get(objective_id)
        if item.state == "cancelled":
            raise ValueError("cancelled objective cannot bind a plan")
        if item.task_id is not None and item.task_id != task_id:
            raise ValueError("objective is already bound to a different canonical plan")
        if item.plan_hash is not None and item.plan_hash != plan_hash:
            raise ValueError("objective is already bound to a different canonical plan")
        now = datetime.now(UTC).isoformat()
        with self._db() as db:
            db.execute("UPDATE objectives SET state='planned', plan_hash=?, task_id=?, updated_at=? WHERE objective_id=?", (plan_hash, task_id, now, objective_id))
        return self.get(objective_id)

    def request_plan(self, objective_id: str, repository_id: str) -> Objective:
        """Request a plan through the configured canonical task boundary only."""
        item = self.get(objective_id)
        if item.state != "planning":
            raise ValueError("objective must be planning before it can request a plan")
        if self.create_task_for_objective is None or self.request_plan_for_task is None:
            raise RuntimeError("canonical planner is unavailable")
        task_id = item.task_id
        if task_id is None:
            task_id = self.create_task_for_objective(item.text, repository_id)
            if not re.fullmatch(r"task_[a-f0-9]{20}", task_id):
                raise ValueError("canonical planner returned an invalid task ID")
            now = datetime.now(UTC).isoformat()
            with self._db() as db:
                db.execute(
                    "UPDATE objectives SET task_id=?, updated_at=? WHERE objective_id=? AND task_id IS NULL",
                    (task_id, now, objective_id),
                )
            item = self.get(objective_id)
            if item.task_id != task_id:
                raise ValueError("objective planning task changed concurrently")
        self.request_plan_for_task(task_id)
        return self.bind_plan(objective_id, task_id)

    def get(self, objective_id: str) -> Objective:
        with self._db() as db:
            row = db.execute("SELECT objective_id, text, state, created_at, updated_at, plan_hash, task_id FROM objectives WHERE objective_id=?", (objective_id,)).fetchone()
        if row is None:
            raise ValueError("objective is unavailable")
        return self._project(Objective(*row))

    def recent(self, limit: int = 20) -> tuple[Objective, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("objective limit must be between 1 and 100")
        with self._db() as db:
            rows = db.execute(
                "SELECT objective_id, text, state, created_at, updated_at, plan_hash, task_id "
                "FROM objectives ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return tuple(self._project(Objective(*row)) for row in rows)

    def _project(self, item: Objective) -> Objective:
        task_state = (
            self.task_state_for_task(item.task_id)
            if item.task_id is not None and self.task_state_for_task is not None
            else None
        )
        return Objective(
            item.objective_id,
            item.text,
            item.state,
            item.created_at,
            item.updated_at,
            item.plan_hash,
            item.task_id,
            task_state,
        )

    def _transition(self, objective_id: str, state: str) -> Objective:
        now = datetime.now(UTC).isoformat()
        with self._db() as db:
            db.execute("UPDATE objectives SET state=?, updated_at=? WHERE objective_id=?", (state, now, objective_id))
        return self.get(objective_id)
