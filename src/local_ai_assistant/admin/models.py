"""Safe projections for Owner Sovereign Mode."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AdminCredentialStatus(StrEnum):
    NOT_ENROLLED = "not_enrolled"
    AVAILABLE = "available"
    INVALID = "invalid"
    DEGRADED = "degraded"
    VAULT_LOCKED = "vault_locked"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class PrivilegedResult:
    operation_id: str
    return_code: int
    stdout: str
    stderr: str
    timed_out: bool
    duration_seconds: float
