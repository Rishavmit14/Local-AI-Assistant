from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import pytest

from local_ai_assistant.voice import (
    FridayWakeVoiceOrchestrator,
    VoiceUtterance,
    WakeCaptureEvent,
    WakeSupervisorResult,
    WakeVoiceOrchestrationError,
)


class FakeWakeCapture:
    def __init__(
        self,
    ) -> None:

        self.pause_calls = 0
        self.resume_calls = 0
        self.paused = False


    def pause(
        self,
    ) -> None:

        self.pause_calls += 1
        self.paused = True


    def resume(
        self,
    ) -> None:

        self.resume_calls += 1
        self.paused = False


class FakeVoice:
    def __init__(
        self,
        *,
        chunks=None,
        fail=False,
    ) -> None:

        self.started = 0
        self.stream_calls = 0
        self.chunks = (
            list(chunks)
            if chunks is not None
            else [
                "Hello ",
                "there.",
            ]
        )

        self.fail = fail
        self.received = None
        self.capture = None


    def start_listening(
        self,
    ) -> None:

        self.started += 1

        if (
            self.capture
            is not None
        ):
            assert (
                self.capture.paused
            )


    def stream_utterance(
        self,
        utterance,
        **kwargs,
    ):

        del kwargs

        self.stream_calls += 1
        self.received = utterance

        if (
            self.capture
            is not None
        ):
            assert (
                self.capture.paused
            )

        if self.fail:
            raise RuntimeError(
                "voice failure"
            )

        yield from self.chunks


@dataclass
class FakeUtterance:
    pcm: bytes = b"\x00\x00"
    sample_rate: int = 16000
    channels: int = 1
    sample_width_bytes: int = 2
    duration_ms: int = 30
    speech_ms: int = 30
    completion_reason: str = "silence"


def utterance(
) -> VoiceUtterance:

    return cast(
        VoiceUtterance,
        FakeUtterance(),
    )


def wake_event(
    *,
    wake=True,
    source="parakeet-full",
    remainder="",
) -> WakeCaptureEvent:

    return WakeCaptureEvent(
        utterance=utterance(),
        result=WakeSupervisorResult(
            enabled=True,
            wake=wake,
            source=(
                source
                if wake
                else None
            ),
            remainder=(
                remainder
                if wake
                else ""
            ),
            primary=None,
            fallback=None,
        ),
    )


def test_handoff_pauses_before_voice_and_resumes_after(
) -> None:

    capture = FakeWakeCapture()

    voice = FakeVoice()

    voice.capture = capture

    orchestrator = (
        FridayWakeVoiceOrchestrator(
            cast(
                object,
                capture,
            ),
            voice,
        )
    )


    result = (
        orchestrator
        .handle_wake_utterance(
            wake_event()
        )
    )


    assert capture.pause_calls == 1
    assert capture.resume_calls == 1
    assert not capture.paused

    assert voice.started == 1
    assert voice.stream_calls == 1

    assert (
        result.response_text
        == "Hello there."
    )

    assert (
        result.wake_source
        == "parakeet-full"
    )


def test_existing_utterance_is_reused(
) -> None:

    capture = FakeWakeCapture()

    voice = FakeVoice()

    event = wake_event(
        remainder=(
            "what time is it"
        )
    )


    orchestrator = (
        FridayWakeVoiceOrchestrator(
            cast(
                object,
                capture,
            ),
            voice,
        )
    )


    result = (
        orchestrator
        .handle_wake_utterance(
            event
        )
    )


    assert (
        voice.received
        is event.utterance
    )

    assert (
        result.wake_remainder
        == "what time is it"
    )


def test_resume_occurs_when_voice_turn_fails(
) -> None:

    capture = FakeWakeCapture()

    voice = FakeVoice(
        fail=True,
    )


    orchestrator = (
        FridayWakeVoiceOrchestrator(
            cast(
                object,
                capture,
            ),
            voice,
        )
    )


    with pytest.raises(
        RuntimeError,
        match="voice failure",
    ):
        orchestrator.handle_wake_utterance(
            wake_event()
        )


    assert capture.pause_calls == 1
    assert capture.resume_calls == 1
    assert not capture.paused


def test_non_wake_event_rejected_without_microphone_change(
) -> None:

    capture = FakeWakeCapture()

    voice = FakeVoice()


    orchestrator = (
        FridayWakeVoiceOrchestrator(
            cast(
                object,
                capture,
            ),
            voice,
        )
    )


    with pytest.raises(
        WakeVoiceOrchestrationError,
        match="non-wake",
    ):
        orchestrator.handle_wake_utterance(
            wake_event(
                wake=False
            )
        )


    assert capture.pause_calls == 0
    assert capture.resume_calls == 0
    assert voice.started == 0
    assert voice.stream_calls == 0


def test_voice_stream_is_fully_consumed_before_resume(
) -> None:

    capture = FakeWakeCapture()

    observed = []


    class Voice:
        def start_listening(
            self,
        ):
            assert capture.paused

        def stream_utterance(
            self,
            utterance,
            **kwargs,
        ):
            del utterance
            del kwargs

            assert capture.paused

            observed.append(
                "first"
            )

            yield "A"

            assert capture.paused

            observed.append(
                "second"
            )

            yield "B"


    orchestrator = (
        FridayWakeVoiceOrchestrator(
            cast(
                object,
                capture,
            ),
            Voice(),
        )
    )


    result = (
        orchestrator
        .handle_wake_utterance(
            wake_event()
        )
    )


    assert observed == [
        "first",
        "second",
    ]

    assert (
        result.response_text
        == "AB"
    )

    assert not capture.paused
