"""Durable local research sources, gaps, synthesis, and curriculum drafts."""
from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import astuple, dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class SourceRecord:
    source_id: str
    domain: str
    title: str
    content: str
    provenance: str
    version: str
    content_hash: str
    created_at: str


class ResearchService:
    """Local-only evidence ledger; it never fetches, trains, or changes weights."""

    def __init__(self, database: Path) -> None:
        self.database = database.resolve()
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS research_sources (source_id TEXT PRIMARY KEY, domain TEXT NOT NULL, title TEXT NOT NULL, content TEXT NOT NULL, provenance TEXT NOT NULL, version TEXT NOT NULL, content_hash TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL)")

    def _db(self):
        return sqlite3.connect(self.database)

    def collect(self, domain: str, title: str, content: str, provenance: str, *, version: str = "1") -> SourceRecord:
        values = [item.strip() for item in (domain, title, content, provenance, version)]
        if not all(values) or len(values[0]) > 128 or len(values[1]) > 500 or len(values[2]) > 100_000 or len(values[3]) > 1_000:
            raise ValueError("research source fields exceed local bounds")
        digest = hashlib.sha256((values[0] + "\0" + values[2]).encode()).hexdigest()
        now = datetime.now(UTC).isoformat()
        with self._db() as db:
            row = db.execute("SELECT * FROM research_sources WHERE content_hash=?", (digest,)).fetchone()
            if row is None:
                record = SourceRecord(uuid4().hex, *values, digest, now)
                db.execute("INSERT INTO research_sources VALUES(?,?,?,?,?,?,?,?)", astuple(record))
                return record
        return SourceRecord(*row)

    def sources(self, domain: str | None = None, *, limit: int = 100) -> tuple[SourceRecord, ...]:
        if not 1 <= limit <= 1000:
            raise ValueError("research source limit is out of bounds")
        with self._db() as db:
            rows = db.execute("SELECT * FROM research_sources WHERE (? IS NULL OR domain=?) ORDER BY created_at DESC LIMIT ?", (domain, domain, limit)).fetchall()
        return tuple(SourceRecord(*row) for row in rows)

    def gaps(self, domain: str, required_topics: tuple[str, ...]) -> tuple[str, ...]:
        corpus = "\n".join(item.content.casefold() for item in self.sources(domain))
        return tuple(topic for topic in required_topics if topic.casefold() not in corpus)

    def synthesis(self, domain: str, question: str) -> str:
        evidence = self.sources(domain, limit=20)
        if not evidence:
            return "No local provenance-bearing evidence is available."
        return "\n\n".join(f"[{item.title}; provenance={item.provenance}; version={item.version}]\n{item.content}" for item in evidence)[:20_000]

    def curriculum(self, domain: str, topics: tuple[str, ...]) -> tuple[dict[str, str], ...]:
        """Build a transparent local study sequence from known/gap evidence."""
        gaps = set(self.gaps(domain, topics))
        return tuple({"topic": topic, "status": "research" if topic in gaps else "evidence_available"} for topic in topics)

    def evaluate(self, domain: str, topic: str, response: str) -> dict[str, object]:
        """Deterministic evidence-presence check; it never advances model state."""
        evidence = self.sources(domain)
        terms = {word.casefold().strip(".,!?;:") for item in evidence for word in item.content.split() if len(word) > 3}
        response_terms = {word.casefold().strip(".,!?;:") for word in response.split()}
        return {"topic": topic, "evidence_available": bool(evidence), "grounded_terms": len(terms & response_terms), "passed": bool(terms & response_terms)}
