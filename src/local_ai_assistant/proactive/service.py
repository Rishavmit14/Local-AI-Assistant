"""Durable, deterministic local watches, schedules, and notifications.

This module deliberately observes and notifies only.  It cannot approve, plan,
execute, or control the desktop; those authorities remain at their existing
explicit boundaries.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from local_ai_assistant.execution.history import redact_data


class EventSource(StrEnum):
    SYSTEM = "system"
    SERVICE = "service"
    REPOSITORY = "repository"
    FILESYSTEM = "filesystem"
    TASK = "task"
    EXTERNAL = "external"
    SCHEDULE = "schedule"


class WatchPermission(StrEnum):
    NOTIFY = "notify"


@dataclass(frozen=True, slots=True)
class Watch:
    watch_id: str
    source: EventSource
    label: str
    permission: WatchPermission = WatchPermission.NOTIFY
    min_relevance: int = 1
    interval_seconds: int = 60
    enabled: bool = True
    schedule: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.watch_id or len(self.watch_id) > 128 or not self.label or len(self.label) > 500:
            raise ValueError("watch identity and label must be bounded")
        if not 1 <= self.min_relevance <= 100:
            raise ValueError("watch relevance must be between 1 and 100")
        if not 1 <= self.interval_seconds <= 86_400:
            raise ValueError("watch interval must be between 1 and 86400 seconds")
        _metadata(self.metadata, "watch")


@dataclass(frozen=True, slots=True)
class ProactiveEvent:
    event_id: str
    watch_id: str
    source: EventSource
    kind: str
    summary: str
    relevance: int
    occurred_at: str
    payload_hash: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Notification:
    notification_id: str
    event_id: str
    watch_id: str
    summary: str
    relevance: int
    created_at: str
    acknowledged_at: str | None = None


class ProactiveEventEngine:
    """SQLite-backed event policy with bounded polling and notification delivery."""

    def __init__(self, database: Path, *, max_notifications_per_hour: int = 20) -> None:
        if not 1 <= max_notifications_per_hour <= 10_000:
            raise ValueError("notification rate must be between 1 and 10000 per hour")
        self.database = database.resolve()
        self.max_notifications_per_hour = max_notifications_per_hour
        self._lock = Lock()
        self._observers: dict[str, Callable[[], tuple[str, str, int, dict[str, Any]] | None]] = {}
        self._initialize()

    def _db(self) -> sqlite3.Connection:
        self.database.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.database)
        db.row_factory = sqlite3.Row
        return db

    def _initialize(self) -> None:
        with self._db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS proactive_watches (
                  watch_id TEXT PRIMARY KEY, source TEXT NOT NULL, label TEXT NOT NULL,
                  permission TEXT NOT NULL, min_relevance INTEGER NOT NULL,
                  interval_seconds INTEGER NOT NULL, enabled INTEGER NOT NULL,
                  schedule INTEGER NOT NULL, metadata_json TEXT NOT NULL,
                  next_due INTEGER NOT NULL DEFAULT 0, last_fingerprint TEXT
                );
                CREATE TABLE IF NOT EXISTS proactive_events (
                  event_id TEXT PRIMARY KEY, watch_id TEXT NOT NULL, source TEXT NOT NULL,
                  kind TEXT NOT NULL, summary TEXT NOT NULL, relevance INTEGER NOT NULL,
                  occurred_at TEXT NOT NULL, payload_hash TEXT NOT NULL, metadata_json TEXT NOT NULL,
                  UNIQUE(watch_id, payload_hash)
                );
                CREATE TABLE IF NOT EXISTS proactive_notifications (
                  notification_id TEXT PRIMARY KEY, event_id TEXT NOT NULL UNIQUE,
                  watch_id TEXT NOT NULL, summary TEXT NOT NULL, relevance INTEGER NOT NULL,
                  created_at TEXT NOT NULL, acknowledged_at TEXT
                );
                CREATE INDEX IF NOT EXISTS proactive_notifications_created
                  ON proactive_notifications(created_at);
            """)

    def register(self, watch: Watch, observer: Callable[[], tuple[str, str, int, dict[str, Any]] | None] | None = None) -> Watch:
        with self._lock, self._db() as db:
            db.execute("""INSERT INTO proactive_watches
                (watch_id,source,label,permission,min_relevance,interval_seconds,enabled,schedule,metadata_json)
                VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(watch_id) DO UPDATE SET source=excluded.source,label=excluded.label,
                permission=excluded.permission,min_relevance=excluded.min_relevance,
                interval_seconds=excluded.interval_seconds,enabled=excluded.enabled,
                schedule=excluded.schedule,metadata_json=excluded.metadata_json""",
                (watch.watch_id, watch.source.value, watch.label, watch.permission.value,
                 watch.min_relevance, watch.interval_seconds, int(watch.enabled), int(watch.schedule),
                 _json(watch.metadata)))
            if observer is not None:
                self._observers[watch.watch_id] = observer
        return watch

    def disable(self, watch_id: str) -> None:
        with self._lock, self._db() as db:
            if db.execute("UPDATE proactive_watches SET enabled=0 WHERE watch_id=?", (watch_id,)).rowcount != 1:
                raise ValueError("watch is unavailable")
            self._observers.pop(watch_id, None)

    def poll_due(self, *, now: int | None = None) -> tuple[Notification, ...]:
        now = int(datetime.now(UTC).timestamp()) if now is None else now
        with self._lock, self._db() as db:
            rows = db.execute("SELECT * FROM proactive_watches WHERE enabled=1 AND next_due<=?", (now,)).fetchall()
            for row in rows:
                db.execute("UPDATE proactive_watches SET next_due=? WHERE watch_id=?", (now + int(row["interval_seconds"]), row["watch_id"]))
        delivered: list[Notification] = []
        for row in rows:
            watch = self._watch(row)
            if watch.schedule:
                result = ("schedule.due", watch.label, 50, {"scheduled": True, "due_at": now})
            else:
                observer = self._observers.get(watch.watch_id)
                result = observer() if observer is not None else None
            if result is not None:
                kind, summary, relevance, metadata = result
                notification = self.ingest(watch.watch_id, kind, summary, relevance, metadata)
                if notification is not None:
                    delivered.append(notification)
        return tuple(delivered)

    def ingest(self, watch_id: str, kind: str, summary: str, relevance: int, metadata: dict[str, Any] | None = None) -> Notification | None:
        if not kind or len(kind) > 128 or not summary or len(summary) > 4_000 or not 0 <= relevance <= 100:
            raise ValueError("event fields are invalid or exceed bounds")
        metadata = _metadata(metadata or {}, "event")
        now = datetime.now(UTC)
        payload_hash = hashlib.sha256(_json({"kind": kind, "summary": summary, "metadata": metadata}).encode()).hexdigest()
        with self._lock, self._db() as db:
            row = db.execute("SELECT * FROM proactive_watches WHERE watch_id=? AND enabled=1", (watch_id,)).fetchone()
            if row is None:
                raise ValueError("enabled watch is required")
            watch = self._watch(row)
            if relevance < watch.min_relevance or watch.permission is not WatchPermission.NOTIFY:
                return None
            event_id = uuid4().hex
            try:
                db.execute("INSERT INTO proactive_events VALUES(?,?,?,?,?,?,?,?,?)", (event_id, watch_id, watch.source.value, kind, summary, relevance, now.isoformat(), payload_hash, _json(metadata)))
            except sqlite3.IntegrityError:
                return None
            hour_ago = datetime.fromtimestamp(now.timestamp() - 3600, UTC).isoformat()
            count = db.execute("SELECT count(*) FROM proactive_notifications WHERE created_at>=?", (hour_ago,)).fetchone()[0]
            if count >= self.max_notifications_per_hour:
                return None
            notification = Notification(uuid4().hex, event_id, watch_id, summary, relevance, now.isoformat())
            db.execute("INSERT INTO proactive_notifications VALUES(?,?,?,?,?,?,NULL)", (notification.notification_id, notification.event_id, notification.watch_id, notification.summary, notification.relevance, notification.created_at))
            return notification

    def external(self, watch_id: str, event_id: str, summary: str, relevance: int, metadata: dict[str, Any] | None = None) -> Notification | None:
        """Accept a bounded external signal only through an explicitly external watch."""
        if not event_id or len(event_id) > 256:
            raise ValueError("external event ID is required")
        with self._lock, self._db() as db:
            row = db.execute("SELECT source FROM proactive_watches WHERE watch_id=?", (watch_id,)).fetchone()
        if row is None or row["source"] != EventSource.EXTERNAL.value:
            raise ValueError("external events require an external watch")
        values = dict(metadata or {})
        values["external_event_id"] = event_id
        return self.ingest(watch_id, "external.received", summary, relevance, values)

    def notifications(self, *, limit: int = 100, include_acknowledged: bool = False) -> tuple[Notification, ...]:
        if not 1 <= limit <= 1000:
            raise ValueError("notification limit must be between 1 and 1000")
        clause = "" if include_acknowledged else "WHERE acknowledged_at IS NULL"
        with self._db() as db:
            rows = db.execute(f"SELECT * FROM proactive_notifications {clause} ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return tuple(Notification(*tuple(row)) for row in rows)

    def acknowledge(self, notification_id: str) -> Notification:
        now = datetime.now(UTC).isoformat()
        with self._lock, self._db() as db:
            if db.execute("UPDATE proactive_notifications SET acknowledged_at=? WHERE notification_id=? AND acknowledged_at IS NULL", (now, notification_id)).rowcount != 1:
                raise ValueError("unacknowledged notification is unavailable")
            row = db.execute("SELECT * FROM proactive_notifications WHERE notification_id=?", (notification_id,)).fetchone()
        return Notification(*tuple(row))

    @staticmethod
    def filesystem_observer(path: Path) -> Callable[[], tuple[str, str, int, dict[str, Any]] | None]:
        """Return a bounded fingerprint observer; paths are read, never changed."""
        root = path.resolve()
        previous: str | None = None
        def observe():
            nonlocal previous
            if not root.exists():
                fingerprint = "missing"
            elif root.is_file():
                stat = root.stat()
                fingerprint = f"file:{stat.st_mtime_ns}:{stat.st_size}"
            else:
                entries = []
                for candidate in sorted(root.rglob("*"))[:10_000]:
                    if candidate.is_file():
                        stat = candidate.stat()
                        entries.append((str(candidate.relative_to(root)), stat.st_mtime_ns, stat.st_size))
                fingerprint = hashlib.sha256(_json(entries).encode()).hexdigest()
            changed = previous is not None and fingerprint != previous
            previous = fingerprint
            return ("filesystem.changed", f"Filesystem watch changed: {root.name}", 50, {"fingerprint": fingerprint}) if changed else None
        return observe

    @staticmethod
    def state_observer(
        source: EventSource,
        label: str,
        snapshot: Callable[[], Any],
        *,
        relevance: int = 60,
    ) -> Callable[[], tuple[str, str, int, dict[str, Any]] | None]:
        """Turn a local system/service/task snapshot into change-only events."""
        previous: str | None = None

        def observe():
            nonlocal previous
            value = _json(snapshot())
            changed = previous is not None and value != previous
            previous = value
            if not changed:
                return None
            return (f"{source.value}.changed", f"{label} changed", relevance, {"snapshot": value[:4000]})

        return observe

    @staticmethod
    def repository_observer(repository: Path) -> Callable[[], tuple[str, str, int, dict[str, Any]] | None]:
        """Observe local Git HEAD/worktree state without changing the repository."""
        root = repository.resolve()

        def snapshot() -> dict[str, str]:
            result = subprocess.run(
                ["git", "status", "--porcelain=v1", "--branch"], cwd=root,
                capture_output=True, text=True, timeout=5, check=False,
            )
            return {"returncode": str(result.returncode), "status": result.stdout[:4000]}

        return ProactiveEventEngine.state_observer(EventSource.REPOSITORY, f"Repository {root.name}", snapshot)

    @staticmethod
    def _watch(row: sqlite3.Row) -> Watch:
        return Watch(row["watch_id"], EventSource(row["source"]), row["label"], WatchPermission(row["permission"]), int(row["min_relevance"]), int(row["interval_seconds"]), bool(row["enabled"]), bool(row["schedule"]), json.loads(row["metadata_json"]))


def _json(value: Any) -> str:
    return json.dumps(redact_data(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _metadata(value: dict[str, Any], subject: str) -> dict[str, Any]:
    if not isinstance(value, dict) or len(value) > 32:
        raise ValueError(f"{subject} metadata is too large")
    safe = redact_data(value)
    if not isinstance(safe, dict) or len(_json(safe)) > 16_384:
        raise ValueError(f"{subject} metadata exceeds the configured bound")
    return safe
