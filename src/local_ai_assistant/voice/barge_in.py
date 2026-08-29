from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

from .aec import PipeWirePcmCapture
from .audio import VoiceAudioConfig
from .piper_runtime import SpeechStopResult
from .silero import SileroVad, SileroVadConfig
from .vad import (
    UtteranceSegmenter,
    VadDetector,
    VoiceUtterance,
    VoiceVadConfig,
)


class BargeInError(RuntimeError):
    """Friday barge-in monitoring error."""


@dataclass(frozen=True, slots=True)
class BargeInPolicy:
    """Qualified production barge-in policy."""

    silero_threshold: float = 0.85
    confirmation_ms: int = 180

    aec_arm_delay_seconds: float = 1.0

    pre_roll_ms: int = 300
    speech_end_silence_ms: int = 600
    minimum_speech_ms: int = 180
    maximum_utterance_ms: int = 30_000

    max_wait_seconds: float = 30.0

    def __post_init__(
        self,
    ) -> None:
        if not (
            0.0
            < self.silero_threshold
            < 1.0
        ):
            raise ValueError(
                "silero_threshold must "
                "be in (0, 1)"
            )

        for name, value in (
            (
                "confirmation_ms",
                self.confirmation_ms,
            ),
            (
                "pre_roll_ms",
                self.pre_roll_ms,
            ),
            (
                "speech_end_silence_ms",
                self.speech_end_silence_ms,
            ),
            (
                "minimum_speech_ms",
                self.minimum_speech_ms,
            ),
            (
                "maximum_utterance_ms",
                self.maximum_utterance_ms,
            ),
        ):
            if value <= 0:
                raise ValueError(
                    f"{name} must be positive"
                )

        if (
            self.aec_arm_delay_seconds
            < 0
        ):
            raise ValueError(
                "aec_arm_delay_seconds "
                "must not be negative"
            )

        if (
            self.max_wait_seconds
            <= 0
        ):
            raise ValueError(
                "max_wait_seconds "
                "must be positive"
            )


@dataclass(frozen=True, slots=True)
class BargeInResult:
    triggered: bool

    detection_elapsed_seconds: (
        float
        | None
    )

    stop_result: (
        SpeechStopResult
        | None
    )

    utterance: (
        VoiceUtterance
        | None
    )

    max_speech_probability: float


class SpeechStopper(Protocol):
    @property
    def is_playing(
        self,
    ) -> bool:
        ...

    def stop(
        self,
    ) -> SpeechStopResult:
        ...


def build_barge_in_segmenter(
    audio_config: VoiceAudioConfig,
    *,
    policy: (
        BargeInPolicy
        | None
    ) = None,
    detector: (
        VadDetector
        | None
    ) = None,
) -> UtteranceSegmenter:
    selected = (
        policy
        if policy is not None
        else BargeInPolicy()
    )

    speech_detector = (
        detector
        if detector is not None
        else SileroVad(
            audio_config=audio_config,
            config=SileroVadConfig(
                threshold=(
                    selected
                    .silero_threshold
                )
            ),
        )
    )

    return UtteranceSegmenter(
        audio_config=audio_config,
        vad_config=VoiceVadConfig(
            speech_start_ms=(
                selected
                .confirmation_ms
            ),
            speech_end_silence_ms=(
                selected
                .speech_end_silence_ms
            ),
            pre_roll_ms=(
                selected.pre_roll_ms
            ),
            minimum_speech_ms=(
                selected
                .minimum_speech_ms
            ),
            maximum_utterance_ms=(
                selected
                .maximum_utterance_ms
            ),
        ),
        detector=speech_detector,
    )


