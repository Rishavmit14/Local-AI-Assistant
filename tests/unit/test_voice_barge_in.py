from __future__ import annotations

from collections import deque

from local_ai_assistant.voice import (
    BargeInPolicy,
    FridayBargeInMonitor,
    SpeechStopResult,
    VadFrame,
    VoiceAudioConfig,
    build_barge_in_segmenter,
)

AUDIO = VoiceAudioConfig(
    sample_rate=16_000,
    channels=1,
    sample_width_bytes=2,
    chunk_ms=30,
)

PCM = (
    b"\x00\x00"
    * AUDIO.chunk_frames
)


class SequenceDetector:
    def __init__(
        self,
        probabilities,
        *,
        threshold: float = 0.85,
    ) -> None:
        self.probabilities = deque(
            probabilities
        )

        self.threshold = threshold
        self.resets = 0

    def reset(self) -> None:
        self.resets += 1

    def analyze(
        self,
        pcm: bytes,
    ) -> VadFrame:
        del pcm

        probability = (
            self.probabilities
            .popleft()
        )

        return VadFrame(
            dbfs=-25.0,
            noise_floor_dbfs=None,
            threshold_dbfs=None,
            speech=(
                probability
                >= self.threshold
            ),
            speech_probability=(
                probability
            ),
        )


class FakeStream:
    def __init__(
        self,
        count: int,
    ) -> None:
        self.count = count

    def read_chunk(
        self,
    ) -> bytes:
        if self.count <= 0:
            return b""

        self.count -= 1

        return PCM

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type,
        exc,
        traceback,
    ) -> None:
        del exc_type
        del exc
        del traceback


class FakeCapture:
    def __init__(
        self,
        count: int,
    ) -> None:
        self.audio_config = AUDIO
        self.count = count

    def open_stream(
        self,
    ) -> FakeStream:
        return FakeStream(
            self.count
        )


class FakePlayer:
    def __init__(self) -> None:
        self.active = True
        self.stop_calls = 0

    @property
    def is_playing(
        self,
    ) -> bool:
        return self.active

    def stop(
        self,
    ) -> SpeechStopResult:
        self.stop_calls += 1
        self.active = False

        return SpeechStopResult(
            stopped=True,
            elapsed_seconds=0.008,
        )


def test_policy_matches_qualified_values() -> None:
    policy = BargeInPolicy()

    assert (
        policy.silero_threshold
        == 0.85
    )

    assert (
        policy.confirmation_ms
        == 180
    )

    assert (
        policy.pre_roll_ms
        == 300
    )

    assert (
        policy.aec_arm_delay_seconds
        == 1.0
    )


def test_six_frames_required_at_180_ms() -> None:
    detector = SequenceDetector(
        [0.90] * 6
    )

    segmenter = (
        build_barge_in_segmenter(
            AUDIO,
            policy=BargeInPolicy(
                aec_arm_delay_seconds=0.0
            ),
            detector=detector,
        )
    )

    for _ in range(5):
        result = (
            segmenter.process(
                PCM
            )
        )

        assert not (
            result.speech_started
        )

    sixth = (
        segmenter.process(
            PCM
        )
    )

    assert (
        sixth.speech_started
    )


def test_four_frame_self_voice_burst_is_rejected() -> None:
    detector = SequenceDetector(
        [
            0.90,
            0.90,
            0.90,
            0.90,
            0.10,
            0.10,
        ]
    )

    segmenter = (
        build_barge_in_segmenter(
            AUDIO,
            policy=BargeInPolicy(
                aec_arm_delay_seconds=0.0
            ),
            detector=detector,
        )
    )

    results = [
        segmenter.process(
            PCM
        )
        for _ in range(6)
    ]

    assert not any(
        result.speech_started
        for result in results
    )


def test_monitor_stops_and_preserves_utterance() -> None:
    probabilities = (
        [0.05] * 4
        + [0.95] * 10
        + [0.05] * 20
    )

    detector = (
        SequenceDetector(
            probabilities
        )
    )

    capture = FakeCapture(
        len(
            probabilities
        )
    )

    player = FakePlayer()

    monitor = (
        FridayBargeInMonitor(
            capture,
            player,
            policy=BargeInPolicy(
                aec_arm_delay_seconds=0.0
            ),
            detector=detector,
        )
    )

    result = (
        monitor.capture_interruption(
            max_wait_seconds=2.0
        )
    )

    assert result.triggered

    assert (
        player.stop_calls
        == 1
    )

    assert (
        result.stop_result
        is not None
    )

    assert (
        result.stop_result.stopped
    )

    assert (
        result.utterance
        is not None
    )

    assert (
        result.utterance.pcm
    )

    assert (
        result.max_speech_probability
        >= 0.95
    )
