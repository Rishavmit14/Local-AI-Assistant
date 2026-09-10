"""Narrow, auditable GNOME desktop actions; never a general shell adapter."""

from __future__ import annotations

import re
import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4


class DesktopAction(StrEnum):
    FOCUS_APP = "focus_app"
    LAUNCH_APP = "launch_app"
    OPEN_URI = "open_uri"
    OPEN_FILE = "open_file"


@dataclass(frozen=True, slots=True)
class DesktopActionRecord:
    action_id: str
    action: DesktopAction
    app_id: str
    state: str
    created_at: str
    approved_at: str | None
    executed_at: str | None


class DesktopControlService:
    """Require an explicit local approval before one exact allowed desktop action."""

    _APP_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,255}$")

    def __init__(self, database: Path, *, allowed_apps: tuple[str, ...] = (),
                 allowed_origins: tuple[str, ...] = (),
                 allowed_file_roots: tuple[Path, ...] = (),
                 approval_seconds: int = 60, runner=subprocess.run) -> None:
        if approval_seconds < 1:
            raise ValueError("approval_seconds must be positive")
        if any(not self._APP_ID.fullmatch(app_id) for app_id in allowed_apps):
            raise ValueError("desktop allowed_apps contains an invalid app id")
        self.database = database.resolve()
        self.allowed_apps = frozenset(allowed_apps)
        self.allowed_origins = frozenset(allowed_origins)
        self.allowed_file_roots = tuple(root.resolve() for root in allowed_file_roots)
        self.approval_seconds = approval_seconds
        self._runner = runner

    def _db(self) -> sqlite3.Connection:
        self.database.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.database)
        db.execute(
            "CREATE TABLE IF NOT EXISTS desktop_actions (action_id TEXT PRIMARY KEY, action TEXT NOT NULL, "
            "app_id TEXT NOT NULL, state TEXT NOT NULL, created_at TEXT NOT NULL, approved_at TEXT, executed_at TEXT)"
        )
        return db

    def propose(self, action: DesktopAction, app_id: str) -> DesktopActionRecord:
        if not isinstance(action, DesktopAction):
            raise ValueError("desktop action is invalid")
        parsed = urlsplit(app_id)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if action is DesktopAction.OPEN_URI and (
            parsed.scheme != "https" or not parsed.netloc or origin not in self.allowed_origins
        ):
            raise ValueError("desktop URI origin is not allowed")
        if action is DesktopAction.OPEN_FILE:
            candidate = Path(app_id).expanduser().resolve()
            if not candidate.is_file() or not any(
                candidate.is_relative_to(root) for root in self.allowed_file_roots
            ):
                raise ValueError("desktop file is not allowed")
            app_id = str(candidate)
        if action not in {DesktopAction.OPEN_URI, DesktopAction.OPEN_FILE} and (
            not self._APP_ID.fullmatch(app_id) or app_id not in self.allowed_apps
        ):
            raise ValueError("desktop app is not allowed")
        record = DesktopActionRecord(uuid4().hex, action, app_id, "proposed", datetime.now(UTC).isoformat(), None, None)
        with self._db() as db:
            db.execute("INSERT INTO desktop_actions VALUES(?,?,?,?,?,?,?)", (
                record.action_id, record.action.value, record.app_id, record.state,
                record.created_at, record.approved_at, record.executed_at,
            ))
        return record

    def approve(self, action_id: str) -> DesktopActionRecord:
        record = self._record(action_id)
        if record.state != "proposed":
            raise ValueError("desktop action is not awaiting approval")
        created = datetime.fromisoformat(record.created_at)
        if datetime.now(UTC) > created + timedelta(seconds=self.approval_seconds):
            self._update(action_id, state="expired")
            raise ValueError("desktop action approval expired")
        approved_at = datetime.now(UTC).isoformat()
        self._update(action_id, state="approved", approved_at=approved_at)
        return self._record(action_id)

    def execute(self, action_id: str) -> DesktopActionRecord:
        record = self._record(action_id)
        if record.state != "approved":
            raise ValueError("desktop action requires explicit approval")
        command = self._command(record)
        result = self._runner(command, capture_output=True, text=True, check=False, timeout=10)
        if result.returncode != 0:
            self._update(action_id, state="failed")
            raise RuntimeError("desktop action failed")
        self._update(action_id, state="executed", executed_at=datetime.now(UTC).isoformat())
        return self._record(action_id)

    def recent(self, limit: int = 20) -> tuple[DesktopActionRecord, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        with self._db() as db:
            rows = db.execute("SELECT action_id, action, app_id, state, created_at, approved_at, executed_at "
                              "FROM desktop_actions ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return tuple(DesktopActionRecord(row[0], DesktopAction(row[1]), *row[2:]) for row in rows)

    def _record(self, action_id: str) -> DesktopActionRecord:
        if not re.fullmatch(r"[a-f0-9]{32}", action_id):
            raise ValueError("desktop action is unavailable")
        with self._db() as db:
            row = db.execute("SELECT action_id, action, app_id, state, created_at, approved_at, executed_at "
                             "FROM desktop_actions WHERE action_id=?", (action_id,)).fetchone()
        if row is None:
            raise ValueError("desktop action is unavailable")
        return DesktopActionRecord(row[0], DesktopAction(row[1]), *row[2:])

    def _update(self, action_id: str, *, state: str, approved_at: str | None = None,
                executed_at: str | None = None) -> None:
        with self._db() as db:
            db.execute("UPDATE desktop_actions SET state=?, approved_at=COALESCE(?, approved_at), "
                       "executed_at=COALESCE(?, executed_at) WHERE action_id=?",
                       (state, approved_at, executed_at, action_id))

    @staticmethod
    def _command(record: DesktopActionRecord) -> list[str]:
        if record.action is DesktopAction.FOCUS_APP:
            return ["gdbus", "call", "--session", "--dest", "org.gnome.Shell", "--object-path",
                    "/org/gnome/Shell", "--method", "org.gnome.Shell.FocusApp", record.app_id]
        if record.action is DesktopAction.OPEN_URI:
            return ["gio", "open", record.app_id]
        if record.action is DesktopAction.OPEN_FILE:
            return ["gio", "open", record.app_id]
        return ["gio", "launch", record.app_id]
