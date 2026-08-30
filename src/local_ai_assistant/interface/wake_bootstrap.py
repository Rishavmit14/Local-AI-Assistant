"""Managed production bootstrap for Friday wake + conversational voice.

Wake capture and conversational work deliberately run on separate threads.

The microphone thread must never execute Whisper, LLM inference, Piper
synthesis, or playback synchronously. A strict wake pauses microphone
ownership immediately, schedules one managed voice-turn thread, and returns
the wake loop to its paused state.

Wake remains completely dormant unless AppConfig.wake.enabled is true.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any, Callable, Iterator, Protocol

from local_ai_assistant.common.config import AppConfig
from local_ai_assistant.voice import (
    BargeInPolicy,
    FridayBargeInMonitor,
    PipeWireAecConfig,
    PipeWireAecSession,
    PipeWirePcmCapture,
    PipeWirePcmCaptureConfig,
    FridayAlwaysOnWakeCapture,
    FridayWakeSupervisor,
    FridayWakeVoiceOrchestrator,
    FridayOneShotFollowUpCapture,
    PersistentWakeDetector,
    PersistentWakeProcessConfig,
    PiperAudioChunk,
    PiperSpeechSynthesizer,
    PipeWireSpeechPlayer,
    SpeechPlaybackResult,
    VoiceUtterance,
    WhisperCppTranscriber,
    WhisperTranscript,
    WakeCaptureEvent,
    AlsaAudioCapture,
    SileroVad,
    UtteranceSegmenter,
    VoiceAudioConfig,
    VoiceVadConfig,

)

from .conversation import FridayConversationService
from .runtime import FridayRuntime
from .voice_conversation import FridayVoiceConversationService


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[3]
)

PARAKEET_PYTHON = Path(
    "/AI/tools/"
    "sherpa-onnx-parakeet-tdt-0.6b-v2/"
    ".venv/bin/python"
)

MOONSHINE_PYTHON = Path(
    "/AI/tools/"
    "moonshine-0.1.5/"
    ".venv/bin/python"
)

PARAKEET_WORKER = (
    PROJECT_ROOT
    / "src/local_ai_assistant/voice/workers/"
    "parakeet_full.py"
)

MOONSHINE_WORKER = (
    PROJECT_ROOT
    / "src/local_ai_assistant/voice/workers/"
    "moonshine_medium.py"
)


# Silero VAD consumes 512 samples at 16 kHz:
# 512 / 16000 = 32 ms.
#
# Wake capture therefore uses one explicit 32 ms audio
# contract end-to-end: ALSA capture -> Silero -> segmenter.
WAKE_AUDIO_CONFIG = VoiceAudioConfig(
    sample_rate=16000,
    channels=1,
    sample_format="S16_LE",
    sample_width_bytes=2,
    chunk_ms=32,
)

WAKE_VAD_CONFIG = VoiceVadConfig()


class ManagedStartableClosable(
    Protocol
):
    def start(
        self,
    ) -> None:
        ...

    def close(
        self,
    ) -> None:
        ...


class WakeCaptureBoundary(
    Protocol
):
    on_wake: Any

    def run(
        self,
        *,
        max_completed_utterances: int | None = None,
    ) -> None:
        ...

    def pause(
        self,
    ) -> None:
        ...

    def resume(
        self,
    ) -> None:
        ...

    def stop(
        self,
    ) -> None:
        ...


class VoiceTurnTelemetry:
    """Thread-safe ordered production voice-stage trace."""

    def __init__(
        self,
    ) -> None:

        self._lock = (
            threading.Lock()
        )

        self._events: list[
            tuple[
                float,
                str,
            ]
        ] = []


    def mark(
        self,
        stage: str,
    ) -> None:

        timestamp = (
            time.monotonic()
        )

        with self._lock:

            self._events.append(
                (
                    timestamp,
                    stage,
                )
            )


        print(
            "FRIDAY_VOICE_STAGE "
            + stage,
            flush=True,
        )


    def snapshot(
        self,
    ) -> tuple[
        tuple[
            float,
            str,
        ],
        ...,
    ]:

        with self._lock:

            return tuple(
                self._events
            )


    def stages(
        self,
    ) -> tuple[
        str,
        ...,
    ]:

        return tuple(
            stage
            for _, stage
            in self.snapshot()
        )


class InstrumentedTranscriber:
    def __init__(
        self,
        inner: WhisperCppTranscriber,
        telemetry: VoiceTurnTelemetry,
    ) -> None:

        self.inner = inner
        self.telemetry = telemetry


    def transcribe(
        self,
        utterance: VoiceUtterance,
    ) -> WhisperTranscript:

        self.telemetry.mark(
            "WHISPER_BEGIN"
        )

        try:

            result = (
                self.inner
                .transcribe(
                    utterance
                )
            )

        except BaseException:

            self.telemetry.mark(
                "WHISPER_ERROR"
            )

            raise


        self.telemetry.mark(
            "WHISPER_COMPLETE"
        )

        return result


class InstrumentedConversation:
    def __init__(
        self,
        inner: FridayConversationService,
        telemetry: VoiceTurnTelemetry,
    ) -> None:

        self.inner = inner
        self.telemetry = telemetry


    def stream_response(
        self,
        prompt: str,
        **kwargs,
    ) -> Iterator[str]:

        self.telemetry.mark(
            "LLM_BEGIN"
        )

        first = True

        try:

            for chunk in (
                self.inner
                .stream_response(
                    prompt,
                    **kwargs,
                )
            ):

                if first:

                    first = False

                    self.telemetry.mark(
                        "LLM_FIRST_TOKEN"
                    )

                yield chunk


        except BaseException:

            self.telemetry.mark(
                "LLM_ERROR"
            )

            raise


        self.telemetry.mark(
            "LLM_COMPLETE"
        )


class InstrumentedSynthesizer:
    def __init__(
        self,
        inner: PiperSpeechSynthesizer,
        telemetry: VoiceTurnTelemetry,
    ) -> None:

        self.inner = inner
        self.telemetry = telemetry


    @property
    def worker_pid(
        self,
    ) -> int | None:

        return self.inner.worker_pid


    def start(
        self,
    ) -> None:

        self.inner.start()


    def close(
        self,
    ) -> None:

        self.inner.close()


    def stream(
        self,
        text: str,
    ) -> Iterator[PiperAudioChunk]:

        self.telemetry.mark(
            "PIPER_BEGIN"
        )

        first = True

        try:

            for chunk in (
                self.inner
                .stream(
                    text
                )
            ):

                if first:

                    first = False

                    self.telemetry.mark(
                        "PIPER_FIRST_AUDIO"
                    )

                yield chunk


        except BaseException:

            self.telemetry.mark(
                "PIPER_ERROR"
            )

            raise


        self.telemetry.mark(
            "PIPER_COMPLETE"
        )


class InstrumentedSpeechPlayer:
    def __init__(
        self,
        inner: PipeWireSpeechPlayer,
        telemetry: VoiceTurnTelemetry,
    ) -> None:

        self.inner = inner
        self.telemetry = telemetry


    @property
    def is_playing(
        self,
    ) -> bool:

        return self.inner.is_playing


    def play(
        self,
        chunks: Iterator[
            PiperAudioChunk
        ],
    ) -> SpeechPlaybackResult:

        self.telemetry.mark(
            "PLAYBACK_BEGIN"
        )

        try:

            result = (
                self.inner
                .play(
                    chunks
                )
            )

        except BaseException:

            self.telemetry.mark(
                "PLAYBACK_ERROR"
            )

            raise


        self.telemetry.mark(
            "PLAYBACK_COMPLETE"
        )

        return result


    def __getattr__(
        self,
        name: str,
    ) -> Any:

        return getattr(
            self.inner,
            name,
        )


VoiceTurnCallable = Callable[
    [
        WakeCaptureEvent,
    ],
    Any,
]


class FridayManagedWakeVoice:
    """Own wake workers, microphone thread, and one asynchronous voice turn."""

    def __init__(
        self,
        *,
        wake_capture: WakeCaptureBoundary,
        primary: ManagedStartableClosable,
        fallback: ManagedStartableClosable,
        speech_synthesizer: ManagedStartableClosable,
        voice_turn: VoiceTurnCallable,
        telemetry: VoiceTurnTelemetry | None = None,
        aec_session: PipeWireAecSession | None = None,
    ) -> None:

        self.wake_capture = (
            wake_capture
        )

        self.primary = primary
        self.fallback = fallback

        self.speech_synthesizer = (
            speech_synthesizer
        )
        self.aec_session = aec_session

        self.voice_turn = (
            voice_turn
        )

        self.telemetry = (
            telemetry
            if telemetry is not None
            else VoiceTurnTelemetry()
        )

        self._lock = (
            threading.RLock()
        )

        self._capture_thread: (
            threading.Thread
            | None
        ) = None

        self._voice_thread: (
            threading.Thread
            | None
        ) = None

        self._capture_error: (
            BaseException
            | None
        ) = None

        self._voice_error: (
            BaseException
            | None
        ) = None


    @property
    def thread_error(
        self,
    ) -> BaseException | None:

        with self._lock:

            return (
                self._capture_error
                or self._voice_error
            )


    @property
    def capture_thread_error(
        self,
    ) -> BaseException | None:

        with self._lock:

            return self._capture_error


    @property
    def voice_thread_error(
        self,
    ) -> BaseException | None:

        with self._lock:

            return self._voice_error


    @property
    def running(
        self,
    ) -> bool:

        with self._lock:

            thread = (
                self._capture_thread
            )

            return (
                thread is not None
                and thread.is_alive()
            )


    @property
    def voice_turn_running(
        self,
    ) -> bool:

        with self._lock:

            thread = (
                self._voice_thread
            )

            return (
                thread is not None
                and thread.is_alive()
            )


    def start(
        self,
    ) -> None:

        with self._lock:

            existing = (
                self._capture_thread
            )

            if (
                existing is not None
                and existing.is_alive()
            ):
                return


            self._capture_error = None
            self._voice_error = None


            try:

                self.telemetry.mark(
                    "PARAKEET_START_BEGIN"
                )

                self.primary.start()

                self.telemetry.mark(
                    "PARAKEET_START_READY"
                )


                self.telemetry.mark(
                    "MOONSHINE_START_BEGIN"
                )

                self.fallback.start()

                self.telemetry.mark(
                    "MOONSHINE_START_READY"
                )


                self.telemetry.mark(
                    "PIPER_START_BEGIN"
                )

                self.speech_synthesizer.start()

                self.telemetry.mark(
                    "PIPER_START_READY"
                )


                self.telemetry.mark(
                    "WAKE_CAPTURE_START"
                )


                thread = threading.Thread(
                    target=self._run_capture,
                    daemon=True,
                    name="friday-always-on-wake",
                )

                self._capture_thread = (
                    thread
                )

                thread.start()


            except BaseException:

                self._close_resources_locked()

                raise


    def handle_wake(
        self,
        event: WakeCaptureEvent,
    ) -> None:
        """Pause microphone ownership synchronously and schedule the voice turn."""

        self.telemetry.mark(
            "WAKE_ACCEPTED"
        )


        # Critical ordering:
        # microphone ownership is released before
        # the wake callback returns to the capture loop.
        self.wake_capture.pause()

        self.telemetry.mark(
            "WAKE_PAUSED"
        )


        with self._lock:

            existing = (
                self._voice_thread
            )


            if (
                existing is not None
                and existing.is_alive()
            ):

                self.wake_capture.resume()

                self.telemetry.mark(
                    "WAKE_RESUMED_DUPLICATE"
                )

                raise RuntimeError(
                    "wake received while a "
                    "voice turn is already running"
                )


            self._voice_error = None


            thread = threading.Thread(
                target=self._run_voice_turn,
                args=(
                    event,
                ),
                daemon=True,
                name="friday-wake-voice-turn",
            )

            self._voice_thread = (
                thread
            )


            try:

                thread.start()

            except BaseException:

                self._voice_thread = None

                self.wake_capture.resume()

                self.telemetry.mark(
                    "WAKE_RESUMED_THREAD_START_ERROR"
                )

                raise


    def close(
        self,
    ) -> None:
        """Always clean subprocesses, even if conversational work is stuck."""

        self.wake_capture.stop()


        with self._lock:

            capture_thread = (
                self._capture_thread
            )

            voice_thread = (
                self._voice_thread
            )


        if (
            capture_thread is not None
            and capture_thread
            is not threading.current_thread()
        ):

            capture_thread.join(
                timeout=10.0
            )


        capture_stuck = (
            capture_thread is not None
            and capture_thread.is_alive()
        )


        # Give a normal voice turn a short chance to finish
        # before closing subprocess resources underneath it.
        if (
            voice_thread is not None
            and voice_thread
            is not threading.current_thread()
        ):

            voice_thread.join(
                timeout=2.0
            )


        # Most important R1 guarantee:
        # resources are closed regardless of either thread state.
        with self._lock:

            self._close_resources_locked()


        # Closing Piper can unblock synthesis/playback error paths.
        if (
            voice_thread is not None
            and voice_thread
            is not threading.current_thread()
            and voice_thread.is_alive()
        ):

            voice_thread.join(
                timeout=2.0
            )


        voice_stuck = (
            voice_thread is not None
            and voice_thread.is_alive()
        )


        with self._lock:

            if not capture_stuck:
                self._capture_thread = None

            if not voice_stuck:
                self._voice_thread = None


        problems = []

        if capture_stuck:

            problems.append(
                "wake capture thread"
            )

        if voice_stuck:

            problems.append(
                "voice turn thread"
            )


        if problems:

            raise RuntimeError(
                "Friday managed shutdown left "
                + " and ".join(
                    problems
                )
                + " alive after worker cleanup"
            )


    def _run_capture(
        self,
    ) -> None:

        try:

            self.wake_capture.run()

        except BaseException as exc:

            print(
                "FRIDAY_VOICE_STAGE "
                "WAKE_CAPTURE_ERROR "
                f"type={type(exc).__name__} "
                f"message={exc}",
                flush=True,
            )

            with self._lock:

                self._capture_error = (
                    exc
                )


    def _run_voice_turn(
        self,
        event: WakeCaptureEvent,
    ) -> None:

        self.telemetry.mark(
            "VOICE_THREAD_BEGIN"
        )


        try:

            self.voice_turn(
                event
            )

        except BaseException as exc:

            self.telemetry.mark(
                "VOICE_THREAD_ERROR"
            )

            with self._lock:

                self._voice_error = (
                    exc
                )


        else:

            self.telemetry.mark(
                "VOICE_THREAD_COMPLETE"
            )


        finally:

            # The orchestrator already resumes in its own finally.
            # This second call is an idempotent ownership guarantee
            # if a future voice boundary fails before reaching it.
            self.wake_capture.resume()

            self.telemetry.mark(
                "WAKE_RESUMED"
            )


    def _close_resources_locked(
        self,
    ) -> None:

        for resource in (
            self.aec_session,
            self.speech_synthesizer,
            self.fallback,
            self.primary,
        ):

            if resource is None:
                continue

            try:

                resource.close()

            except Exception:

                pass




def build_managed_wake_voice(
    config: AppConfig,
    *,
    runtime: FridayRuntime,
    conversation: FridayConversationService,
) -> FridayManagedWakeVoice | None:

    if not config.wake.enabled:

        return None


    telemetry = (
        VoiceTurnTelemetry()
    )


    transcriber = (
        InstrumentedTranscriber(
            WhisperCppTranscriber(),
            telemetry,
        )
    )


    speech_synthesizer = (
        InstrumentedSynthesizer(
            PiperSpeechSynthesizer(),
            telemetry,
        )
    )


    speech_player = (
        InstrumentedSpeechPlayer(
            PipeWireSpeechPlayer(),
            telemetry,
        )
    )


    voice_conversation = (
        InstrumentedConversation(
            conversation,
            telemetry,
        )
    )


    aec_session = (
        PipeWireAecSession(
            PipeWireAecConfig(
                monitor_mode=True,
            )
        )
    )

    try:
        aec_endpoints = (
            aec_session.start()
        )

        aec_capture = (
            PipeWirePcmCapture(
                PipeWirePcmCaptureConfig(
                    target=(
                        aec_endpoints
                        .source_target
                    ),
                    audio=(
                        WAKE_AUDIO_CONFIG
                    ),
                )
            )
        )

        barge_in_monitor = (
            FridayBargeInMonitor(
                aec_capture,
                speech_player,
                policy=(
                    BargeInPolicy()
                ),
            )
        )

    except BaseException:
        aec_session.close()
        raise

    voice = (
        FridayVoiceConversationService(
            transcriber=transcriber,
            conversation=voice_conversation,
            runtime=runtime,
            speech_synthesizer=(
                speech_synthesizer
            ),
            speech_player=(
                speech_player
            ),
            barge_in_monitor=(
                barge_in_monitor
            ),
        )
    )


    primary = (
        PersistentWakeDetector(
            PersistentWakeProcessConfig(
                name="parakeet-full",
                python_path=(
                    PARAKEET_PYTHON
                ),
                worker_path=(
                    PARAKEET_WORKER
                ),
                startup_timeout_seconds=30.0,
                request_timeout_seconds=10.0,
            )
        )
    )


    fallback = (
        PersistentWakeDetector(
            PersistentWakeProcessConfig(
                name="moonshine-medium",
                python_path=(
                    MOONSHINE_PYTHON
                ),
                worker_path=(
                    MOONSHINE_WORKER
                ),
                startup_timeout_seconds=30.0,
                request_timeout_seconds=10.0,
            )
        )
    )


    wake_supervisor = (
        FridayWakeSupervisor(
            primary,
            fallback,
            enabled=True,
            phrase=config.wake.phrase,
        )
    )


    wake_vad = SileroVad(
        audio_config=WAKE_AUDIO_CONFIG,
    )


    wake_segmenter = UtteranceSegmenter(
        audio_config=WAKE_AUDIO_CONFIG,
        vad_config=WAKE_VAD_CONFIG,
        detector=wake_vad,
    )


    wake_capture = (
        FridayAlwaysOnWakeCapture(
            wake_supervisor,
            capture=AlsaAudioCapture(
                config=WAKE_AUDIO_CONFIG,
            ),
            segmenter=wake_segmenter,
        )
    )


    follow_up_capture = (
        FridayOneShotFollowUpCapture(
            capture=AlsaAudioCapture(
                config=WAKE_AUDIO_CONFIG,
            ),
            segmenter_factory=lambda: (
                UtteranceSegmenter(
                    audio_config=WAKE_AUDIO_CONFIG,
                    vad_config=WAKE_VAD_CONFIG,
                    detector=SileroVad(
                        audio_config=WAKE_AUDIO_CONFIG,
                    ),
                )
            ),
            max_wait_seconds=8.0,
        )
    )


    orchestrator = (
        FridayWakeVoiceOrchestrator(
            wake_capture,
            voice,
            follow_up_capture=(
                follow_up_capture
            ),
        )
    )


    managed = (
        FridayManagedWakeVoice(
            wake_capture=(
                wake_capture
            ),
            primary=primary,
            fallback=fallback,
            speech_synthesizer=(
                speech_synthesizer
            ),
            voice_turn=(
                orchestrator
                .handle_wake_utterance
            ),
            telemetry=telemetry,
            aec_session=aec_session,
        )
    )



    wake_capture.on_wake = (
        managed.handle_wake
    )


    return managed


__all__ = [
    "FridayManagedWakeVoice",
    "VoiceTurnTelemetry",
    "build_managed_wake_voice",
]
