"""Typed records for bounded Stage 4 tool execution."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class ToolPermission(StrEnum):
    READ_ONLY = "read_only"
    SAFE_MUTATION = "safe_mutation"
    VALIDATION = "validation"
    HIGH_RISK = "high_risk"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    permission: ToolPermission
    mutates: bool
    timeout_seconds: int
    input_fields: tuple[str, ...] = ()
    approval_required: bool = False
    risk_level: str = "low"


@dataclass(frozen=True, slots=True)
class ToolRequest:
    tool: str
    arguments: dict[str, Any]
    rationale: str
    expected_outcome: str
    plan_step: int
    mutation_intended: bool

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ToolRequest:
        required = {
            "tool",
            "arguments",
            "rationale",
            "expected_outcome",
            "plan_step",
            "mutation_intended",
        }
        missing = required - value.keys()
        if missing:
            raise ValueError("Missing tool request fields: " + ", ".join(sorted(missing)))
        unexpected = value.keys() - required
        if unexpected:
            raise ValueError("Unexpected tool request fields: " + ", ".join(sorted(unexpected)))
        if not isinstance(value["tool"], str) or not value["tool"].strip():
            raise ValueError("tool must be a non-empty string")
        if not isinstance(value["arguments"], dict):
            raise ValueError("arguments must be an object")
        if not isinstance(value["rationale"], str) or not isinstance(
            value["expected_outcome"], str
        ):
            raise ValueError("rationale and expected_outcome must be strings")
        if isinstance(value["plan_step"], bool) or not isinstance(value["plan_step"], int):
            raise ValueError("plan_step must be an integer")
        if not isinstance(value["mutation_intended"], bool):
            raise ValueError("mutation_intended must be a boolean")
        return cls(
            value["tool"],
            value["arguments"],
            value["rationale"],
            value["expected_outcome"],
            value["plan_step"],
            value["mutation_intended"],
        )


@dataclass(frozen=True, slots=True)
class ToolObservation:
    kind: str
    success: bool
    summary: str
    data: dict[str, Any] = field(default_factory=dict)
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False


@dataclass(frozen=True, slots=True)
class ToolEvent:
    task_id: str
    plan_hash: str
    repository: str
    starting_commit: str
    tool_name: str
    arguments: dict[str, Any]
    timestamp: str
    duration_seconds: float
    success: bool
    output_summary: str
    mutation_summary: str
    affected_files: tuple[str, ...]
    risk: str
    approval: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ExecutionReport:
    schema_version: int
    task_id: str
    plan_hash: str
    repository: str
    starting_commit: str
    status: str
    plan_versions: tuple[str, ...]
    events: tuple[ToolEvent, ...]
    final_diff: str = ""
    final_commit: str | None = None
    repairs: int = 0
    replans: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
