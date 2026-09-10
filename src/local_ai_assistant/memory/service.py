"""Local persistent memory with explicit lifecycle and retrieval authority.

The SQLite database is durable authority. Embeddings are a rebuildable local
cache, never a reason to lose a memory record.
"""

from __future__ import annotations

import math
import sqlite3
import struct
import uuid
from collections.abc import Callable, Sequence
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
    EXPIRED = "expired"


class RelationshipState(StrEnum):
    ACTIVE = "active"
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


@dataclass(frozen=True, slots=True)
class MemoryRelationship:
    relationship_id: str
    source_subject: str
    relationship: str
    target_subject: str
    provenance: str
    confidence: float
    created_at: str
    updated_at: str
    state: RelationshipState


@dataclass(frozen=True, slots=True)
class RetentionResult:
    expired: int
    bounded_working: int


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _normalize(value: str, field: str) -> str:
    if not isinstance(value, str) or not (normalized := value.strip()):
        raise ValueError(f"memory {field} must not be empty")
    return normalized


def _vector_bytes(vector: Sequence[float]) -> bytes:
    return struct.pack(f"!{len(vector)}f", *vector)


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    denominator = math.sqrt(sum(item * item for item in left)) * math.sqrt(
        sum(item * item for item in right)
    )
    return sum(a * b for a, b in zip(left, right, strict=True)) / denominator if denominator else 0.0


