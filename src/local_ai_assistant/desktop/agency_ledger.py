"""Durable computer-use provenance with fail-closed action recovery.

The ledger grants no desktop authority. A separate trusted controller must
validate policy, claim an action, execute it, and record a new observation.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import sqlite3
import threading
import weakref
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from .observation import AccessibleElement, DesktopObservation

_ID = re.compile(r"^[a-f0-9]{32}$")
_KINDS = frozenset({
    "focus_app", "launch_app", "open_uri", "open_file", "activate_accessible",
    "move_pointer", "click", "double_click", "right_click", "scroll", "drag",
    "type_text", "press_key", "hotkey", "switch_window", "close_window",
    "open_location", "create_directory", "move_file", "run_read_only_command",
})
_RISK = frozenset({"low", "medium", "consequential"})
_SEMANTIC_KINDS = frozenset({
    "activate_accessible", "move_pointer", "click", "double_click", "right_click",
    "scroll", "drag", "type_text", "press_key", "hotkey",
    "switch_window",
})
# These actions are bound to a resolved URI or installed desktop entry rather
# than a screen element. The runner revalidates that target before dispatch;
# unrelated accessibility-tree changes must not invalidate the claim.
_RESOLVED_TARGET_KINDS = frozenset({
    "launch_app", "open_uri", "open_location", "create_directory",
    "move_file", "run_read_only_command",
})
_OUTCOMES = frozenset({
    "postcondition_verified", "postcondition_failed", "observation_failed",
    "actor_failed", "interrupted",
})
_STALE_REASONS = frozenset({
    "stale_observation_expired", "stale_application_changed", "stale_window_changed",
    "stale_target_disappeared", "stale_target_moved", "stale_focus_changed",
    "stale_collection_changed", "stale_observation_changed",
})
_VERIFICATION_RESULTS = frozenset({
    "active", "focused", "new_visible", "uri_visible", "browser_title_visible",
    "not_found", "not_checked", "location_opened", "filesystem_exists",
    "command_completed", "search_field_opened", "search_field_focused", "search_results_visible",
    "command_palette_ready", "command_palette_focused", "command_palette_dismissed",
    "accessible_view_dismissed", "accessible_view_opened", "terminal_ready", "terminal_created",
    "terminal_output_captured",
    "file_manager_location_verified",
    "file_manager_location_read", "file_manager_location_dismissed",
    "visible_target_opened",
    "window_closed",
    "observation_failed",
})
_TASK_FAILURE_REASONS = frozenset({
    "planner_rejected", "unsupported_goal", "target_unresolved",
    "verification_failed", "cancelled", "execution_failed",
})


def _recent(timestamp: str, *, seconds: int) -> bool:
    try:
        age = (datetime.now(UTC) - datetime.fromisoformat(timestamp)).total_seconds()
    except (ValueError, TypeError):
        return False
    return -2 <= age <= seconds


def _not_expired(timestamp: str) -> bool:
    try:
        return datetime.now(UTC) < datetime.fromisoformat(timestamp)
    except (ValueError, TypeError):
        return False


@dataclass(frozen=True, slots=True)
class ComputerTask:
    task_id: str
    owner_id: str
    request: str
    state: str
    created_at: str
    action_budget: int
    action_count: int
    failure_reason: str | None


@dataclass(frozen=True, slots=True)
class ComputerClarification:
    task_id: str
    owner_id: str
    question: str
    unresolved_referent: str
    observation_id: str | None
    requested_at: str
    expires_at: str
    status: str
    delivery_state: str
    response: str | None


@dataclass(frozen=True, slots=True)
class ComputerActionClaim:
    action_id: str
    task_id: str
    kind: str
    observation_id: str
    target_digest: str
    risk: str
    state: str
    claim_observation_id: str | None
    expected_result: str | None = None


@dataclass(frozen=True, slots=True)
class ComputerActionStatus:
    action_id: str
    kind: str
    state: str
    outcome: str | None
    created_at: str
    target_app: str | None
    target_name: str | None
    expected_name: str | None
    execution_started: bool
    recovery_status: str | None
    target_window: tuple[str, str, str] | None
    recovery_observation_id: str | None
    actor_return_code: int | None
    verification_result: str | None
    verification_match_count: int | None
    result_observation_id: str | None


class ComputerAgencyLedger:
    """Record exact observations and one-time action claims in owner-private SQLite."""

    def __init__(self, database: Path) -> None:
        self.database = database.resolve()
        self.database.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.database.parent.chmod(0o700)
        self._execution_lock = threading.RLock()
        self._execution_depth = 0
        self._execution_fd = os.open(str(self.database) + ".action.lock",
                                     os.O_CREAT | os.O_RDWR | os.O_CLOEXEC, 0o600)
        self._execution_fd_finalizer = weakref.finalize(self, os.close, self._execution_fd)
        os.fchmod(self._execution_fd, 0o600)
        with self._db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS computer_tasks (
                    task_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, request TEXT NOT NULL,
                    state TEXT NOT NULL, created_at TEXT NOT NULL,
                    action_budget INTEGER NOT NULL, action_count INTEGER NOT NULL DEFAULT 0,
                    cancel_requested INTEGER NOT NULL DEFAULT 0,
                    failure_reason TEXT
                );
                CREATE TABLE IF NOT EXISTS computer_observations (
                    observation_id TEXT PRIMARY KEY, task_id TEXT NOT NULL,
                    observed_at TEXT NOT NULL, digest TEXT NOT NULL,
                    element_count INTEGER NOT NULL, monitor_count INTEGER NOT NULL,
                    target_digests TEXT,
                    FOREIGN KEY(task_id) REFERENCES computer_tasks(task_id)
                );
                CREATE TABLE IF NOT EXISTS computer_actions (
                    action_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, kind TEXT NOT NULL,
                    observation_id TEXT NOT NULL, target_digest TEXT NOT NULL,
                    risk TEXT NOT NULL, state TEXT NOT NULL, created_at TEXT NOT NULL,
                    claimed_at TEXT, completed_at TEXT, result_observation_id TEXT,
                    outcome TEXT, claim_observation_id TEXT,
                    expected_result TEXT, target_summary TEXT, target_window TEXT,
                    recovery_observation_id TEXT, recovery_status TEXT,
                    execution_started_at TEXT, actor_return_code INTEGER,
                    verification_result TEXT, verification_match_count INTEGER,
                    FOREIGN KEY(task_id) REFERENCES computer_tasks(task_id),
                    FOREIGN KEY(observation_id) REFERENCES computer_observations(observation_id)
                );
                CREATE TABLE IF NOT EXISTS computer_clarifications (
                    clarification_id TEXT PRIMARY KEY, task_id TEXT NOT NULL,
                    owner_id TEXT NOT NULL, question TEXT NOT NULL,
                    unresolved_referent TEXT NOT NULL DEFAULT '', observation_id TEXT,
                    requested_at TEXT NOT NULL, expires_at TEXT NOT NULL,
                    status TEXT NOT NULL, delivery_state TEXT NOT NULL DEFAULT 'pending',
                    delivered_at TEXT, response TEXT, responded_at TEXT,
                    FOREIGN KEY(task_id) REFERENCES computer_tasks(task_id)
                );
            """)
            columns = {row[1] for row in db.execute("PRAGMA table_info(computer_observations)")}
            if "target_digests" not in columns:
                db.execute("ALTER TABLE computer_observations ADD COLUMN target_digests TEXT")
            task_columns = {row[1] for row in db.execute("PRAGMA table_info(computer_tasks)")}
            if "cancel_requested" not in task_columns:
                db.execute("ALTER TABLE computer_tasks ADD COLUMN cancel_requested INTEGER NOT NULL DEFAULT 0")
            if "failure_reason" not in task_columns:
                db.execute("ALTER TABLE computer_tasks ADD COLUMN failure_reason TEXT")
            columns = {row[1] for row in db.execute("PRAGMA table_info(computer_actions)")}
            if "expected_result" not in columns:
                db.execute("ALTER TABLE computer_actions ADD COLUMN expected_result TEXT")
            if "target_summary" not in columns:
                db.execute("ALTER TABLE computer_actions ADD COLUMN target_summary TEXT")
            if "target_window" not in columns:
                db.execute("ALTER TABLE computer_actions ADD COLUMN target_window TEXT")
            if "recovery_observation_id" not in columns:
                db.execute("ALTER TABLE computer_actions ADD COLUMN recovery_observation_id TEXT")
            if "recovery_status" not in columns:
                db.execute("ALTER TABLE computer_actions ADD COLUMN recovery_status TEXT")
            if "execution_started_at" not in columns:
                db.execute("ALTER TABLE computer_actions ADD COLUMN execution_started_at TEXT")
                # Old claims have no actor-boundary record; report them
                # conservatively as possibly started, never as safely absent.
                db.execute("UPDATE computer_actions SET execution_started_at=claimed_at "
                           "WHERE claimed_at IS NOT NULL")
            if "actor_return_code" not in columns:
                db.execute("ALTER TABLE computer_actions ADD COLUMN actor_return_code INTEGER")
            if "verification_result" not in columns:
                db.execute("ALTER TABLE computer_actions ADD COLUMN verification_result TEXT")
            if "verification_match_count" not in columns:
                db.execute("ALTER TABLE computer_actions ADD COLUMN verification_match_count INTEGER")
        self.recover_in_flight()

    @contextmanager
    def execution_guard(self):
        """Serialize physical-action windows with restart recovery across processes."""
        with self._execution_lock:
            if self._execution_depth == 0:
                fcntl.flock(self._execution_fd, fcntl.LOCK_EX)
            self._execution_depth += 1
            try:
                yield
            finally:
                self._execution_depth -= 1
                if self._execution_depth == 0:
                    fcntl.flock(self._execution_fd, fcntl.LOCK_UN)

    def _db(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.database, timeout=10)
        os.chmod(self.database, 0o600)
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def create(self, owner_id: str, request: str, *, action_budget: int = 20) -> ComputerTask:
        if not owner_id or len(owner_id) > 128 or not request.strip() or len(request) > 20_000:
            raise ValueError("computer task owner or request is invalid")
        if not 1 <= action_budget <= 100:
            raise ValueError("computer action budget is invalid")
        task_id = uuid4().hex
        with self._db() as db:
            db.execute("INSERT INTO computer_tasks "
                       "(task_id,owner_id,request,state,created_at,action_budget,action_count) "
                       "VALUES(?,?,?,?,?,?,0)", (
                task_id, owner_id, request, "active", datetime.now(UTC).isoformat(), action_budget,
            ))
        return self.task(task_id)

    def task(self, task_id: str) -> ComputerTask:
        if not _ID.fullmatch(task_id):
            raise ValueError("computer task is unavailable")
        with self._db() as db:
            row = db.execute("SELECT task_id,owner_id,request,state,created_at,action_budget,action_count,failure_reason "
                             "FROM computer_tasks WHERE task_id=?", (task_id,)).fetchone()
            if row is not None and row[3] == "active" and not _recent(row[4], seconds=1800):
                db.execute("UPDATE computer_tasks SET state='expired' WHERE task_id=?", (task_id,))
                db.execute("UPDATE computer_actions SET state='expired' "
                           "WHERE task_id=? AND state='prepared'", (task_id,))
                row = db.execute("SELECT task_id,owner_id,request,state,created_at,action_budget,action_count,failure_reason "
                                 "FROM computer_tasks WHERE task_id=?", (task_id,)).fetchone()
            if row is not None and row[3] == "awaiting_clarification":
                clarification = db.execute(
                    "SELECT clarification_id,expires_at FROM computer_clarifications "
                    "WHERE task_id=? AND status='awaiting_answer' ORDER BY requested_at DESC LIMIT 1",
                    (task_id,),
                ).fetchone()
                if clarification is None or not _not_expired(clarification[1]):
                    db.execute("UPDATE computer_tasks SET state='expired' WHERE task_id=?", (task_id,))
                    if clarification is not None:
                        db.execute("UPDATE computer_clarifications SET status='expired' "
                                   "WHERE clarification_id=?", (clarification[0],))
                    row = db.execute(
                        "SELECT task_id,owner_id,request,state,created_at,action_budget,action_count,failure_reason "
                        "FROM computer_tasks WHERE task_id=?", (task_id,),
                    ).fetchone()
        if row is None:
            raise ValueError("computer task is unavailable")
        return ComputerTask(*row)

    @staticmethod
    def _clarification_from_row(row) -> ComputerClarification:
        return ComputerClarification(*row)

    def await_clarification(self, task_id: str, question: str, *,
                            unresolved_referent: str = "",
                            observation_id: str | None = None,
                            ttl_seconds: int = 300) -> ComputerClarification:
        """Persist a zero-action task that is waiting for a spoken Owner answer."""
        if (not _ID.fullmatch(task_id) or not isinstance(question, str)
                or not 1 <= len(question.strip()) <= 1000
                or not isinstance(unresolved_referent, str) or len(unresolved_referent) > 256
                or observation_id is not None
                and (not isinstance(observation_id, str) or not 1 <= len(observation_id) <= 128
                     or any(ord(character) < 0x20 for character in observation_id))
                or type(ttl_seconds) is not int or not 30 <= ttl_seconds <= 900):
            raise ValueError("computer clarification is invalid")
        requested = datetime.now(UTC)
        expires = requested + timedelta(seconds=ttl_seconds)
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT owner_id,state,action_count,cancel_requested FROM computer_tasks WHERE task_id=?",
                (task_id,),
            ).fetchone()
            in_flight = db.execute(
                "SELECT 1 FROM computer_actions WHERE task_id=? "
                "AND state IN ('prepared','in_flight') LIMIT 1",
                (task_id,),
            ).fetchone()
            if (row is None or row[1] != "active" or row[3]
                    or in_flight is not None):
                raise ValueError("computer task cannot await clarification")
            if row[2] != 0 and not self._only_location_discovery_actions(db, task_id):
                raise ValueError("computer task has actions that cannot await clarification")
            if observation_id is None:
                latest = db.execute(
                    "SELECT observation_id FROM computer_observations WHERE task_id=? "
                    "ORDER BY observed_at DESC,rowid DESC LIMIT 1", (task_id,),
                ).fetchone()
                observation_id = latest[0] if latest is not None else None
            if observation_id is not None and db.execute(
                    "SELECT 1 FROM computer_observations WHERE observation_id=? AND task_id=?",
                    (observation_id, task_id)).fetchone() is None:
                raise ValueError("clarification observation is not part of this task")
            db.execute("UPDATE computer_tasks SET state='awaiting_clarification' WHERE task_id=?",
                       (task_id,))
            db.execute("UPDATE computer_clarifications SET status='superseded' "
                       "WHERE task_id=? AND status='awaiting_answer'", (task_id,))
            clarification_id = uuid4().hex
            db.execute(
                "INSERT INTO computer_clarifications "
                "(clarification_id,task_id,owner_id,question,unresolved_referent,observation_id,"
                "requested_at,expires_at,status,delivery_state) VALUES(?,?,?,?,?,?,?,?,?,'pending')",
                (clarification_id, task_id, row[0], question.strip(), unresolved_referent,
                 observation_id, requested.isoformat(), expires.isoformat(), "awaiting_answer"),
            )
        return self.clarification(task_id)

    def clarification(self, task_id: str) -> ComputerClarification:
        if not _ID.fullmatch(task_id):
            raise ValueError("computer clarification is unavailable")
        with self._db() as db:
            row = db.execute(
                "SELECT task_id,owner_id,question,unresolved_referent,observation_id,requested_at,"
                "expires_at,status,delivery_state,response FROM computer_clarifications "
                "WHERE task_id=? ORDER BY requested_at DESC LIMIT 1", (task_id,),
            ).fetchone()
        if row is None:
            raise ValueError("computer clarification is unavailable")
        return self._clarification_from_row(row)

    def pending_clarification(self, owner_id: str) -> ComputerClarification | None:
        if not owner_id or len(owner_id) > 128:
            return None
        with self._db() as db:
            rows = db.execute(
                "SELECT task_id FROM computer_clarifications WHERE owner_id=? "
                "AND status='awaiting_answer' AND delivery_state='played' "
                "ORDER BY requested_at DESC LIMIT 20", (owner_id,),
            ).fetchall()
        for (task_id,) in rows:
            task = self.task(task_id)
            if task.state == "awaiting_clarification":
                return self.clarification(task_id)
        return None

    def record_clarification_delivery(self, task_id: str, *, played: bool) -> ComputerClarification:
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT clarification_id FROM computer_clarifications WHERE task_id=? "
                "AND status='awaiting_answer' ORDER BY requested_at DESC LIMIT 1", (task_id,),
            ).fetchone()
            if row is None:
                raise ValueError("computer clarification is unavailable")
            db.execute("UPDATE computer_clarifications SET delivery_state=?,delivered_at=? "
                       "WHERE clarification_id=?",
                       ("played" if played else "failed",
                        datetime.now(UTC).isoformat() if played else None, row[0]))
        return self.clarification(task_id)

    def resume_clarification(self, task_id: str, owner_id: str, response: str) -> ComputerTask:
        if not isinstance(response, str) or not 1 <= len(response.strip()) <= 512 \
                or any(ord(character) < 0x20 and character not in "\t" for character in response):
            raise ValueError("clarification response is invalid")
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            clarification = db.execute(
                "SELECT clarification_id,expires_at,delivery_state FROM computer_clarifications "
                "WHERE task_id=? AND owner_id=? AND status='awaiting_answer' "
                "ORDER BY requested_at DESC LIMIT 1", (task_id, owner_id),
            ).fetchone()
            task = db.execute(
                "SELECT state,action_count,cancel_requested FROM computer_tasks WHERE task_id=? AND owner_id=?",
                (task_id, owner_id),
            ).fetchone()
            if (clarification is None or task is None or task[0] != "awaiting_clarification"
                    or task[2] or clarification[2] != "played"
                    or not _not_expired(clarification[1])):
                raise ValueError("computer clarification cannot be resumed")
            if task[1] != 0 and not self._only_location_discovery_actions(db, task_id):
                raise ValueError("computer clarification has an uncertain action outcome")
            db.execute("UPDATE computer_tasks SET state='active' WHERE task_id=?", (task_id,))
            db.execute("UPDATE computer_clarifications SET status='answered',response=?,responded_at=? "
                       "WHERE clarification_id=?",
                       (response.strip(), datetime.now(UTC).isoformat(), clarification[0]))
        return self.task(task_id)

    @staticmethod
    def _only_location_discovery_actions(db: sqlite3.Connection, task_id: str) -> bool:
        rows = db.execute(
            "SELECT kind,state,verification_result FROM computer_actions "
            "WHERE task_id=? ORDER BY rowid", (task_id,),
        ).fetchall()
        if not rows or len(rows) % 2:
            return False
        for index in range(0, len(rows), 2):
            read, dismiss = rows[index:index + 2]
            if (read != ("hotkey", "verified", "file_manager_location_read")
                    or dismiss != ("press_key", "verified", "file_manager_location_dismissed")):
                return False
        return True

    def can_await_clarification(self, task_id: str) -> bool:
        """Permit clarification after no action or only verified location-bar reads."""
        with self._db() as db:
            task = db.execute(
                "SELECT state,action_count,cancel_requested FROM computer_tasks WHERE task_id=?",
                (task_id,),
            ).fetchone()
            if task is None or task[0] != "active" or task[2]:
                return False
            in_flight = db.execute(
                "SELECT 1 FROM computer_actions WHERE task_id=? "
                "AND state IN ('prepared','in_flight') LIMIT 1",
                (task_id,),
            ).fetchone()
            return in_flight is None and (
                task[1] == 0 or self._only_location_discovery_actions(db, task_id)
            )

    def cancel_clarification(self, task_id: str, owner_id: str) -> ComputerTask:
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            changed = db.execute(
                "UPDATE computer_tasks SET state='cancelled' WHERE task_id=? AND owner_id=? "
                "AND state='awaiting_clarification' AND action_count=0", (task_id, owner_id),
            ).rowcount
            if changed != 1:
                raise ValueError("computer clarification cannot be cancelled")
            db.execute("UPDATE computer_clarifications SET status='cancelled' "
                       "WHERE task_id=? AND status='awaiting_answer'", (task_id,))
        return self.task(task_id)

    def recent_tasks(self, owner_id: str, *, limit: int = 20) -> tuple[ComputerTask, ...]:
        if not owner_id or not 1 <= limit <= 20:
            raise ValueError("computer task query is invalid")
        with self._db() as db:
            rows = db.execute(
                "SELECT * FROM computer_tasks WHERE owner_id=? ORDER BY created_at DESC LIMIT ?",
                (owner_id, limit),
            ).fetchall()
        return tuple(self.task(row[0]) for row in rows)

    def active_task_ids(self) -> tuple[str, ...]:
        """Return every active, recovery, or clarification task for gate scoping."""
        with self._db() as db:
            rows = db.execute(
                "SELECT task_id FROM computer_tasks "
                "WHERE state IN ('active','recovery_required','awaiting_clarification') "
                "ORDER BY task_id"
            ).fetchall()
        return tuple(row[0] for row in rows)

    def record_observation(self, task_id: str, observation: DesktopObservation) -> None:
        self._validate_observation(observation)
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            task = db.execute("SELECT state,created_at,cancel_requested FROM computer_tasks WHERE task_id=?", (task_id,)).fetchone()
            if task is None or task[0] != "active" or task[2] or not _recent(task[1], seconds=1800):
                raise ValueError("computer task is not active")
            count = db.execute("SELECT COUNT(*) FROM computer_observations WHERE task_id=?",
                               (task_id,)).fetchone()[0]
            if count >= 1000:
                raise ValueError("computer observation budget is exhausted")
            db.execute("INSERT INTO computer_observations "
                       "(observation_id,task_id,observed_at,digest,element_count,monitor_count,target_digests) "
                       "VALUES(?,?,?,?,?,?,?)", (
                observation.observation_id, task_id, observation.observed_at,
                observation.digest, len(observation.elements), len(observation.monitors),
                self._target_digests(observation),
            ))

    def record_stale_attempt(
        self, task_id: str, *, kind: str, observation_id: str, target_digest: str,
        fresh_observation: DesktopObservation, reason: str,
        target_summary: tuple[str, str],
        target_window: tuple[str, str, str] | None,
    ) -> ComputerActionClaim:
        """Durably reject a bound action after its source observation changes.

        Rejected attempts do not consume physical action budget. The prior and
        detecting observation IDs remain linked through the action record.
        """
        self._validate_observation(fresh_observation)
        if (kind not in _KINDS or reason not in _STALE_REASONS
                or not re.fullmatch(r"[a-f0-9]{64}", target_digest)
                or not re.fullmatch(r"observation_[a-f0-9]{32}", observation_id)
                or not isinstance(target_summary, tuple) or len(target_summary) != 2
                or any(not isinstance(value, str) or len(value) > 256 for value in target_summary)
                or target_window is not None and (
                    not isinstance(target_window, tuple) or len(target_window) != 3
                    or any(not isinstance(value, str) or len(value) > 256
                           for value in target_window)
                )):
            raise ValueError("stale computer action evidence is invalid")
        if not _recent(fresh_observation.observed_at, seconds=15):
            raise ValueError("stale computer action requires a fresh detecting observation")
        action_id = uuid4().hex
        now = datetime.now(UTC).isoformat()
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            task = db.execute(
                "SELECT state,action_budget,cancel_requested FROM computer_tasks WHERE task_id=?",
                (task_id,),
            ).fetchone()
            prior = db.execute(
                "SELECT observed_at,target_digests FROM computer_observations "
                "WHERE observation_id=? AND task_id=?", (observation_id, task_id),
            ).fetchone()
            rejections = db.execute(
                "SELECT COUNT(*) FROM computer_actions WHERE task_id=? AND state='stale' "
                "AND outcome LIKE 'stale_%'", (task_id,),
            ).fetchone()[0]
            if (task is None or task[0] != "active" or task[2]
                    or prior is None or not _recent(prior[0], seconds=1800)
                    or rejections >= 2):
                raise ValueError("stale computer recovery is unavailable or exhausted")
            if prior[1] is not None and target_digest not in json.loads(prior[1]):
                raise ValueError("stale action target was not present in its bound observation")
            db.execute(
                "INSERT INTO computer_observations "
                "(observation_id,task_id,observed_at,digest,element_count,monitor_count,target_digests) "
                "VALUES(?,?,?,?,?,?,?)", (
                    fresh_observation.observation_id, task_id, fresh_observation.observed_at,
                    fresh_observation.digest, len(fresh_observation.elements),
                    len(fresh_observation.monitors), self._target_digests(fresh_observation),
                ),
            )
            db.execute(
                "INSERT INTO computer_actions "
                "(action_id,task_id,kind,observation_id,target_digest,risk,state,created_at,completed_at,"
                "outcome,claim_observation_id,target_summary,target_window) "
                "VALUES(?,?,?,?,?,'low','stale',?,?,?,?,?,?)", (
                    action_id, task_id, kind, observation_id, target_digest,
                    now, now, reason, fresh_observation.observation_id,
                    json.dumps(target_summary),
                    json.dumps(target_window) if target_window is not None else None,
                ),
            )
        return self.action(action_id)

    @staticmethod
    def fingerprint(observation: DesktopObservation, element: AccessibleElement) -> str:
        parents = [candidate for candidate in observation.elements
                   if candidate.path != element.path and len(candidate.path) < len(element.path)
                   and element.path[:len(candidate.path)] == candidate.path
                   and candidate.role in {"frame", "window", "dialog"}]
        parent = max(parents, key=lambda candidate: len(candidate.path), default=None)
        payload = {
            "path": element.path, "application": element.application, "role": element.role,
            "name": element.name, "bounds": element.bounds,
            "text_length": element.text_length, "selection": element.selection,
            "window": (parent.application, parent.role, parent.name, parent.bounds) if parent else None,
            "monitors": [(monitor.identity, monitor.bounds, monitor.scale)
                         for monitor in observation.monitors],
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    @classmethod
    def _target_digests(cls, observation: DesktopObservation) -> str:
        return json.dumps([cls.fingerprint(observation, element)
                           for element in observation.elements], separators=(",", ":"))

    @staticmethod
    def _validate_observation(observation: DesktopObservation) -> None:
        if type(observation.complete) is not bool:
            raise ValueError("observation completeness is invalid")
        if not re.fullmatch(r"observation_[a-f0-9]{32}", observation.observation_id):
            raise ValueError("observation ID is invalid")
        if not re.fullmatch(r"[a-f0-9]{64}", observation.digest):
            raise ValueError("observation digest is invalid")

    @staticmethod
    def _within_window(observation: DesktopObservation, element: AccessibleElement,
                       identity: tuple[str, str, str] | None) -> bool:
        if identity is None:
            return False
        windows = [candidate for candidate in observation.elements
                   if (candidate.application, candidate.role, candidate.name) == identity
                   and element.path[:len(candidate.path)] == candidate.path]
        return len(windows) == 1

    def prepare(self, task_id: str, *, kind: str, observation_id: str,
                target_digest: str, risk: str,
                expected_result: tuple[str, str, str] | None = None,
                target_summary: tuple[str, str] | None = None,
                target_window: tuple[str, str, str] | None = None) -> ComputerActionClaim:
        if kind not in _KINDS or risk not in _RISK or not re.fullmatch(r"[a-f0-9]{64}", target_digest):
            raise ValueError("computer action specification is invalid")
        if expected_result is not None:
            if not isinstance(expected_result, tuple) or len(expected_result) != 3:
                raise ValueError("computer expected result is invalid")
            terminal_input_result = (
                kind == "hotkey"
                and expected_result[1:] == ("__vscode_terminal_input__", "focused")
            )
            terminal_after_escape_result = (
                kind == "press_key"
                and expected_result[1:] == ("__vscode_terminal_after_escape__", "focused")
            )
            if ((kind not in {"activate_accessible", "click", "double_click", "right_click"}
                    and not terminal_input_result and not terminal_after_escape_result) or any(
                        not isinstance(part, str) or not part or len(part) > limit
                        for part, limit in zip(expected_result, (128, 64, 256))
                    ) or (expected_result[1] in {
                        "__vscode_terminal_input__", "__vscode_terminal_after_escape__",
                    } and not (terminal_input_result or terminal_after_escape_result))):
                raise ValueError("computer expected result is invalid")
        if target_summary is not None and (
            not isinstance(target_summary, tuple) or len(target_summary) != 2
            or any(not isinstance(part, str) or not part or len(part) > limit
                   for part, limit in zip(target_summary, (1024, 256)))
        ):
            raise ValueError("computer target summary is invalid")
        if target_window is not None and (
            not isinstance(target_window, tuple) or len(target_window) != 3
            or any(not isinstance(part, str) or not part or len(part) > limit
                   for part, limit in zip(target_window, (128, 64, 256)))
            or target_window[1] not in {"frame", "window", "dialog"}
        ):
            raise ValueError("computer target window is invalid")
        action_id = uuid4().hex
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT state,action_count,action_budget,created_at,cancel_requested "
                             "FROM computer_tasks WHERE task_id=?", (task_id,)).fetchone()
            if row is None or row[0] != "active" or row[1] >= row[2] or row[4] or not _recent(row[3], seconds=1800):
                raise ValueError("computer task is unavailable or action budget exhausted")
            observation = db.execute(
                "SELECT target_digests,observed_at FROM computer_observations WHERE observation_id=? AND task_id=?",
                (observation_id, task_id),
            ).fetchone()
            if observation is None:
                raise ValueError("observation does not belong to computer task")
            if not _recent(observation[1], seconds=15):
                raise ValueError("computer observation is too old")
            if (kind in _SEMANTIC_KINDS and observation[0] is not None
                    and target_digest not in json.loads(observation[0])):
                raise ValueError("computer target changed since observation")
            db.execute("INSERT INTO computer_actions "
                       "(action_id,task_id,kind,observation_id,target_digest,risk,state,created_at,"
                       "expected_result,target_summary,target_window) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (
                           action_id, task_id, kind, observation_id, target_digest,
                           risk, "prepared", datetime.now(UTC).isoformat(),
                           json.dumps(expected_result) if expected_result else None,
                           json.dumps(target_summary) if target_summary else None,
                           json.dumps(target_window) if target_window else None,
                       ))
        return self.action(action_id)

    def action(self, action_id: str) -> ComputerActionClaim:
        if not _ID.fullmatch(action_id):
            raise ValueError("computer action is unavailable")
        with self._db() as db:
            row = db.execute(
                "SELECT action_id,task_id,kind,observation_id,target_digest,risk,state,claim_observation_id,expected_result "
                "FROM computer_actions WHERE action_id=?", (action_id,),
            ).fetchone()
        if row is None:
            raise ValueError("computer action is unavailable")
        return ComputerActionClaim(*row)

    def recent_actions(self, task_id: str, *, limit: int = 20) -> tuple[ComputerActionStatus, ...]:
        if not _ID.fullmatch(task_id) or not 1 <= limit <= 20:
            raise ValueError("computer action query is invalid")
        with self._db() as db:
            rows = db.execute(
                "SELECT action_id,kind,state,outcome,created_at,target_summary,expected_result,"
                "execution_started_at,recovery_status,target_window,recovery_observation_id,"
                "actor_return_code,verification_result,verification_match_count,result_observation_id "
                "FROM computer_actions "
                "WHERE task_id=? ORDER BY created_at DESC LIMIT ?", (task_id, limit),
            ).fetchall()
        return tuple(ComputerActionStatus(
            row[0], row[1], row[2], row[3], row[4],
            json.loads(row[5])[0] if row[5] else None,
            json.loads(row[5])[1] if row[5] else None,
            json.loads(row[6])[2] if row[6] else None,
            row[7] is not None, row[8], tuple(json.loads(row[9])) if row[9] else None,
            row[10], row[11], row[12], row[13], row[14],
        ) for row in rows)

    def claim(self, action_id: str, *, fresh_observation: DesktopObservation) -> ComputerActionClaim:
        """Claim once before any physical effect; stale or consequential actions fail."""
        self._validate_observation(fresh_observation)
        if not _recent(fresh_observation.observed_at, seconds=15):
            raise ValueError("fresh computer observation is too old")
        stale = False
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT a.task_id,a.state,a.risk,a.observation_id,t.state,t.action_count,t.action_budget,"
                "o.digest,o.target_digests,a.target_digest,a.kind,t.cancel_requested FROM computer_actions a "
                "JOIN computer_tasks t ON a.task_id=t.task_id "
                "JOIN computer_observations o ON a.observation_id=o.observation_id "
                "WHERE a.action_id=?", (action_id,),
            ).fetchone()
            if row is None or row[1] != "prepared" or row[4] != "active" or row[5] >= row[6] or row[11]:
                raise ValueError("computer action cannot be claimed")
            if row[2] == "consequential":
                raise ValueError("consequential computer action requires canonical approval")
            if fresh_observation.observation_id == row[3]:
                raise ValueError("computer action requires a new observation")
            fresh_targets = self._target_digests(fresh_observation)
            db.execute("INSERT INTO computer_observations "
                       "(observation_id,task_id,observed_at,digest,element_count,monitor_count,target_digests) "
                       "VALUES(?,?,?,?,?,?,?)", (
                fresh_observation.observation_id, row[0], fresh_observation.observed_at,
                fresh_observation.digest, len(fresh_observation.elements),
                len(fresh_observation.monitors), fresh_targets,
            ))
            scoped = row[10] in _SEMANTIC_KINDS and row[8] is not None
            target_changed = scoped and row[9] not in json.loads(fresh_targets)
            whole_desktop_changed = (
                not scoped and row[10] not in _RESOLVED_TARGET_KINDS
                and fresh_observation.digest != row[7]
            )
            if target_changed or whole_desktop_changed:
                db.execute("UPDATE computer_actions SET state='stale',claim_observation_id=? "
                           "WHERE action_id=?", (fresh_observation.observation_id, action_id))
                stale = True
            else:
                db.execute("UPDATE computer_actions SET state='in_flight',claimed_at=?,claim_observation_id=? "
                           "WHERE action_id=?", (
                    datetime.now(UTC).isoformat(), fresh_observation.observation_id, action_id,
                ))
                db.execute("UPDATE computer_tasks SET action_count=action_count+1 WHERE task_id=?", (row[0],))
        if stale:
            raise ValueError("computer observation is stale")
        return self.action(action_id)

    def claim_current(self, action_id: str, *, observation: DesktopObservation) -> ComputerActionClaim:
        """Claim against one freshly recorded state when another scan would age it out."""
        self._validate_observation(observation)
        if not _recent(observation.observed_at, seconds=15):
            raise ValueError("current computer observation is too old")
        stale = False
        with self.execution_guard(), self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT a.task_id,a.state,a.risk,a.observation_id,t.state,t.action_count,"
                "t.action_budget,t.cancel_requested,o.digest,o.target_digests,a.target_digest,a.kind "
                "FROM computer_actions a JOIN computer_tasks t ON a.task_id=t.task_id "
                "JOIN computer_observations o ON a.observation_id=o.observation_id "
                "WHERE a.action_id=?", (action_id,),
            ).fetchone()
            if (row is None or row[1] != "prepared" or row[4] != "active"
                    or row[5] >= row[6] or row[7]):
                raise ValueError("computer action cannot be claimed")
            if row[2] == "consequential":
                raise ValueError("consequential computer action requires canonical approval")
            if observation.observation_id != row[3]:
                raise ValueError("current computer observation does not match the action")
            fresh_targets = self._target_digests(observation)
            scoped = row[11] in _SEMANTIC_KINDS and row[9] is not None
            stale = (observation.digest != row[8]
                     or fresh_targets != row[9]
                     or (scoped and row[10] not in json.loads(fresh_targets)))
            if stale:
                db.execute("UPDATE computer_actions SET state='stale' WHERE action_id=?", (action_id,))
            else:
                db.execute("UPDATE computer_actions SET state='in_flight',claimed_at=?,claim_observation_id=? "
                           "WHERE action_id=?", (
                               datetime.now(UTC).isoformat(), observation.observation_id, action_id,
                           ))
                db.execute("UPDATE computer_tasks SET action_count=action_count+1 WHERE task_id=?",
                           (row[0],))
        if stale:
            raise ValueError("computer observation is stale")
        return self.action(action_id)

    def mark_execution_started(self, action_id: str) -> None:
        """Durably mark the boundary immediately before invoking the physical actor."""
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT a.state,a.execution_started_at,t.state,t.cancel_requested "
                             "FROM computer_actions a "
                             "JOIN computer_tasks t ON t.task_id=a.task_id WHERE a.action_id=?",
                             (action_id,)).fetchone()
            if row is None or row[0] != "in_flight" or row[1] is not None or row[2] != "active" or row[3]:
                raise ValueError("computer action execution cannot start")
            db.execute("UPDATE computer_actions SET execution_started_at=? WHERE action_id=?",
                       (datetime.now(UTC).isoformat(), action_id))

    def finish(self, action_id: str, *, result_observation: DesktopObservation | None,
               verified: bool, outcome: str, actor_return_code: int | None = None,
               verification_result: str | None = None,
               verification_match_count: int | None = None) -> ComputerActionClaim:
        if (outcome not in _OUTCOMES or verified != (outcome == "postcondition_verified")
                or (verified and result_observation is None)
                or (actor_return_code is not None and (
                    type(actor_return_code) is not int or not -255 <= actor_return_code <= 255
                ))
                or (verification_result is not None and verification_result not in _VERIFICATION_RESULTS)
                or (verification_match_count is not None and (
                    type(verification_match_count) is not int or not 0 <= verification_match_count <= 200
                ))
                or ((verification_result is None) != (verification_match_count is None))):
            raise ValueError("computer action outcome is invalid")
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT task_id,state FROM computer_actions WHERE action_id=?", (action_id,)).fetchone()
            if row is None or row[1] != "in_flight":
                raise ValueError("computer action is not in flight")
            task_id = row[0]
            if result_observation is not None:
                db.execute("INSERT INTO computer_observations "
                           "(observation_id,task_id,observed_at,digest,element_count,monitor_count,target_digests) "
                           "VALUES(?,?,?,?,?,?,?)", (
                    result_observation.observation_id, task_id, result_observation.observed_at,
                    result_observation.digest, len(result_observation.elements), len(result_observation.monitors),
                    self._target_digests(result_observation),
                ))
            state = "verified" if verified and result_observation is not None else "failed"
            db.execute("UPDATE computer_actions SET state=?,completed_at=?,result_observation_id=?,outcome=?,"
                       "actor_return_code=?,verification_result=?,verification_match_count=? "
                       "WHERE action_id=?", (
                           state, datetime.now(UTC).isoformat(),
                           result_observation.observation_id if result_observation else None,
                           outcome, actor_return_code, verification_result,
                           verification_match_count, action_id,
                       ))
        return self.action(action_id)

    def mark_in_doubt(self, action_id: str, *,
                      result_observation: DesktopObservation | None = None,
                      actor_return_code: int | None = None,
                      verification_result: str | None = None,
                      verification_match_count: int | None = None) -> ComputerActionClaim:
        """Transport may have acted before its result was lost; never replay it."""
        if (actor_return_code is not None and (
                type(actor_return_code) is not int or not -255 <= actor_return_code <= 255
            )):
            raise ValueError("computer action outcome is invalid")
        if verification_result is not None and verification_result not in _VERIFICATION_RESULTS:
            raise ValueError("computer action outcome is invalid")
        if (verification_match_count is not None and (
                type(verification_match_count) is not int or not 0 <= verification_match_count <= 200
            )):
            raise ValueError("computer action outcome is invalid")
        if (verification_result is None) != (verification_match_count is None):
            raise ValueError("computer action outcome is invalid")
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT task_id,state FROM computer_actions WHERE action_id=?",
                             (action_id,)).fetchone()
            if row is None or row[1] != "in_flight":
                raise ValueError("computer action is not in flight")
            if result_observation is not None:
                db.execute("INSERT INTO computer_observations "
                           "(observation_id,task_id,observed_at,digest,element_count,monitor_count,target_digests) "
                           "VALUES(?,?,?,?,?,?,?)", (
                    result_observation.observation_id, row[0], result_observation.observed_at,
                    result_observation.digest, len(result_observation.elements), len(result_observation.monitors),
                    self._target_digests(result_observation),
                ))
            db.execute("UPDATE computer_actions SET state='in_doubt',completed_at=?,outcome='interrupted',"
                       "result_observation_id=?,actor_return_code=?,verification_result=?,"
                       "verification_match_count=? WHERE action_id=?", (
                           datetime.now(UTC).isoformat(),
                           result_observation.observation_id if result_observation else None,
                           actor_return_code, verification_result, verification_match_count, action_id,
                       ))
            db.execute("UPDATE computer_tasks SET state='recovery_required' "
                       "WHERE task_id=? AND state='active'", (row[0],))
        return self.action(action_id)

    def reconcile_visible_result(self, action_id: str,
                                 observation: DesktopObservation) -> bool:
        """Record a positive post-crash result without replaying or resuming the task."""
        self._validate_observation(observation)
        if not _recent(observation.observed_at, seconds=15):
            raise ValueError("recovery observation is too old")
        with self.execution_guard(), self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT a.task_id,a.state,a.expected_result,t.state,a.target_window FROM computer_actions a "
                "JOIN computer_tasks t ON t.task_id=a.task_id WHERE a.action_id=?",
                (action_id,),
            ).fetchone()
            if row is None or row[3] != "recovery_required" or row[1] not in {"in_doubt", "result_present"}:
                raise ValueError("computer action is not awaiting recovery")
            if row[1] == "result_present":
                return True
            if row[2] is None:
                return False
            application, role, name = json.loads(row[2])
            target_window = tuple(json.loads(row[4])) if row[4] else None
            if role in {
                "__vscode_terminal_input__", "__vscode_terminal_after_escape__",
            }:
                matches = [element for element in observation.elements
                           if element.application == application
                           and element.role in {"entry", "text entry", "text"}
                           and element.focused
                           and re.match(r"^terminal\s+\d+\s*,", element.name, re.I)
                           and self._within_window(observation, element, target_window)]
            else:
                matches = [element for element in observation.elements
                           if element.application == application and element.name == name
                           and (role == "*" or element.role == role)
                           and self._within_window(observation, element, target_window)]
            db.execute("INSERT INTO computer_observations "
                       "(observation_id,task_id,observed_at,digest,element_count,monitor_count,target_digests) "
                       "VALUES(?,?,?,?,?,?,?)", (
                observation.observation_id, row[0], observation.observed_at,
                observation.digest, len(observation.elements), len(observation.monitors),
                self._target_digests(observation),
            ))
            if len(matches) != 1:
                db.execute("UPDATE computer_actions SET recovery_observation_id=?,recovery_status=? "
                           "WHERE action_id=?", (
                    observation.observation_id,
                    "window_unbound" if target_window is None else
                    "not_observed" if not matches else "ambiguous", action_id,
                ))
                return False
            db.execute("UPDATE computer_actions SET state='result_present',outcome='result_present_after_recovery',"
                       "result_observation_id=?,recovery_observation_id=?,recovery_status='result_present',"
                       "completed_at=? WHERE action_id=?", (
                observation.observation_id, observation.observation_id,
                datetime.now(UTC).isoformat(), action_id,
            ))
        return True

    def resume_native_plan(self, task_id: str, *, step_count: int,
                           fresh_observation: DesktopObservation | None = None) -> int:
        """Resume only a paused native plan with no unaccounted physical effect."""
        if not _ID.fullmatch(task_id) or not 1 <= step_count <= 3:
            raise ValueError("native task cannot be resumed")
        with self.execution_guard(), self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            task = db.execute("SELECT state,cancel_requested,action_count,action_budget "
                              "FROM computer_tasks WHERE task_id=?", (task_id,)).fetchone()
            actions = db.execute("SELECT action_id,kind,state,execution_started_at,expected_result,target_window "
                                 "FROM computer_actions WHERE task_id=? AND state NOT IN ('prepared','stale') "
                                 "ORDER BY rowid", (task_id,)).fetchall()
            if (task is None or task[0] != "recovery_required" or task[1]
                    or not actions or len(actions) > step_count):
                raise ValueError("native task cannot be resumed")
            prefix, last = actions[:-1], actions[-1]
            if (any(row[1] != "activate_accessible" or row[2] != "verified" for row in prefix)
                    or last[1] != "activate_accessible"
                    or not (last[2] == "result_present" and last[4] is not None
                            or last[2] == "in_doubt" and last[3] is None)):
                raise ValueError("native action outcome cannot be resumed safely")
            completed = len(prefix) + (last[2] == "result_present")
            if completed < step_count and task[2] >= task[3]:
                raise ValueError("native task action budget is exhausted")
            if last[2] == "result_present":
                if fresh_observation is None:
                    raise ValueError("fresh result evidence is required to resume")
                self._validate_observation(fresh_observation)
                if not _recent(fresh_observation.observed_at, seconds=15):
                    raise ValueError("fresh result evidence is too old")
                application, role, name = json.loads(last[4])
                window = tuple(json.loads(last[5])) if last[5] else None
                if window is None:
                    raise ValueError("recovered action has no trusted window binding")
                matches = [element for element in fresh_observation.elements
                           if element.application == application and element.name == name
                           and (role == "*" or element.role == role)
                           and self._within_window(fresh_observation, element, window)]
                if len(matches) != 1:
                    raise ValueError("recovered result is no longer uniquely visible")
                db.execute("INSERT INTO computer_observations "
                           "(observation_id,task_id,observed_at,digest,element_count,monitor_count,target_digests) "
                           "VALUES(?,?,?,?,?,?,?)", (
                    fresh_observation.observation_id, task_id, fresh_observation.observed_at,
                    fresh_observation.digest, len(fresh_observation.elements),
                    len(fresh_observation.monitors), self._target_digests(fresh_observation),
                ))
                db.execute("UPDATE computer_actions SET recovery_observation_id=? WHERE action_id=?",
                           (fresh_observation.observation_id, last[0]))
            if last[2] == "in_doubt":
                db.execute("UPDATE computer_actions SET state='not_executed',"
                           "outcome='interrupted_before_execution' WHERE action_id=?", (last[0],))
            db.execute("UPDATE computer_tasks SET state='active' WHERE task_id=?", (task_id,))
        return int(completed)

    def cancel(self, task_id: str) -> ComputerTask:
        current = self.task(task_id)
        if current.state == "awaiting_clarification":
            return self.cancel_clarification(task_id, current.owner_id)
        self.request_cancel(task_id)
        with self.execution_guard(), self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT state FROM computer_tasks WHERE task_id=?", (task_id,)).fetchone()
            if row is None or row[0] not in {"active", "recovery_required"}:
                raise ValueError("computer task cannot be cancelled")
            db.execute("UPDATE computer_tasks SET state='cancelled' WHERE task_id=?", (task_id,))
            db.execute("UPDATE computer_actions SET state='cancelled' "
                       "WHERE task_id=? AND state='prepared'", (task_id,))
        return self.task(task_id)

    def request_cancel(self, task_id: str) -> None:
        """Persist Stop intent immediately without waiting for an active action guard."""
        if not _ID.fullmatch(task_id):
            raise ValueError("computer task cannot be cancelled")
        with self._db() as db:
            changed = db.execute("UPDATE computer_tasks SET cancel_requested=1 "
                                 "WHERE task_id=? AND state IN ('active','recovery_required')",
                                 (task_id,)).rowcount
            if changed != 1:
                raise ValueError("computer task cannot be cancelled")

    def cancellation_requested(self, task_id: str) -> bool:
        """Read the durable stop intent without waiting for the action guard."""
        if not _ID.fullmatch(task_id):
            raise ValueError("computer task is unavailable")
        with self._db() as db:
            row = db.execute(
                "SELECT state,cancel_requested FROM computer_tasks WHERE task_id=?",
                (task_id,),
            ).fetchone()
        if row is None:
            raise ValueError("computer task is unavailable")
        return row[0] != "active" or bool(row[1])

    def cancel_active_tasks(self) -> tuple[str, ...]:
        """Emergency stop all local computer tasks, including recovery review."""
        task_ids = self.request_cancel_active_tasks()
        with self.execution_guard(), self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            placeholders = ",".join("?" for _ in task_ids)
            if task_ids:
                db.execute(f"UPDATE computer_tasks SET state='cancelled' WHERE task_id IN ({placeholders})",
                           task_ids)
            if task_ids:
                db.execute(f"UPDATE computer_actions SET state='cancelled' "
                           f"WHERE state='prepared' AND task_id IN ({placeholders})", task_ids)
                db.execute(f"UPDATE computer_clarifications SET status='cancelled' "
                           f"WHERE status='awaiting_answer' AND task_id IN ({placeholders})", task_ids)
        return task_ids

    def request_cancel_active_tasks(self) -> tuple[str, ...]:
        """Persist global Stop requests without waiting for an action to finish."""
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute(
                "SELECT task_id FROM computer_tasks "
                "WHERE state IN ('active','recovery_required','awaiting_clarification')"
            ).fetchall()
            task_ids = tuple(row[0] for row in rows)
            db.execute("UPDATE computer_tasks SET cancel_requested=1 "
                       "WHERE state IN ('active','recovery_required','awaiting_clarification')")
            db.execute("COMMIT")
        return task_ids

    def complete(self, task_id: str, *, succeeded: bool,
                 failure_reason: str | None = None) -> ComputerTask:
        if succeeded:
            if failure_reason is not None:
                raise ValueError("successful computer task cannot have a failure reason")
        elif failure_reason is None:
            failure_reason = "execution_failed"
        if failure_reason is not None and failure_reason not in _TASK_FAILURE_REASONS:
            raise ValueError("computer task failure reason is invalid")
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT state,cancel_requested FROM computer_tasks WHERE task_id=?",
                             (task_id,)).fetchone()
            in_flight = db.execute("SELECT 1 FROM computer_actions WHERE task_id=? AND state='in_flight'",
                                   (task_id,)).fetchone()
            if row is None or row[0] != "active" or row[1] or in_flight is not None:
                raise ValueError("computer task cannot be completed")
            db.execute("UPDATE computer_tasks SET state=?,failure_reason=? WHERE task_id=?",
                       ("succeeded" if succeeded else "failed", failure_reason, task_id))
            db.execute("UPDATE computer_actions SET state='cancelled' "
                       "WHERE task_id=? AND state='prepared'", (task_id,))
        return self.task(task_id)

    def recover_in_flight(self) -> int:
        """On restart, never replay an action whose physical outcome is unknown."""
        with self.execution_guard(), self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute("SELECT DISTINCT task_id FROM computer_actions WHERE state='in_flight'").fetchall()
            db.execute("UPDATE computer_actions SET state='in_doubt',completed_at=?,outcome='interrupted' "
                       "WHERE state='in_flight'", (datetime.now(UTC).isoformat(),))
            for (task_id,) in rows:
                db.execute("UPDATE computer_tasks SET state='recovery_required' "
                           "WHERE task_id=? AND state='active'", (task_id,))
        return len(rows)
