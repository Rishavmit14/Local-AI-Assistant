from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from local_ai_assistant.voice import VoiceUtterance, WhisperTranscript

from .conversation import FridayConversationService
from .events import FridayEventType
from .runtime import FridayRuntime, InvalidRuntimeTransition
from .states import FridayRuntimeState

_TERMINAL_STATES = frozenset(
    {
        FridayRuntimeState.COMPLETED,
        FridayRuntimeState.ERROR,
        FridayRuntimeState.CANCELLED,
    }
)


class VoiceTranscriber(Protocol):
    """Minimal transcription boundary used by Friday voice orchestration."""

    def transcribe(
        self,
        utterance: VoiceUtterance,
    ) -> WhisperTranscript:
        ...


class FridayVoiceConversationService:
    """
    Route completed voice utterances through Friday's existing
    conversation boundary.
    """

    def __init__(
        self,
        transcriber: VoiceTranscriber,
        conversation: FridayConversationService,
        runtime: FridayRuntime,
    ) -> None:
        self.transcriber = transcriber
        self.conversation = conversation
        self.runtime = runtime

    def start_listening(self) -> None:
        if self.runtime.state in _TERMINAL_STATES:
            self.runtime.transition(
                FridayRuntimeState.IDLE,
                reason="voice_ready",
            )

        self.runtime.transition(
            FridayRuntimeState.LISTENING,
            reason="voice_listening_started",
        )

        self.runtime.emit(
            FridayEventType.VOICE_LISTENING_STARTED,
            state=FridayRuntimeState.LISTENING,
        )

    def stream_utterance(
        self,
        utterance: VoiceUtterance,
        *,
        system_prompt: str = (
            "You are Friday, a precise, technically accurate AI assistant."
        ),
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> Iterator[str]:
        if self.runtime.state is not FridayRuntimeState.LISTENING:
            raise InvalidRuntimeTransition(
                "voice utterance requires listening state; "
                f"runtime is {self.runtime.state.value}"
            )

        self.runtime.emit(
            FridayEventType.VOICE_LISTENING_STOPPED,
            state=FridayRuntimeState.LISTENING,
            metadata={
                "reason": "utterance_complete",
            },
        )

        self.runtime.transition(
            FridayRuntimeState.TRANSCRIBING,
            reason="voice_utterance_complete",
        )

        try:
            transcript = self.transcriber.transcribe(
                utterance
            )

        except Exception as exc:
            self.runtime.emit(
                FridayEventType.RUNTIME_ERROR,
                state=FridayRuntimeState.TRANSCRIBING,
                text="voice transcription failed",
                metadata={
                    "error_type": type(exc).__name__,
                },
            )

            self.runtime.transition(
                FridayRuntimeState.ERROR,
                reason="voice_transcription_failed",
            )

            raise

        text = transcript.text.strip()

        self.runtime.emit(
            FridayEventType.VOICE_TRANSCRIPTION,
            state=FridayRuntimeState.TRANSCRIBING,
            text=text,
            metadata={
                "elapsed_seconds": transcript.elapsed_seconds,
                "audio_duration_ms": transcript.audio_duration_ms,
                "language": transcript.language,
                "model_path": str(
                    transcript.model_path
                ),
            },
        )

        if not text:
            self.runtime.transition(
                FridayRuntimeState.IDLE,
                reason="voice_transcription_empty",
            )
            return

        yield from self.conversation.stream_response(
            text,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )


__all__ = [
    "FridayVoiceConversationService",
    "VoiceTranscriber",
]
