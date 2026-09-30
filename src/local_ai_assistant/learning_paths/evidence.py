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

    def dynamic_node_evidence(self, path_id: str, path_version: int, node: dict) -> CompetencyEvidence | None:
        """Read evidence for the same unchanged node contract across path revisions."""
        from local_ai_assistant.career_forge.generalized import GeneralizedLearningService

        fingerprint = GeneralizedLearningService.contract_fingerprint(node)
        with self.career_forge._db() as db:
            exists = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='dynamic_learning_subjects'"
            ).fetchone()
            if not exists:
                return None
            row = db.execute(
                "SELECT s.competency_id,l.mastery FROM dynamic_learning_subjects s "
                "JOIN learner_competencies l USING(competency_id) WHERE s.path_id=? AND s.node_id=? "
                "AND s.contract_fingerprint=? ORDER BY s.path_version DESC,s.created_at DESC LIMIT 1",
                (path_id, str(node["node_id"]), fingerprint),
            ).fetchone()
            if row is None:
                return None
            competency_id, mastery_value = str(row[0]), str(row[1])
            due = db.execute(
                "SELECT 1 FROM retention_reviews WHERE competency_id=? "
                "AND state IN ('scheduled','delivered') AND due_at<=? LIMIT 1",
                (competency_id, datetime.now(UTC).isoformat()),
            ).fetchone() is not None
            latest_review = db.execute(
                "SELECT state,evaluation FROM retention_reviews WHERE competency_id=? "
                "AND state='completed' ORDER BY evaluated_at DESC,created_at DESC LIMIT 1",
                (competency_id,),
            ).fetchone()
            independent = int(db.execute(
                "SELECT COUNT(*) FROM lesson_attempts a JOIN missions m USING(mission_id) "
                "WHERE m.competency_id=? AND a.evaluation='correct' AND a.assistance_level IS NULL",
                (competency_id,),
            ).fetchone()[0])
        weak = bool(latest_review and latest_review[0] == "completed" and latest_review[1] in {"incorrect", "uncertain"})
        mastery = MasteryLevel(mastery_value)
        if mastery is MasteryLevel.UNVERIFIED:
            confidence, retention = "unverified", "not_scheduled"
        elif weak:
            confidence, retention = "weak", "failed"
        elif due:
            confidence, retention = "stale", "due"
        elif latest_review and latest_review[0] == "completed" and latest_review[1] == "correct":
            confidence, retention = "reinforced", "passed"
        else:
            confidence, retention = "current", "scheduled"
        return CompetencyEvidence(
            competency_id, mastery.value, confidence, retention, independent,
            ("failed retention reassessment",) if weak else (), due,
        )
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
