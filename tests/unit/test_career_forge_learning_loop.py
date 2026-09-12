from local_ai_assistant.career_forge import (
    AssistanceLevel,
    AttemptEvaluation,
    CareerForgeLearningLoop,
    CareerForgeService,
    LessonPhase,
    TutorMode,
)


def test_explicit_attempt_evaluation_records_evidence_without_promoting_mastery(tmp_path):
    forge = CareerForgeService(tmp_path / "career.sqlite3")
    mission = forge.start_mission("se.python", "Verify Python")
    forge.update_resume(mission.mission_id, {"phase": LessonPhase.QUESTION, "question_id": "mutable_default"})
    loop = CareerForgeLearningLoop(forge)

    directive = loop.prepare("A default list is reused between calls.", mode=f"career_forge:explain:{mission.mission_id}")
    assert directive and directive.action == "attempt_received"
    attempt = forge.latest_attempt(mission.mission_id, pending_only=True)
    assert attempt and attempt.question_id == "mutable_default"

    evaluation = loop.prepare("Check my answer.", mode=f"career_forge:explain:{mission.mission_id}")
    assert evaluation and evaluation.action == "evaluate"
    loop.complete(evaluation, "ASSESSMENT: correct\nCorrect: the same mutable object is reused. Test two calls.")

    recorded = forge.attempt(attempt.attempt_id)
    assert recorded.evaluation is AttemptEvaluation.CORRECT
    assert recorded.evidence_type == "quiz_response"
    assert not recorded.retry_needed
    assert forge.competencies()[0].mastery.value == "unverified"
    assert forge.resume().resume_point["phase"] == LessonPhase.TEACH_BACK


def test_progressive_help_is_automatic_and_does_not_skip_levels(tmp_path):
    forge = CareerForgeService(tmp_path / "career.sqlite3")
    mission = forge.start_mission("se.python", "Verify Python")
    loop = CareerForgeLearningLoop(forge)

    first = loop.prepare("Give me a hint, but don't tell me the answer.", mode=f"career_forge:explain:{mission.mission_id}")
    assert first and first.assistance_level is AssistanceLevel.PROMPT
    assert "not giving the final answer" in first.response
    loop.complete(first, first.response)
    second = loop.prepare("I don't understand; give me a hint.", mode=f"career_forge:explain:{mission.mission_id}")
    assert second and second.assistance_level is AssistanceLevel.CONCEPTUAL_HINT
    loop.complete(second, second.response)
    assert forge.latest_assistance_level(mission.mission_id) is AssistanceLevel.CONCEPTUAL_HINT
    assert forge.resume().assistance_level == AssistanceLevel.CONCEPTUAL_HINT


def test_asr_hint_variants_and_pending_retry_stay_inside_lesson_boundary(tmp_path):
    forge = CareerForgeService(tmp_path / "career.sqlite3")
    mission = forge.start_mission("se.python", "Verify Python")
    forge.update_resume(mission.mission_id, {"phase": LessonPhase.EVALUATION, "question_id": "mutable_default"})
    pending = forge.record_attempt(mission.mission_id, "mutable_default", "An incomplete answer.", mode=TutorMode.EXPLAIN)
    loop = CareerForgeLearningLoop(forge)

    hint = loop.prepare("Give me a hand but do not tell me the answer", mode=f"career_forge:explain:{mission.mission_id}")
    assert hint and hint.action == "assistance" and hint.response
    loop.complete(hint, hint.response)
    replacement = loop.prepare("The default list is shared across calls.", mode=f"career_forge:explain:{mission.mission_id}")
    assert replacement and replacement.action == "attempt_received"
    assert forge.latest_attempt(mission.mission_id).attempt_id != pending.attempt_id


