from pathlib import Path
from threading import Barrier, Thread

import pytest

from local_ai_assistant.career_forge.generalized import GeneralizedLearningService
from local_ai_assistant.career_forge.models import (
    AssistanceLevel,
    AttemptEvaluation,
    MasteryLevel,
    TutorMode,
)
from local_ai_assistant.career_forge.service import CareerForgeService
from local_ai_assistant.learning_paths.evidence import CareerForgeEvidenceProjection, evidence_state
from local_ai_assistant.learning_paths.service import LearningPathService
from tests.fixtures.learning_path_curricula import curriculum


def _node(**changes):
    return {
        "node_id": "sql-plans",
        "title": "SQL execution plans",
        "type": "concept",
        "objectives": ["Explain how an index changes a query plan"],
        "evidence_requirements": ["Interpret a simple plan"],
        **changes,
    }


def test_dynamic_subject_registration_is_restart_safe_and_does_not_claim_mastery(tmp_path: Path):
    db = tmp_path / "learner.sqlite3"
    forge = CareerForgeService(db)
    service = GeneralizedLearningService(forge)

    first = service.register(path_id="path-a", path_version=1, node=_node())
    again = GeneralizedLearningService(CareerForgeService(db)).register(
        path_id="path-a", path_version=1, node=_node()
    )

    assert first == again
    assert first.mastery is MasteryLevel.UNVERIFIED
    assert service.matching_evidence_count(first.subject_id) == 0


def test_contract_hash_ignores_cosmetic_title_but_changes_with_objectives():
    original = _node()
    renamed = _node(title="SQL Plans: an introduction")
    changed = _node(objectives=["Compare multi-column index plans and estimate scan cost"])

    assert GeneralizedLearningService.contract_fingerprint(original) == GeneralizedLearningService.contract_fingerprint(renamed)
    assert GeneralizedLearningService.contract_fingerprint(original) != GeneralizedLearningService.contract_fingerprint(changed)


def test_dynamic_subject_session_is_bound_and_conflicting_mission_is_preserved(tmp_path: Path):
    forge = CareerForgeService(tmp_path / "learner.sqlite3")
    service = GeneralizedLearningService(forge)
    subject = service.register(path_id="path-a", path_version=1, node=_node())
    mission = service.start_session(subject.subject_id)

    assert mission.resume_point["contract_fingerprint"] == subject.contract_fingerprint
    assert service.start_session(subject.subject_id).mission_id == mission.mission_id
    other = service.register(path_id="path-b", path_version=1, node=_node())
    with pytest.raises(ValueError, match="already has active mission"):
        service.start_session(other.subject_id)
    assert forge.resume().mission_id == mission.mission_id


def test_mastery_rejects_missing_or_unrelated_contract_evidence(tmp_path: Path):
    forge = CareerForgeService(tmp_path / "learner.sqlite3")
    service = GeneralizedLearningService(forge)
    subject = service.register(path_id="path-a", path_version=1, node=_node())

    with pytest.raises(ValueError, match="matching contract evidence"):
        service.advance_mastery(subject.subject_id, MasteryLevel.RECOGNIZE, evidence_id="forged")


def test_dynamic_correct_assessment_creates_one_contract_bound_evidence_and_one_rung(tmp_path: Path):
    forge = CareerForgeService(tmp_path / "learner.sqlite3")
    service = GeneralizedLearningService(forge)
    subject = service.register(path_id="path-a", path_version=1, node=_node())
    service.start_session(subject.subject_id)
    attempt = service.record_attempt(subject.subject_id, "q1", "An index can reduce scanned rows.")

    prompt = service.assessment_prompt(subject.subject_id, attempt.attempt_id)
    assert subject.contract_fingerprint in prompt or "Explain how an index" in prompt
    result = service.assess_attempt(subject.subject_id, attempt.attempt_id,
                                    "ASSESSMENT: correct\nThe answer identifies the index effect.")

    assert result["evaluation"] == "correct"
    assert result["evidence_id"]
    assert result["mastery"] == MasteryLevel.RECOGNIZE
    assert service.matching_evidence_count(subject.subject_id) == 1
    with pytest.raises(ValueError, match="already been evaluated"):
        service.assess_attempt(subject.subject_id, attempt.attempt_id, "ASSESSMENT: correct\nReplay")


