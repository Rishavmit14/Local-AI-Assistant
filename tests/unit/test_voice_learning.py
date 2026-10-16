from __future__ import annotations

from threading import Event, Thread

from local_ai_assistant.career_forge.models import AttemptEvaluation
from local_ai_assistant.career_forge.service import CareerForgeService
from local_ai_assistant.interface.runtime import FridayRuntime
from local_ai_assistant.interface.voice_intents import FridayVoiceIntentRouter
from local_ai_assistant.interface.voice_learning import VoiceLearningCoordinator
from local_ai_assistant.learning_paths import CareerForgeEvidenceProjection, LearningPathService
from tests.fixtures.stage31_ml_curriculum import stage31_ml_engineering_curriculum


class CorrectReviewer:
    def stream_chat(self, prompt, *, system_prompt="", temperature=0.2, max_tokens=512, cancel_event=None):
        yield "ASSESSMENT: correct\nThe explanation directly addresses the contract."


class CancelReviewer:
    def stream_chat(self, prompt, *, system_prompt="", temperature=0.2, max_tokens=512, cancel_event=None):
        yield "ASSESSMENT: correct\nThis result must be discarded after cancellation."
        cancel_event.set()


class IncorrectReviewer:
    def stream_chat(self, prompt, *, system_prompt="", temperature=0.2, max_tokens=512, cancel_event=None):
        yield "ASSESSMENT: incorrect\nThe answer needs a clearer explanation of the held-out test set."


class FailingReviewer:
    def stream_chat(self, *_args, **_kwargs):
        raise RuntimeError("local reviewer unavailable")


class WaitingReviewer:
    def __init__(self):
        self.started = Event()
        self.release = Event()

    def stream_chat(self, prompt, *, system_prompt="", temperature=0.2, max_tokens=512, cancel_event=None):
        self.started.set()
        self.release.wait(timeout=2)
        yield "ASSESSMENT: correct\nA late result must not survive Stop."


def setup_coordinator(tmp_path, *, owner=True, reviewer=None):
    career = CareerForgeService(tmp_path / "career.sqlite3")
    paths = LearningPathService(
        tmp_path / "paths.sqlite3",
        evidence_provider=CareerForgeEvidenceProjection(career),
    )
    path = paths.create(stage31_ml_engineering_curriculum())
    paths.select(path.path_id)
    paths.activate(path.path_id)
    runtime = FridayRuntime("voice-learning-test")
    coordinator = VoiceLearningCoordinator(
        paths,
        career,
        runtime,
        owner_principal=(lambda: "local-owner") if owner else None,
        reviewer=reviewer or CorrectReviewer(),
    )
    return coordinator, career, paths, path, runtime


def intent(text: str, *, pending=False):
    return FridayVoiceIntentRouter().classify(text, pending_voice_answer=pending)


def handle(coordinator, text: str, *, pending=False, cancel_event=None, turn_id="turn-one"):
    return coordinator.handle(
        intent(text, pending=pending),
        owner_turn_id=turn_id,
        cancel_event=cancel_event or Event(),
    )


def test_voice_learning_requires_local_owner_before_creating_a_lesson(tmp_path):
    coordinator, career, paths, path, _ = setup_coordinator(tmp_path, owner=False)
    before = paths.sequence(path.path_id)

    decision = handle(coordinator, "continue my course")

    assert decision.response and "Owner authorization is unavailable" in decision.response
    assert career.resume() is None
    assert paths.sequence(path.path_id) == before


def test_voice_answer_is_only_recorded_after_explicit_confirmation(tmp_path):
    coordinator, career, _, _, runtime = setup_coordinator(tmp_path)
    lesson = handle(coordinator, "continue my course")
    assert lesson.lesson_turn and lesson.navigate_to_lesson
    mission = career.resume()
    first_question = mission.resume_point["question_id"]
    subject_id = mission.resume_point["subject_id"]

    draft = handle(coordinator, "my answer is I would separate train and test before fitting transforms")
    assert "not recorded an assessment yet" in draft.response
    assert coordinator.generalized.learning_state(subject_id)["attempts"] == []

    corrected = handle(
        coordinator,
        "correction: fit preprocessing on training only and evaluate once on held-out data",
        pending=True,
        turn_id="turn-correction",
    )
    assert "replaced the draft" in corrected.response
    assert coordinator.generalized.learning_state(subject_id)["attempts"] == []

    assessed = handle(coordinator, "yes, submit it", pending=True, turn_id="turn-confirm")
    attempts = coordinator.generalized.learning_state(subject_id)["attempts"]
    assert len(attempts) == 1
    assert attempts[0]["response"].startswith("fit preprocessing on training only")
    assert attempts[0]["evaluation"] == AttemptEvaluation.CORRECT.value
    assert attempts[0]["question_id"] == first_question
    assert "marked your answer correct" in assessed.response
    assert coordinator.generalized.learning_state(subject_id)["mastery"] != "unverified"

    handle(coordinator, "yes", pending=True, turn_id="turn-duplicate")
    assert len(coordinator.generalized.learning_state(subject_id)["attempts"]) == 1
    assert any(event.event_type.value == "voice.learning.state" for event in runtime.events_since())


