"""Deterministic, read-only task recovery projection over canonical authorities."""

from __future__ import annotations

import json
import re
import sqlite3
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from local_ai_assistant.autonomy.service import ObjectiveService
from local_ai_assistant.history.errors import HistoryDatabaseError
from local_ai_assistant.history.models import TERMINAL_STATUSES, TaskStatus
from local_ai_assistant.history.service import TaskHistoryService
from local_ai_assistant.isolation.models import WorktreeState
from local_ai_assistant.isolation.recovery import TaskIsolationEvidence, inspect_task_isolation


@dataclass(frozen=True, slots=True)
class RecoveryClaim:
    state: str
    expires_at: str | None = None
    lease_seconds: int | None = None


@dataclass(frozen=True, slots=True)
class RecoveryObjectiveLink:
    objective_id: str | None
    state: str
    plan_matches_task: bool | None


@dataclass(frozen=True, slots=True)
class RecoveryIsolation:
    status: str
    state: str | None
    worktree_present: bool | None
    summary: str


@dataclass(frozen=True, slots=True)
class RecoveryRollback:
    state: str
    operation_id: str | None = None
    checkpoint_id: str | None = None
    result: str | None = None


@dataclass(frozen=True, slots=True)
class RecoveryCleanup:
    state: str


@dataclass(frozen=True, slots=True)
class RecoveryReconciliation:
    state: str
    execution_evidence_count: int
    terminal_artifact_statuses: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FridayTaskRecovery:
    task_id: str
    objective_links: tuple[RecoveryObjectiveLink, ...]
    task_status: str
    overall_status: str
    owner_attention: str
    worker_liveness: str
    isolation: RecoveryIsolation
    planning_claim: RecoveryClaim
    execution_claim: RecoveryClaim
    rollback: RecoveryRollback
    cleanup: RecoveryCleanup
    reconciliation: RecoveryReconciliation
    evidence_sources: tuple[str, ...]
    limitations: tuple[str, ...]
    summary: str

    def to_dict(self) -> dict:
        value = asdict(self)
        # Keep the bounded Phase 10/14 field name while exposing the richer DTO.
        value["status"] = self.overall_status
        value["isolation_state"] = self.isolation.state
        value["cleanup_state"] = self.cleanup.state
        return value