def test_explicit_cross_path_equivalence_reuses_only_matching_qualified_evidence(tmp_path: Path):
    forge = CareerForgeService(tmp_path / "learner.sqlite3")
    service = GeneralizedLearningService(forge)
    projection = CareerForgeEvidenceProjection(forge)
    source_node = _node(equivalence_key="sql.query-plan.interpretation")
    source = service.register(path_id="path-source", path_version=1, node=source_node)
    service.start_session(source.subject_id)
    for index in range(4):
        attempt = service.record_attempt(source.subject_id, f"q{index}", f"Independent explanation {index}.")
        result = service.assess_attempt(source.subject_id, attempt.attempt_id,
                                        "ASSESSMENT: correct\nCorrect independent application.")
        assert result["evidence_id"]

    target_node = _node(node_id="query-plans-target", title="Query plan analysis",
                        equivalence_key="sql.query-plan.interpretation")
    declared_sources = {("path-source", "sql-plans")}
    reused = projection.dynamic_node_evidence("path-target", 1, target_node, equivalent_sources=declared_sources)

    assert reused is not None
    assert reused.mastery == MasteryLevel.APPLY_INDEPENDENTLY
    assert reused.confidence == "current"
    assert reused.equivalent_source["path_id"] == "path-source"
    assert reused.equivalent_source["node_id"] == "sql-plans"
    assert reused.equivalent_source["evidence_id"]
    assert reused.equivalent_source["evaluation_authority"] == "career_forge_local_assessment"
    assert projection.dynamic_node_evidence("path-target", 1, target_node) is None
    assert projection.dynamic_node_evidence(
        "path-target", 1, _node(node_id="other", equivalence_key="sql.other")
    ) is None
    assert projection.dynamic_node_evidence(
        "path-target", 1, _node(node_id="other", objectives=["Advanced optimizer cost analysis"],
                                 equivalence_key="sql.query-plan.interpretation"),
        equivalent_sources=declared_sources,
    ) is None


def test_cross_path_equivalence_rejects_failed_or_lower_level_evidence(tmp_path: Path):
    forge = CareerForgeService(tmp_path / "learner.sqlite3")
    service = GeneralizedLearningService(forge)
    projection = CareerForgeEvidenceProjection(forge)
    node = _node(equivalence_key="sql.query-plan.interpretation")
    source = service.register(path_id="path-source", path_version=1, node=node)
    service.start_session(source.subject_id)
    attempt = service.record_attempt(source.subject_id, "wrong", "Incorrect answer.")
    service.assess_attempt(source.subject_id, attempt.attempt_id, "ASSESSMENT: incorrect\nIncorrect.")
    target = _node(node_id="target", equivalence_key="sql.query-plan.interpretation")
    assert projection.dynamic_node_evidence("path-target", 1, target) is None

    # One successful attempt creates evidence, but its recognized-level mastery
    # remains below the independent-application threshold used by DLP.
    attempt = service.record_attempt(source.subject_id, "right", "A correct basic answer.")
    service.assess_attempt(source.subject_id, attempt.attempt_id, "ASSESSMENT: correct\nCorrect.")
    result = projection.dynamic_node_evidence("path-target", 1, target,
                                              equivalent_sources={("path-source", "sql-plans")})
    assert result is not None
    assert result.mastery == MasteryLevel.RECOGNIZE
    assert result.confidence == "current"
    assert evidence_state(result) == "needs_diagnostic"


