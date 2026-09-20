import sqlite3

import pytest

from local_ai_assistant.career_forge import (
    AssistanceLevel,
    AttemptEvaluation,
    CareerForgeService,
    MasteryLevel,
    TutorMode,
    competency_graph,
    evaluate_publication,
)


def test_ml_ai_engineer_curriculum_is_dependency_ordered_and_unverified_by_default():
    graph = competency_graph()
    identifiers = {item.competency_id for item in graph}
    assert len(identifiers) == len(graph)
    assert all(set(item.prerequisites) <= identifiers for item in graph)
    assert MasteryLevel.UNVERIFIED.value == "unverified"
    assert {item.domain for item in graph} == {
        "software_engineering", "math_data", "classical_ml", "deep_learning",
        "transformers_nlp", "generative_ai", "production_ml", "system_design",
        "work_simulation", "interview_career_proof",
    }


def test_existing_retention_queue_schema_migrates_for_governed_outcomes(tmp_path):
    path = tmp_path / "learner.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TABLE retention_reviews (review_id TEXT PRIMARY KEY, competency_id TEXT NOT NULL, "
            "evidence_id TEXT NOT NULL UNIQUE, mastery TEXT NOT NULL, due_at TEXT NOT NULL, "
            "state TEXT NOT NULL, created_at TEXT NOT NULL)"
        )

    CareerForgeService(path)

    with sqlite3.connect(path) as db:
        columns = {row[1] for row in db.execute("PRAGMA table_info(retention_reviews)")}
    assert {"response", "evaluation", "feedback", "evaluated_at"} <= columns


def test_existing_public_evidence_schema_migrates_for_gateway_binding(tmp_path):
    path = tmp_path / "learner.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TABLE public_evidence_candidates (candidate_id TEXT PRIMARY KEY, "
            "mission_id TEXT NOT NULL, artifact_ref TEXT NOT NULL, state TEXT NOT NULL, "
            "reasons_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, "
            "approved_at TEXT)"
        )

    CareerForgeService(path)

    with sqlite3.connect(path) as db:
        columns = {row[1] for row in db.execute("PRAGMA table_info(public_evidence_candidates)")}
    assert {
        "task_id", "repository_id", "base_branch", "publication_state",
        "publication_url", "publication_error", "published_at",
    } <= columns


def test_learner_twin_starts_unverified_and_resumes_exact_mission_state(tmp_path):
    forge = CareerForgeService(tmp_path / "learner.sqlite3")
    assert all(item.mastery is MasteryLevel.UNVERIFIED for item in forge.competencies())
    assert forge.next_competency().competency_id == "se.python"
    assert "mutable-default" in forge.next_mission_brief().owner_attempt
    mission = forge.start_mission("se.python", "Verify Python mental model")
    evidence = forge.record_evidence(mission.mission_id, "explanation", "Explained mutable defaults", assistance_level="hint")
    updated = forge.update_resume(
        mission.mission_id,
        {"phase": "independent_attempt", "task": "write a test"},
        assistance_level="hint",
    )
    assert forge.resume() == updated
    assert updated.resume_point["phase"] == "independent_attempt"
    promoted = forge.advance_mastery("se.python", MasteryLevel.RECOGNIZE, evidence_id=evidence)
    assert promoted.mastery is MasteryLevel.RECOGNIZE
    reviews = forge.retention_reviews()
    assert len(reviews) == 1
    assert reviews[0].competency_id == "se.python"
    assert reviews[0].evidence_id == evidence
    assert reviews[0].mastery is MasteryLevel.RECOGNIZE
    assert reviews[0].state == "scheduled"


def test_retention_review_is_evidence_backed_and_does_not_claim_completion(tmp_path):
    forge = CareerForgeService(tmp_path / "learner.sqlite3")
    mission = forge.start_mission("se.python", "Verify Python")
    evidence = forge.record_evidence(mission.mission_id, "explanation", "Explained defaults")
    forge.advance_mastery("se.python", MasteryLevel.RECOGNIZE, evidence_id=evidence)

    review = forge.progress().retention_reviews[0]
    assert review.evidence_id == evidence
    assert review.state == "scheduled"
    assert review.due_at > review.created_at


