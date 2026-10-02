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
from uuid import UUID

from local_ai_assistant.history.models import TERMINAL_STATUSES, TaskStatus
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
                 *, review_seconds: int = 90, worker_status=None):
        self.history, self.worktrees, self.checkpoints = history, worktrees, checkpoints
        self.transactional, self.review_seconds = transactional, review_seconds
        self.worker_status = worker_status

    def reconcile_validation_failure(
        self, task_id: str, plan_hash: str, idempotency_key: str, principal: str,
    ) -> dict:
        """Owner-authorized checkpoint rollback for a failed validation worker."""
        try:
            UUID(idempotency_key)
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("a UUID reconciliation idempotency key is required") from exc
        task = self.history.get(task_id)
        if task is None or task.plan_hash != plan_hash:
            raise ValueError("the exact current task and approved plan are required")
        if task.status is TaskStatus.EXECUTING:
            return self.reconcile_failed_retry_setup(task_id, plan_hash, idempotency_key)
        events = self.history.timeline(task_id)
        completed = next((
            event for event in reversed(events)
            if event.event_type == "validation_failure_checkpoint_rollback_completed"
            and event.metadata.get("idempotency_key") == idempotency_key
        ), None)
        if completed:
            self._record_validation_failure_rollback(
                operation_id=str(completed.metadata.get("operation_id", "")),
                task_id=task_id, checkpoint_id=str(completed.metadata.get("checkpoint_id", "")),
                plan_hash=plan_hash, principal=principal,
                idempotency_key=idempotency_key,
                fingerprint=self._validation_failure_fingerprint(events, idempotency_key),
                state="succeeded",
            )
            return {"task_id": task_id, "plan_hash": plan_hash,
                    "status": self.history.get(task_id).status.value,
                    "checkpoint_id": completed.metadata.get("checkpoint_id"),
                    "duplicate": True}
        prior_start = next((
            event for event in reversed(events)
            if event.event_type == "validation_failure_checkpoint_rollback_started"
            and event.metadata.get("idempotency_key") == idempotency_key
        ), None)
        if task.status is TaskStatus.ROLLED_BACK and prior_start:
            operation_id = prior_start.metadata.get("operation_id")
            restored_event = next((
                event for event in reversed(events)
                if event.event_type == "rollback_restore_succeeded"
                and event.metadata.get("owner_operation_id") == operation_id
            ), None)
            if not restored_event:
                raise ValueError("terminal task lacks verified checkpoint restore evidence")
            checkpoint_id = prior_start.metadata.get("checkpoint_id")
            self._record_validation_failure_rollback(
                operation_id=str(operation_id), task_id=task_id,
                checkpoint_id=str(checkpoint_id), plan_hash=plan_hash,
                principal=principal, idempotency_key=idempotency_key,
                fingerprint=str(prior_start.metadata.get("workspace_fingerprint", "")),
                state="succeeded",
            )
            identity = self.worktrees.load(
                Path(task.repository), task_id,
                starting_commit=task.starting_commit, plan_hash=plan_hash,
            )
            if identity.state is not WorktreeState.CLEANED:
                if identity.state is not WorktreeState.ROLLED_BACK:
                    identity = self.worktrees.transition(identity, WorktreeState.ROLLED_BACK)
                self.worktrees.cleanup(identity, delete_branch=False)
            self.history.store.add_event(
                task_id, "recovery", "validation_failure_checkpoint_rollback_completed",
                "Failed validation attempt preserved and baseline checkpoint restored",
                artifact_id=prior_start.metadata.get("attempt_id"), status="rolled_back",
                metadata={"plan_hash": plan_hash,
                          "attempt_id": prior_start.metadata.get("attempt_id"),
                          "checkpoint_id": checkpoint_id, "operation_id": operation_id,
                          "idempotency_key": idempotency_key, "principal": principal},
            )
            return {"task_id": task_id, "plan_hash": plan_hash,
                    "attempt_id": prior_start.metadata.get("attempt_id"),
                    "checkpoint_id": checkpoint_id, "status": "rolled_back",
                    "duplicate": True}
        if task.status not in {
            TaskStatus.VALIDATING, TaskStatus.REVIEWING, TaskStatus.RECOVERY_REQUIRED,
        }:
            raise ValueError("task is not in a failed validation recovery state")
        if task.approval_state != "explicitly_approved":
            raise ValueError("the exact plan is not explicitly approved")
        attempts = self.history.store.execution_attempts(task_id)
        if not attempts:
            raise ValueError("no canonical execution attempt is recorded")
        attempt = attempts[-1]
        if (attempt["plan_hash"] != plan_hash or attempt["state"] != "failed"
                or not attempt.get("failure_type")):
            raise ValueError("latest execution attempt is not a failed exact-plan attempt")
        validation_started = any(
            event.event_type == "status_changed" and event.subsystem == "validation"
            and event.status == TaskStatus.VALIDATING.value
            for event in events
        )
        failure_recorded = any(
            event.event_type == "execution_attempt_failed"
            and event.status == "failed"
            and event.metadata.get("attempt_id") == attempt["attempt_id"]
            and event.metadata.get("failure_type") == attempt["failure_type"]
            for event in events
        )
        if not validation_started or not failure_recorded:
            raise ValueError("validation start and matching failed-attempt audit events are required")
        worker = self.worker_status(task_id) if self.worker_status else None
        worker_state = worker.get("status") if isinstance(worker, dict) else None
        if worker_state not in {"failed", "process_replaced"}:
            raise ValueError("authoritative worker evidence does not prove termination")
        claims = self.history.store.task_claims(task_id)
        if claims.get("execution") is not None:
            raise ValueError("execution claim must be reconciled before checkpoint rollback")
        artifacts = self.history.artifacts(task_id)
        execution_rows = artifacts.get("executions", [])
        prior_attempt_ids = {item["attempt_id"] for item in attempts[:-1]}
        if any(row["run_id"] == attempt["attempt_id"] for row in execution_rows):
            raise ValueError("failed validation attempt already has a persisted execution artifact")
        if any(row["run_id"] not in prior_attempt_ids or row["status"] != "rolled_back"
               for row in execution_rows):
            raise ValueError("historical execution artifacts are not all tied to prior rolled-back attempts")
        if artifacts.get("validations") or artifacts.get("reviews"):
            previous_artifacts = [item for item in attempts[:-1]
                                  if any(row["run_id"] == item["attempt_id"] for row in execution_rows)]
            if not previous_artifacts:
                raise ValueError("historical validation evidence cannot be tied to a rolled-back attempt")
            # Reuse the same strict digest, plan/base/worktree, failure-only,
            # import-window and embedded-review checks as rolled-back retry admission.
            from local_ai_assistant.gateway.recovery import TaskExecutionRetryService

            TaskExecutionRetryService(self.history, None, None, self.worktrees.root)._allow_only_failed_rollback_validation(
                task, previous_artifacts[-1], artifacts,
                additional_failed_attempt=attempt,
            )
        isolation_events = [event for event in events if event.subsystem == "isolation"]

        identity = self.worktrees.load(
            Path(task.repository), task_id,
            starting_commit=task.starting_commit, plan_hash=plan_hash,
        )
        allowed_states = {WorktreeState.EXECUTING, WorktreeState.VALIDATING,
                          WorktreeState.RECOVERY_REQUIRED}
        if identity.state not in allowed_states:
            raise ValueError("task worktree is not in a recoverable validation lifecycle")
        checkpoint = self.checkpoints.load(task_id, "baseline", plan_hash)
        if checkpoint.head != task.starting_commit:
            raise ValueError("baseline checkpoint does not match the approved starting commit")
        canonical = Path(task.repository).resolve(strict=True)
        if canonical in {Path("/AI/projects/Local-AI-Assistant").resolve(),
                         Path("/AI/projects/Local-AI-Assistant-terra-integration").resolve()}:
            raise ValueError("protected Friday repositories cannot use task rollback")
        from .transactional_rollback import worktree_fingerprint
        fingerprint = worktree_fingerprint(Path(identity.worktree))

        if any(
            "rollback" in event.event_type
            and datetime.fromisoformat(event.timestamp) >= datetime.fromisoformat(attempt["created_at"])
            and event.metadata.get("owner_operation_id") != (prior_start.metadata.get("operation_id") if prior_start else None)
            for event in isolation_events
        ):
            raise ValueError("an earlier unrelated rollback operation requires inspection")
        if prior_start:
            if (prior_start.metadata.get("plan_hash") != plan_hash
                    or prior_start.metadata.get("attempt_id") != attempt["attempt_id"]):
                raise ValueError("idempotency key is bound to different failure evidence")
            checkpoint_id = prior_start.metadata.get("checkpoint_id")
            operation_id = prior_start.metadata.get("operation_id")
        else:
            checkpoint_id = checkpoint.checkpoint_id
            operation_id = uuid.uuid4().hex
            self.history.store.add_event(
                task_id, "recovery", "validation_failure_checkpoint_rollback_started",
                "Owner-authorized rollback started for failed validation/repair worker",
                artifact_id=attempt["attempt_id"], status="rollback_started",
                metadata={"plan_hash": plan_hash, "attempt_id": attempt["attempt_id"],
                          "failure_type": attempt["failure_type"], "worker_state": worker_state,
                          "checkpoint_id": checkpoint_id, "operation_id": operation_id,
                          "idempotency_key": idempotency_key,
                          "workspace_fingerprint": fingerprint, "principal": principal},
            )
        fingerprint = str(prior_start.metadata.get("workspace_fingerprint", fingerprint)) if prior_start else fingerprint
        self._record_validation_failure_rollback(
            operation_id=operation_id, task_id=task_id, checkpoint_id=checkpoint_id,
            plan_hash=plan_hash, principal=principal, idempotency_key=idempotency_key,
            fingerprint=fingerprint, state="executing",
        )
        if task.status in {TaskStatus.VALIDATING, TaskStatus.REVIEWING}:
            self.history.transition(
                task_id, TaskStatus.RECOVERY_REQUIRED,
                "Failed validation worker terminated; exact checkpoint rollback is required",
                subsystem="recovery",
            )
        current_identity = self.worktrees.load(
            canonical, task_id, starting_commit=task.starting_commit, plan_hash=plan_hash,
        )
        if current_identity.state is not WorktreeState.RECOVERY_REQUIRED:
            current_identity = self.worktrees.transition(
                current_identity, WorktreeState.RECOVERY_REQUIRED
            )
        current_fingerprint = worktree_fingerprint(Path(current_identity.worktree))
        restore_already_recorded = any(
            event.event_type == "rollback_restore_succeeded"
            and event.metadata.get("owner_operation_id") == operation_id
            for event in isolation_events
        )
        if not restore_already_recorded:
            rollback = self.transactional.restore(
                canonical, task_id, plan_hash, "baseline",
                expected_current_state=current_fingerprint, operation_id=operation_id,
            )
            if rollback.status != "restored":
                state = "failed_recovered" if rollback.status == "failed_recovered" else "recovery_required"
                self._record_validation_failure_rollback(
                    operation_id=operation_id, task_id=task_id, checkpoint_id=checkpoint_id,
                    plan_hash=plan_hash, principal=principal, idempotency_key=idempotency_key,
                    fingerprint=fingerprint, state=state,
                    result={"operation_id": operation_id, "task_id": task_id,
                            "checkpoint_id": checkpoint_id, "status": rollback.status},
                )
                raise RuntimeError("checkpoint restore did not complete; task remains recovery-required")
        self._record_validation_failure_rollback(
            operation_id=operation_id, task_id=task_id, checkpoint_id=checkpoint_id,
            plan_hash=plan_hash, principal=principal, idempotency_key=idempotency_key,
            fingerprint=fingerprint, state="succeeded",
            result={"operation_id": operation_id, "task_id": task_id,
                    "checkpoint_id": checkpoint_id, "status": "restored"},
        )
        restored = self.worktrees.load(
            canonical, task_id, starting_commit=task.starting_commit, plan_hash=plan_hash,
        )
        self.worktrees.transition(restored, WorktreeState.ROLLED_BACK)
        self.history.finalize(
            task_id, canonical, TaskStatus.ROLLED_BACK,
            final_commit=task.starting_commit,
            decision="rolled_back",
            outcome="Validation repair worker failed; exact baseline checkpoint restored.",
            failure_reason=f"{attempt['failure_type']} during validation/repair",
        )
        self.worktrees.cleanup(
            self.worktrees.load(canonical, task_id, plan_hash=plan_hash),
            delete_branch=False,
        )
        self.history.store.add_event(
            task_id, "recovery", "validation_failure_checkpoint_rollback_completed",
            "Failed validation attempt preserved and baseline checkpoint restored",
            artifact_id=attempt["attempt_id"], status="rolled_back",
            metadata={"plan_hash": plan_hash, "attempt_id": attempt["attempt_id"],
                      "checkpoint_id": checkpoint_id, "operation_id": operation_id,
                      "idempotency_key": idempotency_key, "principal": principal},
        )
        return {"task_id": task_id, "plan_hash": plan_hash,
                "attempt_id": attempt["attempt_id"], "checkpoint_id": checkpoint_id,
                "status": "rolled_back", "worker_state": worker_state,
                "duplicate": False}

    def reconcile_failed_retry_setup(self, task_id: str, plan_hash: str, idempotency_key: str) -> dict:
        """Reconcile a dead, artifactless retry to its verified prior baseline rollback."""
        try:
            UUID(idempotency_key)
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("a UUID reconciliation idempotency key is required") from exc
        task = self.history.get(task_id)
        if (task is None or task.status is not TaskStatus.EXECUTING
                or task.plan_hash != plan_hash or task.approval_state != "explicitly_approved"):
            raise ValueError("the exact approved task must have a failed retry setup")
        attempts = self.history.store.execution_attempts(task_id)
        if (not attempts or attempts[-1]["attempt_kind"] != "retry"
                or attempts[-1]["state"] != "failed" or attempts[-1]["plan_hash"] != plan_hash
                or attempts[-1].get("artifact_id") or not attempts[-1].get("failure_type")):
            raise ValueError("latest retry must have failed before creating an execution artifact")
        events = self.history.timeline(task_id)
        failed = any(
            event.event_type == "execution_attempt_failed"
            and event.metadata.get("attempt_id") == attempts[-1]["attempt_id"]
            and event.metadata.get("failure_type") == attempts[-1]["failure_type"]
            for event in events
        )
        if not failed:
            raise ValueError("matching failed-retry audit evidence is required")
        worker = self.worker_status(task_id) if self.worker_status else None
        worker_state = worker.get("status") if isinstance(worker, dict) else None
        if worker_state not in {"failed", "process_replaced"}:
            raise ValueError("authoritative worker evidence does not prove termination")
        if self.history.store.task_claims(task_id).get("execution") is not None:
            raise ValueError("execution claim must be reconciled before setup rollback")
        prior_ids = {item["attempt_id"] for item in attempts[:-1]}
        completed = next((
            event for event in reversed(events)
            if event.event_type == "validation_failure_checkpoint_rollback_completed"
            and event.metadata.get("plan_hash") == plan_hash
            and event.metadata.get("attempt_id") in prior_ids
        ), None)
        if completed is None:
            raise ValueError("a verified prior baseline rollback is required")
        identity = self.worktrees.load(
            Path(task.repository), task_id,
            starting_commit=task.starting_commit, plan_hash=plan_hash,
        )
        canonical = Path(task.repository)
        if (identity.state is not WorktreeState.CLEANED or Path(identity.worktree).exists()
                or _git(canonical, "rev-parse", identity.branch) != task.starting_commit
                or _git(canonical, "status", "--porcelain")):
            raise ValueError("the prior task workspace is not verified clean")
        fingerprint = hashlib.sha256(
            f"{task_id}\0{plan_hash}\0{attempts[-1]['attempt_id']}\0{identity.repository_id}\0{identity.branch}\0{task.starting_commit}\0{worker_state}".encode()
        ).hexdigest()
        reconciled = self.history.store.reconcile_failed_retry_setup(
            task_id, plan_hash, attempts[-1]["attempt_id"],
            checkpoint_id=str(completed.metadata.get("checkpoint_id", "")),
            operation_id=str(completed.metadata.get("operation_id", "")),
            workspace_fingerprint=fingerprint, worker_state=worker_state,
        )
        return {"task_id": task_id, "plan_hash": plan_hash,
                "attempt_id": attempts[-1]["attempt_id"],
                "checkpoint_id": completed.metadata.get("checkpoint_id"),
                "status": reconciled.status.value, "duplicate": False}

    def _record_validation_failure_rollback(
        self, *, operation_id: str, task_id: str, checkpoint_id: str, plan_hash: str,
        principal: str, idempotency_key: str, fingerprint: str, state: str,
        result: dict | None = None,
    ) -> None:
        """Keep validation-failure recovery visible in the canonical rollback ledger."""
        if not operation_id or not checkpoint_id or not fingerprint:
            raise ValueError("rollback identity is incomplete")
        now = datetime.now(UTC)
        payload = json.dumps(result or {"operation_id": operation_id, "task_id": task_id,
                                        "checkpoint_id": checkpoint_id, "status": "restored"},
                             sort_keys=True)
        with self.history.store.transaction() as db:
            row = db.execute(
                "SELECT task_id,checkpoint_id,plan_hash,principal,fingerprint,idempotency_key "
                "FROM rollback_operations WHERE operation_id=?", (operation_id,),
            ).fetchone()
            if row:
                if (row["task_id"], row["checkpoint_id"], row["plan_hash"],
                        row["principal"], row["fingerprint"], row["idempotency_key"]) != (
                        task_id, checkpoint_id, plan_hash, principal, fingerprint, idempotency_key):
                    raise ValueError("rollback operation identity conflicts with recorded recovery")
                db.execute("UPDATE rollback_operations SET state=?,result_json=? WHERE operation_id=?",
                           (state, payload, operation_id))
            else:
                db.execute(
                    "INSERT INTO rollback_operations(operation_id,task_id,checkpoint_id,plan_hash,principal,state,fingerprint,created_at,expires_at,idempotency_key,result_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (operation_id, task_id, checkpoint_id, plan_hash, principal, state,
                     fingerprint, now.isoformat(), (now + timedelta(seconds=self.review_seconds)).isoformat(),
                     idempotency_key, payload),
                )

    @staticmethod
    def _validation_failure_fingerprint(events, idempotency_key: str) -> str:
        start = next((event for event in reversed(events)
                      if event.event_type == "validation_failure_checkpoint_rollback_started"
                      and event.metadata.get("idempotency_key") == idempotency_key), None)
        return str(start.metadata.get("workspace_fingerprint", "")) if start else ""

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
                    "plan_hash": task.plan_hash[:12], "plan_hash_full": task.plan_hash,
                    "head": record.head[:12],
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