def test_cross_path_equivalent_evidence_obeys_canonical_retention_state(tmp_path: Path):
    forge = CareerForgeService(tmp_path / "learner.sqlite3")
    service = GeneralizedLearningService(forge)
    projection = CareerForgeEvidenceProjection(forge)
    node = _node(equivalence_key="sql.query-plan.interpretation")
    source = service.register(path_id="path-source", path_version=1, node=node)
    service.start_session(source.subject_id)
    for index in range(4):
        attempt = service.record_attempt(source.subject_id, f"q{index}", f"Independent {index}.")
        service.assess_attempt(source.subject_id, attempt.attempt_id, "ASSESSMENT: correct\nCorrect.")
    with forge._db() as db:
        db.execute("UPDATE retention_reviews SET due_at='2000-01-01T00:00:00+00:00' WHERE competency_id=?",
                   (source.competency_id,))
    result = projection.dynamic_node_evidence(
        "path-target", 1, _node(node_id="target", equivalence_key="sql.query-plan.interpretation"),
        equivalent_sources={("path-source", "sql-plans")},
    )
    assert result is not None
    assert result.mastery == MasteryLevel.APPLY_INDEPENDENTLY
    assert result.confidence == "stale"
    assert result.review_due


def test_dlp_sequences_cross_path_evidence_with_source_after_reconstruction(tmp_path: Path):
    learner_db = tmp_path / "learner.sqlite3"
    paths_db = tmp_path / "paths.sqlite3"
    forge = CareerForgeService(learner_db)
    learning = LearningPathService(paths_db, evidence_provider=CareerForgeEvidenceProjection(forge))
    source_payload = curriculum()
    target_payload = curriculum()
    for payload, title in ((source_payload, "Source curriculum"), (target_payload, "Target curriculum")):
        payload["nodes"][0].update(
            title=title, objectives=["Explain how indexes affect a query plan"],
            evidence_requirements=["Interpret a representative execution plan"],
            equivalence_key="sql.query-plan.interpretation",
        )
    source_path = learning.create(source_payload)
    target_path = learning.create(target_payload)
    source_node = source_payload["nodes"][0]
    generalized = GeneralizedLearningService(forge)
    subject = generalized.register(path_id=source_path.path_id, path_version=1, node=source_node)
    generalized.start_session(subject.subject_id)
    for index in range(4):
        attempt = generalized.record_attempt(subject.subject_id, f"q{index}", f"Independent application {index}.")
        generalized.assess_attempt(subject.subject_id, attempt.attempt_id,
                                   "ASSESSMENT: correct\nCorrect independent application.")

    reconstructed = LearningPathService(
        paths_db, evidence_provider=CareerForgeEvidenceProjection(CareerForgeService(learner_db))
    )
    target = next(item for item in reconstructed.sequence(target_path.path_id)["nodes"]
                  if item["node_id"] == "arrays")
    assert target["evidence_state"] == "satisfied"
    assert target["decision"] == "SKIP_ALREADY_SUPPORTED"
    assert target["evidence"]["equivalent_source"]["path_id"] == source_path.path_id
    assert target["evidence"]["equivalent_source"]["node_id"] == "arrays"
    assert "source history is unchanged" in target["reason"]
    assert generalized.matching_evidence_count(subject.subject_id) == 4

    advanced_payload = curriculum()
    advanced_payload["nodes"][0].update(
        objectives=["Explain how indexes affect a query plan"],
        evidence_requirements=["Interpret a representative execution plan"],
        equivalence_key="sql.query-plan.interpretation", required_mastery="transfer_debug",
    )
    advanced_path = reconstructed.create(advanced_payload)
    advanced = next(item for item in reconstructed.sequence(advanced_path.path_id)["nodes"]
                    if item["node_id"] == "arrays")
    assert advanced["evidence_state"] == "needs_diagnostic"
    assert advanced["decision"] == "DIAGNOSTIC_FIRST"
    assert "at apply_independently" in advanced["reason"]
    assert "needs transfer_debug" in advanced["reason"]
    assert generalized.get(subject.subject_id).mastery == MasteryLevel.APPLY_INDEPENDENTLY


