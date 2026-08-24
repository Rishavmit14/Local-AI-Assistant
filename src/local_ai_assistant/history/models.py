"""Typed Stage 7 task, timeline, search, and metrics records."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class TaskStatus(StrEnum):
    CREATED = "created"
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    EXECUTING = "executing"
    VALIDATING = "validating"
    REVIEWING = "reviewing"
    REAPPROVAL_REQUIRED = "reapproval_required"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


TERMINAL_STATUSES = {
    TaskStatus.SUCCEEDED,
    TaskStatus.FAILED,
    TaskStatus.BLOCKED,
    TaskStatus.ROLLED_BACK,
    TaskStatus.CANCELLED,
}

ALLOWED_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.CREATED: frozenset({TaskStatus.PLANNING, TaskStatus.CANCELLED, TaskStatus.FAILED}),
    TaskStatus.PLANNING: frozenset(
        {TaskStatus.AWAITING_APPROVAL, TaskStatus.APPROVED, TaskStatus.BLOCKED, TaskStatus.FAILED, TaskStatus.CANCELLED}
    ),
    TaskStatus.AWAITING_APPROVAL: frozenset(
        {TaskStatus.APPROVED, TaskStatus.BLOCKED, TaskStatus.CANCELLED}
    ),
    TaskStatus.APPROVED: frozenset(
        {TaskStatus.EXECUTING, TaskStatus.REAPPROVAL_REQUIRED, TaskStatus.CANCELLED}
    ),
    TaskStatus.EXECUTING: frozenset(
        {TaskStatus.VALIDATING, TaskStatus.REAPPROVAL_REQUIRED, TaskStatus.FAILED, TaskStatus.ROLLED_BACK, TaskStatus.CANCELLED}
    ),
    TaskStatus.VALIDATING: frozenset(
        {TaskStatus.REVIEWING, TaskStatus.EXECUTING, TaskStatus.REAPPROVAL_REQUIRED, TaskStatus.FAILED, TaskStatus.ROLLED_BACK, TaskStatus.CANCELLED}
    ),
    TaskStatus.REVIEWING: frozenset(
        {TaskStatus.SUCCEEDED, TaskStatus.EXECUTING, TaskStatus.REAPPROVAL_REQUIRED, TaskStatus.BLOCKED, TaskStatus.FAILED, TaskStatus.ROLLED_BACK}
    ),
    TaskStatus.REAPPROVAL_REQUIRED: frozenset(
        {TaskStatus.APPROVED, TaskStatus.BLOCKED, TaskStatus.CANCELLED}
    ),
    **{status: frozenset() for status in TERMINAL_STATUSES},
}


def stable_task_id(repository: str, starting_commit: str, request: str, created_at: str) -> str:
    payload = "\0".join((repository, starting_commit, request, created_at))
    return "task_" + hashlib.sha256(payload.encode()).hexdigest()[:20]


@dataclass(frozen=True, slots=True)
class TaskRecord:
    task_id: str
    original_request: str
    repository: str
    starting_commit: str
    branch: str
    created_at: str
    updated_at: str
    status: TaskStatus = TaskStatus.CREATED
    final_commit: str | None = None
    classification: str = "unknown_mixed"
    risk: str = "unknown"
    confidence: float | None = None
    approval_state: str = "unknown"
    plan_hash: str | None = None
    final_decision: str | None = None
    outcome: str | None = None
    failure_reason: str | None = None
    human_review_state: str = "not_requested"
    duration_seconds: float | None = None
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["status"] = self.status.value
        return value


@dataclass(frozen=True, slots=True)
class TimelineEvent:
    event_id: str
    task_id: str
    timestamp: str
    subsystem: str
    event_type: str
    summary: str
    artifact_id: str | None = None
    artifact_path: str | None = None
    status: str | None = None
    risk_or_severity: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TaskFilter:
    task_id: str | None = None
    repository: str | None = None
    branch: str | None = None
    status: str | None = None
    classification: str | None = None
    risk: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    affected_file: str | None = None
    affected_symbol: str | None = None
    language: str | None = None
    outcome: str | None = None
    text: str | None = None
    limit: int = 100


@dataclass(frozen=True, slots=True)
class MetricsSnapshot:
    total_tasks: int
    status_counts: dict[str, int]
    classification_counts: dict[str, int]
    risk_counts: dict[str, int]
    repository_counts: dict[str, int]
    language_counts: dict[str, int]
    tasks_over_time: dict[str, int]
    outcome_counts: dict[str, int]
    failure_category_counts: dict[str, int]
    success_rate: float
    average_duration_seconds: float | None
    average_planning_seconds: float | None
    average_validation_seconds: float | None
    average_repairs: float
    first_pass_success_rate: float
    scope_violations: int
    reapprovals: int
    rollbacks: int
    validation_failures: int
    security_blocking_findings: int
    tests_run: int
    tool_calls: int
    model_calls: int
    input_tokens: int | None
    output_tokens: int | None
    index_refresh_seconds: float | None
    plan_validation_success_rate: float | None
    patch_preflight_success_rate: float | None
    first_targeted_test_pass_rate: float | None
    first_full_suite_pass_rate: float | None
    repeated_failures: int
    review_blocking_findings: int
    commit_success_rate: float | None
