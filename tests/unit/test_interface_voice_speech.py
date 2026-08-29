from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest

from local_ai_assistant.interface.conversation import (
    FridayConversationService,
)
from local_ai_assistant.interface.events import (
    FridayEventType,
)
from local_ai_assistant.interface.runtime import (
    FridayRuntime,
)
from local_ai_assistant.interface.states import (
    FridayRuntimeState,
)
from local_ai_assistant.interface.voice_conversation import (
    FridayVoiceConversationService,
)
from local_ai_assistant.voice import (
    PiperAudioChunk,
    SpeechPlaybackResult,
    VoiceUtterance,
)


class FakeTranscriber:
    def __init__(
        self,
        text: str = "Friday voice request",
    ) -> None:
        self.text = text
        self.calls = 0

    def transcribe(
        self,
        utterance: VoiceUtterance,
    ):
        self.calls += 1

        return SimpleNamespace(
            text=self.text,
            elapsed_seconds=0.1,
            audio_duration_ms=(
                utterance.duration_ms
            ),
            language="en",
            model_path=Path(
                "/tmp/friday-test-whisper.bin"
            ),
        )


class FakeStreamingLLM:
    def __init__(
        self,
        chunks: list[str],
    ) -> None:
        self.chunks = chunks
        self.calls: list[str] = []

    def stream_chat(
        self,
        prompt: str,
        *,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> Iterator[str]:
        del system_prompt
        del temperature
        del max_tokens

        self.calls.append(
            prompt
        )

        yield from self.chunks


class FakeSpeechSynthesizer:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def stream(
        self,
        text: str,
    ) -> Iterator[PiperAudioChunk]:
        self.calls.append(
            text
        )

        yield PiperAudioChunk(
            pcm=b"\x01\x00" * 100,
            sample_rate=22_050,
            sample_width_bytes=2,
            channels=1,
        )


class FakeSpeechPlayer:
    def __init__(
        self,
        *,
        interrupted: bool = False,
        error: Exception | None = None,
    ) -> None:
        self.interrupted = interrupted
        self.error = error
        self.calls = 0
        self.received_bytes = 0

    def play(
        self,
        chunks: Iterator[PiperAudioChunk],
    ) -> SpeechPlaybackResult:
        self.calls += 1

        if self.error is not None:
            raise self.error

        for chunk in chunks:
            self.received_bytes += len(
                chunk.pcm
            )

        return SpeechPlaybackResult(
            interrupted=self.interrupted,
            elapsed_seconds=0.25,
            pcm_bytes_written=self.received_bytes,
            sample_rate=22_050,
        )


def make_utterance() -> VoiceUtterance:
    return VoiceUtterance(
        pcm=b"\x00\x00" * 16_000,
        sample_rate=16_000,
        channels=1,
        sample_width_bytes=2,
        duration_ms=1_000,
        speech_ms=800,
        completion_reason="silence",
    )


def make_voice_service(
    *,
    chunks: list[str] | None = None,
    player: FakeSpeechPlayer | None = None,
):
    runtime = FridayRuntime(
        "stage-11f3-test"
    )

    transcriber = FakeTranscriber()

    llm = FakeStreamingLLM(
        chunks
        if chunks is not None
        else [
            "Friday ",
            "speech ready.",
        ]
    )

    conversation = FridayConversationService(
        llm,
        runtime,
    )

    synthesizer = (
        FakeSpeechSynthesizer()
    )

    player = (
        player
        if player is not None
        else FakeSpeechPlayer()
    )

    service = (
        FridayVoiceConversationService(
            transcriber,
            conversation,
            runtime,
            speech_synthesizer=(
                synthesizer
            ),
            speech_player=player,
        )
    )

    return (
        service,
        runtime,
        transcriber,
        llm,
        synthesizer,
        player,
    )


def state_path(
    runtime: FridayRuntime,
) -> list[FridayRuntimeState]:
    return [
        event.state
        for event in runtime.events_since()
        if (
            event.event_type
            is FridayEventType.RUNTIME_STATE_CHANGED
        )
        and event.state is not None
    ]


def test_completed_response_enters_speaking_then_idle() -> None:
    (
        voice,
        runtime,
        _,
        _,
        synthesizer,
        player,
    ) = make_voice_service()

    voice.start_listening()

    output = "".join(
        voice.stream_utterance(
            make_utterance()
        )
    )

    assert (
        output
        == "Friday speech ready."
    )

    assert (
        synthesizer.calls
        == [
            "Friday speech ready.",
        ]
    )

    assert player.calls == 1

    assert (
        player.received_bytes
        == 200
    )

    assert (
        runtime.state
        is FridayRuntimeState.IDLE
    )

    assert state_path(
        runtime
    ) == [
        FridayRuntimeState.LISTENING,
        FridayRuntimeState.TRANSCRIBING,
        FridayRuntimeState.THINKING,
        FridayRuntimeState.COMPLETED,
        FridayRuntimeState.SPEAKING,
        FridayRuntimeState.IDLE,
    ]

    event_types = [
        event.event_type
        for event in runtime.events_since()
    ]

    completed_index = event_types.index(
        FridayEventType.CONVERSATION_ASSISTANT_COMPLETED
    )

    speaking_index = event_types.index(
        FridayEventType.VOICE_SPEECH_STARTED
    )

    speech_completed_index = (
        event_types.index(
            FridayEventType.VOICE_SPEECH_COMPLETED
        )
    )

    assert (
        completed_index
        < speaking_index
        < speech_completed_index
    )

    assert (
        FridayEventType.VOICE_SPEECH_INTERRUPTED
        not in event_types
    )


def test_interrupted_playback_emits_interrupted_and_returns_idle() -> None:
    player = FakeSpeechPlayer(
        interrupted=True
    )

    (
        voice,
        runtime,
        _,
        _,
        _,
        _,
    ) = make_voice_service(
        player=player
    )

    voice.start_listening()

    output = "".join(
        voice.stream_utterance(
            make_utterance()
        )
    )

    assert output

    assert (
        runtime.state
        is FridayRuntimeState.IDLE
    )

    event_types = [
        event.event_type
        for event in runtime.events_since()
    ]

    assert (
        FridayEventType.VOICE_SPEECH_INTERRUPTED
        in event_types
    )

    assert (
        FridayEventType.VOICE_SPEECH_COMPLETED
        not in event_types
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

    assert (
        "voice_speech_interrupted"
        in reasons
    )


def test_speech_failure_fails_closed_to_error() -> None:
    player = FakeSpeechPlayer(
        error=RuntimeError(
            "speaker unavailable"
        )
    )

    (
        voice,
        runtime,
        _,
        _,
        _,
        _,
    ) = make_voice_service(
        player=player
    )

    voice.start_listening()

    with pytest.raises(
        RuntimeError,
        match="speaker unavailable",
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

    errors = [
        event
        for event in runtime.events_since()
        if (
            event.event_type
            is FridayEventType.RUNTIME_ERROR
        )
    ]

    assert errors

    assert (
        errors[-1].text
        == "voice speech failed"
    )


def test_empty_assistant_response_does_not_start_speech() -> None:
    (
        voice,
        runtime,
        _,
        _,
        synthesizer,
        player,
    ) = make_voice_service(
        chunks=[]
    )

    voice.start_listening()

    output = "".join(
        voice.stream_utterance(
            make_utterance()
        )
    )

    assert output == ""

    assert (
        runtime.state
        is FridayRuntimeState.COMPLETED
    )

    assert synthesizer.calls == []
    assert player.calls == 0

    event_types = {
        event.event_type
        for event in runtime.events_since()
    }

    assert (
        FridayEventType.VOICE_SPEECH_STARTED
        not in event_types
    )


def test_partial_speech_configuration_is_rejected() -> None:
    runtime = FridayRuntime(
        "stage-11f3-config"
    )

    conversation = (
        FridayConversationService(
            FakeStreamingLLM(
                ["unused"]
            ),
            runtime,
        )
    )

    with pytest.raises(
        ValueError,
        match="configured together",
    ):
        FridayVoiceConversationService(
            FakeTranscriber(),
            conversation,
            runtime,
            speech_synthesizer=(
                FakeSpeechSynthesizer()
            ),
        )

    with pytest.raises(
        ValueError,
        match="configured together",
    ):
        FridayVoiceConversationService(
            FakeTranscriber(),
            conversation,
            runtime,
            speech_player=(
                FakeSpeechPlayer()
            ),
        )


def test_speech_disabled_preserves_existing_completed_behavior() -> None:
    runtime = FridayRuntime(
        "stage-11f3-disabled"
    )

    conversation = (
        FridayConversationService(
            FakeStreamingLLM(
                ["unchanged"]
            ),
            runtime,
        )
    )

    voice = FridayVoiceConversationService(
        FakeTranscriber(),
        conversation,
        runtime,
    )

    voice.start_listening()

    output = "".join(
        voice.stream_utterance(
            make_utterance()
        )
    )

    assert output == "unchanged"

    assert (
        runtime.state
        is FridayRuntimeState.COMPLETED
    )

    event_types = {
        event.event_type
        for event in runtime.events_since()
    }

    assert (
        FridayEventType.VOICE_SPEECH_STARTED
        not in event_types
    )
