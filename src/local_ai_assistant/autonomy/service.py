"""Durable objective lifecycle; it intentionally does not execute tools."""

from __future__ import annotations

import sqlite3
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


class ObjectiveService:
    """Persist bounded owner objectives before planning or execution begins."""

    def __init__(self, database: Path) -> None:
        self.database = database.resolve()

    def _db(self) -> sqlite3.Connection:
        self.database.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.database)
        db.execute("CREATE TABLE IF NOT EXISTS objectives (objective_id TEXT PRIMARY KEY, text TEXT NOT NULL, state TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
        return db

    def create(self, text: str) -> Objective:
        text = text.strip()
        if not text or len(text) > 4000:
            raise ValueError("objective text must be between 1 and 4000 characters")
        now = datetime.now(UTC).isoformat()
        item = Objective(uuid4().hex, text, "created", now, now)
        with self._db() as db:
            db.execute("INSERT INTO objectives VALUES(?,?,?,?,?)", (item.objective_id, item.text, item.state, item.created_at, item.updated_at))
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
        return self._transition(objective_id, "cancelled")

    def get(self, objective_id: str) -> Objective:
        with self._db() as db:
            row = db.execute("SELECT objective_id, text, state, created_at, updated_at FROM objectives WHERE objective_id=?", (objective_id,)).fetchone()
        if row is None:
            raise ValueError("objective is unavailable")
        return Objective(*row)

    def _transition(self, objective_id: str, state: str) -> Objective:
        now = datetime.now(UTC).isoformat()
        with self._db() as db:
            db.execute("UPDATE objectives SET state=?, updated_at=? WHERE objective_id=?", (state, now, objective_id))
        return self.get(objective_id)
