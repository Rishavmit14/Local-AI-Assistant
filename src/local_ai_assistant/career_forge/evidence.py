"""Deterministic public-career-evidence gate; it never publishes on its own."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PublicationDecision:
    approved: bool
    reasons: tuple[str, ...]


def evaluate_publication(
    *,
    genuine_work: bool,
    validation_passed: bool,
    secret_scan_passed: bool,
    privacy_review_passed: bool,
    documentation_complete: bool,
    artifact_quality_passed: bool,
) -> PublicationDecision:
    """Gate public evidence; GitHub activity is an outcome, never the objective."""
    checks = {
        "artifact is not demonstrated genuine learning work": genuine_work,
        "validation/tests have not passed": validation_passed,
        "secret scan has not passed": secret_scan_passed,
        "privacy/proprietary-data review has not passed": privacy_review_passed,
        "documentation is incomplete": documentation_complete,
        "artifact quality review has not passed": artifact_quality_passed,
    }
    reasons = tuple(reason for reason, passed in checks.items() if not passed)
    return PublicationDecision(approved=not reasons, reasons=reasons)