class TaskRecoveryProjectionService:
    """Composes existing task, objective, claim, rollback and isolation evidence."""

    def __init__(
        self,
        history: TaskHistoryService,
        isolation_root: Path | None,
        objectives: ObjectiveService | None = None,
        worker_status: Callable[[str], dict] | None = None,
        *,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.history = history
        self.isolation_root = isolation_root
        self.objectives = objectives
        self.worker_status = worker_status
        self.clock = clock

    def project(self, task_id: str) -> FridayTaskRecovery:
        task = self.history.get(task_id)
        if task is None:
            raise KeyError(task_id)

        now = int(self.clock())
        raw_claims = self.history.store.task_claims(task_id)
        planning_claim = self._claim(raw_claims.get("planning"), now)
        execution_claim = self._claim(raw_claims.get("execution"), now)
        worker_liveness = self._worker_liveness(task_id)
        isolation_evidence = (
            inspect_task_isolation(
                self.isolation_root,
                task_id,
                canonical_repository=Path(task.repository),
                starting_commit=task.starting_commit,
                plan_hash=task.plan_hash,
            )
            if self.isolation_root is not None
            else TaskIsolationEvidence("unavailable")
        )
        rollback = self._rollback(task_id, now)
        objective_links = self._objectives(task_id, task.plan_hash)
        reconciliation = self._reconciliation(task_id, task.status)
        cleanup_state = self._cleanup_state(isolation_evidence)
        overall_status, owner_attention, summary = self._classify(
            task.status,
            isolation_evidence,
            planning_claim,
            execution_claim,
            rollback,
            worker_liveness,
            objective_links,
            reconciliation,
        )
        sources = ["TaskHistoryService.task"]
        if self.isolation_root is not None:
            sources.append("WorktreeManager.metadata")
        sources.append("TaskHistoryStore.admission_claims")
        sources.append("TaskHistoryStore.rollback_operations")
        if self.objectives is not None:
            sources.append("ObjectiveService.task_link")
        if reconciliation.execution_evidence_count:
            sources.append("TaskHistoryService.execution_artifacts")
        if self.worker_status is not None:
            sources.append("CodeAgentExecutionService.process_local_status")
        return FridayTaskRecovery(
            task_id=task_id,
            objective_links=objective_links,
            task_status=task.status.value,
            overall_status=overall_status,
            owner_attention=owner_attention,
            worker_liveness=worker_liveness,
            isolation=RecoveryIsolation(
                isolation_evidence.status,
                isolation_evidence.state,
                isolation_evidence.worktree_present,
                isolation_evidence.summary,
            ),
            planning_claim=planning_claim,
            execution_claim=execution_claim,
            rollback=rollback,
            cleanup=RecoveryCleanup(cleanup_state),
            reconciliation=reconciliation,
            evidence_sources=tuple(sources),
            limitations=(
                "A claim records admission ownership, not worker liveness or work outcome.",
                "A lease expiry permits later admission; it does not prove prior work did not happen.",
                "No interrupted planning, execution, validation, rollback, or cleanup is resumed automatically.",
                "TaskHistory, objective, isolation, rollback, and worker evidence retain separate authority.",
            ),
            summary=summary,
        )

    def _claim(self, value: dict[str, int] | None, now: int) -> RecoveryClaim:
        if value is None:
            return RecoveryClaim("none")
        try:
            claimed = int(value["claimed_at"])
            expires = int(value["expires_at"])
            if claimed < 0 or expires < claimed:
                return RecoveryClaim("unavailable")
            return RecoveryClaim(
                "expired" if expires <= now else "active",
                datetime.fromtimestamp(expires, UTC).isoformat(),
                max(0, expires - claimed),
            )
        except (OverflowError, OSError, TypeError, ValueError, KeyError):
            return RecoveryClaim("unavailable")

    def _worker_liveness(self, task_id: str) -> str:
        if self.worker_status is None:
            return "unknown"
        try:
            status = self.worker_status(task_id)
        except Exception:
            return "unknown"
        if not isinstance(status, dict):
            return "unknown"
        value = status.get("status")
        if value == "running":
            return "running"
        if value in {"completed", "failed", "cancelled"}:
            return "not_running"
        return "unknown"

    def _rollback(self, task_id: str, now: int) -> RecoveryRollback:
        try:
            rows = self.history.store.task_rollback_operations(task_id, limit=20)
        except (HistoryDatabaseError, sqlite3.DatabaseError, OSError):
            return RecoveryRollback("unavailable")
        if not rows:
            return RecoveryRollback("none")
        row = rows[0]
        state = str(row.get("state", "unknown"))
        result = None
        try:
            payload = json.loads(row.get("result_json") or "{}")
            candidate = payload.get("status") if isinstance(payload, dict) else None
            if candidate in {"restored", "failed_recovered", "recovery_required"}:
                result = candidate
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
        if state == "reviewed":
            try:
                expired = datetime.fromisoformat(str(row["expires_at"])) <= datetime.fromtimestamp(now, UTC)
            except (KeyError, TypeError, ValueError):
                expired = True
            state = "review_expired" if expired else "review_pending"
        if state not in {"review_pending", "review_expired", "executing", "succeeded", "failed_recovered", "recovery_required"}:
            state = "unknown"
        return RecoveryRollback(
            state=state,
            operation_id=(str(row["operation_id"]) if re.fullmatch(r"[a-f0-9]{32}", str(row.get("operation_id", ""))) else None),
            checkpoint_id=(str(row["checkpoint_id"]) if re.fullmatch(r"[a-f0-9]{24}", str(row.get("checkpoint_id", ""))) else None),
            result=result,
        )

    def _objectives(self, task_id: str, plan_hash: str | None) -> tuple[RecoveryObjectiveLink, ...]:
        if self.objectives is None:
            return ()
        try:
            links = self.objectives.linked_to_task(task_id)
        except (OSError, ValueError, HistoryDatabaseError, sqlite3.DatabaseError):
            return (RecoveryObjectiveLink(None, "unavailable", None),)
        return tuple(
            RecoveryObjectiveLink(
                link.objective_id if isinstance(link.objective_id, str) and re.fullmatch(r"[a-f0-9]{32}", link.objective_id) else None,
                link.state if isinstance(link.objective_id, str) and re.fullmatch(r"[a-f0-9]{32}", link.objective_id) and isinstance(link.state, str) and link.state in {"created", "planning", "planned", "completed", "cancelled"} else "unavailable",
                None if link.plan_hash is None or plan_hash is None else link.plan_hash == plan_hash,
            )
            for link in links
        )

    def _reconciliation(self, task_id: str, task_status: TaskStatus) -> RecoveryReconciliation:
        try:
            records = self.history.store.artifact_records(task_id, "executions", limit=100)
        except (HistoryDatabaseError, sqlite3.DatabaseError, OSError):
            return RecoveryReconciliation("unavailable", 0, ())
        statuses = tuple(sorted({
            status for record in records
            if (status := record.get("status")) in {
                "complete", "committed", "merged", "no_changes", "rolled_back",
                "cancelled", "cancelled_rolled_back", "failed", "failed_validation",
            }
        }))
        if task_status in TERMINAL_STATUSES:
            state = "terminal_recorded"
        elif statuses:
            state = "terminal_evidence_unreconciled"
        else:
            state = "not_recorded"
        return RecoveryReconciliation(state, len(records), statuses)

    @staticmethod
    def _cleanup_state(evidence: TaskIsolationEvidence) -> str:
        if evidence.status == "cleanup_pending":
            return "pending"
        if evidence.state == WorktreeState.CLEANED.value:
            return "complete"
        if evidence.status in {"no_isolation_record", "unavailable", "corrupt", "path_rejected", "identity_collision", "identity_mismatch"}:
            return "unknown"
        return "not_started"

    @staticmethod
    def _classify(task_status, isolation, planning, execution, rollback, worker, links, reconciliation):
        if isolation.status in {"corrupt", "path_rejected", "identity_collision", "identity_mismatch", "unavailable"}:
            return isolation.status, "inspect", isolation.summary
        if isolation.status == "recovery_required" or rollback.state == "recovery_required":
            if task_status in TERMINAL_STATUSES:
                return "recovery_required", "inspect", "TaskHistory records a terminal state while isolation or rollback evidence records recovery_required; owner inspection is required."
            return "recovery_required", "inspect", "Recovery inspection is required; no automatic action is authorized."
        if isolation.state == WorktreeState.ROLLBACK_IN_PROGRESS.value or rollback.state == "executing":
            return "rollback_in_progress", "inspect", "Rollback was interrupted before a verified terminal result was recorded."
        if rollback.state == "failed_recovered" or rollback.result == "failed_recovered":
            return "rollback_failed_recovered", "no_action", "The requested rollback failed; the pre-rollback worktree state was verified restored."
        if isolation.status == "cleanup_pending":
            return "cleanup_pending", "inspect", "Cleanup is pending. The task's canonical outcome is unchanged."
        if isolation.status == "missing_worktree":
            return "missing_worktree", "inspect", isolation.summary
        if rollback.state == "succeeded" and rollback.result == "restored":
            return "rollback_completed", "inspect", "The owner-reviewed checkpoint rollback completed; TaskHistory lifecycle remains unchanged and no further action was taken."
        if any(link.state == "unavailable" for link in links):
            return "objective_unavailable", "inspect", "Canonical objective linkage could not be read; task status remains authoritative."
        if len(links) > 1 or any(link.plan_matches_task is False for link in links):
            return "objective_task_mismatch", "inspect", "Objective/task linkage evidence conflicts; both canonical records are preserved."
        if reconciliation.state == "terminal_evidence_unreconciled":
            return "terminal_evidence_unreconciled", "inspect", "An execution artifact records a terminal result while task history remains nonterminal; no automatic reconciliation was performed."
        if task_status in TERMINAL_STATUSES:
            if isolation.state == WorktreeState.CLEANED.value and isolation.cleanup_state == "cleaned":
                return "terminal_consistent", "no_action", "Task history records a terminal state and isolation metadata records cleanup complete."
            if isolation.status == "no_isolation_record":
                return "no_isolation_record", "unknown", "Task history is terminal; isolation recovery health is unknown because no isolation record exists."
            return "terminal_recorded", "no_action", "TaskHistory records a terminal state; isolation evidence is shown separately."
        active_lifecycle = isolation.state in {
            WorktreeState.CREATING.value, WorktreeState.EXECUTING.value,
            WorktreeState.VALIDATING.value,
        } or task_status in {TaskStatus.PLANNING, TaskStatus.EXECUTING, TaskStatus.VALIDATING, TaskStatus.REVIEWING}
        if worker == "running":
            return "in_progress_known", "wait", "The managed local worker is currently observed running for this task."
        if active_lifecycle:
            active_claim = (
                planning.state == "active" if task_status is TaskStatus.PLANNING
                else execution.state == "active"
            )
            if active_claim:
                return "claim_waiting", "wait", "An admission claim remains active; worker liveness and prior work outcome are not inferred from the claim."
            if planning.state == "expired" or execution.state == "expired":
                return "claim_expired", "inspect", "An admission claim lease expired. This permits later admission but does not establish the prior work outcome."
            return "interrupted_lifecycle", "inspect", "Task or isolation metadata records an in-progress lifecycle; worker liveness is unknown and inspection is required."
        if execution.state == "active" or planning.state == "active":
            return "claim_waiting", "wait", "An admission claim remains active; it does not establish worker liveness."
        if execution.state == "expired" or planning.state == "expired":
            return "claim_expired", "inspect", "An admission claim lease expired. This permits later admission but does not establish the prior work outcome."
        if isolation.status == "no_isolation_record":
            return "no_isolation_record", "unknown", isolation.summary
        return "no_recovery_issue", "no_action", "No canonical recovery issue is recorded; current worker liveness remains separate."
