"""Deterministic local SQLite memory with explicit lifecycle authority."""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path


class MemoryKind(StrEnum):
    EPISODIC = "episodic"
    PREFERENCE = "preference"
    FACT = "fact"
    WORKING = "working"


class MemoryState(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    CONFLICTED = "conflicted"
    DELETED = "deleted"


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    memory_id: str
    kind: MemoryKind
    subject: str
    content: str
    provenance: str
    confidence: float
    created_at: str
    updated_at: str
    state: MemoryState
    supersedes: str | None
    expires_at: str | None


def _now() -> str:
    return datetime.now(UTC).isoformat()


class FridayMemoryService:
    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS memories (memory_id TEXT PRIMARY KEY, kind TEXT, subject TEXT, content TEXT, provenance TEXT, confidence REAL, created_at TEXT, updated_at TEXT, state TEXT, supersedes TEXT, expires_at TEXT)"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS memory_subject_active ON memories(subject, state)"
            )

    def _db(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def remember(
        self,
        *,
        kind: MemoryKind,
        subject: str,
        content: str,
        provenance: str,
        confidence: float,
        supersedes: str | None = None,
        expires_at: str | None = None,
    ) -> MemoryRecord:
        if not all(
            isinstance(value, str) and value.strip() for value in (subject, content, provenance)
        ):
            raise ValueError("memory subject, content, and provenance must not be empty")
        if not 0 <= confidence <= 1:
            raise ValueError("memory confidence must be between 0 and 1")
        now, memory_id = _now(), "mem_" + uuid.uuid4().hex
        with self._db() as db:
            if (
                supersedes
                and db.execute(
                    "UPDATE memories SET state=?, updated_at=? WHERE memory_id=? AND state=?",
                    (MemoryState.SUPERSEDED, now, supersedes, MemoryState.ACTIVE),
                ).rowcount
                != 1
            ):
                raise ValueError("superseded memory must be active")
            db.execute(
                "INSERT INTO memories VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    memory_id,
                    kind,
                    subject.strip(),
                    content.strip(),
                    provenance.strip(),
                    confidence,
                    now,
                    now,
                    MemoryState.ACTIVE,
                    supersedes,
                    expires_at,
                ),
            )
        return self.get(memory_id)

    def get(self, memory_id: str) -> MemoryRecord:
        with self._db() as db:
            row = db.execute("SELECT * FROM memories WHERE memory_id=?", (memory_id,)).fetchone()
        if row is None:
            raise KeyError(memory_id)
        return MemoryRecord(
            row[0],
            MemoryKind(row[1]),
            row[2],
            row[3],
            row[4],
            row[5],
            row[6],
            row[7],
            MemoryState(row[8]),
            row[9],
            row[10],
        )

    def recall(self, subject: str, limit: int = 20) -> tuple[MemoryRecord, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("memory recall limit must be between 1 and 100")
        with self._db() as db:
            rows = db.execute(
                "SELECT memory_id FROM memories WHERE subject=? AND state=? AND (expires_at IS NULL OR expires_at>?) ORDER BY confidence DESC, updated_at DESC LIMIT ?",
                (subject, MemoryState.ACTIVE, _now(), limit),
            ).fetchall()
        return tuple(self.get(row[0]) for row in rows)

    def search(self, query: str, limit: int = 20) -> tuple[MemoryRecord, ...]:
        """Deterministic local lexical retrieval before optional semantic ranking."""
        if not query.strip():
            raise ValueError("memory search query must not be empty")
        if not 1 <= limit <= 100:
            raise ValueError("memory search limit must be between 1 and 100")
        pattern = "%" + query.strip().lower() + "%"
        with self._db() as db:
            rows = db.execute(
                "SELECT memory_id FROM memories WHERE state=? AND (expires_at IS NULL OR expires_at>?) AND (lower(subject) LIKE ? OR lower(content) LIKE ?) ORDER BY confidence DESC, updated_at DESC LIMIT ?",
                (MemoryState.ACTIVE, _now(), pattern, pattern, limit),
            ).fetchall()
        return tuple(self.get(row[0]) for row in rows)

    def _state(self, memory_id: str, state: MemoryState) -> None:
        with self._db() as db:
            changed = db.execute(
                "UPDATE memories SET state=?, updated_at=? WHERE memory_id=? AND state=?",
                (state, _now(), memory_id, MemoryState.ACTIVE),
            ).rowcount
        if changed != 1:
            raise ValueError("memory is not active")

    def mark_conflicted(self, memory_id: str) -> None:
        self._state(memory_id, MemoryState.CONFLICTED)

    def forget(self, memory_id: str) -> None:
        self._state(memory_id, MemoryState.DELETED)
