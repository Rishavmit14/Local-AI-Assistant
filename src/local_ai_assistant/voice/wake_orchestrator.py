"""Wake-to-conversation microphone ownership handoff.

This module coordinates already-qualified components. It does not
implement microphone capture, ASR, VAD, conversation, or speech.

Wake capture owns the microphone while Friday sleeps. A wake event
releases that ownership before an existing voice conversation turn
begins, and ownership returns to wake capture after that turn exits.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol

from .vad import VoiceUtterance
from .wake_capture import (
    FridayAlwaysOnWakeCapture,
    WakeCaptureEvent,
)


class WakeVoiceOrchestrationError(
    RuntimeError
):
    """Failure coordinating wake and conversation microphone ownership."""


class FollowUpCaptureBoundary(
    Protocol
):
    """Capture at most one fresh command utterance after a bare wake."""

    def capture_utterance(
        self,
    ) -> VoiceUtterance | None:
        ...


class VoiceConversationBoundary(
    Protocol
):
    """Existing Friday voice-conversation contract consumed by wake."""

    def start_listening(
        self,
    ) -> None:
        ...

    def stop_listening(
        self,
        *,
        reason: str = "voice_listening_stopped",
    ) -> None:
        ...


    def stream_text(
        self,
        text: str,
        *,
        system_prompt: str = (
            "You are Friday, a precise, "
            "technically accurate AI assistant."
        ),
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> Iterator[str]:
        ...

    def stream_utterance(
        self,
        utterance: VoiceUtterance,
        *,
        system_prompt: str = (
            "You are Friday, a precise, "
            "technically accurate AI assistant."
        ),
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> Iterator[str]:
        ...


@dataclass(
    frozen=True,
    slots=True,
)
class WakeVoiceTurnResult:
    """Outcome of one wake-triggered existing voice turn."""

    wake_source: str | None
    wake_remainder: str
    response_text: str


class FridayWakeVoiceOrchestrator:
    """Transfer microphone ownership around an existing voice turn."""

    def __init__(
        self,
        wake_capture: FridayAlwaysOnWakeCapture,
        voice: VoiceConversationBoundary,
        *,
        follow_up_capture: FollowUpCaptureBoundary | None = None,
    ) -> None:

        self.wake_capture = (
            wake_capture
        )

        self.voice = voice
        self.follow_up_capture = (
            follow_up_capture
        )


    def handle_wake_utterance(
        self,
        event: WakeCaptureEvent,
        *,
        system_prompt: str = (
            "You are Friday, a precise, "
            "technically accurate AI assistant."
        ),
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> WakeVoiceTurnResult:
        """Run the wake utterance through Friday's existing voice boundary.

        The wake capture stream is released before LISTENING begins and is
        always made eligible for reacquisition after the voice turn exits.

        Inline wake commands use the already-recognized wake remainder directly.
        Bare wake commands require a fresh follow-up capture and never reuse the
        original wake utterance as conversation input.
        """

        if not event.result.wake:
            raise WakeVoiceOrchestrationError(
                "cannot start a voice turn "
                "from a non-wake event"
            )


        self.wake_capture.pause()


        try:

            self.voice.start_listening()

            if event.result.remainder:
                chunks = (
                    self.voice
                    .stream_text(
                        event.result.remainder,
                        system_prompt=(
                            system_prompt
                        ),
                        temperature=(
                            temperature
                        ),
                        max_tokens=(
                            max_tokens
                        ),
                    )
                )
            else:
                follow_up_capture = (
                    self.follow_up_capture
                )

                if follow_up_capture is None:
                    self.voice.stop_listening(
                        reason="bare_wake_follow_up_unavailable",
                    )
                    raise WakeVoiceOrchestrationError(
                        "bare wake requires a fresh follow-up capture boundary"
                    )
                else:
                    try:
                        follow_up = (
                            follow_up_capture
                            .capture_utterance()
                        )
                    except Exception:
                        self.voice.stop_listening(
                            reason="bare_wake_follow_up_error",
                        )
                        raise

                    if follow_up is None:
                        self.voice.stop_listening(
                            reason="bare_wake_follow_up_timeout",
                        )
                        return WakeVoiceTurnResult(
                            wake_source=(
                                event.result.source
                            ),
                            wake_remainder="",
                            response_text="",
                        )

                    chunks = (
                        self.voice
                        .stream_utterance(
                            follow_up,
                            system_prompt=(
                                system_prompt
                            ),
                            temperature=(
                                temperature
                            ),
                            max_tokens=(
                                max_tokens
                            ),
                        )
                    )

            response_parts: list[str] = []

            for chunk in chunks:
                response_parts.append(
                    chunk
                )


            return WakeVoiceTurnResult(
                wake_source=(
                    event.result.source
                ),
                wake_remainder=(
                    event.result.remainder
                ),
                response_text="".join(
                    response_parts
                ),
            )


        finally:

            self.wake_capture.resume()


__all__ = [
    "FollowUpCaptureBoundary",
    "FridayWakeVoiceOrchestrator",
    "VoiceConversationBoundary",
    "WakeVoiceOrchestrationError",
    "WakeVoiceTurnResult",
]
