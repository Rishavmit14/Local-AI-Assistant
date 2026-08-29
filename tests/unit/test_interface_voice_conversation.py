from __future__ import annotations

from pathlib import Path

import pytest

from local_ai_assistant.interface.conversation import FridayConversationService
from local_ai_assistant.interface.events import FridayEventType
from local_ai_assistant.interface.runtime import (
    FridayRuntime,
    InvalidRuntimeTransition,
)
from local_ai_assistant.interface.states import FridayRuntimeState
from local_ai_assistant.interface.voice_conversation import (
    FridayVoiceConversationService,
)
from local_ai_assistant.voice import VoiceUtterance, WhisperTranscript


class FakeStreamingLLM:
    def __init__(
        self,
        chunks: list[str] | None = None,
    ) -> None:
        self.chunks = list(
            chunks or []
        )
        self.calls: list[dict] = []

    def stream_chat(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ):
        self.calls.append(
            {
                "prompt": prompt,
                "system_prompt": system_prompt,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )

        yield from self.chunks


class FakeTranscriber:
    def __init__(
        self,
        text: str = "Friday voice test",
        error: Exception | None = None,
    ) -> None:
        self.text = text
        self.error = error
        self.calls: list[
            VoiceUtterance
        ] = []

    def transcribe(
        self,
        utterance: VoiceUtterance,
    ) -> WhisperTranscript:
        self.calls.append(
            utterance
        )

        if self.error is not None:
            raise self.error

        return WhisperTranscript(
            text=self.text,
            elapsed_seconds=0.42,
            audio_duration_ms=100,
            language="en",
            model_path=Path(
                "/AI/models/friday/stt/ggml-base.bin"
            ),
            diagnostics="test",
        )


def make_utterance() -> VoiceUtterance:
    return VoiceUtterance(
        pcm=b"\x00\x00" * 1600,
        sample_rate=16_000,
        channels=1,
        sample_width_bytes=2,
        duration_ms=100,
        speech_ms=100,
        completion_reason="silence",
    )


def make_service(
    *,
    transcript: str = "Friday voice test",
    chunks: list[str] | None = None,
):
    runtime = FridayRuntime(
        "session-voice"
    )

    llm = FakeStreamingLLM(
        chunks
        if chunks is not None
        else ["Hello", " Friday"]
    )

    conversation = FridayConversationService(
        llm,
        runtime,
    )

    transcriber = FakeTranscriber(
        transcript
    )

    voice = FridayVoiceConversationService(
        transcriber,
        conversation,
        runtime,
    )

    return (
        voice,
        transcriber,
        llm,
        runtime,
    )


def test_start_listening_enters_authoritative_state() -> None:
    voice, _, _, runtime = (
        make_service()
    )

    voice.start_listening()

    assert (
        runtime.state
        is FridayRuntimeState.LISTENING
    )

    events = runtime.events_since()

    assert [
        event.event_type
        for event in events
    ] == [
        FridayEventType.RUNTIME_STATE_CHANGED,
        FridayEventType.VOICE_LISTENING_STARTED,
    ]


def test_voice_transcript_enters_existing_conversation_boundary() -> None:
    voice, transcriber, llm, runtime = (
        make_service(
            transcript=(
                "  Friday can you hear me clearly?  "
            ),
            chunks=[
                "Yes",
                ", clearly.",
            ],
        )
    )

    utterance = make_utterance()

    voice.start_listening()

    output = "".join(
        voice.stream_utterance(
            utterance,
            system_prompt="Friday test",
            temperature=0.4,
            max_tokens=256,
        )
    )

    assert output == "Yes, clearly."
    assert transcriber.calls == [
        utterance
    ]

    assert llm.calls == [
        {
            "prompt": "Friday can you hear me clearly?",
            "system_prompt": "Friday test",
            "temperature": 0.4,
            "max_tokens": 256,
        }
    ]

    assert (
        runtime.state
        is FridayRuntimeState.COMPLETED
    )

    events = runtime.events_since()

    voice_event = next(
        event
        for event in events
        if (
            event.event_type
            is FridayEventType.VOICE_TRANSCRIPTION
        )
    )

    user_event = next(
        event
        for event in events
        if (
            event.event_type
            is FridayEventType.CONVERSATION_USER_TEXT
        )
    )

    assert (
        voice_event.text
        == "Friday can you hear me clearly?"
    )

    assert (
        user_event.text
        == voice_event.text
    )

    states = [
        event.state
        for event in events
        if (
            event.event_type
            is FridayEventType.RUNTIME_STATE_CHANGED
            and event.state is not None
        )
    ]

    assert states == [
        FridayRuntimeState.LISTENING,
        FridayRuntimeState.TRANSCRIBING,
        FridayRuntimeState.THINKING,
        FridayRuntimeState.COMPLETED,
    ]


def test_empty_transcript_returns_idle_without_llm() -> None:
    voice, _, llm, runtime = (
        make_service(
            transcript="   "
        )
    )

    voice.start_listening()

    output = "".join(
        voice.stream_utterance(
            make_utterance()
        )
    )

    assert output == ""
    assert llm.calls == []

    assert (
        runtime.state
        is FridayRuntimeState.IDLE
    )

    assert not any(
        event.event_type
        is FridayEventType.CONVERSATION_USER_TEXT
        for event in runtime.events_since()
    )


def test_transcription_failure_fails_closed() -> None:
    runtime = FridayRuntime(
        "session-error"
    )

    llm = FakeStreamingLLM(
        ["unused"]
    )

    conversation = FridayConversationService(
        llm,
        runtime,
    )

    voice = FridayVoiceConversationService(
        FakeTranscriber(
            error=RuntimeError(
                "whisper unavailable"
            )
        ),
        conversation,
        runtime,
    )

    voice.start_listening()

    with pytest.raises(
        RuntimeError,
        match="whisper unavailable",
    ):
        list(
            voice.stream_utterance(
                make_utterance()
            )
        )

    assert (
        runtime.state
        is FridayRuntimeState.ERROR
    )

    assert llm.calls == []

    events = runtime.events_since()

    assert any(
        (
            event.event_type
            is FridayEventType.RUNTIME_ERROR
        )
        and (
            event.text
            == "voice transcription failed"
        )
        for event in events
    )

    assert not any(
        event.event_type
        is FridayEventType.CONVERSATION_USER_TEXT
        for event in events
    )


def test_utterance_fails_closed_when_not_listening() -> None:
    voice, transcriber, llm, runtime = (
        make_service()
    )

    with pytest.raises(
        InvalidRuntimeTransition,
        match="requires listening state",
    ):
        list(
            voice.stream_utterance(
                make_utterance()
            )
        )

    assert (
        runtime.state
        is FridayRuntimeState.IDLE
    )

    assert runtime.events_since() == ()
    assert transcriber.calls == []
    assert llm.calls == []


def test_next_voice_turn_recovers_from_completed() -> None:
    voice, _, llm, runtime = (
        make_service(
            transcript="Voice request",
            chunks=["ok"],
        )
    )

    voice.start_listening()

    first = "".join(
        voice.stream_utterance(
            make_utterance()
        )
    )

    assert first == "ok"

    assert (
        runtime.state
        is FridayRuntimeState.COMPLETED
    )

    voice.start_listening()

    assert (
        runtime.state
        is FridayRuntimeState.LISTENING
    )

    second = "".join(
        voice.stream_utterance(
            make_utterance()
        )
    )

    assert second == "ok"
    assert len(llm.calls) == 2

    assert (
        runtime.state
        is FridayRuntimeState.COMPLETED
    )

    reasons = [
        event.metadata.get(
            "reason"
        )
        for event in runtime.events_since()
        if (
            event.event_type
            is FridayEventType.RUNTIME_STATE_CHANGED
        )
    ]

    assert "voice_ready" in reasons
