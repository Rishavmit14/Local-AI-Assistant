"""Bounded, read-only projection of Career Forge truth for DLP sequencing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from local_ai_assistant.career_forge.models import MasteryLevel


@dataclass(frozen=True, slots=True)
class CompetencyEvidence:
    competency_id: str
    mastery: str
    confidence: str
    retention: str
    independent_correct_attempts: int
    weak_reasons: tuple[str, ...]
    review_due: bool


class LearningEvidenceProvider(Protocol):
    def competency_evidence(self, competency_ids: set[str]) -> dict[str, CompetencyEvidence]: ...


class CareerForgeEvidenceProjection:
    """Adapter deliberately exposes only bounded categorical evidence, never raw answers."""

    def __init__(self, career_forge):
        self.career_forge = career_forge

    def competency_evidence(self, competency_ids: set[str]) -> dict[str, CompetencyEvidence]:
        # Canonical CF projection methods are read-only. Unknown IDs stay absent.
        known = set(self.career_forge.graph).intersection(competency_ids)
        confidence = {item.competency_id: item for item in self.career_forge.learner_confidence()}
        weak = {item.competency_id: item for item in self.career_forge.weak_areas(limit=100)}
        due = {
            item.competency_id for item in self.career_forge.retention_reviews(limit=100)
            if item.state in {"scheduled", "delivered"} and item.due_at <= datetime.now(UTC).isoformat()
        }
        return {
            key: CompetencyEvidence(
                competency_id=key,
                mastery=confidence[key].mastery.value,
                confidence=confidence[key].status,
                retention=confidence[key].retention_state,
                independent_correct_attempts=confidence[key].independent_correct_attempts,
                weak_reasons=tuple(weak[key].reasons) if key in weak else (),
                review_due=key in due,
            )
            for key in sorted(known) if key in confidence
        }


def evidence_state(evidence: CompetencyEvidence | None) -> str:
    if evidence is None:
        return "unmapped"
    if evidence.confidence == "unverified" or evidence.mastery == MasteryLevel.UNVERIFIED:
        return "needs_diagnostic"
    if evidence.confidence == "stale" or evidence.review_due:
        return "needs_review"
    if evidence.confidence == "weak":
        return "unsatisfied"
    ladder = tuple(MasteryLevel)
    if ladder.index(MasteryLevel(evidence.mastery)) < ladder.index(MasteryLevel.APPLY_INDEPENDENTLY):
        return "needs_diagnostic"
    if evidence.confidence in {"current", "reinforced"}:
        return "satisfied"
    return "unsatisfied"
