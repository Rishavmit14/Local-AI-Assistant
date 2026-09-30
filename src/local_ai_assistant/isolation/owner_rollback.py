"""Owner-reviewed, one-time rollback operations over the transactional kernel."""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from local_ai_assistant.history.models import TERMINAL_STATUSES
from local_ai_assistant.history.service import TaskHistoryService
from local_ai_assistant.isolation.checkpoints import CheckpointManager, _git
from local_ai_assistant.isolation.models import WorktreeState
from local_ai_assistant.isolation.recovery import inspect_recovery
from local_ai_assistant.isolation.transactional_rollback import (
    TransactionalRollbackService,
    worktree_fingerprint,
)
from local_ai_assistant.isolation.worktrees import WorktreeManager


class OwnerBrowserSessions:
    """Volatile short-lived owner sessions; process restart revokes all sessions."""
    def __init__(self, token_hash: str, *, lifetime_seconds: int = 600):
        if len(token_hash) != 64 or any(c not in "0123456789abcdefABCDEF" for c in token_hash):
            raise ValueError("owner rollback token digest must be SHA-256 hex")
        self._token_hash = token_hash.lower()
        self._sessions: dict[str, tuple[str, float]] = {}
        self.lifetime = lifetime_seconds
        self._failures: dict[str, list[float]] = {}

    def unlock(self, token: str, client: str = "local") -> tuple[str, str] | None:
        now = time.monotonic()
        failures = [stamp for stamp in self._failures.get(client, []) if now - stamp < 60]
        self._failures[client] = failures
        if len(failures) >= 5:
            raise RuntimeError("rate limited")
        if not hmac.compare_digest(hashlib.sha256(token.encode()).hexdigest(), self._token_hash):
            failures.append(now)
            self._failures[client] = failures
            return None
        self._sessions = {key: value for key, value in self._sessions.items() if value[1] > now}
        if len(self._sessions) >= 128:
            self._sessions.pop(next(iter(self._sessions)))
        session, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        self._sessions[hashlib.sha256(session.encode()).hexdigest()] = (hashlib.sha256(csrf.encode()).hexdigest(), time.monotonic() + self.lifetime)
        return session, csrf

    def principal(self, session: str | None, csrf: str | None = None) -> str | None:
        if not session:
            return None
        key = hashlib.sha256(session.encode()).hexdigest()
        value = self._sessions.get(key)
        if not value or value[1] <= time.monotonic():
            self._sessions.pop(key, None)
            return None
        if csrf is not None and not hmac.compare_digest(value[0], hashlib.sha256(csrf.encode()).hexdigest()):
            return None
        return "local-owner"

    def revoke(self, session: str | None) -> None:
        if session:
            self._sessions.pop(hashlib.sha256(session.encode()).hexdigest(), None)


# Compatibility name for the existing rollback-only integration.
OwnerRollbackSessions = OwnerBrowserSessions