def test_cancel_discards_only_the_unsubmitted_voice_draft(tmp_path):
    coordinator, career, _, _, _ = setup_coordinator(tmp_path)
    handle(coordinator, "continue my course")
    mission = career.resume()
    subject_id = mission.resume_point["subject_id"]
    handle(coordinator, "my answer is a draft that should never be submitted")

    decision = handle(coordinator, "cancel my answer", pending=True)

    assert "discarded the unsubmitted answer" in decision.response
    assert coordinator.generalized.learning_state(subject_id)["attempts"] == []
    assert not coordinator.has_pending_answer


def test_cancelled_reviewer_keeps_confirmed_attempt_pending_without_evidence(tmp_path):
    coordinator, career, _, _, _ = setup_coordinator(tmp_path, reviewer=CancelReviewer())
    handle(coordinator, "continue my course")
    subject_id = career.resume().resume_point["subject_id"]
    handle(coordinator, "my answer is a confirmed submission")

    cancel_event = Event()
    result = handle(
        coordinator,
        "yes",
        pending=True,
        cancel_event=cancel_event,
        turn_id="cancelled-review-turn",
    )

    state = coordinator.generalized.learning_state(subject_id)
    assert result.system_context is None
    assert state["attempts"][0]["evaluation"] == AttemptEvaluation.PENDING.value
    assert state["attempts"][0]["evidence_id"] is None
    assert state["evidence_count"] == 0


def test_stop_racing_with_reviewer_result_does_not_commit_late_feedback(tmp_path):
    reviewer = WaitingReviewer()
    coordinator, career, _, _, _ = setup_coordinator(tmp_path, reviewer=reviewer)
    handle(coordinator, "continue my course")
    subject_id = career.resume().resume_point["subject_id"]
    handle(coordinator, "my answer is a confirmed submission")
    cancel_event = Event()
    result = []
    worker = Thread(target=lambda: result.append(handle(
        coordinator,
        "yes",
        pending=True,
        cancel_event=cancel_event,
        turn_id="review-race-turn",
    )))
    worker.start()
    assert reviewer.started.wait(timeout=2)
    cancel_event.set()
    reviewer.release.set()
    worker.join(timeout=2)

    assert not worker.is_alive()
    assert result[0].system_context is None
    state = coordinator.generalized.learning_state(subject_id)
    assert len(state["attempts"]) == 1
    assert state["attempts"][0]["evaluation"] == AttemptEvaluation.PENDING.value
    assert state["attempts"][0]["evidence_id"] is None
    assert state["evidence_count"] == 0


def test_reviewer_failure_releases_turn_marker_and_allows_safe_retry(tmp_path):
    coordinator, career, _, _, _ = setup_coordinator(tmp_path, reviewer=FailingReviewer())
    handle(coordinator, "continue my course")
    subject_id = career.resume().resume_point["subject_id"]
    handle(coordinator, "my answer is a complete answer for review")

    pending = handle(coordinator, "yes", pending=True, turn_id="review-failure-turn")
    assert "awaiting Friday's local Reviewer" in pending.response
    assert coordinator.generalized.learning_state(subject_id)["attempts"][0]["evaluation"] == AttemptEvaluation.PENDING.value

    coordinator.reviewer = CorrectReviewer()
    retried = handle(coordinator, "check my answer", turn_id="review-retry-turn")

    state = coordinator.generalized.learning_state(subject_id)
    assert "marked your answer correct" in retried.response
    assert state["attempts"][0]["evaluation"] == AttemptEvaluation.CORRECT.value
    assert state["evidence_count"] == 1


def test_cancel_before_confirmation_does_not_write_an_attempt(tmp_path):
    coordinator, career, _, _, _ = setup_coordinator(tmp_path)
    handle(coordinator, "continue my course")
    subject_id = career.resume().resume_point["subject_id"]
    handle(coordinator, "my answer is still only a draft")
    cancel_event = Event()
    cancel_event.set()

    handle(coordinator, "yes", pending=True, cancel_event=cancel_event)

    assert coordinator.generalized.learning_state(subject_id)["attempts"] == []


def test_incorrect_voice_assessment_recommends_reinforcement_without_mastery(tmp_path):
    coordinator, career, _, path, _ = setup_coordinator(tmp_path, reviewer=IncorrectReviewer())
    handle(coordinator, "continue my course")
    subject_id = career.resume().resume_point["subject_id"]
    handle(coordinator, "my answer is accuracy proves the model works")

    result = handle(coordinator, "yes", pending=True)

    state = coordinator.generalized.learning_state(subject_id)
    projection = coordinator.learning_paths.sequence(path.path_id)
    assert "marked this answer incorrect" in result.response
    assert "reinforce" in result.response.lower()
    assert state["attempts"][0]["evaluation"] == AttemptEvaluation.INCORRECT.value
    assert state["attempts"][0]["evidence_id"] is None
    assert state["mastery"] == "unverified"
    assert projection["nodes"][0]["recommendation"] == "reinforce"
