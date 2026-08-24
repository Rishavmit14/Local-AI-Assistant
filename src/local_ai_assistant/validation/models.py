"""Typed Stage 5 validation and review records."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class Requirement(StrEnum):
    REQUIRED = "required"
    RECOMMENDED = "recommended"
    OPTIONAL = "optional"


class ValidationKind(StrEnum):
    STRUCTURAL = "structural"
    TEST = "test"
    LINT = "lint"
    TYPECHECK = "typecheck"
    BUILD = "build"
    SECURITY = "security"
    ADVISORY = "advisory"


class FailureCategory(StrEnum):
    SYNTAX = "syntax"
    IMPORT = "import"
    TYPE = "type"
    LINT = "lint"
    ASSERTION = "assertion"
    REGRESSION = "regression"
    FLAKY = "flaky"
    TIMEOUT = "timeout"
    BUILD = "build"
    DEPENDENCY = "dependency"
    ENVIRONMENT = "environment"
    SCOPE_VIOLATION = "scope_violation"
    SECURITY = "security"
    INFRASTRUCTURE = "infrastructure"
    UNKNOWN = "unknown"


class ReviewSeverity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DecisionStatus(StrEnum):
    PASS = "pass"
    PASS_WITH_WARNINGS = "pass_with_warnings"
    REPAIR_REQUIRED = "repair_required"
    REAPPROVAL_REQUIRED = "reapproval_required"
    BLOCKED = "blocked"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ValidationStep:
    step_id: str
    kind: ValidationKind
    requirement: Requirement
    command: str | None
    reason: str
    targeted: bool = False
    tool: str | None = None
    timeout_seconds: int = 300
    related_files: tuple[str, ...] = ()
    related_symbols: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ValidationStep:
        data = dict(value)
        data["kind"] = ValidationKind(data["kind"])
        data["requirement"] = Requirement(data["requirement"])
        data["related_files"] = tuple(data.get("related_files", ()))
        data["related_symbols"] = tuple(data.get("related_symbols", ()))
        return cls(**data)


@dataclass(frozen=True, slots=True)
class ValidationPlan:
    schema_version: int
    validation_id: str
    task_id: str
    plan_hash: str
    repository: str
    starting_commit: str
    risk_level: str
    affected_files: tuple[str, ...]
    affected_symbols: tuple[str, ...]
    targeted_steps: tuple[ValidationStep, ...]
    final_steps: tuple[ValidationStep, ...]
    expected_coverage: str
    timeout_policy: dict[str, int]
    failure_policy: str
    tdd_enabled: bool = False
    configuration_identity: str = ""

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        for name, kind in (
            ("structural_checks", ValidationKind.STRUCTURAL),
            ("lint_steps", ValidationKind.LINT),
            ("typecheck_steps", ValidationKind.TYPECHECK),
            ("build_steps", ValidationKind.BUILD),
            ("test_steps", ValidationKind.TEST),
            ("security_checks", ValidationKind.SECURITY),
            ("optional_advisory_checks", ValidationKind.ADVISORY),
        ):
            value[name] = [
                asdict(item)
                for item in (*self.targeted_steps, *self.final_steps)
                if item.kind is kind
            ]
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ValidationPlan:
        if value.get("schema_version") != 1:
            raise ValueError("unsupported validation plan schema")
        data = dict(value)
        for name in (
            "structural_checks",
            "lint_steps",
            "typecheck_steps",
            "build_steps",
            "test_steps",
            "security_checks",
            "optional_advisory_checks",
        ):
            data.pop(name, None)
        for name in ("affected_files", "affected_symbols"):
            data[name] = tuple(data.get(name, ()))
        for name in ("targeted_steps", "final_steps"):
            data[name] = tuple(ValidationStep.from_dict(item) for item in data.get(name, ()))
        data["timeout_policy"] = {
            str(key): int(item) for key, item in data.get("timeout_policy", {}).items()
        }
        return cls(**data)


@dataclass(frozen=True, slots=True)
class ValidationProvenance:
    check_name: str
    command: str | None
    file: str | None
    symbol: str | None
    line_start: int | None
    line_end: int | None
    plan_step: int | None
    timestamp: str
    result: str
    severity: ReviewSeverity
    evidence: str


@dataclass(frozen=True, slots=True)
class ValidationResult:
    step_id: str
    success: bool
    skipped: bool
    return_code: int | None
    summary: str
    output: str = ""
    cached: bool = False
    provenance: ValidationProvenance | None = None


@dataclass(frozen=True, slots=True)
class FailureRecord:
    category: FailureCategory
    command: str
    exit_code: int | None
    relevant_output: str
    affected_tests: tuple[str, ...]
    related_files: tuple[str, ...]
    related_symbols: tuple[str, ...]
    confidence: float
    repair_appropriate: bool
    reasons: tuple[str, ...]
    flaky_evidence: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ReviewFinding:
    category: str
    severity: ReviewSeverity
    file: str | None
    symbol: str | None
    line_start: int | None
    line_end: int | None
    evidence: str
    rationale: str
    origin: str
    blocking: bool
    check_name: str


@dataclass(frozen=True, slots=True)
class ReviewResult:
    plan_hash: str
    diff_hash: str
    findings: tuple[ReviewFinding, ...]
    model_summary: str | None = None
    context_truncated: bool = False


@dataclass(frozen=True, slots=True)
class FinalDecision:
    status: DecisionStatus
    reasons: tuple[str, ...]
    evidence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ValidationReport:
    schema_version: int
    plan: ValidationPlan
    results: tuple[ValidationResult, ...]
    failures: tuple[FailureRecord, ...]
    review: ReviewResult
    decision: FinalDecision
    generated_tests: tuple[str, ...] = ()
    repair_attempts: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