class OwnerRollbackService:
    def __init__(self, history: TaskHistoryService, worktrees: WorktreeManager,
                 checkpoints: CheckpointManager, transactional: TransactionalRollbackService,
                 *, review_seconds: int = 90):
        self.history, self.worktrees, self.checkpoints = history, worktrees, checkpoints
        self.transactional, self.review_seconds = transactional, review_seconds

    def available(self, task_id: str) -> list[dict]:
        task = self.history.get(task_id)
        if task is None:
            raise KeyError(task_id)
        identity = self.worktrees.load(Path(task.repository), task_id, plan_hash=task.plan_hash)
        worktree = Path(identity.worktree)
        head = _git(worktree, "rev-parse", "HEAD")
        recovery = any(item.task_id == task_id for item in inspect_recovery(self.worktrees.root))
        protected = {Path("/AI/projects/Local-AI-Assistant").resolve(),
                     Path("/AI/projects/Local-AI-Assistant-terra-integration").resolve()}
        eligible = (identity.state in {WorktreeState.READY, WorktreeState.FAILED}
                    and task.status not in TERMINAL_STATUSES and not recovery
                    and Path(task.repository).resolve() not in protected)
        result = []
        root = self.checkpoints.root / task_id
        if root.is_dir() and not root.is_symlink():
            for directory in sorted(root.iterdir()):
                if not directory.is_dir() or directory.is_symlink():
                    continue
                try:
                    record = self.checkpoints.load(task_id, directory.name, task.plan_hash)
                except Exception:
                    continue
                if record.schema_version != 2:
                    continue
                result.append({"task_id": task_id, "checkpoint_id": record.checkpoint_id,
                    "label": directory.name, "created_at": record.created_at,
                    "plan_hash": task.plan_hash[:12], "head": record.head[:12],
                    "schema_version": 2,
                    "eligible": eligible and record.head == head,
                    "reason": None if eligible and record.head == head else
                    ("recovery_required" if recovery else "task_or_checkpoint_state_ineligible")})
        return result

    def review(self, task_id: str, checkpoint_id: str, principal: str) -> dict:
        matches = [item for item in self.available(task_id) if item["checkpoint_id"] == checkpoint_id]
        if len(matches) != 1 or not matches[0]["eligible"]:
            raise ValueError("checkpoint is not eligible for rollback")
        item = matches[0]
        task = self.history.get(task_id)
        identity = self.worktrees.load(Path(task.repository), task_id, plan_hash=task.plan_hash)
        fingerprint = worktree_fingerprint(Path(identity.worktree))
        now = datetime.now(UTC)
        operation_id = uuid.uuid4().hex
        expires = now + timedelta(seconds=self.review_seconds)
        with self.history.store.transaction() as db:
            db.execute("INSERT INTO rollback_operations(operation_id,task_id,checkpoint_id,plan_hash,principal,state,fingerprint,created_at,expires_at) VALUES (?,?,?,?,?,'reviewed',?,?,?)",
                (operation_id, task_id, checkpoint_id, task.plan_hash, principal, fingerprint, now.isoformat(), expires.isoformat()))
        return {"operation_id": operation_id, "task_id": task_id, "checkpoint_id": checkpoint_id,
                "plan_hash": task.plan_hash[:12], "head": item["head"], "expires_at": expires.isoformat(),
                "action": "restore_exact_checkpoint_in_isolated_task_worktree"}

    def execute(self, operation_id: str, principal: str, idempotency_key: str) -> dict:
        if not idempotency_key or len(idempotency_key) > 128:
            raise ValueError("valid idempotency key required")
        row = self._row(operation_id)
        if row is None or row["principal"] != principal:
            raise KeyError(operation_id)
        if row["state"] in {"succeeded", "failed_recovered", "recovery_required"} and row["idempotency_key"] == idempotency_key:
            return json.loads(row["result_json"] or "{}")
        if row["state"] == "executing" and row["idempotency_key"] == idempotency_key:
            recovered = self._recover_result(row)
            if recovered is not None:
                return recovered
        if row["state"] != "reviewed":
            raise ValueError("rollback review expired, stale, or already consumed")
        if datetime.fromisoformat(row["expires_at"]) <= datetime.now(UTC):
            self._mark(operation_id, "expired")
            raise ValueError("rollback review expired")
        task = self.history.get(row["task_id"])
        if task is None or task.plan_hash != row["plan_hash"]:
            self._mark(operation_id, "stale")
            raise ValueError("rollback review is stale")
        candidates = [x for x in self.available(row["task_id"]) if x["checkpoint_id"] == row["checkpoint_id"] and x["eligible"]]
        identity = self.worktrees.load(Path(task.repository), row["task_id"], plan_hash=task.plan_hash)
        if len(candidates) != 1 or worktree_fingerprint(Path(identity.worktree)) != row["fingerprint"]:
            self._mark(operation_id, "stale")
            raise ValueError("rollback review is stale")
        with self.history.store.transaction() as db:
            changed = db.execute("UPDATE rollback_operations SET state='executing',idempotency_key=? WHERE operation_id=? AND state='reviewed'",
                (idempotency_key, operation_id)).rowcount
            if changed != 1:
                raise ValueError("rollback review already consumed")
        labels = [item["label"] for item in candidates]
        result = self.transactional.restore(
            Path(task.repository), row["task_id"], row["plan_hash"], labels[0],
            expected_current_state=row["fingerprint"], operation_id=operation_id,
        )
        payload = {"operation_id": operation_id, "task_id": row["task_id"], "checkpoint_id": row["checkpoint_id"], "status": result.status}
        state = {"restored": "succeeded", "failed_recovered": "failed_recovered", "recovery_required": "recovery_required"}[result.status]
        with self.history.store.transaction() as db:
            db.execute("UPDATE rollback_operations SET state=?,result_json=? WHERE operation_id=? AND state='executing'",
                (state, json.dumps(payload, sort_keys=True), operation_id))
        return payload

    def _recover_result(self, row) -> dict | None:
        outcome = {
            "rollback_restore_succeeded": "restored",
            "rollback_failed_recovered": "failed_recovered",
            "rollback_recovery_required": "recovery_required",
        }
        for event in reversed(self.history.timeline(row["task_id"])):
            if (event.event_type in outcome
                    and event.metadata.get("owner_operation_id") == row["operation_id"]):
                payload = {"operation_id": row["operation_id"], "task_id": row["task_id"],
                           "checkpoint_id": row["checkpoint_id"], "status": outcome[event.event_type]}
                with self.history.store.transaction() as db:
                    db.execute("UPDATE rollback_operations SET state=?,result_json=? WHERE operation_id=? AND state='executing'",
                               ({"restored": "succeeded", "failed_recovered": "failed_recovered", "recovery_required": "recovery_required"}[payload["status"]],
                                json.dumps(payload, sort_keys=True), row["operation_id"]))
                return payload
        return None

    def recent(self, task_id: str, principal: str) -> list[dict]:
        with self.history.store._connect() as db:
            rows = db.execute(
                "SELECT operation_id,checkpoint_id,state,created_at,expires_at,result_json FROM rollback_operations WHERE task_id=? AND principal=? ORDER BY created_at DESC LIMIT 20",
                (task_id, principal),
            ).fetchall()
        return [{"operation_id": row[0], "checkpoint_id": row[1], "state": row[2],
                 "created_at": row[3], "expires_at": row[4],
                 "result": json.loads(row[5]) if row[5] else None} for row in rows]

    def _row(self, operation_id: str):
        with self.history.store._connect() as db:
            db.row_factory = __import__("sqlite3").Row
            return db.execute("SELECT * FROM rollback_operations WHERE operation_id=?", (operation_id,)).fetchone()

    def _mark(self, operation_id: str, state: str) -> None:
        with self.history.store.transaction() as db:
            db.execute("UPDATE rollback_operations SET state=? WHERE operation_id=? AND state='reviewed'", (state, operation_id))
