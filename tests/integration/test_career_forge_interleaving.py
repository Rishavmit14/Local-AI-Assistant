import pytest

from local_ai_assistant.career_forge import (
    AttemptEvaluation,
    CareerForgeService,
    MasteryLevel,
    TutorMode,
)


def _advance(forge: CareerForgeService, competency_id: str, title: str) -> str:
    mission = forge.start_mission(competency_id, title)
    evidence = forge.record_evidence(mission.mission_id, "explanation", f"Objective evidence for {competency_id}")
    forge.advance_mastery(competency_id, MasteryLevel.RECOGNIZE, evidence_id=evidence)
    return evidence


def test_relevant_older_concept_is_interleaved_twice_with_restart_safe_transfer_evidence(tmp_path):
    path = tmp_path / "learner.sqlite3"
    forge = CareerForgeService(path)
    original_evidence = _advance(forge, "se.python", "Learn Python")
    newer = forge.start_mission("se.engineering", "Learn engineering")

    first = forge.interleaving_candidate(newer.mission_id)
    assert first is not None
    assert first.competency_id == "se.python"
    assert first.relationship == "prerequisite_critical"
    assert first.source_evidence_id == original_evidence
    assert "0 independent correct demonstrations" in first.reason
    forge.submit_interleaving(first.interleave_id, "Defaults are allocated once; create state inside each call.")
    first = forge.evaluate_interleaving(first.interleave_id, AttemptEvaluation.CORRECT, "Correct transfer.")
    assert first.evidence_id
    assert CareerForgeService(path).interleaving(first.interleave_id) == first
    assert forge.evidence_history()[0].competency_id == "se.python"
    assert forge.learner_confidence()[0].independent_correct_attempts == 1
    assert forge.interleaving_candidate(newer.mission_id) is None

    engineering_evidence = forge.record_evidence(newer.mission_id, "design", "Explained typed boundaries")
    forge.advance_mastery("se.engineering", MasteryLevel.RECOGNIZE, evidence_id=engineering_evidence)
    later = forge.start_mission("se.delivery", "Learn delivery")
    with forge._db() as db:
        db.execute(
            "UPDATE retention_reviews SET due_at='2000-01-01T00:00:00+00:00' WHERE evidence_id=?",
            (first.evidence_id,),
        )
    second = forge.interleaving_candidate(later.mission_id)
    assert second is not None and second.competency_id == "se.python"
    assert second.relationship == "retention_monitoring"
    assert "confidence is stale" in second.reason
    forge.submit_interleaving(second.interleave_id, "A new context still needs per-call state isolation.")
    forge.evaluate_interleaving(second.interleave_id, AttemptEvaluation.CORRECT, "Correct independent transfer.")
    confidence = forge.learner_confidence()[0]
    assert confidence.independent_correct_attempts == 2
    assert confidence.status == "current"


def test_failed_critical_interleave_blocks_only_current_progression_and_cannot_replay(tmp_path):
    forge = CareerForgeService(tmp_path / "learner.sqlite3")
    _advance(forge, "se.python", "Learn Python")
    newer = forge.start_mission("se.engineering", "Learn engineering")
    check = forge.interleaving_candidate(newer.mission_id)
    assert check is not None
    forge.submit_interleaving(check.interleave_id, "Defaults are fresh every call.")
    failed = forge.evaluate_interleaving(check.interleave_id, AttemptEvaluation.INCORRECT, "Shared state remains misunderstood.")
    assert failed.evaluation is AttemptEvaluation.INCORRECT
    assert forge.learner_confidence()[0].status == "weak"
    with pytest.raises(ValueError, match="not awaiting an answer"):
        forge.submit_interleaving(check.interleave_id, "Replay")

    evidence = forge.record_evidence(newer.mission_id, "design", "Explained engineering")
    with pytest.raises(ValueError, match="critical interleaved prerequisite"):
        forge.advance_mastery("se.engineering", MasteryLevel.RECOGNIZE, evidence_id=evidence)
    assert forge.competencies()[1].mastery is MasteryLevel.UNVERIFIED

    retry = forge.interleaving_candidate(newer.mission_id)
    assert retry is not None and retry.interleave_id != check.interleave_id
    with pytest.raises(ValueError, match="fresh independent response"):
        forge.submit_interleaving(retry.interleave_id, "Defaults are fresh every call.")
    forge.submit_interleaving(retry.interleave_id, "The definition-time object is shared; allocate inside instead.")
    forge.evaluate_interleaving(retry.interleave_id, AttemptEvaluation.CORRECT, "Misconception repaired.")
    assert not forge.unresolved_attempts()
    promoted = forge.advance_mastery("se.engineering", MasteryLevel.RECOGNIZE, evidence_id=evidence)
    assert promoted.mastery is MasteryLevel.RECOGNIZE


def test_failed_transitive_retention_check_does_not_block_newer_noncritical_progression(tmp_path):
    forge = CareerForgeService(tmp_path / "learner.sqlite3")
    _advance(forge, "se.python", "Learn Python")
    engineering = forge.start_mission("se.engineering", "Learn engineering")
    for index in range(2):
        attempt = forge.record_attempt(
            engineering.mission_id, f"engineering-{index}", "Independent engineering explanation",
            mode=TutorMode.CHALLENGE,
        )
        forge.evaluate_attempt(attempt.attempt_id, AttemptEvaluation.CORRECT, "Correct.")
    evidence = forge.record_evidence(engineering.mission_id, "design", "Explained engineering")
    forge.advance_mastery("se.engineering", MasteryLevel.RECOGNIZE, evidence_id=evidence)
    delivery = forge.start_mission("se.delivery", "Learn delivery")

    check = forge.interleaving_candidate(delivery.mission_id)
    assert check is not None and check.competency_id == "se.python"
    assert check.relationship == "retention_monitoring"
    assert "ml.classical" not in check.prompt
    forge.submit_interleaving(check.interleave_id, "Incorrect old-concept transfer")
    forge.evaluate_interleaving(check.interleave_id, AttemptEvaluation.INCORRECT, "Reinforce later.")
    delivery_evidence = forge.record_evidence(delivery.mission_id, "delivery", "Validated tests and APIs")

    promoted = forge.advance_mastery("se.delivery", MasteryLevel.RECOGNIZE, evidence_id=delivery_evidence)
    assert promoted.mastery is MasteryLevel.RECOGNIZE
    assert forge.learner_confidence()[0].status == "weak"
