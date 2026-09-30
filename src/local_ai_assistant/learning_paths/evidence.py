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
    equivalent_source: dict | None = None


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

    def dynamic_node_evidence(
        self, path_id: str, path_version: int, node: dict, *,
        equivalent_sources: set[tuple[str, str]] | None = None,
    ) -> CompetencyEvidence | None:
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
            source = None
            if row is None and equivalent_sources:
                candidates = []
                for source_path, source_node in sorted(equivalent_sources):
                    candidates.extend(db.execute(
                        "SELECT s.subject_id,s.competency_id,s.path_id,s.path_version,s.node_id,l.mastery "
                        "FROM dynamic_learning_subjects s JOIN learner_competencies l USING(competency_id) "
                        "WHERE s.path_id=? AND s.node_id=? AND s.contract_fingerprint=? "
                        "ORDER BY s.path_version DESC,s.created_at DESC,s.subject_id",
                        (source_path, source_node, fingerprint),
                    ).fetchall())
                for candidate in candidates:
                    provenance = db.execute(
                        "SELECT e.evidence_id,e.source_attempt_id,e.artifact_ref,e.created_at "
                        "FROM mission_evidence e JOIN missions m USING(mission_id) "
                        "JOIN lesson_attempts a ON a.attempt_id=e.source_attempt_id "
                        "WHERE m.competency_id=? AND e.contract_fingerprint=? "
                        "AND a.evaluation='correct' "
                        "ORDER BY e.created_at DESC,e.evidence_id LIMIT 1",
                        (candidate[1], fingerprint),
                    ).fetchone()
                    if provenance is None:
                        continue
                    source = {"path_id": str(candidate[2]), "path_version": int(candidate[3]),
                              "node_id": str(candidate[4]), "evidence_id": str(provenance[0]),
                              "attempt_id": str(provenance[1]) if provenance[1] else None,
                              "artifact_ref": str(provenance[2]) if provenance[2] else None,
                              "created_at": str(provenance[3]),
                              "evaluation": "correct",
                              "evaluation_authority": "career_forge_local_assessment"}
                    row = candidate
                    break
            if row is None:
                return None
            competency_id, mastery_value = str(row[1] if source else row[0]), str(row[5] if source else row[1])
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
        # Use Career Forge's full canonical projection for weak/stale signals,
        # including failed attempts and retention state, rather than inventing
        # a cross-path decay or supersession policy here.
        canonical = next((item for item in self.career_forge.learner_confidence()
                          if item.competency_id == competency_id), None)
        if canonical is not None:
            confidence, retention = canonical.status, canonical.retention_state
        return CompetencyEvidence(
            competency_id, mastery.value, confidence, retention, independent,
            (("failed retention reassessment",) if weak else
             ((canonical.reason,) if canonical is not None and canonical.status == "weak" else ())),
            due, source,
        )
def evidence_state(evidence: CompetencyEvidence | None, required_mastery: str = MasteryLevel.APPLY_INDEPENDENTLY.value) -> str:
    if evidence is None:
        return "unmapped"
    if evidence.confidence == "unverified" or evidence.mastery == MasteryLevel.UNVERIFIED:
        return "needs_diagnostic"
    if evidence.confidence == "stale" or evidence.review_due:
        return "needs_review"
    if evidence.confidence == "weak":
        return "unsatisfied"
    ladder = tuple(MasteryLevel)
    if ladder.index(MasteryLevel(evidence.mastery)) < ladder.index(MasteryLevel(required_mastery)):
        return "needs_diagnostic"
    if evidence.confidence in {"current", "reinforced"}:
        return "satisfied"
    return "unsatisfied"