@pytest.mark.parametrize("model_response", ["no label", "ASSESSMENT: uncertain\\nNeeds detail", "ASSESSMENT: incorrect\\nRetry"])
def test_noncorrect_or_malformed_dynamic_assessment_never_creates_evidence(tmp_path: Path, model_response):
    forge = CareerForgeService(tmp_path / "learner.sqlite3")
    service = GeneralizedLearningService(forge)
    subject = service.register(path_id="path-a", path_version=1, node=_node())
    service.start_session(subject.subject_id)
    attempt = service.record_attempt(subject.subject_id, "q1", "An answer that needs assessment.")

    result = service.assess_attempt(subject.subject_id, attempt.attempt_id, model_response)

    assert result["evaluation"] in {AttemptEvaluation.INCORRECT.value, AttemptEvaluation.UNCERTAIN.value}
    assert result["evidence_id"] is None
    assert result["mastery"] == MasteryLevel.UNVERIFIED
    assert service.matching_evidence_count(subject.subject_id) == 0
    assert any(area.competency_id == subject.competency_id for area in forge.progress().weak_areas)


def test_dynamic_retention_delivery_and_failure_weakens_only_current_subject(tmp_path: Path):
    forge = CareerForgeService(tmp_path / "learner.sqlite3")
    service = GeneralizedLearningService(forge)
    subject = service.register(path_id="path-a", path_version=1, node=_node())
    service.start_session(subject.subject_id)
    for rung in range(4):
        attempt = service.record_attempt(subject.subject_id, f"q{rung}", f"Independent response {rung}.")
        service.assess_attempt(subject.subject_id, attempt.attempt_id, "ASSESSMENT: correct\nDemonstrated.")
    review = next(item for item in forge.retention_reviews(limit=100) if item.competency_id == subject.competency_id)
    with forge._db() as db:
        db.execute("UPDATE retention_reviews SET due_at='2000-01-01T00:00:00+00:00' WHERE review_id=?", (review.review_id,))
    delivered, prompt = forge.deliver_retention_review(review.review_id)
    assert delivered.state == "delivered"
    assert "SQL execution plans" in prompt
    forge.evaluate_retention_review(review.review_id, "I forgot the mechanism.", AttemptEvaluation.INCORRECT, "Review the objective.")
    evidence = CareerForgeEvidenceProjection(forge).dynamic_node_evidence("path-a", 1, _node())
    assert evidence is not None
    assert evidence.confidence == "weak"
    assert evidence.retention == "failed"


def test_dynamic_assistance_provenance_prevents_helped_answer_from_counting_as_independent(tmp_path: Path):
    forge = CareerForgeService(tmp_path / "learner.sqlite3")
    service = GeneralizedLearningService(forge)
    subject = service.register(path_id="path-a", path_version=1, node=_node())
    mission = service.start_session(subject.subject_id)
    forge.offer_assistance(mission.mission_id, TutorMode.HINT, AssistanceLevel.PROMPT, "Check the access path.")

    attempt = service.record_attempt(subject.subject_id, "assisted-q", "An index can reduce scanned rows.")

    assert attempt.assistance_level is AssistanceLevel.PROMPT
    result = service.assess_attempt(subject.subject_id, attempt.attempt_id, "ASSESSMENT: correct\nDemonstrated.")
    assert result["mastery"] == MasteryLevel.RECOGNIZE
    assert service.get(subject.subject_id).mastery is not MasteryLevel.APPLY_INDEPENDENTLY


