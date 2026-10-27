from __future__ import annotations

from threading import Event

from local_ai_assistant.career_forge.service import CareerForgeService
from local_ai_assistant.interface.runtime import FridayRuntime
from local_ai_assistant.interface.voice_intents import (
    FridayVoiceIntentRouter,
    VoiceLearningAction,
)
from local_ai_assistant.interface.voice_learning import VoiceLearningCoordinator
from local_ai_assistant.learning_paths import (
    CareerForgeEvidenceProjection,
    LearningPathService,
)
from tests.fixtures.stage31_ml_curriculum import stage31_ml_engineering_curriculum


def test_clear_barge_in_repeat_request_routes_to_active_lesson(
    tmp_path,
) -> None:
    career = CareerForgeService(tmp_path / "career.sqlite3")
    paths = LearningPathService(
        tmp_path / "paths.sqlite3",
        evidence_provider=CareerForgeEvidenceProjection(career),
    )
    path = paths.create(stage31_ml_engineering_curriculum())
    paths.select(path.path_id)
    paths.activate(path.path_id)
    runtime = FridayRuntime("stage32-barge-in-integration")
    coordinator = VoiceLearningCoordinator(
        paths,
        career,
        runtime,
        owner_principal=lambda: "local-owner",
        reviewer=None,
    )
    router = FridayVoiceIntentRouter()

    initial = coordinator.handle(
        router.classify("continue my course"),
        owner_turn_id="initial-lesson-turn",
        cancel_event=Event(),
    )
    assert initial is not None and initial.lesson_turn
    mission_before_repeat = career.resume()
    assert mission_before_repeat is not None

    observed_asr_text = "Please explain the lesson again."
    repeat_intent = router.classify(observed_asr_text)
    assert repeat_intent.learning_action is VoiceLearningAction.REPEAT

    repeated = coordinator.handle(
        repeat_intent,
        owner_turn_id="physical-barge-in-follow-up",
        cancel_event=Event(),
    )

    assert repeated is not None and repeated.lesson_turn
    assert repeated.path_id == initial.path_id == path.path_id
    assert repeated.node_id == initial.node_id
    assert repeated.system_context is not None
    assert "Owner asked to hear this lesson again" in repeated.system_context
    assert career.resume().mission_id == mission_before_repeat.mission_id
    assert (
        coordinator.generalized.learning_state(mission_before_repeat.resume_point["subject_id"])[
            "attempts"
        ]
        == []
    )

    contexts = [
        event
        for event in runtime.events_since()
        if event.event_type.value == "voice.learning.context"
        and event.metadata.get("voice_turn_id") == "physical-barge-in-follow-up"
    ]
    assert len(contexts) == 1
    assert contexts[0].metadata["path_id"] == path.path_id
    assert contexts[0].metadata["node_id"] == initial.node_id