def test_due_retention_review_is_delivered_once_without_changing_mastery_or_evidence(tmp_path):
    forge = CareerForgeService(tmp_path / "learner.sqlite3")
    mission = forge.start_mission("se.python", "Verify Python")
    evidence = forge.record_evidence(mission.mission_id, "explanation", "Explained defaults")
    forge.advance_mastery("se.python", MasteryLevel.RECOGNIZE, evidence_id=evidence)
    review = forge.retention_reviews()[0]
    with forge._db() as db:
        db.execute("UPDATE retention_reviews SET due_at='2000-01-01T00:00:00+00:00' WHERE review_id=?", (review.review_id,))

    delivered, prompt = forge.deliver_retention_review(review.review_id)

    assert delivered.state == "delivered"
    assert "mutable default" in prompt.lower()
    assert forge.competencies()[0].mastery is MasteryLevel.RECOGNIZE
    assert forge.evidence_history()[0].evidence_id == evidence
    with pytest.raises(ValueError, match="already been delivered"):
        forge.deliver_retention_review(review.review_id)


def test_retention_outcome_derives_weak_area_without_changing_mastery(tmp_path):
    forge = CareerForgeService(tmp_path / "learner.sqlite3")
    mission = forge.start_mission("se.python", "Verify Python")
    evidence = forge.record_evidence(mission.mission_id, "explanation", "Explained defaults")
    forge.advance_mastery("se.python", MasteryLevel.RECOGNIZE, evidence_id=evidence)
    review = forge.retention_reviews()[0]
    with forge._db() as db:
        db.execute("UPDATE retention_reviews SET due_at='2000-01-01T00:00:00+00:00' WHERE review_id=?", (review.review_id,))
    forge.deliver_retention_review(review.review_id)

    completed = forge.evaluate_retention_review(
        review.review_id, "Defaults are made each call.",
        AttemptEvaluation.INCORRECT, "Defaults are created once; revisit object lifetime.",
    )

    assert completed.state == "completed"
    assert completed.evaluation is AttemptEvaluation.INCORRECT
    assert forge.competencies()[0].mastery is MasteryLevel.RECOGNIZE
    weak = forge.weak_areas()
    assert len(weak) == 1
    assert weak[0].competency_id == "se.python"
    assert weak[0].retention_failures == 1
    assert "failed retention review" in weak[0].reasons[0]
    assert forge.progress().weak_areas == weak
    assert "Reinforce the evidence-backed weak area" in forge.progress().next_action
    with pytest.raises(ValueError, match="already been evaluated"):
        forge.evaluate_retention_review(
            review.review_id, "Another answer", AttemptEvaluation.CORRECT, "Too late",
        )


def test_reinforcement_interrupts_then_resumes_newer_mission_without_automatic_mastery(tmp_path):
    forge = CareerForgeService(tmp_path / "learner.sqlite3")
    foundation = forge.start_mission("se.python", "Verify Python")
    evidence = forge.record_evidence(foundation.mission_id, "explanation", "Explained defaults")
    forge.advance_mastery("se.python", MasteryLevel.RECOGNIZE, evidence_id=evidence)
    interrupted = forge.start_mission("se.engineering", "Continue software engineering")
    review = forge.retention_reviews()[0]
    with forge._db() as db:
        db.execute("UPDATE retention_reviews SET due_at='2000-01-01T00:00:00+00:00' WHERE review_id=?", (review.review_id,))
    forge.deliver_retention_review(review.review_id)
    forge.evaluate_retention_review(
        review.review_id, "A new default is created each call.",
        AttemptEvaluation.INCORRECT, "Revisit object creation time.",
    )

    reinforcement = forge.start_reinforcement("se.python")

    assert reinforcement.title == "Reinforce Python foundations"
    assert reinforcement.resume_point == {
        "phase": "prerequisite_verification",
        "reinforcement": True,
        "reasons": ["1 failed retention review"],
        "interrupted_mission_id": interrupted.mission_id,
    }
    assert forge.resume() == reinforcement
    assert forge.competencies()[0].mastery is MasteryLevel.RECOGNIZE
    with pytest.raises(ValueError, match="already has an active mission"):
        forge.start_reinforcement("se.python")

    reinforcement_evidence = forge.record_evidence(
        reinforcement.mission_id, "teach_back", "Explained default object lifetime independently.",
    )
    forge.advance_mastery("se.python", MasteryLevel.EXPLAIN, evidence_id=reinforcement_evidence)

    assert forge.mission(reinforcement.mission_id).state == "completed"
    assert forge.resume().mission_id == interrupted.mission_id