def test_dynamic_assistance_provenance_expires_after_the_answer_it_helped(tmp_path: Path):
    forge = CareerForgeService(tmp_path / "career.sqlite3")
    service = GeneralizedLearningService(forge)
    subject = service.register(path_id="path-a", path_version=1, node=_node())
    mission = service.start_session(subject.subject_id)
    forge.offer_assistance(mission.mission_id, TutorMode.HINT, AssistanceLevel.PROMPT, "Check the access path.")

    assisted = service.record_attempt(subject.subject_id, "assisted-q", "An index can reduce scanned rows.")
    service.assess_attempt(subject.subject_id, assisted.attempt_id, "ASSESSMENT: correct\nDemonstrated.")
    independent_attempts = []
    for index in range(3):
        attempt = service.record_attempt(subject.subject_id, f"independent-{index}", "The optimizer compares index access cost with a table scan.")
        assert attempt.assistance_level is None
        service.assess_attempt(subject.subject_id, attempt.attempt_id, "ASSESSMENT: correct\nDemonstrated.")
        independent_attempts.append(attempt)

    assert service.get(subject.subject_id).mastery is MasteryLevel.APPLY_INDEPENDENTLY
    with forge._db() as db:
        evidence_assistance = db.execute(
            "SELECT assistance_level FROM mission_evidence WHERE source_attempt_id=?",
            (assisted.attempt_id,),
        ).fetchone()[0]
        later_provenance = db.execute(
            "SELECT assistance_level FROM lesson_attempts WHERE attempt_id=?",
            (independent_attempts[0].attempt_id,),
        ).fetchone()[0]
    assert evidence_assistance == AssistanceLevel.PROMPT
    assert later_provenance is None


def test_correct_assisted_evidence_cannot_fail_when_independent_threshold_is_not_met(tmp_path: Path):
    forge = CareerForgeService(tmp_path / "career.sqlite3")
    service = GeneralizedLearningService(forge)
    subject = service.register(path_id="path-a", path_version=1, node=_node())
    mission = service.start_session(subject.subject_id)

    for index in range(4):
        forge.offer_assistance(mission.mission_id, TutorMode.HINT, AssistanceLevel.PROMPT, f"Hint {index}.")
        attempt = service.record_attempt(subject.subject_id, f"helped-{index}", "An index can reduce scanned rows.")
        result = service.assess_attempt(subject.subject_id, attempt.attempt_id, "ASSESSMENT: correct\nDemonstrated.")

    assert result["evaluation"] == AttemptEvaluation.CORRECT
    assert result["evidence_id"]
    assert result["mastery"] == MasteryLevel.APPLY_WITH_HELP
    assert service.matching_evidence_count(subject.subject_id) == 4


def test_concurrent_dynamic_assessment_replay_has_one_evidence_and_transition(tmp_path: Path):
    forge = CareerForgeService(tmp_path / "career.sqlite3")
    service = GeneralizedLearningService(forge)
    subject = service.register(path_id="path-a", path_version=1, node=_node())
    service.start_session(subject.subject_id)
    attempt = service.record_attempt(subject.subject_id, "concurrent-q", "An index can reduce rows visited.")
    barrier = Barrier(3)
    outcomes = []

    def assess():
        barrier.wait()
        try:
            outcomes.append(service.assess_attempt(
                subject.subject_id, attempt.attempt_id, "ASSESSMENT: correct\nDemonstrated.",
            ))
        except ValueError as exc:
            outcomes.append(exc)

    workers = [Thread(target=assess) for _ in range(2)]
    for worker in workers:
        worker.start()
    barrier.wait()
    for worker in workers:
        worker.join(timeout=5)
        assert not worker.is_alive()

    assert sum(isinstance(item, dict) for item in outcomes) == 1
    with forge._db() as db:
        assert db.execute("SELECT COUNT(*) FROM mission_evidence WHERE source_attempt_id=?", (attempt.attempt_id,)).fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM dynamic_mastery_transitions").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM retention_reviews WHERE evidence_id IN (SELECT evidence_id FROM mission_evidence WHERE source_attempt_id=?)", (attempt.attempt_id,)).fetchone()[0] == 1
