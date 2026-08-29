from __future__ import annotations

import math
import os
import struct
from collections import deque
from dataclasses import dataclass
from typing import Literal, Protocol

from .audio import VoiceAudioConfig

_MIN_DBFS = -120.0


@dataclass(frozen=True, slots=True)
class VoiceVadConfig:
    """Configuration for Friday's dependency-free voice activity detector."""

    absolute_speech_dbfs: float = -42.0
    speech_margin_db: float = 10.0
    noise_floor_initial_dbfs: float = -58.0
    noise_floor_alpha: float = 0.05
    speech_start_ms: int = 90
    speech_end_silence_ms: int = 600
    pre_roll_ms: int = 300
    minimum_speech_ms: int = 180
    maximum_utterance_ms: int = 30_000

    def __post_init__(self) -> None:
        if self.speech_margin_db <= 0:
            raise ValueError("speech_margin_db must be positive")

        if not 0.0 < self.noise_floor_alpha <= 1.0:
            raise ValueError(
                "noise_floor_alpha must be in the range (0, 1]"
            )

        for name, value in (
            ("speech_start_ms", self.speech_start_ms),
            (
                "speech_end_silence_ms",
                self.speech_end_silence_ms,
            ),
            ("pre_roll_ms", self.pre_roll_ms),
            ("minimum_speech_ms", self.minimum_speech_ms),
            (
                "maximum_utterance_ms",
                self.maximum_utterance_ms,
            ),
        ):
            if value < 0:
                raise ValueError(f"{name} must not be negative")

        if self.speech_start_ms == 0:
            raise ValueError("speech_start_ms must be positive")

        if self.speech_end_silence_ms == 0:
            raise ValueError(
                "speech_end_silence_ms must be positive"
            )

        if self.maximum_utterance_ms == 0:
            raise ValueError(
                "maximum_utterance_ms must be positive"
            )

    @classmethod
    def from_env(cls) -> VoiceVadConfig:
        return cls(
            absolute_speech_dbfs=_env_float(
                "FRIDAY_VAD_ABSOLUTE_DBFS",
                -42.0,
            ),
            speech_margin_db=_env_float(
                "FRIDAY_VAD_SPEECH_MARGIN_DB",
                10.0,
            ),
            noise_floor_initial_dbfs=_env_float(
                "FRIDAY_VAD_INITIAL_NOISE_DBFS",
                -58.0,
            ),
            noise_floor_alpha=_env_float(
                "FRIDAY_VAD_NOISE_ALPHA",
                0.05,
            ),
            speech_start_ms=_env_int(
                "FRIDAY_VAD_START_MS",
                90,
            ),
            speech_end_silence_ms=_env_int(
                "FRIDAY_VAD_END_SILENCE_MS",
                600,
            ),
            pre_roll_ms=_env_int(
                "FRIDAY_VAD_PRE_ROLL_MS",
                300,
            ),
            minimum_speech_ms=_env_int(
                "FRIDAY_VAD_MINIMUM_SPEECH_MS",
                180,
            ),
            maximum_utterance_ms=_env_int(
                "FRIDAY_VAD_MAX_UTTERANCE_MS",
                30_000,
            ),
        )


@dataclass(frozen=True, slots=True)
class VadFrame:
    """Classification result for one PCM chunk."""

    dbfs: float
    noise_floor_dbfs: float | None
    threshold_dbfs: float | None
    speech: bool
    speech_probability: float | None = None


class VadDetector(Protocol):
    """Detector contract consumed by the utterance segmenter."""

    def reset(self) -> None:
        """Reset detector state."""
        ...

    def analyze(self, pcm: bytes) -> VadFrame:
        """Classify one PCM chunk."""
        ...


@dataclass(frozen=True, slots=True)
class VoiceUtterance:
    """A complete raw PCM utterance ready for transcription."""

    pcm: bytes
    sample_rate: int
    channels: int
    sample_width_bytes: int
    duration_ms: int
    speech_ms: int
    completion_reason: Literal[
        "silence",
        "maximum_duration",
    ]


@dataclass(frozen=True, slots=True)
class VoiceSegmentationResult:
    """Result from processing one microphone chunk."""

    frame: VadFrame
    speech_started: bool = False
    utterance: VoiceUtterance | None = None
    discarded_short_utterance: bool = False


