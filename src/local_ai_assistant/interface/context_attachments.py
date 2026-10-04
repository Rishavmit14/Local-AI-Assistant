"""Durable, bounded owner-selected context for ordinary Conversation.

Attachments are reference snapshots. They never grant access or mutation authority.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from uuid import uuid4

MAX_ATTACHMENTS = 3
MAX_SNAPSHOT_CHARS = 6000
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


class ContextAttachmentStore:
    """Resolve only supported canonical records and retain immutable provenance."""

    def __init__(self, database: Path, learning_paths, projects, cross_path=None):
        self.database = Path(database).resolve()
        self.learning_paths = learning_paths
        self.projects = projects
        self.cross_path = cross_path
        self._lock = RLock()
        self.database.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.database.parent, 0o700)
        fd = os.open(self.database, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(fd)
        os.chmod(self.database, 0o600)
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS attachments (
                    attachment_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL,
                    kind TEXT NOT NULL, source_id TEXT NOT NULL,
                    route TEXT NOT NULL, source_version TEXT NOT NULL,
                    digest TEXT NOT NULL, snapshot_json TEXT NOT NULL,
                    created_at TEXT NOT NULL, message_id TEXT
                );
                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL,
                    prompt TEXT NOT NULL, answer TEXT NOT NULL DEFAULT '',
                    state TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS attachments_message ON attachments(message_id);
            """)

    def _connect(self):
        db = sqlite3.connect(self.database, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def _source(self, kind: str, source_id: str) -> tuple[str, dict]:
        if not isinstance(source_id, str) or not _ID.fullmatch(source_id):
            raise ValueError("invalid context source identity")
        if kind == "learning_path" and self.learning_paths is not None:
            detail = self.learning_paths.detail(source_id)
            path, version = detail["path"], detail["current"]
            payload = {"path": asdict(path), "version": version.version,
                       "modules": version.modules, "nodes": version.nodes,
                       "prerequisites": version.prerequisites, "milestones": version.milestones}
            return str(version.version), payload
        if kind == "project" and self.projects is not None:
            project = self.projects.get(source_id)
            assignment = (
                self.learning_paths.repository.project_assignment_for_project(source_id)
                if self.learning_paths is not None and hasattr(self.learning_paths, "repository") else None
            )
            payload = {"project": asdict(project),
                       "learning_assignment": assignment,
                       "artifacts": [asdict(item) for item in self.projects.artifacts(source_id)],
                       "missions": [asdict(item) for item in self.projects.mission_links(source_id)]}
            return project.updated_at, payload
        if kind in {"competency", "evidence", "review"} and self.cross_path is not None:
            payload = self.cross_path.resolve(kind, source_id)
            return str(payload.get("version", "canonical")), payload
        raise ValueError("unsupported context type")

    @staticmethod
    def _canonical(value: dict) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def create(self, owner_id: str, kind: str, source_id: str) -> dict:
        version, payload = self._source(kind, source_id)
        canonical = self._canonical(payload)
        if kind == "learning_path":
            path = payload["path"]
            snapshot = {"path": {key: path.get(key) for key in
                                   ("path_id", "title", "goal", "state", "current_version")},
                        "version": payload["version"], "node_count": len(payload["nodes"]),
                        "nodes": [{key: node.get(key) for key in
                                   ("node_id", "title", "type", "competency_key", "objectives")}
                                  for node in payload["nodes"][:8]],
                        "content_omitted": len(payload["nodes"]) > 8}
        elif kind == "project":
            project = payload["project"]
            brief = str(project.get("brief") or "")
            snapshot = {"project": {key: project.get(key) for key in
                                    ("project_id", "title", "state", "mission_id", "objective_id", "task_id", "updated_at")},
                        "learning_assignment": payload["learning_assignment"],
                        "brief": brief[:2000], "brief_truncated": len(brief) > 2000,
                        "artifact_count": len(payload["artifacts"]),
                        "artifacts": payload["artifacts"][:8],
                        "content_omitted": len(payload["artifacts"]) > 8}
        else:
            snapshot = self.cross_path.model_context(kind, source_id)
        if len(self._canonical(snapshot)) > MAX_SNAPSHOT_CHARS:
            # Keep exact source identity and digest even when content is omitted.
            snapshot = {"source_id": source_id, "kind": kind, "content_omitted": True,
                        "title": payload.get("path", payload.get("project", {})).get("title", "")}
        digest = hashlib.sha256(canonical.encode()).hexdigest()
        attachment_id = "ctx_" + uuid4().hex
        route = {"learning_path": "#learn", "project": "#projects", "competency": "#progress",
                 "evidence": "#progress", "review": "#learn"}[kind]
        created_at = datetime.now(UTC).isoformat()
        with self._lock, self._connect() as db:
            db.execute("INSERT INTO attachments VALUES(?,?,?,?,?,?,?,?,?,NULL)",
                       (attachment_id, owner_id, kind, source_id, route, version,
                        digest, self._canonical(snapshot), created_at))
        return self.get(owner_id, attachment_id)

    def get(self, owner_id: str, attachment_id: str) -> dict:
        if not isinstance(attachment_id, str) or not re.fullmatch(r"ctx_[0-9a-f]{32}", attachment_id):
            raise ValueError("invalid attachment identity")
        with self._connect() as db:
            row = db.execute("SELECT * FROM attachments WHERE attachment_id=? AND owner_id=?",
                             (attachment_id, owner_id)).fetchone()
        if row is None:
            raise KeyError(attachment_id)
        result = dict(row)
        result["snapshot"] = json.loads(result.pop("snapshot_json"))
        try:
            version, payload = self._source(result["kind"], result["source_id"])
            digest = hashlib.sha256(self._canonical(payload).encode()).hexdigest()
            result["status"] = "current" if version == result["source_version"] and digest == result["digest"] else "stale"
        except (KeyError, ValueError):
            result["status"] = "unavailable"
        return result

    def bind(self, owner_id: str, ids: list[str], prompt: str) -> tuple[str, list[dict]]:
        if not isinstance(ids, list) or len(ids) > MAX_ATTACHMENTS or len(ids) != len(set(ids)):
            raise ValueError("bounded unique attachments are required")
        resolved = [self.get(owner_id, value) for value in ids]
        if len({(item["kind"], item["source_id"]) for item in resolved}) != len(resolved):
            raise ValueError("duplicate context source")
        if any(item["status"] != "current" or item["message_id"] for item in resolved):
            raise ValueError("attachment is stale, unavailable, or already used")
        message_id = "msg_" + uuid4().hex
        with self._lock, self._connect() as db:
            db.execute("INSERT INTO messages(message_id,owner_id,prompt,state,created_at) VALUES(?,?,?,'pending',?)",
                       (message_id, owner_id, prompt, datetime.now(UTC).isoformat()))
            for item in resolved:
                cursor = db.execute("UPDATE attachments SET message_id=? WHERE attachment_id=? AND owner_id=? AND message_id IS NULL",
                                    (message_id, item["attachment_id"], owner_id))
                if cursor.rowcount != 1:
                    raise ValueError("attachment was already used")
        return message_id, resolved

    def finish(self, owner_id: str, message_id: str, answer: str, state: str) -> None:
        if state not in {"completed", "failed"}:
            raise ValueError("invalid message state")
        with self._lock, self._connect() as db:
            db.execute("UPDATE messages SET answer=?,state=? WHERE message_id=? AND owner_id=?",
                       (answer[:20_000], state, message_id, owner_id))

    def history(self, owner_id: str) -> list[dict]:
        with self._connect() as db:
            messages = [dict(row) for row in db.execute(
                "SELECT * FROM messages WHERE owner_id=? ORDER BY created_at DESC LIMIT 100", (owner_id,))]
        for message in messages:
            with self._connect() as db:
                ids = [row[0] for row in db.execute(
                    "SELECT attachment_id FROM attachments WHERE message_id=? ORDER BY rowid", (message["message_id"],))]
            message["attachments"] = [self.get(owner_id, value) for value in ids]
        return list(reversed(messages))