def test_latest_correct_retention_outcome_clears_historical_retention_weakness(tmp_path):
    forge = CareerForgeService(tmp_path / "learner.sqlite3")
    mission = forge.start_mission("se.python", "Verify Python")
    evidence = forge.record_evidence(mission.mission_id, "explanation", "Explained defaults")
    forge.advance_mastery("se.python", MasteryLevel.RECOGNIZE, evidence_id=evidence)
    first = forge.retention_reviews()[0]
    with forge._db() as db:
        db.execute("UPDATE retention_reviews SET due_at='2000-01-01T00:00:00+00:00' WHERE review_id=?", (first.review_id,))
    forge.deliver_retention_review(first.review_id)
    forge.evaluate_retention_review(first.review_id, "Wrong", AttemptEvaluation.INCORRECT, "Retry.")
    assert forge.weak_areas()[0].retention_failures == 1

    with forge._db() as db:
        db.execute(
            "INSERT INTO retention_reviews "
            "(review_id, competency_id, evidence_id, mastery, due_at, state, created_at, response, evaluation, feedback, evaluated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            ("review_followup", "se.python", "evidence_followup", "recognize", "2001-01-01T00:00:00+00:00", "completed",
             "2001-01-01T00:00:00+00:00", "Correct", "correct", "Recovered.", "2099-01-01T00:00:00+00:00"),
        )

    assert forge.weak_areas() == ()
    with pytest.raises(ValueError, match="not a current evidence-backed weak area"):
        forge.start_reinforcement("se.python")


def test_mission_loop_and_progressive_assistance_preserve_independence_context(tmp_path):
    forge = CareerForgeService(tmp_path / "learner.sqlite3")
    mission = forge.start_mission("se.python", "Verify Python")
    assert forge.mission_loop(mission.mission_id)[0] == "why_it_matters"
    forge.offer_assistance(mission.mission_id, TutorMode.HINT, AssistanceLevel.PROMPT, "Predict first")
    with pytest.raises(ValueError, match="minimum useful"):
        forge.offer_assistance(mission.mission_id, TutorMode.GUIDE, AssistanceLevel.PARTIAL_EXAMPLE, "code")
    forge.offer_assistance(mission.mission_id, TutorMode.HINT, AssistanceLevel.CONCEPTUAL_HINT, "Think mutation")
    assert forge.resume().assistance_level == AssistanceLevel.CONCEPTUAL_HINT


def test_interview_mode_runs_bounded_no_help_followups_and_records_only_earned_evidence(tmp_path):
    path = tmp_path / "learner.sqlite3"
    forge = CareerForgeService(path)
    mission = forge.start_mission("se.python", "Verify Python")

    interview = forge.start_interview(mission.mission_id)
    assert interview.state == "awaiting_answer"
    assert interview.turn_number == 1
    assert "mutable default" in interview.prompt.lower()
    with pytest.raises(ValueError, match="already has an active interview"):
        forge.start_interview(mission.mission_id)

    first = forge.submit_interview_answer(
        interview.interview_id, "The same default list is reused between calls.",
    )
    assert first.tutor_mode is TutorMode.INTERVIEW
    assert first.assistance_level is None
    forge = CareerForgeService(path)
    assert forge.active_interview(mission.mission_id).state == "awaiting_evaluation"
    followup, evaluated = forge.evaluate_interview_answer(
        interview.interview_id, AttemptEvaluation.CORRECT, "Correct mechanism and consequence.",
    )
    assert evaluated.evidence_type == "interview_response"
    assert followup.state == "awaiting_answer"
    assert followup.turn_number == 2
    assert followup.question_id == "interview_followup"

    second = forge.submit_interview_answer(interview.interview_id, "I am not sure how to defend it.")
    completed, evaluated_second = forge.evaluate_interview_answer(
        interview.interview_id, AttemptEvaluation.UNCERTAIN, "The defense needs a concrete verification.",
    )
    assert second.attempt_id == evaluated_second.attempt_id
    assert evaluated_second.evidence_type is None
    assert completed.state == "completed"
    assert forge.active_interview(mission.mission_id) is None
    assert forge.competencies()[0].mastery is MasteryLevel.UNVERIFIED


def test_public_evidence_gate_rejects_fake_or_unsafe_activity():
    rejected = evaluate_publication(
        genuine_work=False, validation_passed=True, secret_scan_passed=False,
        privacy_review_passed=False, documentation_complete=False, artifact_quality_passed=True,
    )
    assert not rejected.approved
    assert len(rejected.reasons) == 4
    approved = evaluate_publication(
        genuine_work=True, validation_passed=True, secret_scan_passed=True,
        privacy_review_passed=True, documentation_complete=True, artifact_quality_passed=True,
    )
    assert approved.approved and not approved.reasons


