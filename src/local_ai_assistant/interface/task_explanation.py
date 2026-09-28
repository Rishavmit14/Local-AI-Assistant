"""Bounded, deterministic explanations over canonical task/objective records."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

from local_ai_assistant.autonomy.service import ObjectiveService
from local_ai_assistant.execution.history import redact
from local_ai_assistant.history.errors import HistoryDatabaseError
from local_ai_assistant.history.models import TaskRecord, TaskStatus
from local_ai_assistant.history.service import TaskHistoryService
from local_ai_assistant.interface.progress_projection import task_recovery_projection

_TASK_ID = re.compile(r"task_[0-9a-f]{20}\Z")
_OBJECTIVE_ID = re.compile(r"[0-9a-f]{32}\Z")
_PATH = re.compile(r"(?<![\w:])/(?:[^\s,;]+/)*[^\s,;]+")
_WINDOWS_PATH = re.compile(r"(?i)\b[A-Z]:\\(?:[^\s,;]+\\)*[^\s,;]+")
_EVENT_NAMES = {
    "task_created": "Task record created",
    "plan_attached": "Plan record attached",
    "plan_ready": "Plan recorded as ready",
    "approval_recorded": "Approval record added",
    "execution_started": "Execution start recorded",
    "execution_imported": "Execution evidence imported",
    "validation_imported": "Validation evidence imported",
    "review_imported": "Review evidence imported",
    "task_status_changed": "Task status changed",
    "cancel_requested": "Cancellation request recorded",
}
_STATUS_NARRATIVE = {
    TaskStatus.CREATED: "The canonical task record exists; planning has not started.",
    TaskStatus.PLANNING: "Task history records planning in progress.",
    TaskStatus.AWAITING_APPROVAL: "Task history records that owner approval is awaited.",
    TaskStatus.APPROVED: "Task history records approval; this does not establish execution.",
    TaskStatus.EXECUTING: "Task history records the executing state; worker liveness is unavailable here.",
    TaskStatus.VALIDATING: "Task history records the validating state.",
    TaskStatus.REVIEWING: "Task history records the reviewing state.",
    TaskStatus.REAPPROVAL_REQUIRED: "Task history records that renewed approval is required.",
    TaskStatus.SUCCEEDED: "Task history records the task as succeeded.",
    TaskStatus.FAILED: "Task history records the task as failed.",
    TaskStatus.BLOCKED: "Task history records the task as blocked.",
    TaskStatus.ROLLED_BACK: "Task history records the task as rolled back; no further recovery is inferred.",
    TaskStatus.CANCELLED: "Task history records the task as cancelled.",
}


def safe_explanation_text(value: str | None, limit: int = 600) -> str | None:
    if not value:
        return None
    cleaned = redact(value)
    cleaned = _PATH.sub("[private path]", cleaned)
    cleaned = _WINDOWS_PATH.sub("[private path]", cleaned)
    return cleaned[:limit]


@dataclass(frozen=True, slots=True)
class ExplanationFact:
    label: str
    value: str
    source: str


@dataclass(frozen=True, slots=True)
class ExplanationEvent:
    timestamp: str
    kind: str
    status: str | None
    source: str = "TaskHistoryService.timeline"


@dataclass(frozen=True, slots=True)
class FridayTaskExplanation:
    task_id: str
    objective_id: str | None
    objective_text: str | None
    objective_state: str | None
    canonical_status: str
    outcome: str | None
    owner_attention: str
    summary: str
    facts: tuple[ExplanationFact, ...]
    timeline: tuple[ExplanationEvent, ...]
    latest_event: ExplanationEvent | None
    recovery: dict[str, str | None]
    evidence_sources: tuple[str, ...]
    limitations: tuple[str, ...]
    generated: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    def conversation_text(self) -> str:
        lines = [self.summary, "Canonical facts:"]
        lines.extend(f"- {fact.label}: {fact.value} [{fact.source}]" for fact in self.facts)
        if self.latest_event:
            lines.append(
                f"Latest task-history event: {self.latest_event.kind} at "
                f"{self.latest_event.timestamp}; this records order, not a separate causal claim."
            )
        lines.append(f"Recovery: {self.recovery['summary']}")
        lines.append("This is a deterministic, read-only explanation from canonical records.")
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class FridayObjectiveExplanation:
    objective_id: str
    objective_text: str
    objective_state: str
    task_id: str | None
    task_state: str | None
    summary: str
    facts: tuple[ExplanationFact, ...]
    evidence_sources: tuple[str, ...] = ("ObjectiveService.objective",)
    limitations: tuple[str, ...] = ("No task explanation is added without a canonical linked task ID.",)
    generated: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    def conversation_text(self) -> str:
        return "\n".join((
            self.summary,
            "Canonical facts:",
            *(f"- {fact.label}: {fact.value} [{fact.source}]" for fact in self.facts),
            "This is a deterministic, read-only explanation from canonical records.",
        ))


class TaskExplanationNotFound(ValueError):
    """An exact task/objective identity has no canonical record."""


class TaskExplanationService:
    """Read a single task or linked objective into a safe, typed explanation."""

    def __init__(
        self,
        history: TaskHistoryService,
        objectives: ObjectiveService | None = None,
        isolation_root: Path | None = None,
    ) -> None:
        self.history = history
        self.objectives = objectives
        self.isolation_root = isolation_root

    def task(self, task_id: str) -> FridayTaskExplanation:
        if not _TASK_ID.fullmatch(task_id):
            raise TaskExplanationNotFound("No canonical task record exists for that exact ID.")
        task = self.history.store.get_task(task_id)
        if task is None:
            raise TaskExplanationNotFound("No canonical task record exists for that exact ID.")
        return self._explain(task, objective=None)

    def objective(self, objective_id: str) -> FridayTaskExplanation | FridayObjectiveExplanation:
        if self.objectives is None or not _OBJECTIVE_ID.fullmatch(objective_id):
            raise TaskExplanationNotFound("No canonical objective record exists for that exact ID.")
        try:
            objective = self.objectives.get(objective_id)
        except ValueError as exc:
            raise TaskExplanationNotFound("No canonical objective record exists for that exact ID.") from exc
        if objective.task_id is None:
            state = safe_explanation_text(objective.state, 100) or "unknown"
            return FridayObjectiveExplanation(
                objective_id=objective.objective_id,
                objective_text=safe_explanation_text(objective.text, 1000) or "Objective text unavailable.",
                objective_state=state,
                task_id=None,
                task_state=None,
                summary=f"Objective {objective.objective_id} exists and is recorded as {state}. No canonical task is linked.",
                facts=(
                    ExplanationFact("Objective state", state, "ObjectiveService.objective"),
                    ExplanationFact("Linked task", "none", "ObjectiveService.objective"),
                ),
            )
        task = self.history.store.get_task(objective.task_id)
        if task is None:
            return FridayObjectiveExplanation(
                objective_id=objective.objective_id,
                objective_text=safe_explanation_text(objective.text, 1000) or "Objective text unavailable.",
                objective_state=safe_explanation_text(objective.state, 100) or "unknown",
                task_id=objective.task_id,
                task_state=None,
                summary=(
                    f"Objective {objective.objective_id} is recorded as {objective.state} and links to task "
                    f"{objective.task_id}, but that canonical task record is unavailable."
                ),
                facts=(
                    ExplanationFact("Objective state", objective.state, "ObjectiveService.objective"),
                    ExplanationFact("Linked task ID", objective.task_id, "ObjectiveService.objective"),
                    ExplanationFact("Linked task record", "unavailable", "TaskHistoryService.task"),
                ),
                limitations=("The linked task record is unavailable; no task lifecycle or execution claims are made.",),
            )
        return self._explain(task, objective=objective)

    def _explain(self, task: TaskRecord, *, objective) -> FridayTaskExplanation:
        artifacts = self.history.artifacts(task.task_id)
        events = self.history.timeline(task.task_id)[-20:]
        timeline = tuple(
            ExplanationEvent(
                timestamp=event.timestamp,
                kind=_EVENT_NAMES.get(event.event_type, "Canonical task event recorded"),
                status=event.status if event.status in {status.value for status in TaskStatus} else None,
            )
            for event in events
        )
        status = task.status
        owner_attention = (
            "approval_required" if status is TaskStatus.AWAITING_APPROVAL
            else "reapproval_required" if status is TaskStatus.REAPPROVAL_REQUIRED
            else "none_recorded"
        )
        plan_count = len(artifacts["plans"])
        approval_count = len(artifacts["approvals"])
        execution_count = len(artifacts["executions"])
        validation_rows = artifacts["validations"][:20]
        review_rows = artifacts["reviews"][:20]
        outcome = safe_explanation_text(task.outcome)
        failure = safe_explanation_text(task.failure_reason)
        final_decision = safe_explanation_text(task.final_decision)

        facts = [
            ExplanationFact("Canonical task status", status.value, "TaskHistoryService.task"),
            ExplanationFact("Plan record", f"{plan_count} present" if plan_count else "none present", "TaskHistoryService.plans"),
            ExplanationFact("Plan hash present", "yes" if task.plan_hash else "no", "TaskHistoryService.task"),
            ExplanationFact("Approval state", safe_explanation_text(task.approval_state, 120) or "unknown", "TaskHistoryService.task"),
            ExplanationFact("Approval records", str(approval_count), "TaskHistoryService.approvals"),
            ExplanationFact(
                "Execution records",
                f"{execution_count} present" if execution_count else "none present",
                "TaskHistoryService.executions",
            ),
            ExplanationFact("Validation records", str(len(artifacts["validations"])), "TaskHistoryService.validations"),
            ExplanationFact("Review records", str(len(artifacts["reviews"])), "TaskHistoryService.reviews"),
            ExplanationFact("Outcome", outcome or "none recorded", "TaskHistoryService.task"),
            ExplanationFact("Final decision", final_decision or "none recorded", "TaskHistoryService.task"),
            ExplanationFact("Failure reason", failure or "none recorded", "TaskHistoryService.task"),
            ExplanationFact("Human review state", safe_explanation_text(task.human_review_state, 120) or "unknown", "TaskHistoryService.task"),
        ]
        for index, row in enumerate(validation_rows, 1):
            decision = row.get("decision")
            if decision not in {"passed", "failed", "blocked", "unknown", None}:
                decision = "unrecognized"
            facts.append(ExplanationFact(f"Validation {index}", str(decision or "status unavailable"), "TaskHistoryService.validations"))
        for index, row in enumerate(review_rows, 1):
            facts.append(ExplanationFact(
                f"Review {index}",
                f"{int(row.get('blocking_findings') or 0)} blocking, {int(row.get('security_findings') or 0)} security findings",
                "TaskHistoryService.reviews",
            ))
        if objective is not None:
            facts.append(ExplanationFact("Objective state", objective.state, "ObjectiveService.objective"))

        pieces = [f"Task {task.task_id} exists. {_STATUS_NARRATIVE[status]}"]
        if objective is not None:
            pieces.append(
                f"The linked objective {objective.objective_id} is recorded as {objective.state}; "
                "objective and task lifecycle states are separate records."
            )
        pieces.append("A canonical plan is recorded." if plan_count or task.plan_hash else "No canonical plan record is present.")
        pieces.append(
            f"Task history contains {approval_count} approval record(s); approval state is {task.approval_state}."
        )
        pieces.append(
            "No execution record is present in TaskHistory."
            if not execution_count
            else f"TaskHistory contains {execution_count} execution record(s); record presence alone does not establish success."
        )
        pieces.append(
            "No terminal outcome is recorded."
            if task.outcome is None and status not in {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.BLOCKED, TaskStatus.ROLLED_BACK, TaskStatus.CANCELLED}
            else f"Recorded outcome: {outcome or 'status is terminal, but no outcome value is present.'}"
        )
        if failure:
            pieces.append(f"Recorded failure reason: {failure}")
        if not timeline:
            pieces.append("No task timeline event is recorded.")
        recovery = task_recovery_projection(self.isolation_root, task.task_id)
        pieces.append(recovery["summary"])
        return FridayTaskExplanation(
            task_id=task.task_id,
            objective_id=objective.objective_id if objective is not None else None,
            objective_text=safe_explanation_text(objective.text, 1000) if objective is not None else None,
            objective_state=objective.state if objective is not None else None,
            canonical_status=status.value,
            outcome=outcome,
            owner_attention=owner_attention,
            summary=" ".join(pieces),
            facts=tuple(facts),
            timeline=timeline,
            latest_event=timeline[-1] if timeline else None,
            recovery=recovery,
            evidence_sources=("TaskHistoryService.task", "TaskHistoryService.timeline", "ObjectiveService.objective" if objective is not None else "TaskHistoryService artifacts"),
            limitations=(
                "Only canonical task and explicitly linked objective records are included.",
                "Timeline ordering does not establish causality beyond the canonical task identity.",
                "Raw requests, summaries, commands, artifact contents, paths, and arbitrary metadata are not exposed.",
                "Task state does not establish current worker liveness.",
            ),
        )



__all__ = ["ExplanationEvent", "ExplanationFact", "FridayObjectiveExplanation", "FridayTaskExplanation", "TaskExplanationNotFound", "TaskExplanationService"]
