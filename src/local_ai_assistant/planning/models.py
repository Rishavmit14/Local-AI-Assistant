"""Typed Stage 3 planning, scope, risk, and approval records."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class TaskCategory(StrEnum):
    EXPLAIN = "explain"
    BUG_FIX = "bug_fix"
    FEATURE = "feature"
    REFACTOR = "refactor"
    TEST = "test"
    DOCUMENTATION = "documentation"
    CONFIGURATION = "configuration"
    DEPENDENCY_CHANGE = "dependency_change"
    DATABASE_MIGRATION = "database_migration"
    SECURITY_SENSITIVE = "security_sensitive"
    AUTHENTICATION_AUTHORIZATION = "authentication_authorization"
    DEPLOYMENT_OPERATIONS = "deployment_operations"
    UNKNOWN_MIXED = "unknown_mixed"


class ScopeRole(StrEnum):
    DIRECT = "direct"
    DEPENDENT = "dependent"
    OPTIONAL = "optional_contextual"
    UNRESOLVED = "unresolved"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ApprovalStatus(StrEnum):
    AUTOMATIC = "safe_to_continue_automatically"
    REVIEW = "requires_human_review"
    BLOCKED = "blocked_until_explicit_approval"
    REJECTED = "rejected_due_to_policy_or_scope_errors"


class IssueSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFORMATIONAL = "informational"


class DependencyChangeKind(StrEnum):
    NEW = "new_dependency"
    REMOVED = "removed_dependency"
    VERSION = "version_change"
    UNKNOWN = "unknown_dependency_impact"


@dataclass(frozen=True, slots=True)
class TaskClassification:
    category: TaskCategory
    confidence: float
    reasons: tuple[str, ...]
    raw_request: str

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> TaskClassification:
        return cls(TaskCategory(value["category"]), float(value["confidence"]), tuple(value.get("reasons", ())), value["raw_request"])


@dataclass(frozen=True, slots=True)
class ScopeCandidate:
    path: str
    symbol_id: str | None
    qualified_name: str | None
    reason: str
    relationship: str
    retrieval_score: float | None
    provenance: dict[str, Any]
    confidence: float
    role: ScopeRole

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ScopeCandidate:
        data = dict(value)
        data["role"] = ScopeRole(data["role"])
        return cls(**data)


@dataclass(frozen=True, slots=True)
class PlanStep:
    order: int
    description: str
    files: tuple[str, ...] = ()
    symbols: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> PlanStep:
        return cls(int(value["order"]), value["description"], tuple(value.get("files", ())), tuple(value.get("symbols", ())))


@dataclass(frozen=True, slots=True)
class DependencyChange:
    manifest: str
    kind: DependencyChangeKind
    description: str

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> DependencyChange:
        return cls(value["manifest"], DependencyChangeKind(value.get("kind", "unknown_dependency_impact")), value["description"])


@dataclass(frozen=True, slots=True)
class PlannedTest:
    path: str
    reason: str
    command: str
    required_full_suite: bool = False

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> PlannedTest:
        return cls(value["path"], value["reason"], value["command"], bool(value.get("required_full_suite", False)))


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    level: RiskLevel
    reasons: tuple[str, ...]
    security_sensitive: bool = False
    dependency_change: bool = False
    migration: bool = False

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> RiskAssessment:
        return cls(RiskLevel(value["level"]), tuple(value.get("reasons", ())), bool(value.get("security_sensitive", False)), bool(value.get("dependency_change", False)), bool(value.get("migration", False)))


@dataclass(frozen=True, slots=True)
class ConfidenceAssessment:
    score: float
    factors: dict[str, float]
    reasons: tuple[str, ...]

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ConfidenceAssessment:
        return cls(float(value["score"]), {key: float(item) for key, item in value.get("factors", {}).items()}, tuple(value.get("reasons", ())))


@dataclass(frozen=True, slots=True)
class ApprovalDecision:
    status: ApprovalStatus
    reasons: tuple[str, ...]

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ApprovalDecision:
        return cls(ApprovalStatus(value["status"]), tuple(value.get("reasons", ())))


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    severity: IssueSeverity
    code: str
    message: str
    target: str | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ValidationIssue:
        data = dict(value)
        data["severity"] = IssueSeverity(data["severity"])
        return cls(**data)


@dataclass(frozen=True, slots=True)
class ImplementationPlan:
    task_id: str
    original_request: str
    classification: TaskClassification
    summary: str
    assumptions: tuple[str, ...]
    direct_scope: tuple[ScopeCandidate, ...]
    dependent_scope: tuple[ScopeCandidate, ...]
    files_to_inspect: tuple[str, ...]
    files_to_modify: tuple[str, ...]
    files_to_create: tuple[str, ...]
    files_to_delete_or_rename: tuple[str, ...]
    symbols_to_modify: tuple[str, ...]
    symbols_to_create: tuple[str, ...]
    steps: tuple[PlanStep, ...]
    relevant_tests: tuple[PlannedTest, ...]
    validation_commands: tuple[str, ...]
    dependency_changes: tuple[DependencyChange, ...]
    migration_implications: tuple[str, ...]
    security_implications: tuple[str, ...]
    rollback_considerations: tuple[str, ...]
    unresolved_questions: tuple[str, ...]
    confidence: ConfidenceAssessment
    risk: RiskAssessment
    approval: ApprovalDecision

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ImplementationPlan:
        data = dict(value)
        data["classification"] = TaskClassification.from_dict(data["classification"])
        data["direct_scope"] = tuple(ScopeCandidate.from_dict(item) for item in data.get("direct_scope", ()))
        data["dependent_scope"] = tuple(ScopeCandidate.from_dict(item) for item in data.get("dependent_scope", ()))
        data["steps"] = tuple(PlanStep.from_dict(item) for item in data.get("steps", ()))
        data["relevant_tests"] = tuple(PlannedTest.from_dict(item) for item in data.get("relevant_tests", ()))
        data["dependency_changes"] = tuple(DependencyChange.from_dict(item) for item in data.get("dependency_changes", ()))
        data["confidence"] = ConfidenceAssessment.from_dict(data["confidence"])
        data["risk"] = RiskAssessment.from_dict(data["risk"])
        data["approval"] = ApprovalDecision.from_dict(data["approval"])
        for name in (
            "assumptions", "files_to_inspect", "files_to_modify", "files_to_create",
            "files_to_delete_or_rename", "symbols_to_modify", "symbols_to_create",
            "validation_commands", "migration_implications",
            "security_implications", "rollback_considerations", "unresolved_questions",
        ):
            data[name] = tuple(data.get(name, ()))
        return cls(**data)


@dataclass(frozen=True, slots=True)
class ScopeGuardPolicy:
    allowed_files: tuple[str, ...]
    allowed_symbols: tuple[str, ...]
    allowed_new_symbols: tuple[str, ...]
    allowed_new_files: tuple[str, ...]
    allowed_deletes_or_renames: tuple[str, ...]
    max_file_count: int
    max_symbol_count: int
    protected_paths: tuple[str, ...]
    dependency_file_policy: str
    generated_file_policy: str
    security_sensitive_path_policy: str
    symbol_scoped_files: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PlanningArtifact:
    timestamp: str
    repository: str
    starting_commit: str
    request: str
    classification: TaskClassification
    scope_candidates: tuple[ScopeCandidate, ...]
    plan: ImplementationPlan
    validation_issues: tuple[ValidationIssue, ...] = field(default_factory=tuple)
    instruction_sources: tuple[str, ...] = field(default_factory=tuple)
    context_truncated: bool = False
    schema_version: int = 2

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> PlanningArtifact:
        schema_version = value.get("schema_version")
        if schema_version not in {1, 2}:
            raise ValueError(f"Unsupported planning artifact schema: {schema_version!r}")
        return cls(
            timestamp=value["timestamp"],
            repository=value["repository"],
            starting_commit=value["starting_commit"],
            request=value["request"],
            classification=TaskClassification.from_dict(value["classification"]),
            scope_candidates=tuple(ScopeCandidate.from_dict(item) for item in value.get("scope_candidates", ())),
            plan=ImplementationPlan.from_dict(value["plan"]),
            validation_issues=tuple(ValidationIssue.from_dict(item) for item in value.get("validation_issues", ())),
            instruction_sources=tuple(value.get("instruction_sources", ())),
            context_truncated=bool(value.get("context_truncated", False)),
            schema_version=2,
        )


def plan_approval_token(plan: ImplementationPlan) -> str:
    """Bind explicit approval to the exact validated plan contents."""
    payload = json.dumps(plan.to_dict(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()
