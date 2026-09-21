from local_ai_assistant.career_forge import (
    AssistanceLevel,
    AttemptEvaluation,
    CareerForgeService,
    MasteryLevel,
    PracticeLabService,
    TutorMode,
)


def _make_review_due(forge: CareerForgeService, review_id: str) -> None:
    with forge._db() as db:
        db.execute(
            "UPDATE retention_reviews SET due_at='2000-01-01T00:00:00+00:00' WHERE review_id=?",
            (review_id,),
        )


def _record_objective_weakness(forge: CareerForgeService) -> str:
    mission = forge.start_mission("se.python", "Establish Python foundations")
    evidence_id = forge.record_evidence(
        mission.mission_id, "explanation", "Explained mutable-default object lifetime."
    )
    forge.advance_mastery("se.python", MasteryLevel.RECOGNIZE, evidence_id=evidence_id)
    review = forge.retention_reviews()[0]
    _make_review_due(forge, review.review_id)
    forge.deliver_retention_review(review.review_id)
    forge.evaluate_retention_review(
        review.review_id,
        "A fresh list is created for every call.",
        AttemptEvaluation.INCORRECT,
        "The default object is created once; revisit its lifetime.",
    )
    return review.review_id


def _fixed_practice_code(code: str) -> str:
    return code.replace("bucket=[]", "bucket=None").replace(
        "    bucket.append(item)",
        "    if bucket is None:\n        bucket = []\n    bucket.append(item)",
    )


def test_governed_loop_proves_persistent_evidence_positive_cognitive_improvement(tmp_path):
    path = tmp_path / "learner.sqlite3"
    forge = CareerForgeService(path)
    baseline_review_id = _record_objective_weakness(forge)
    assert forge.weak_areas()[0].competency_id == "se.python"

    reinforcement = forge.start_reinforcement("se.python")
    initial = forge.cognitive_improvement_evaluations()[0]
    assert initial.status == "intervention_active"
    assert initial.baseline_review_ids == (baseline_review_id,)
    assert not initial.evidence_positive

    forge.offer_assistance(
        reinforcement.mission_id,
        TutorMode.HINT,
        AssistanceLevel.PROMPT,
        "Trace whether two calls share the same default object.",
    )
    lab = PracticeLabService(forge, tmp_path / "lab")
    fixed = _fixed_practice_code(lab.open(reinforcement.mission_id).draft_code)
    lab.save_draft(reinforcement.mission_id, fixed)
    assert lab.test(reinforcement.mission_id).passed is True
    submitted = lab.submit(reinforcement.mission_id)
    assert submitted.attempt.evaluation is AttemptEvaluation.CORRECT
    assert submitted.attempt.evidence_type == "practice_lab_bounded_test"

    practice_evidence = next(
        item for item in forge.evidence_history(limit=100)
        if item.mission_id == reinforcement.mission_id
    )
    forge.advance_mastery(
        "se.python", MasteryLevel.EXPLAIN, evidence_id=practice_evidence.evidence_id
    )
    reassessment = next(
        item for item in forge.retention_reviews(limit=100)
        if item.evidence_id == practice_evidence.evidence_id
    )
    _make_review_due(forge, reassessment.review_id)
    forge.deliver_retention_review(reassessment.review_id)
    forge.evaluate_retention_review(
        reassessment.review_id,
        "The default is allocated when the function is defined, so use None and allocate inside each call.",
        AttemptEvaluation.CORRECT,
        "Correctly connected definition-time allocation to the safe per-call pattern.",
    )

    restored = CareerForgeService(path)
    result = restored.cognitive_improvement_evaluations()[0]
    assert result.status == "evidence_positive"
    assert result.practice_attempt_id == submitted.attempt.attempt_id
    assert result.practice_evidence_id == practice_evidence.evidence_id
    assert result.reassessment_review_id == reassessment.review_id
    assert result.objective_score_delta == 1
    assert result.mastery_rung_delta == 1
    assert result.weak_area_resolved
    assert result.evidence_positive
    assert restored.progress().cognitive_improvements == (result,)


def test_incorrect_fresh_reassessment_is_a_negative_control(tmp_path):
    forge = CareerForgeService(tmp_path / "learner.sqlite3")
    _record_objective_weakness(forge)
    reinforcement = forge.start_reinforcement("se.python")
    attempt = forge.record_attempt(
        reinforcement.mission_id,
        "fresh-transfer-question",
        "Use None and create a list inside the function.",
        mode=TutorMode.CHALLENGE,
    )
    forge.evaluate_attempt(
        attempt.attempt_id,
        AttemptEvaluation.CORRECT,
        "Correct transfer answer.",
        evidence_type="transfer_challenge",
    )
    practice_evidence = next(
        item for item in forge.evidence_history(limit=100)
        if item.mission_id == reinforcement.mission_id
    )
    forge.advance_mastery(
        "se.python", MasteryLevel.EXPLAIN, evidence_id=practice_evidence.evidence_id
    )
    reassessment = next(
        item for item in forge.retention_reviews(limit=100)
        if item.evidence_id == practice_evidence.evidence_id
    )
    _make_review_due(forge, reassessment.review_id)
    forge.deliver_retention_review(reassessment.review_id)
    forge.evaluate_retention_review(
        reassessment.review_id,
        "It creates a new default on every call.",
        AttemptEvaluation.INCORRECT,
        "The original misconception remains.",
    )

    result = forge.cognitive_improvement_evaluations()[0]
    assert result.status == "reassessment_failed"
    assert result.objective_score_delta == 0
    assert result.mastery_rung_delta == 1
    assert not result.weak_area_resolved
    assert not result.evidence_positive