class PcmEnergyVad:
    """Adaptive energy VAD for 16-bit little-endian PCM."""

    def __init__(
        self,
        config: VoiceVadConfig | None = None,
    ) -> None:
        self.config = (
            config
            if config is not None
            else VoiceVadConfig.from_env()
        )

        self._noise_floor_dbfs = (
            self.config.noise_floor_initial_dbfs
        )

    @property
    def noise_floor_dbfs(self) -> float:
        return self._noise_floor_dbfs

    def reset(self) -> None:
        self._noise_floor_dbfs = (
            self.config.noise_floor_initial_dbfs
        )

    def analyze(self, pcm: bytes) -> VadFrame:
        dbfs = pcm16_dbfs(pcm)

        adaptive_threshold = (
            self._noise_floor_dbfs
            + self.config.speech_margin_db
        )

        threshold = max(
            self.config.absolute_speech_dbfs,
            adaptive_threshold,
        )

        speech = dbfs >= threshold

        if not speech:
            self._update_noise_floor(dbfs)

            adaptive_threshold = (
                self._noise_floor_dbfs
                + self.config.speech_margin_db
            )

            threshold = max(
                self.config.absolute_speech_dbfs,
                adaptive_threshold,
            )

        return VadFrame(
            dbfs=dbfs,
            noise_floor_dbfs=self._noise_floor_dbfs,
            threshold_dbfs=threshold,
            speech=speech,
        )

    def _update_noise_floor(
        self,
        dbfs: float,
    ) -> None:
        alpha = self.config.noise_floor_alpha

        self._noise_floor_dbfs = (
            (1.0 - alpha)
            * self._noise_floor_dbfs
            + alpha
            * dbfs
        )


