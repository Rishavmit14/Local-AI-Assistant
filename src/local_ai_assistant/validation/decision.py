"""Deterministic final execution decision."""

from __future__ import annotations

from .models import (
    DecisionStatus,
    FailureCategory,
    FinalDecision,
    Requirement,
    ReviewResult,
    ReviewSeverity,
    ValidationPlan,
    ValidationResult,
)


def decide_final(plan: ValidationPlan, results: tuple[ValidationResult, ...], review: ReviewResult, *, scope_violation: bool = False, reapproval_required: bool = False) -> FinalDecision:
    if scope_violation or reapproval_required:
        return FinalDecision(DecisionStatus.REAPPROVAL_REQUIRED, ("Approved scope or risk must expand.",), ("scope_guard",))
    required_ids = {item.step_id for item in (*plan.targeted_steps, *plan.final_steps) if item.requirement is Requirement.REQUIRED}
    by_id = {item.step_id: item for item in results}
    missing = sorted(required_ids - by_id.keys())
    failed = sorted(step_id for step_id in required_ids if step_id in by_id and (not by_id[step_id].success or by_id[step_id].skipped))
    blocking = [item for item in review.findings if item.blocking]
    if missing or failed:
        return FinalDecision(DecisionStatus.FAILED, tuple([*(f"Required validation missing: {item}" for item in missing), *(f"Required validation failed: {item}" for item in failed)]), tuple((*missing, *failed)))
    if blocking:
        return FinalDecision(DecisionStatus.BLOCKED, tuple(f"Blocking {item.category}: {item.rationale}" for item in blocking), tuple(item.check_name for item in blocking))
    warnings = [item for item in review.findings if item.severity in {ReviewSeverity.LOW, ReviewSeverity.MEDIUM}]
    return FinalDecision(DecisionStatus.PASS_WITH_WARNINGS if warnings else DecisionStatus.PASS, ("All deterministic gates passed.",), tuple(item.check_name for item in warnings))


def repair_decision(category: FailureCategory, attempts: int, max_attempts: int, *, repeated: bool = False, scope_increase: bool = False, risk_increase: bool = False) -> DecisionStatus:
    if scope_increase or risk_increase:
        return DecisionStatus.REAPPROVAL_REQUIRED
    if category in {FailureCategory.ENVIRONMENT, FailureCategory.INFRASTRUCTURE, FailureCategory.SECURITY, FailureCategory.SCOPE_VIOLATION, FailureCategory.FLAKY, FailureCategory.TIMEOUT}:
        return DecisionStatus.BLOCKED
    if repeated or attempts >= max_attempts:
        return DecisionStatus.FAILED
    return DecisionStatus.REPAIR_REQUIRED
