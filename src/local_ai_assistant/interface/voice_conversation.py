from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from local_ai_assistant.voice import (
    PiperAudioChunk,
    SpeechPlaybackResult,
    VoiceUtterance,
    WhisperTranscript,
)

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


class VoiceSpeechSynthesizer(Protocol):
    """Minimal local speech-synthesis boundary used by voice orchestration."""

    def stream(
        self,
        text: str,
    ) -> Iterator[PiperAudioChunk]:
        ...


class VoiceSpeechPlayer(Protocol):
    """Minimal local speaker boundary used by voice orchestration."""

    def play(
        self,
        chunks: Iterator[PiperAudioChunk],
    ) -> SpeechPlaybackResult:
        ...


class FridayVoiceConversationService:
    """
    Route completed voice utterances through Friday's existing
    conversation boundary and optionally speak the completed response.
    """

    def __init__(
        self,
        transcriber: VoiceTranscriber,
        conversation: FridayConversationService,
        runtime: FridayRuntime,
        *,
        speech_synthesizer: VoiceSpeechSynthesizer | None = None,
        speech_player: VoiceSpeechPlayer | None = None,
    ) -> None:
        if (
            speech_synthesizer is None
        ) != (
            speech_player is None
        ):
            raise ValueError(
                "speech_synthesizer and speech_player "
                "must be configured together"
            )

        self.transcriber = transcriber
        self.conversation = conversation
        self.runtime = runtime
        self.speech_synthesizer = speech_synthesizer
        self.speech_player = speech_player

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

        response_parts: list[str] = []

        for chunk in self.conversation.stream_response(
            text,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            response_parts.append(
                chunk
            )

            yield chunk

        self._speak_response(
            "".join(
                response_parts
            )
        )

    def _speak_response(
        self,
        text: str,
    ) -> None:
        synthesizer = (
            self.speech_synthesizer
        )

        player = (
            self.speech_player
        )

        if (
            synthesizer is None
            or player is None
        ):
            return

        spoken_text = text.strip()

        if not spoken_text:
            return

        if (
            self.runtime.state
            is not FridayRuntimeState.COMPLETED
        ):
            raise InvalidRuntimeTransition(
                "voice speech requires completed "
                "conversation state; "
                f"runtime is {self.runtime.state.value}"
            )

        self.runtime.transition(
            FridayRuntimeState.SPEAKING,
            reason="voice_speech_started",
        )

        self.runtime.emit(
            FridayEventType.VOICE_SPEECH_STARTED,
            state=FridayRuntimeState.SPEAKING,
            text=spoken_text,
            metadata={
                "characters": len(
                    spoken_text
                ),
            },
        )

        try:
            result = player.play(
                synthesizer.stream(
                    spoken_text
                )
            )

        except Exception as exc:
            self.runtime.emit(
                FridayEventType.RUNTIME_ERROR,
                state=FridayRuntimeState.SPEAKING,
                text="voice speech failed",
                metadata={
                    "error_type": type(exc).__name__,
                },
            )

            if (
                self.runtime.state
                is not FridayRuntimeState.ERROR
            ):
                self.runtime.transition(
                    FridayRuntimeState.ERROR,
                    reason="voice_speech_failed",
                )

            raise

        metadata = {
            "elapsed_seconds": result.elapsed_seconds,
            "pcm_bytes_written": result.pcm_bytes_written,
            "sample_rate": result.sample_rate,
        }

        if result.interrupted:
            self.runtime.emit(
                FridayEventType.VOICE_SPEECH_INTERRUPTED,
                state=FridayRuntimeState.SPEAKING,
                text=spoken_text,
                metadata=metadata,
            )

            self.runtime.transition(
                FridayRuntimeState.IDLE,
                reason="voice_speech_interrupted",
            )

            return

        self.runtime.emit(
            FridayEventType.VOICE_SPEECH_COMPLETED,
            state=FridayRuntimeState.SPEAKING,
            text=spoken_text,
            metadata=metadata,
        )

        self.runtime.transition(
            FridayRuntimeState.IDLE,
            reason="voice_speech_completed",
        )


__all__ = [
    "FridayVoiceConversationService",
    "VoiceSpeechPlayer",
    "VoiceSpeechSynthesizer",
    "VoiceTranscriber",
]
