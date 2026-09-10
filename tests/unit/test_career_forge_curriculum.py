import pytest

from local_ai_assistant.career_forge import (
    AssistanceLevel,
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


def test_mission_loop_and_progressive_assistance_preserve_independence_context(tmp_path):
    forge = CareerForgeService(tmp_path / "learner.sqlite3")
    mission = forge.start_mission("se.python", "Verify Python")
    assert forge.mission_loop(mission.mission_id)[0] == "why_it_matters"
    forge.offer_assistance(mission.mission_id, TutorMode.HINT, AssistanceLevel.PROMPT, "Predict first")
    with pytest.raises(ValueError, match="minimum useful"):
        forge.offer_assistance(mission.mission_id, TutorMode.GUIDE, AssistanceLevel.PARTIAL_EXAMPLE, "code")
    forge.offer_assistance(mission.mission_id, TutorMode.HINT, AssistanceLevel.CONCEPTUAL_HINT, "Think mutation")
    assert forge.resume().assistance_level == AssistanceLevel.CONCEPTUAL_HINT


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
    linked = forge.link_project(fraud.mission_id)
    assert linked.project_name == "FraudShield"
    assert forge.project_links() == (linked,)
    with pytest.raises(ValueError, match="already linked"):
        forge.link_project(fraud.mission_id)
