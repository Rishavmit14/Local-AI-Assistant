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


class FreshFollowUpCaptureForLegacyTests:
    # Supply a fresh command utterance to legacy orchestration tests.

    def __init__(self) -> None:
        self.utterance = FakeUtterance(
            pcm=b"\x01\x02\x03\x04",
            sample_rate=16000,
            channels=1,
            sample_width_bytes=2,
            duration_ms=640,
            speech_ms=384,
        )

    def capture_utterance(self):
        return self.utterance


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
        self.stop_reasons = []


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


    def stop_listening(
        self,
        *,
        reason: str = "voice_listening_stopped",
    ) -> None:
        self.stop_reasons.append(
            reason
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
            follow_up_capture=cast(
                object,
                FreshFollowUpCaptureForLegacyTests(),
            ),
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


def test_inline_wake_remainder_bypasses_original_utterance(
) -> None:

    capture = FakeWakeCapture()

    class InlineVoice(FakeVoice):
        def __init__(self) -> None:
            super().__init__()
            self.text_calls = []

        def stream_text(
            self,
            text,
            **kwargs,
        ):
            self.text_calls.append(
                (text, kwargs)
            )
            yield "direct"

    voice = InlineVoice()

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


    assert voice.received is None
    assert voice.stream_calls == 0

    assert voice.text_calls == [
        (
            "what time is it",
            {
                "system_prompt": (
                    "You are Friday, a precise, "
                    "technically accurate AI assistant."
                ),
                "temperature": 0.2,
                "max_tokens": 1024,
            },
        )
    ]

    assert (
        result.wake_remainder
        == "what time is it"
    )

    assert result.response_text == "direct"


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
            follow_up_capture=cast(
                object,
                FreshFollowUpCaptureForLegacyTests(),
            ),
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
            follow_up_capture=cast(
                object,
                FreshFollowUpCaptureForLegacyTests(),
            ),
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


def test_inline_wake_command_uses_remainder_without_retranscribing_wake_audio() -> None:
    capture = FakeWakeCapture()

    class InlineCommandVoice(FakeVoice):
        def __init__(self) -> None:
            super().__init__()
            self.text_calls = []

        def stream_text(
            self,
            text,
            **kwargs,
        ):
            self.text_calls.append(
                {
                    "text": text,
                    "kwargs": kwargs,
                }
            )
            yield "It is noon."

        def stream_utterance(
            self,
            utterance,
            **kwargs,
        ):
            del utterance
            del kwargs
            raise AssertionError(
                "inline wake command must not retranscribe the original wake utterance"
            )
            yield

    voice = InlineCommandVoice()
    voice.capture = capture

    event = wake_event(
        remainder="what time is it",
    )

    orchestrator = FridayWakeVoiceOrchestrator(
        cast(
            object,
            capture,
        ),
        voice,
    )

    result = orchestrator.handle_wake_utterance(
        event,
        system_prompt="Friday inline command test",
        temperature=0.3,
        max_tokens=64,
    )

    assert capture.pause_calls == 1
    assert capture.resume_calls == 1
    assert not capture.paused

    assert voice.started == 1
    assert voice.stream_calls == 0

    assert voice.text_calls == [
        {
            "text": "what time is it",
            "kwargs": {
                "system_prompt": "Friday inline command test",
                "temperature": 0.3,
                "max_tokens": 64,
            },
        }
    ]

    assert result.wake_remainder == (
        "what time is it"
    )
    assert result.response_text == (
        "It is noon."
    )


def test_bare_wake_without_follow_up_boundary_fails_closed() -> None:
    capture = FakeWakeCapture()

    class BareWakeVoice(FakeVoice):
        def __init__(self) -> None:
            super().__init__()
            self.text_calls = []

        def stream_text(
            self,
            text,
            **kwargs,
        ):
            self.text_calls.append(
                (text, kwargs)
            )
            yield "unexpected"

    voice = BareWakeVoice()
    voice.capture = capture

    orchestrator = FridayWakeVoiceOrchestrator(
        cast(
            object,
            capture,
        ),
        voice,
    )

    with pytest.raises(
        WakeVoiceOrchestrationError,
        match="fresh follow-up capture boundary",
    ):
        orchestrator.handle_wake_utterance(
            wake_event(
                remainder="",
            )
        )

    assert voice.text_calls == []
    assert voice.stream_calls == 0
    assert voice.stop_reasons == [
        "bare_wake_follow_up_unavailable",
    ]
    assert capture.pause_calls == 1
    assert capture.resume_calls == 1
    assert not capture.paused

def test_bare_wake_captures_fresh_follow_up_utterance() -> None:
    capture = FakeWakeCapture()
    voice = FakeVoice()

    wake = wake_event(
        remainder="",
    )

    follow_up = FakeUtterance(
        pcm=b"\x01\x02\x03\x04",
        sample_rate=16000,
        channels=1,
        sample_width_bytes=2,
        duration_ms=640,
        speech_ms=384,
    )

    class FollowUpCapture:
        def __init__(self) -> None:
            self.calls = 0

        def capture_utterance(self):
            self.calls += 1
            return follow_up

    follow_up_capture = FollowUpCapture()

    orchestrator = FridayWakeVoiceOrchestrator(
        cast(
            object,
            capture,
        ),
        voice,
        follow_up_capture=cast(
            object,
            follow_up_capture,
        ),
    )

    result = orchestrator.handle_wake_utterance(
        wake,
        system_prompt="Friday bare wake follow-up test",
        temperature=0.3,
        max_tokens=64,
    )

    assert capture.pause_calls == 1
    assert capture.resume_calls == 1
    assert not capture.paused

    assert follow_up_capture.calls == 1
    assert voice.started == 1
    assert voice.stream_calls == 1

    assert voice.received is follow_up
    assert voice.received is not wake.utterance

    assert result.wake_remainder == ""
    assert result.response_text == "Hello there."


def test_bare_wake_follow_up_timeout_never_reuses_wake_audio() -> None:
    capture = FakeWakeCapture()
    wake = wake_event(
        remainder="",
    )

    class NoReuseVoice(FakeVoice):
        def stream_utterance(
            self,
            utterance,
            **kwargs,
        ):
            if utterance is wake.utterance:
                raise AssertionError(
                    "bare wake timeout must never retranscribe "
                    "the original wake utterance"
                )
            yield from super().stream_utterance(
                utterance,
                **kwargs,
            )

    voice = NoReuseVoice()

    class FollowUpCapture:
        def __init__(self) -> None:
            self.calls = 0

        def capture_utterance(self):
            self.calls += 1
            return None

    follow_up_capture = FollowUpCapture()

    orchestrator = FridayWakeVoiceOrchestrator(
        cast(
            object,
            capture,
        ),
        voice,
        follow_up_capture=cast(
            object,
            follow_up_capture,
        ),
    )

    result = orchestrator.handle_wake_utterance(
        wake,
    )

    assert follow_up_capture.calls == 1
    assert voice.started == 1
    assert voice.stream_calls == 0
    assert voice.received is None

    assert result.wake_remainder == ""
    assert result.response_text == ""

    assert capture.pause_calls == 1
    assert capture.resume_calls == 1
    assert not capture.paused


def test_bare_wake_follow_up_timeout_closes_listening_state() -> None:
    capture = FakeWakeCapture()
    voice = FakeVoice()

    class FollowUpCapture:
        def capture_utterance(self):
            return None

    orchestrator = FridayWakeVoiceOrchestrator(
        cast(
            object,
            capture,
        ),
        voice,
        follow_up_capture=cast(
            object,
            FollowUpCapture(),
        ),
    )

    result = orchestrator.handle_wake_utterance(
        wake_event(
            remainder="",
        ),
    )

    assert result.response_text == ""
    assert voice.stop_reasons == [
        "bare_wake_follow_up_timeout",
    ]
    assert capture.resume_calls == 1
    assert not capture.paused


def test_bare_wake_follow_up_error_closes_listening_state() -> None:
    capture = FakeWakeCapture()
    voice = FakeVoice()

    class FollowUpCapture:
        def capture_utterance(self):
            raise RuntimeError(
                "fresh capture boom"
            )

    orchestrator = FridayWakeVoiceOrchestrator(
        cast(
            object,
            capture,
        ),
        voice,
        follow_up_capture=cast(
            object,
            FollowUpCapture(),
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="fresh capture boom",
    ):
        orchestrator.handle_wake_utterance(
            wake_event(
                remainder="",
            ),
        )

    assert voice.stop_reasons == [
        "bare_wake_follow_up_error",
    ]
    assert capture.resume_calls == 1
    assert not capture.paused