class FridayMemoryService:
    """Owner-controlled local memory; model output has no mutation path here."""

    def __init__(
        self,
        path: Path,
        *,
        embed: Callable[[Sequence[str]], Sequence[Sequence[float]]] | None = None,
        embedding_model: str = "BAAI/bge-small-en-v1.5",
        embedding_device: str = "cpu",
        working_subject_limit: int = 50,
    ) -> None:
        if working_subject_limit < 1:
            raise ValueError("working_subject_limit must be at least 1")
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._embed = embed
        self.embedding_model = embedding_model
        self.embedding_device = embedding_device
        self.working_subject_limit = working_subject_limit
        with self._db() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    memory_id TEXT PRIMARY KEY, kind TEXT NOT NULL, subject TEXT NOT NULL,
                    content TEXT NOT NULL, provenance TEXT NOT NULL, confidence REAL NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, state TEXT NOT NULL,
                    supersedes TEXT, expires_at TEXT
                );
                CREATE INDEX IF NOT EXISTS memory_subject_active
                    ON memories(subject, state, updated_at DESC);
                CREATE INDEX IF NOT EXISTS memory_active_expiry
                    ON memories(state, expires_at);
                CREATE TABLE IF NOT EXISTS memory_embeddings (
                    memory_id TEXT PRIMARY KEY REFERENCES memories(memory_id),
                    model TEXT NOT NULL, dimension INTEGER NOT NULL, vector BLOB NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS memory_relationships (
                    relationship_id TEXT PRIMARY KEY, source_subject TEXT NOT NULL,
                    relationship TEXT NOT NULL, target_subject TEXT NOT NULL,
                    provenance TEXT NOT NULL, confidence REAL NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, state TEXT NOT NULL,
                    UNIQUE(source_subject, relationship, target_subject, state)
                );
                CREATE INDEX IF NOT EXISTS memory_relationship_subject_active
                    ON memory_relationships(source_subject, target_subject, state);
                """
            )

    def _db(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path)
        db.execute("PRAGMA foreign_keys = ON")
        return db

    @staticmethod
    def _record(row: tuple) -> MemoryRecord:
        return MemoryRecord(
            row[0], MemoryKind(row[1]), row[2], row[3], row[4], row[5], row[6], row[7],
            MemoryState(row[8]), row[9], row[10],
        )

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
        subject, content, provenance = (
            _normalize(subject, "subject"),
            _normalize(content, "content"),
            _normalize(provenance, "provenance"),
        )
        if not 0 <= confidence <= 1:
            raise ValueError("memory confidence must be between 0 and 1")
        now, memory_id = _now(), "mem_" + uuid.uuid4().hex
        with self._db() as db:
            if supersedes and db.execute(
                "UPDATE memories SET state=?, updated_at=? WHERE memory_id=? AND state=?",
                (MemoryState.SUPERSEDED, now, supersedes, MemoryState.ACTIVE),
            ).rowcount != 1:
                raise ValueError("superseded memory must be active")
            db.execute(
                "INSERT INTO memories VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    memory_id, kind, subject, content, provenance, confidence, now, now,
                    MemoryState.ACTIVE, supersedes, expires_at,
                ),
            )
        self.enforce_retention()
        return self.get(memory_id)

    def get(self, memory_id: str) -> MemoryRecord:
        with self._db() as db:
            row = db.execute("SELECT * FROM memories WHERE memory_id=?", (memory_id,)).fetchone()
        if row is None:
            raise KeyError(memory_id)
        return self._record(row)

    def recall(self, subject: str, limit: int = 20) -> tuple[MemoryRecord, ...]:
        subject = _normalize(subject, "subject")
        self._limit(limit)
        self.enforce_retention()
        with self._db() as db:
            rows = db.execute(
                "SELECT * FROM memories WHERE subject=? AND state=? "
                "ORDER BY confidence DESC, updated_at DESC LIMIT ?",
                (subject, MemoryState.ACTIVE, limit),
            ).fetchall()
        return tuple(self._record(row) for row in rows)

    def search(self, query: str, limit: int = 20) -> tuple[MemoryRecord, ...]:
        """Return bounded hybrid local retrieval, safely falling back to lexical."""
        query = _normalize(query, "search query")
        self._limit(limit)
        self.enforce_retention()
        with self._db() as db:
            rows = db.execute(
                "SELECT * FROM memories WHERE state=? "
                "ORDER BY confidence DESC, updated_at DESC LIMIT 500",
                (MemoryState.ACTIVE,),
            ).fetchall()
        records = [self._record(row) for row in rows]
        lexical = self._lexical_scores(query, records)
        semantic = self._semantic_scores(query, records)
        scored = [
            (
                0.65 * semantic.get(record.memory_id, 0.0)
                + 0.25 * lexical.get(record.memory_id, 0.0)
                + 0.10 * record.confidence,
                record,
            )
            for record in records
            if record.memory_id in lexical or record.memory_id in semantic
        ]
        return tuple(
            record
            for _score, record in sorted(
                scored, key=lambda item: (item[0], item[1].updated_at), reverse=True
            )[:limit]
        )

    def _lexical_scores(
        self, query: str, records: Sequence[MemoryRecord]
    ) -> dict[str, float]:
        terms = {term for term in query.lower().split() if len(term) > 1}
        if not terms:
            terms = {query.lower()}
        scores: dict[str, float] = {}
        for record in records:
            haystack = f"{record.subject} {record.content}".lower()
            matched = sum(term in haystack for term in terms)
            if matched:
                scores[record.memory_id] = matched / len(terms)
        return scores

    def _semantic_scores(
        self, query: str, records: Sequence[MemoryRecord]
    ) -> dict[str, float]:
        if not records:
            return {}
        cached: dict[str, tuple[float, ...]] = {}
        with self._db() as db:
            rows = db.execute(
                "SELECT memory_id, dimension, vector FROM memory_embeddings WHERE model=?",
                (self.embedding_model,),
            ).fetchall()
        for memory_id, dimension, vector in rows:
            cached[memory_id] = struct.unpack(f"!{dimension}f", vector)
        missing = [record for record in records if record.memory_id not in cached]
        try:
            vectors = self._encode(
                [query, *(f"{item.subject}\n{item.content}" for item in missing)]
            )
        except (ImportError, KeyError, OSError, RuntimeError, ValueError):
            return {}
        if len(vectors) != len(missing) + 1 or not vectors[0]:
            return {}
        query_vector = vectors[0]
        with self._db() as db:
            for record, vector in zip(missing, vectors[1:], strict=True):
                if len(vector) != len(query_vector):
                    return {}
                db.execute(
                    "INSERT OR REPLACE INTO memory_embeddings VALUES(?,?,?,?,?)",
                    (record.memory_id, self.embedding_model, len(vector), _vector_bytes(vector), _now()),
                )
                cached[record.memory_id] = vector
        scores: dict[str, float] = {}
        for record in records:
            vector = cached[record.memory_id]
            if len(vector) != len(query_vector):
                continue
            scores[record.memory_id] = max(0.0, _cosine(query_vector, vector))
        return scores

    def _encode(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        if self._embed is None:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(
                self.embedding_model, device=self.embedding_device, local_files_only=True
            )
            self._embed = lambda values: model.encode(  # noqa: E731
                list(values), normalize_embeddings=True, convert_to_numpy=True
            )
        return tuple(tuple(float(value) for value in vector) for vector in self._embed(texts))

    @staticmethod
    def _limit(limit: int) -> None:
        if not 1 <= limit <= 100:
            raise ValueError("memory recall limit must be between 1 and 100")

    def enforce_retention(self) -> RetentionResult:
        """Apply expiry and the per-subject working-memory bound deterministically."""
        now = _now()
        with self._db() as db:
            expired = db.execute(
                "UPDATE memories SET state=?, updated_at=? "
                "WHERE state=? AND expires_at IS NOT NULL AND expires_at<=?",
                (MemoryState.EXPIRED, now, MemoryState.ACTIVE, now),
            ).rowcount
            subjects = db.execute(
                "SELECT DISTINCT subject FROM memories WHERE kind=? AND state=?",
                (MemoryKind.WORKING, MemoryState.ACTIVE),
            ).fetchall()
            bounded = 0
            for (subject,) in subjects:
                rows = db.execute(
                    "SELECT memory_id FROM memories WHERE kind=? AND subject=? AND state=? "
                    "ORDER BY updated_at DESC, memory_id DESC LIMIT -1 OFFSET ?",
                    (MemoryKind.WORKING, subject, MemoryState.ACTIVE, self.working_subject_limit),
                ).fetchall()
                for (memory_id,) in rows:
                    bounded += db.execute(
                        "UPDATE memories SET state=?, updated_at=? "
                        "WHERE memory_id=? AND state=?",
                        (MemoryState.EXPIRED, now, memory_id, MemoryState.ACTIVE),
                    ).rowcount
        return RetentionResult(expired=expired, bounded_working=bounded)

    def relate(
        self,
        *,
        source_subject: str,
        relationship: str,
        target_subject: str,
        provenance: str,
        confidence: float,
    ) -> MemoryRelationship:
        source_subject, relationship, target_subject, provenance = (
            _normalize(source_subject, "relationship source"),
            _normalize(relationship, "relationship"),
            _normalize(target_subject, "relationship target"),
            _normalize(provenance, "provenance"),
        )
        if not 0 <= confidence <= 1:
            raise ValueError("relationship confidence must be between 0 and 1")
        now, relationship_id = _now(), "rel_" + uuid.uuid4().hex
        with self._db() as db:
            db.execute(
                "INSERT INTO memory_relationships VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    relationship_id, source_subject, relationship, target_subject, provenance,
                    confidence, now, now, RelationshipState.ACTIVE,
                ),
            )
        return self.get_relationship(relationship_id)

    def get_relationship(self, relationship_id: str) -> MemoryRelationship:
        with self._db() as db:
            row = db.execute(
                "SELECT * FROM memory_relationships WHERE relationship_id=?", (relationship_id,)
            ).fetchone()
        if row is None:
            raise KeyError(relationship_id)
        return MemoryRelationship(*row[:8], RelationshipState(row[8]))

    def relationships(self, subject: str, limit: int = 20) -> tuple[MemoryRelationship, ...]:
        subject = _normalize(subject, "relationship subject")
        self._limit(limit)
        with self._db() as db:
            rows = db.execute(
                "SELECT * FROM memory_relationships WHERE state=? "
                "AND (source_subject=? OR target_subject=?) "
                "ORDER BY confidence DESC, updated_at DESC LIMIT ?",
                (RelationshipState.ACTIVE, subject, subject, limit),
            ).fetchall()
        return tuple(MemoryRelationship(*row[:8], RelationshipState(row[8])) for row in rows)

    def forget_relationship(self, relationship_id: str) -> None:
        with self._db() as db:
            changed = db.execute(
                "UPDATE memory_relationships SET state=?, updated_at=? "
                "WHERE relationship_id=? AND state=?",
                (RelationshipState.DELETED, _now(), relationship_id, RelationshipState.ACTIVE),
            ).rowcount
        if changed != 1:
            raise ValueError("relationship is not active")

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
        with self._db() as db:
            changed = db.execute(
                "UPDATE memories SET state=?, updated_at=? WHERE memory_id=? AND state!=?",
                (MemoryState.DELETED, _now(), memory_id, MemoryState.DELETED),
            ).rowcount
        if changed != 1:
            raise ValueError("memory is already deleted or does not exist")