def test_uncertain_evaluation_requires_retry_and_survives_restart(tmp_path):
    path = tmp_path / "career.sqlite3"
    forge = CareerForgeService(path)
    mission = forge.start_mission("se.python", "Verify Python")
    forge.update_resume(mission.mission_id, {"phase": LessonPhase.TEACH_BACK, "question_id": "teach_back"})
    loop = CareerForgeLearningLoop(forge)
    received = loop.prepare("It has something to do with functions.", mode=f"career_forge:teach_back:{mission.mission_id}")
    assert received and received.action == "teach_back_evaluate"
    loop.complete(received, "The response was not structured enough to assess.")

    restored = CareerForgeService(path)
    attempt = restored.latest_attempt(mission.mission_id)
    assert attempt and attempt.evaluation is AttemptEvaluation.UNCERTAIN and attempt.retry_needed
    assert restored.resume().mission_id == mission.mission_id


def test_teach_back_is_evaluated_immediately_and_check_me_answer_is_recognized(tmp_path):
    forge = CareerForgeService(tmp_path / "career.sqlite3")
    mission = forge.start_mission("se.python", "Verify Python")
    forge.update_resume(mission.mission_id, {"phase": LessonPhase.TEACH_BACK, "question_id": "teach_back"})
    loop = CareerForgeLearningLoop(forge)
    directive = loop.prepare("A default list is made once and reused across calls.", mode=f"career_forge:teach_back:{mission.mission_id}")
    assert directive and directive.action == "teach_back_evaluate"
    loop.complete(directive, "ASSESSMENT: correct\nYou named the creation time and the shared-object consequence.")
    attempt = forge.latest_attempt(mission.mission_id)
    assert attempt.evaluation is AttemptEvaluation.CORRECT and attempt.evidence_type == "teach_back"

    forge.update_resume(mission.mission_id, {"phase": LessonPhase.QUESTION, "question_id": "another"})
    forge.record_attempt(mission.mission_id, "another", "Answer", mode=TutorMode.EXPLAIN)
    check = loop.prepare("Check me answer.", mode=f"career_forge:explain:{mission.mission_id}")
    assert check and check.action == "evaluate"


def test_short_conversational_aside_is_not_an_assessed_attempt(tmp_path):
    forge = CareerForgeService(tmp_path / "career.sqlite3")
    mission = forge.start_mission("se.python", "Verify Python")
    forge.update_resume(mission.mission_id, {"phase": LessonPhase.QUESTION, "question_id": "mutable_default"})
    loop = CareerForgeLearningLoop(forge)

    assert loop.prepare("Guess what?", mode=f"career_forge:explain:{mission.mission_id}") is None
    assert not forge.attempts(mission.mission_id)


def test_progress_projection_is_canonical_bounded_and_survives_restart(tmp_path):
    path = tmp_path / "career.sqlite3"
    forge = CareerForgeService(path)
    mission = forge.start_mission("se.python", "Verify Python")
    forge.update_resume(mission.mission_id, {"phase": LessonPhase.QUESTION, "question_id": "mutable_default"})
    first = forge.record_attempt(mission.mission_id, "mutable_default", "A new list is made each time.", mode=TutorMode.EXPLAIN)
    forge.evaluate_attempt(first.attempt_id, AttemptEvaluation.INCORRECT, "Defaults are created once; retry.")
    forge.offer_assistance(mission.mission_id, TutorMode.HINT, AssistanceLevel.PROMPT, "Trace two calls.")
    second = forge.record_attempt(mission.mission_id, "mutable_default", "The same default list is reused.", mode=TutorMode.EXPLAIN, assistance_level=AssistanceLevel.PROMPT)
    forge.evaluate_attempt(second.attempt_id, AttemptEvaluation.CORRECT, "Correct mechanism.", evidence_type="quiz_response")

    progress = CareerForgeService(path).progress()

    assert [item.attempt_order for item in progress.recent_attempts] == [2, 1]
    assert progress.assistance[0].level is AssistanceLevel.PROMPT
    assert progress.evidence[0].evidence_type == "quiz_response"
    assert progress.unresolved_retries[0].attempt_id == first.attempt_id
    assert progress.history[0].occurred_at >= progress.history[-1].occurred_at
    assert "Retry the active mission" in progress.next_action
    assert "percentage" not in progress.next_action
