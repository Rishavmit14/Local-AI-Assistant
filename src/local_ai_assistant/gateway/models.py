"""Typed contracts for external integrations. External content is never policy."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class GatewayScope(StrEnum):
    READ_STATUS = "read_status"
    READ_HISTORY = "read_history"
    CREATE_TASK = "create_task"
    REQUEST_PLAN = "request_plan"
    SUBMIT_APPROVAL = "submit_approval"
    REQUEST_EXECUTION = "request_execution"
    REQUEST_CANCEL = "request_cancel"
    GITHUB_READ = "github_read"
    GITHUB_WRITE = "github_write"


class ExternalSyncState(StrEnum):
    NOT_REQUESTED = "not_requested"
    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"
    RETRYABLE = "retryable"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class ExternalProvenance:
    source: str
    event_id: str
    repository_id: str
    actor: str = "unknown"
    payload_hash: str = ""
    received_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    adapter_version: str = "1"
    principal: str = "unknown"

    @classmethod
    def from_payload(cls, source: str, event_id: str, repository_id: str, payload: str, **kwargs: Any):
        return cls(source, event_id, repository_id, payload_hash=hashlib.sha256(payload.encode()).hexdigest(), **kwargs)


@dataclass(frozen=True, slots=True)
class GatewayEvent:
    event_id: str
    sequence: int
    task_id: str | None
    event_type: str
    timestamp: str
    summary: str
    source: str = "gateway"
    critical: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RepositoryMapping:
    repository_id: str
    local_path: str
    github_owner: str
    github_name: str


@dataclass(frozen=True, slots=True)
class CIStatus:
    name: str
    status: str
    conclusion: str | None
    commit_sha: str
    url: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    external_repository: str | None = None
