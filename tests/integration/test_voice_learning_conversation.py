from __future__ import annotations

import hashlib
from collections.abc import Iterator
from pathlib import Path

from fastapi.testclient import TestClient

from local_ai_assistant.career_forge.generalized import GeneralizedLearningService
from local_ai_assistant.career_forge.models import AttemptEvaluation
from local_ai_assistant.career_forge.service import CareerForgeService
from local_ai_assistant.interface.api import create_presentation_app
from local_ai_assistant.interface.conversation import FridayConversationService
from local_ai_assistant.interface.events import FridayEventType
from local_ai_assistant.interface.runtime import FridayRuntime
from local_ai_assistant.interface.voice_conversation import FridayVoiceConversationService
from local_ai_assistant.interface.voice_learning import VoiceLearningCoordinator
from local_ai_assistant.isolation.owner_rollback import OwnerBrowserSessions
from local_ai_assistant.learning_paths import CareerForgeEvidenceProjection, LearningPathService
from local_ai_assistant.voice import (
    PiperAudioChunk,
    SpeechPlaybackResult,
    VoiceUtterance,
    WhisperTranscript,
)
from tests.fixtures.stage31_ml_curriculum import stage31_ml_engineering_curriculum

OWNER_ORIGIN = "http://127.0.0.1:5193"
OWNER_CREDENTIAL = "isolated-stage32-voice-owner-credential"


class FixtureQwen:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def stream_chat(self, prompt: str, system_prompt: str = "", temperature: float = 0.2,
                    max_tokens: int = 1024, cancel_event=None) -> Iterator[str]:
        self.calls.append({"prompt": prompt, "system_prompt": system_prompt, "max_tokens": max_tokens})
        if cancel_event is not None and cancel_event.is_set():
            return
        yield (
            "A safe evaluation keeps preprocessing fit on training data only. "
            "For example, we choose the fraud threshold on validation data and "
            "reserve test data for one final estimate. How would you detect leakage?"
        )


class FixtureReviewer:
    def stream_chat(self, _prompt: str, *, system_prompt: str = "", temperature: float = 0.1,
                    max_tokens: int = 512, cancel_event=None) -> Iterator[str]:
        del system_prompt, temperature, max_tokens
        if cancel_event is not None and cancel_event.is_set():
            return
        yield "ASSESSMENT: correct\nThe response follows the fixed lesson contract."


class SyntheticFinalASR:
    def __init__(self, transcripts: list[str]) -> None:
        self.transcripts = iter(transcripts)

    def transcribe(self, utterance: VoiceUtterance) -> WhisperTranscript:
        del utterance
        return WhisperTranscript(
            text=next(self.transcripts),
            elapsed_seconds=0.0,
            audio_duration_ms=800,
            language="en",
            model_path=Path("/fixture/final-asr"),
            diagnostics="synthetic final transcript",
        )


class FixtureAnna:
    def __init__(self) -> None:
        self.spoken: list[str] = []

    def stream(self, text: str) -> Iterator[PiperAudioChunk]:
        self.spoken.append(text)
        yield PiperAudioChunk(b"\x01\x00" * 64, 22_050, 2, 1)


class FixturePlayback:
    def __init__(self) -> None:
        self.calls = 0

    def play(self, chunks: Iterator[PiperAudioChunk]) -> SpeechPlaybackResult:
        self.calls += 1
        byte_count = sum(len(chunk.pcm) for chunk in chunks)
        return SpeechPlaybackResult(False, 0.0, byte_count, 22_050)


def _utterance() -> VoiceUtterance:
    return VoiceUtterance(
        pcm=b"\x00\x00" * 12_800,
        sample_rate=16_000,
        channels=1,
        sample_width_bytes=2,
        duration_ms=800,
        speech_ms=700,
        completion_reason="synthetic_final_asr",
    )