class FridayBargeInMonitor:
    """
    Monitor Friday's echo-cancelled microphone stream.

    Playback is stopped only after the qualified
    0.85 / 180 ms human-speech confirmation.
    """

    def __init__(
        self,
        capture: PipeWirePcmCapture,
        speech_player: SpeechStopper,
        *,
        policy: (
            BargeInPolicy
            | None
        ) = None,
        detector: (
            VadDetector
            | None
        ) = None,
    ) -> None:
        self.capture = capture

        self.speech_player = (
            speech_player
        )

        self.policy = (
            policy
            if policy is not None
            else BargeInPolicy()
        )

        self._detector = detector

    def capture_interruption(
        self,
        *,
        max_wait_seconds: (
            float
            | None
        ) = None,
    ) -> BargeInResult:
        if not (
            self.speech_player
            .is_playing
        ):
            raise BargeInError(
                "barge-in monitoring "
                "requires active Friday speech"
            )

        timeout = (
            max_wait_seconds
            if max_wait_seconds
            is not None
            else self.policy
            .max_wait_seconds
        )

        if timeout <= 0:
            raise ValueError(
                "max_wait_seconds "
                "must be positive"
            )

        detector = (
            self._detector
            if self._detector
            is not None
            else SileroVad(
                audio_config=(
                    self.capture
                    .audio_config
                ),
                config=SileroVadConfig(
                    threshold=(
                        self.policy
                        .silero_threshold
                    )
                ),
            )
        )

        segmenter = (
            build_barge_in_segmenter(
                self.capture
                .audio_config,
                policy=self.policy,
                detector=detector,
            )
        )

        started = (
            time.monotonic()
        )

        armed = (
            self.policy
            .aec_arm_delay_seconds
            == 0
        )

        triggered = False

        detection_elapsed = None
        stop_result = None

        max_probability = 0.0

        with (
            self.capture
            .open_stream()
            as stream
        ):
            while (
                time.monotonic()
                - started
                < timeout
            ):
                if (
                    not triggered
                    and not (
                        self.speech_player
                        .is_playing
                    )
                ):
                    return BargeInResult(
                        triggered=False,
                        detection_elapsed_seconds=None,
                        stop_result=None,
                        utterance=None,
                        max_speech_probability=(
                            max_probability
                        ),
                    )

                pcm = (
                    stream.read_chunk()
                )

                if not pcm:
                    raise BargeInError(
                        "AEC microphone "
                        "stream ended unexpectedly"
                    )

                elapsed = (
                    time.monotonic()
                    - started
                )

                if not armed:
                    if (
                        elapsed
                        < self.policy
                        .aec_arm_delay_seconds
                    ):
                        continue

                    detector.reset()
                    segmenter.reset()

                    armed = True

                result = (
                    segmenter.process(
                        pcm
                    )
                )

                probability = (
                    result.frame
                    .speech_probability
                )

                if (
                    probability
                    is not None
                ):
                    max_probability = max(
                        max_probability,
                        float(
                            probability
                        ),
                    )

                if (
                    result.speech_started
                    and not triggered
                ):
                    stop = (
                        self.speech_player
                        .stop()
                    )

                    if not stop.stopped:
                        return BargeInResult(
                            triggered=False,
                            detection_elapsed_seconds=None,
                            stop_result=stop,
                            utterance=None,
                            max_speech_probability=(
                                max_probability
                            ),
                        )

                    triggered = True

                    stop_result = stop

                    detection_elapsed = (
                        elapsed
                    )

                if (
                    triggered
                    and result.utterance
                    is not None
                ):
                    return BargeInResult(
                        triggered=True,
                        detection_elapsed_seconds=(
                            detection_elapsed
                        ),
                        stop_result=(
                            stop_result
                        ),
                        utterance=(
                            result.utterance
                        ),
                        max_speech_probability=(
                            max_probability
                        ),
                    )

        return BargeInResult(
            triggered=triggered,
            detection_elapsed_seconds=(
                detection_elapsed
            ),
            stop_result=(
                stop_result
            ),
            utterance=None,
            max_speech_probability=(
                max_probability
            ),
        )


__all__ = [
    "BargeInError",
    "BargeInPolicy",
    "BargeInResult",
    "FridayBargeInMonitor",
    "SpeechStopper",
    "build_barge_in_segmenter",
]
