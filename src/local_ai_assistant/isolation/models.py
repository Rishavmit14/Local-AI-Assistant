"""Typed Stage 8 isolation records and policy."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path


class CapabilityState(StrEnum):
    SUPPORTED = "supported"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class NetworkPolicy(StrEnum):
    DENY = "deny"
    LOOPBACK_ONLY = "loopback_only"
    ALLOWED = "allowed"


class CachePolicy(StrEnum):
    READ_ONLY_SHARED = "read_only_shared"
    TASK_LOCAL = "task_local"
    DISABLED = "disabled"


class WorktreeState(StrEnum):
    CREATING = "creating"
    READY = "ready"
    EXECUTING = "executing"
    VALIDATING = "validating"
    PROMOTION_READY = "promotion_ready"
    PROMOTED = "promoted"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"
    RECOVERY_REQUIRED = "recovery_required"
    CLEANUP_PENDING = "cleanup_pending"
    CLEANED = "cleaned"


@dataclass(frozen=True, slots=True)
class ResourcePolicy:
    wall_seconds: int = 900
    cpu_seconds: int = 600
    max_processes: int = 64
    max_open_files: int = 256
    max_output_bytes: int = 20_000
    memory_bytes: int = 4 * 1024**3
    max_file_bytes: int = 512 * 1024**2


@dataclass(frozen=True, slots=True)
class SandboxCapabilities:
    backend: str
    process: CapabilityState
    filesystem: CapabilityState
    network: CapabilityState
    resource_limits: CapabilityState
    user_namespaces: CapabilityState
    cgroups: CapabilityState
    details: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class WorktreeIdentity:
    schema_version: int
    task_id: str
    repository_id: str
    canonical_repository: str
    worktree: str
    branch: str
    starting_commit: str
    plan_hash: str
    created_at: str
    state: WorktreeState
    current_commit: str | None = None
    cleanup_status: str = "pending"

    def to_dict(self) -> dict:
        value = asdict(self)
        value["state"] = self.state.value
        return value


@dataclass(frozen=True, slots=True)
class CheckpointRecord:
    schema_version: int
    checkpoint_id: str
    task_id: str
    plan_hash: str
    head: str
    staged_diff_hash: str
    unstaged_diff_hash: str
    untracked_hash: str
    archive_hash: str
    created_at: str
    path: Path


@dataclass(frozen=True, slots=True)
class SandboxResult:
    command: tuple[str, ...]
    return_code: int
    stdout: str
    stderr: str
    timed_out: bool
    cancelled: bool
    output_truncated: bool
    duration_seconds: float
    backend: str