def test_project_link_is_local_and_limited_to_the_missions_canonical_family(tmp_path):
    forge = CareerForgeService(tmp_path / "learner.sqlite3")
    python = forge.start_mission("se.python", "Verify Python")
    with pytest.raises(ValueError, match="no canonical project family"):
        forge.link_project(python.mission_id)

    evidence = forge.record_evidence(python.mission_id, "explanation", "Explained state")
    forge.advance_mastery("se.python", MasteryLevel.RECOGNIZE, evidence_id=evidence)
    engineering = forge.start_mission("se.engineering", "Verify engineering")
    evidence = forge.record_evidence(engineering.mission_id, "explanation", "Explained typing")
    forge.advance_mastery("se.engineering", MasteryLevel.RECOGNIZE, evidence_id=evidence)
    delivery = forge.start_mission("se.delivery", "Verify delivery")
    evidence = forge.record_evidence(delivery.mission_id, "explanation", "Explained tests")
    forge.advance_mastery("se.delivery", MasteryLevel.RECOGNIZE, evidence_id=evidence)
    data = forge.start_mission("math.data", "Verify data")
    evidence = forge.record_evidence(data.mission_id, "explanation", "Explained arrays")
    forge.advance_mastery("math.data", MasteryLevel.RECOGNIZE, evidence_id=evidence)
    maths = forge.start_mission("math.ml", "Verify math")
    evidence = forge.record_evidence(maths.mission_id, "explanation", "Explained gradients")
    forge.advance_mastery("math.ml", MasteryLevel.RECOGNIZE, evidence_id=evidence)
    fraud = forge.start_mission("ml.classical", "Build FraudShield baseline")
    forge.record_evidence(fraud.mission_id, "validated_project", "Validated a local baseline.")
    linked = forge.link_project(fraud.mission_id)
    assert linked.project_name == "FraudShield"
    assert forge.project_links() == (linked,)
    with pytest.raises(ValueError, match="already linked"):
        forge.link_project(fraud.mission_id)
    blocked = forge.create_public_evidence_candidate(
        fraud.mission_id, "artifacts/fraud-report.md",
        genuine_work=True, validation_passed=True, secret_scan_passed=False,
        privacy_review_passed=True, documentation_complete=True,
        artifact_quality_passed=True,
    )
    assert blocked.state == "blocked"
    assert blocked.reasons == ("secret scan has not passed",)
    with pytest.raises(ValueError, match="only qualified"):
        forge.approve_public_evidence(blocked.candidate_id)
    qualified = forge.create_public_evidence_candidate(
        fraud.mission_id, "artifacts/fraud-report.md",
        genuine_work=True, validation_passed=True, secret_scan_passed=True,
        privacy_review_passed=True, documentation_complete=True,
        artifact_quality_passed=True,
    )
    assert qualified.state == "qualified" and qualified.approved_at is None
    approved = forge.approve_public_evidence(qualified.candidate_id)
    assert approved.state == "approved" and approved.approved_at is not None
    bound = forge.bind_public_evidence_publication(
        approved.candidate_id, "task_123", "fraud-shield", "main",
    )
    assert (bound.task_id, bound.repository_id, bound.publication_state) == (
        "task_123", "fraud-shield", "ready",
    )
    failed = forge.record_public_evidence_publication_failure(bound.candidate_id, "network unavailable")
    assert failed.state == "approved" and failed.publication_state == "failed"
    published = forge.record_public_evidence_publication(
        bound.candidate_id, {"state": "published", "pr_url": "https://github.com/acme/fraud/pull/7"},
    )
    assert published.state == "published"
    assert published.publication_url == "https://github.com/acme/fraud/pull/7"
    assert published.published_at is not None
    with pytest.raises(ValueError, match="cannot be rebound"):
        forge.bind_public_evidence_publication(published.candidate_id, "task_999", "other", "main")
    with forge._db() as db:
        db.execute("UPDATE missions SET state='completed' WHERE mission_id=?", (fraud.mission_id,))
    with pytest.raises(ValueError, match="only an active mission"):
        forge.link_project(fraud.mission_id)


def test_active_mission_links_exactly_one_governed_objective(tmp_path):
    forge = CareerForgeService(tmp_path / "learner.sqlite3")
    mission = forge.start_mission("se.python", "Build a verified Python artifact")
    objective_id = "a" * 32

    linked = forge.link_mission_objective(mission.mission_id, objective_id)

    assert forge.mission_objective(mission.mission_id) == linked
    assert forge.link_mission_objective(mission.mission_id, objective_id) == linked
    with pytest.raises(ValueError, match="another objective"):
        forge.link_mission_objective(mission.mission_id, "b" * 32)