class UtteranceSegmenter:
    """
    Convert fixed-duration PCM chunks into complete speech utterances.

    The segmenter preserves a short pre-roll so speech beginnings are not
    clipped, requires consecutive speech frames before activation, and ends
    an utterance after configurable trailing silence or maximum duration.
    """

    def __init__(
        self,
        audio_config: VoiceAudioConfig | None = None,
        vad_config: VoiceVadConfig | None = None,
        detector: VadDetector | None = None,
    ) -> None:
        self.audio_config = (
            audio_config
            if audio_config is not None
            else VoiceAudioConfig.from_env()
        )

        self.vad_config = (
            vad_config
            if vad_config is not None
            else VoiceVadConfig.from_env()
        )

        self.detector = (
            detector
            if detector is not None
            else PcmEnergyVad(self.vad_config)
        )

        self._start_chunks = _milliseconds_to_chunks(
            self.vad_config.speech_start_ms,
            self.audio_config.chunk_ms,
            minimum=1,
        )

        self._end_silence_chunks = _milliseconds_to_chunks(
            self.vad_config.speech_end_silence_ms,
            self.audio_config.chunk_ms,
            minimum=1,
        )

        self._pre_roll_chunks = _milliseconds_to_chunks(
            self.vad_config.pre_roll_ms,
            self.audio_config.chunk_ms,
            minimum=0,
        )

        self._minimum_speech_chunks = _milliseconds_to_chunks(
            self.vad_config.minimum_speech_ms,
            self.audio_config.chunk_ms,
            minimum=0,
        )

        self._maximum_chunks = _milliseconds_to_chunks(
            self.vad_config.maximum_utterance_ms,
            self.audio_config.chunk_ms,
            minimum=1,
        )

        self._pre_roll: deque[bytes] = deque(
            maxlen=self._pre_roll_chunks or None
        )

        self._active_chunks: list[bytes] = []
        self._consecutive_speech = 0
        self._speech_chunks = 0
        self._silence_chunks = 0
        self._active = False

    @property
    def active(self) -> bool:
        return self._active

    def reset(self) -> None:
        self.detector.reset()
        self._pre_roll.clear()
        self._active_chunks.clear()
        self._consecutive_speech = 0
        self._speech_chunks = 0
        self._silence_chunks = 0
        self._active = False

    def process(
        self,
        pcm: bytes,
    ) -> VoiceSegmentationResult:
        if len(pcm) != self.audio_config.chunk_bytes:
            raise ValueError(
                "PCM chunk must contain exactly "
                f"{self.audio_config.chunk_bytes} bytes; "
                f"received {len(pcm)}"
            )

        frame = self.detector.analyze(pcm)

        if not self._active:
            return self._process_idle(
                pcm,
                frame,
            )

        return self._process_active(
            pcm,
            frame,
        )

    def _process_idle(
        self,
        pcm: bytes,
        frame: VadFrame,
    ) -> VoiceSegmentationResult:
        if self._pre_roll_chunks > 0:
            self._pre_roll.append(pcm)

        if frame.speech:
            self._consecutive_speech += 1
        else:
            self._consecutive_speech = 0

        if self._consecutive_speech < self._start_chunks:
            return VoiceSegmentationResult(
                frame=frame,
            )

        self._active = True

        if self._pre_roll_chunks > 0:
            self._active_chunks = list(
                self._pre_roll
            )
        else:
            self._active_chunks = [pcm]

        self._pre_roll.clear()

        self._speech_chunks = (
            self._consecutive_speech
        )

        self._silence_chunks = 0
        self._consecutive_speech = 0

        return VoiceSegmentationResult(
            frame=frame,
            speech_started=True,
        )

    def _process_active(
        self,
        pcm: bytes,
        frame: VadFrame,
    ) -> VoiceSegmentationResult:
        self._active_chunks.append(pcm)

        if frame.speech:
            self._speech_chunks += 1
            self._silence_chunks = 0
        else:
            self._silence_chunks += 1

        if (
            len(self._active_chunks)
            >= self._maximum_chunks
        ):
            return self._finish(
                frame,
                "maximum_duration",
            )

        if (
            self._silence_chunks
            >= self._end_silence_chunks
        ):
            return self._finish(
                frame,
                "silence",
            )

        return VoiceSegmentationResult(
            frame=frame,
        )

    def _finish(
        self,
        frame: VadFrame,
        reason: Literal[
            "silence",
            "maximum_duration",
        ],
    ) -> VoiceSegmentationResult:
        speech_chunks = self._speech_chunks

        if (
            speech_chunks
            < self._minimum_speech_chunks
        ):
            self._clear_active_state()

            return VoiceSegmentationResult(
                frame=frame,
                discarded_short_utterance=True,
            )

        pcm = b"".join(
            self._active_chunks
        )

        duration_ms = (
            len(self._active_chunks)
            * self.audio_config.chunk_ms
        )

        speech_ms = (
            speech_chunks
            * self.audio_config.chunk_ms
        )

        utterance = VoiceUtterance(
            pcm=pcm,
            sample_rate=self.audio_config.sample_rate,
            channels=self.audio_config.channels,
            sample_width_bytes=(
                self.audio_config.sample_width_bytes
            ),
            duration_ms=duration_ms,
            speech_ms=speech_ms,
            completion_reason=reason,
        )

        self._clear_active_state()

        return VoiceSegmentationResult(
            frame=frame,
            utterance=utterance,
        )

    def _clear_active_state(self) -> None:
        self._active_chunks = []
        self._consecutive_speech = 0
        self._speech_chunks = 0
        self._silence_chunks = 0
        self._active = False
        self._pre_roll.clear()


def pcm16_dbfs(pcm: bytes) -> float:
    """Return RMS level in dBFS for little-endian signed 16-bit PCM."""

    if len(pcm) % 2:
        raise ValueError(
            "16-bit PCM byte length must be even"
        )

    if not pcm:
        return _MIN_DBFS

    sample_count = len(pcm) // 2

    total_square = 0.0

    for (sample,) in struct.iter_unpack(
        "<h",
        pcm,
    ):
        total_square += float(sample * sample)

    rms = math.sqrt(
        total_square / sample_count
    )

    if rms <= 0:
        return _MIN_DBFS

    normalized = rms / 32768.0

    return max(
        _MIN_DBFS,
        20.0 * math.log10(normalized),
    )


def _milliseconds_to_chunks(
    milliseconds: int,
    chunk_ms: int,
    *,
    minimum: int,
) -> int:
    if milliseconds <= 0:
        return minimum

    return max(
        minimum,
        math.ceil(
            milliseconds / chunk_ms
        ),
    )


def _env_int(
    name: str,
    default: int,
) -> int:
    raw = os.getenv(name)

    if raw is None:
        return default

    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(
            f"{name} must be an integer"
        ) from exc


def _env_float(
    name: str,
    default: float,
) -> float:
    raw = os.getenv(name)

    if raw is None:
        return default

    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(
            f"{name} must be a number"
        ) from exc