def test_final_voice_transcripts_complete_canonical_learning_journey(tmp_path):
    career_db = tmp_path / "career.sqlite3"
    paths_db = tmp_path / "learning-paths.sqlite3"
    career = CareerForgeService(career_db)
    paths = LearningPathService(paths_db, evidence_provider=CareerForgeEvidenceProjection(career))
    path = paths.create(stage31_ml_engineering_curriculum())
    paths.select(path.path_id)
    paths.activate(path.path_id)
    runtime = FridayRuntime("isolated-voice-learning-journey")
    qwen = FixtureQwen()
    coordinator = VoiceLearningCoordinator(
        paths,
        career,
        runtime,
        owner_principal=lambda: "local-owner",
        reviewer=FixtureReviewer(),
    )
    conversation = FridayConversationService(qwen, runtime, voice_learning=coordinator)
    anna = FixtureAnna()
    playback = FixturePlayback()
    voice = FridayVoiceConversationService(
        SyntheticFinalASR([
            "Friday, continue my machine learning course.",
            "My answer is I fit preprocessing on training only, select the threshold on validation, and check features for information from after the decision.",
            "Yes, submit it.",
        ]),
        conversation,
        runtime,
        speech_synthesizer=anna,
        speech_player=playback,
    )
    utterance = _utterance()

    voice.start_listening()
    teaching = "".join(voice.stream_utterance(utterance))
    assert "How would you detect leakage?" in teaching
    assert "train/validation/test" in qwen.calls[0]["system_prompt"]
    assert "Explain how you would detect target leakage" in qwen.calls[0]["system_prompt"]
    assert anna.spoken and playback.calls > 0

    context_event = next(
        event for event in runtime.events_since()
        if event.event_type is FridayEventType.VOICE_LEARNING_CONTEXT
    )
    assert context_event.metadata["path_id"] == path.path_id
    assert context_event.metadata["node_id"] == "data-evaluation"

    voice.start_listening()
    answer_ack = "".join(voice.stream_utterance(utterance))
    assert "not recorded an assessment yet" in answer_ack
    state = coordinator.generalized.learning_state(career.resume().resume_point["subject_id"])
    assert state["attempts"] == []
    draft_event = next(
        event for event in reversed(runtime.events_since())
        if event.event_type is FridayEventType.VOICE_LEARNING_STATE
    )
    assert draft_event.metadata["state"] == "pending_confirmation"
    assert draft_event.text.startswith("I fit preprocessing")

    voice.start_listening()
    assessment = "".join(voice.stream_utterance(utterance))
    subject_id = career.resume().resume_point["subject_id"]
    state = coordinator.generalized.learning_state(subject_id)
    assert "marked your answer correct" in assessment
    assert len(state["attempts"]) == 1
    assert state["attempts"][0]["evaluation"] == AttemptEvaluation.CORRECT.value
    assert state["attempts"][0]["evidence_id"]
    assert state["evidence_count"] == 1
    assert "another fixed assessment question" in assessment

    # The existing API exposes the same canonical path/evidence and keeps its
    # browser mutation boundary independent from trusted local voice calls.
    sessions = OwnerBrowserSessions(hashlib.sha256(OWNER_CREDENTIAL.encode()).hexdigest())
    app = create_presentation_app(
        runtime,
        conversation,
        learning_paths=paths,
        career_forge=career,
        project_execution_sessions=sessions,
        project_execution_allowed_origins=(OWNER_ORIGIN,),
    )
    with TestClient(app, base_url=OWNER_ORIGIN) as client:
        session, _csrf = sessions.unlock(OWNER_CREDENTIAL)
        client.cookies.set("friday_project_session", session)
        sequence_response = client.get(f"/api/v1/learning-paths/{path.path_id}/sequence")
        assert sequence_response.status_code == 200
        assert sequence_response.json()["nodes"][0]["evidence_state"] != "satisfied"
        event_response = client.get("/api/v1/runtime/events?cursor=0")
        assert event_response.status_code == 200
        assert any(event["event_type"] == "voice.learning.context" for event in event_response.json())

    denied_app = create_presentation_app(runtime, conversation, learning_paths=paths, career_forge=career,
                                         project_execution_sessions=sessions,
                                         project_execution_allowed_origins=(OWNER_ORIGIN,))
    with TestClient(denied_app, base_url=OWNER_ORIGIN) as client:
        denied = client.post(
            f"/api/v1/career-forge/dynamic-learning/{subject_id}/attempts",
            headers={"Origin": OWNER_ORIGIN},
            json={"submission_id": "unauthorized-stage32-voice", "question_id": "data-leakage-reasoning-v1",
                  "response": "unauthorized"},
        )
        assert denied.status_code == 401
        assert len(coordinator.generalized.learning_state(subject_id)["attempts"]) == 1

    # Reconstruct both authorities from the same isolated SQLite files as an
    # API restart would; submitted feedback/evidence survives, drafts do not.
    recovered_career = CareerForgeService(career_db)
    recovered_paths = LearningPathService(
        paths_db, evidence_provider=CareerForgeEvidenceProjection(recovered_career),
    )
    recovered_subject = recovered_career.resume().resume_point["subject_id"]
    recovered_state = GeneralizedLearningService(recovered_career).learning_state(recovered_subject)
    assert recovered_state["attempts"][0]["evaluation"] == AttemptEvaluation.CORRECT.value
    assert recovered_state["evidence_count"] == 1
    assert recovered_paths.sequence(path.path_id)["nodes"][0]["evidence_state"] != "unverified"
    assert not coordinator.has_pending_answer

    recovered_runtime = FridayRuntime("isolated-voice-learning-api-restart")
    recovered_app = create_presentation_app(
        recovered_runtime,
        FridayConversationService(FixtureQwen(), recovered_runtime),
        learning_paths=recovered_paths,
        career_forge=recovered_career,
        project_execution_sessions=sessions,
        project_execution_allowed_origins=(OWNER_ORIGIN,),
    )
    with TestClient(recovered_app, base_url=OWNER_ORIGIN) as client:
        session, _csrf = sessions.unlock(OWNER_CREDENTIAL)
        client.cookies.set("friday_project_session", session)
        recovered_sequence = client.get(f"/api/v1/learning-paths/{path.path_id}/sequence")
        assert recovered_sequence.status_code == 200
    assert recovered_sequence.json()["nodes"][0]["evidence_state"] != "satisfied"
