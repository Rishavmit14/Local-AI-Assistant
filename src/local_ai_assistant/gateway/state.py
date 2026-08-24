"""Small transactional gateway state store for idempotency/publication identities."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path


class GatewayState:
    def __init__(self, path: Path):
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA busy_timeout=5000")
            c.execute("CREATE TABLE IF NOT EXISTS gateway_idempotency (source TEXT NOT NULL, event_id TEXT NOT NULL, repository_id TEXT NOT NULL, task_id TEXT NOT NULL, PRIMARY KEY(source,event_id,repository_id))")
            c.execute("CREATE TABLE IF NOT EXISTS gateway_publications (task_id TEXT PRIMARY KEY, external_id TEXT NOT NULL, state TEXT NOT NULL, commit_sha TEXT, updated_at TEXT NOT NULL)")

    def existing_task(self, source: str, event_id: str, repository_id: str) -> str | None:
        with self._connect() as c:
            row = c.execute("SELECT task_id FROM gateway_idempotency WHERE source=? AND event_id=? AND repository_id=?", (source,event_id,repository_id)).fetchone()
            return row[0] if row else None

    def remember(self, source: str, event_id: str, repository_id: str, task_id: str) -> str:
        with self._connect() as c:
            c.execute("INSERT OR IGNORE INTO gateway_idempotency VALUES (?,?,?,?)", (source,event_id,repository_id,task_id))
            row = c.execute("SELECT task_id FROM gateway_idempotency WHERE source=? AND event_id=? AND repository_id=?", (source,event_id,repository_id)).fetchone()
            return row[0]

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=5)
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
