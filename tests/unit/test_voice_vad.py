from __future__ import annotations

import math
import struct

import pytest

from local_ai_assistant.voice.audio import (
    VoiceAudioConfig,
)
from local_ai_assistant.voice.vad import (
    PcmEnergyVad,
    UtteranceSegmenter,
    VoiceVadConfig,
    pcm16_dbfs,
)

AUDIO = VoiceAudioConfig(
    sample_rate=16_000,
    channels=1,
    chunk_ms=30,
)


def chunk(
    amplitude: int,
) -> bytes:
    return struct.pack(
        "<" + "h" * AUDIO.chunk_frames,
        *([amplitude] * AUDIO.chunk_frames),
    )


SILENCE = chunk(0)
QUIET = chunk(150)
SPEECH = chunk(10_000)


def test_pcm_dbfs_reports_silence() -> None:
    assert pcm16_dbfs(SILENCE) == -120.0


def test_pcm_dbfs_reports_expected_signal_level() -> None:
    level = pcm16_dbfs(SPEECH)

    expected = 20.0 * math.log10(
        10_000 / 32768.0
    )

    assert level == pytest.approx(
        expected,
        abs=0.01,
    )


def test_pcm_dbfs_rejects_invalid_pcm() -> None:
    with pytest.raises(
        ValueError,
        match="even",
    ):
        pcm16_dbfs(b"\x00")


def test_vad_detects_clear_speech() -> None:
    detector = PcmEnergyVad(
        VoiceVadConfig(
            absolute_speech_dbfs=-42.0,
            speech_margin_db=10.0,
            noise_floor_initial_dbfs=-60.0,
        )
    )

    frame = detector.analyze(SPEECH)

    assert frame.speech
    assert frame.dbfs > frame.threshold_dbfs


def test_vad_does_not_classify_silence_as_speech() -> None:
    detector = PcmEnergyVad()

    frame = detector.analyze(SILENCE)

    assert not frame.speech


def test_vad_updates_noise_floor_on_non_speech() -> None:
    detector = PcmEnergyVad(
        VoiceVadConfig(
            noise_floor_initial_dbfs=-40.0,
            noise_floor_alpha=0.5,
            absolute_speech_dbfs=-20.0,
        )
    )

    before = detector.noise_floor_dbfs

    detector.analyze(QUIET)

    assert detector.noise_floor_dbfs < before


def test_segmenter_requires_confirmed_speech_start() -> None:
    segmenter = UtteranceSegmenter(
        AUDIO,
        VoiceVadConfig(
            speech_start_ms=90,
            minimum_speech_ms=90,
        ),
    )

    first = segmenter.process(SPEECH)
    second = segmenter.process(SPEECH)
    third = segmenter.process(SPEECH)

    assert not first.speech_started
    assert not second.speech_started
    assert third.speech_started
    assert segmenter.active


def test_segmenter_preserves_pre_roll() -> None:
    vad = VoiceVadConfig(
        pre_roll_ms=300,
        speech_start_ms=90,
        minimum_speech_ms=90,
        speech_end_silence_ms=90,
    )

    segmenter = UtteranceSegmenter(
        AUDIO,
        vad,
    )

    for _ in range(7):
        segmenter.process(SILENCE)

    for _ in range(3):
        result = segmenter.process(SPEECH)

    assert result.speech_started

    for _ in range(3):
        result = segmenter.process(SILENCE)

    assert result.utterance is not None

    # 7 silence + 3 speech entered the 10-chunk pre-roll,
    # then 3 trailing-silence chunks completed the utterance.
    assert result.utterance.duration_ms == 390
    assert result.utterance.pcm.startswith(SILENCE)


def test_segmenter_completes_after_trailing_silence() -> None:
    segmenter = UtteranceSegmenter(
        AUDIO,
        VoiceVadConfig(
            pre_roll_ms=0,
            speech_start_ms=90,
            minimum_speech_ms=90,
            speech_end_silence_ms=90,
        ),
    )

    for _ in range(3):
        result = segmenter.process(SPEECH)

    assert result.speech_started

    result = segmenter.process(SPEECH)
    assert result.utterance is None

    for _ in range(3):
        result = segmenter.process(SILENCE)

    assert result.utterance is not None
    assert (
        result.utterance.completion_reason
        == "silence"
    )
    assert result.utterance.speech_ms == 120


def test_segmenter_discards_short_utterance() -> None:
    segmenter = UtteranceSegmenter(
        AUDIO,
        VoiceVadConfig(
            pre_roll_ms=0,
            speech_start_ms=60,
            minimum_speech_ms=180,
            speech_end_silence_ms=60,
        ),
    )

    segmenter.process(SPEECH)
    started = segmenter.process(SPEECH)

    assert started.speech_started

    segmenter.process(SILENCE)
    finished = segmenter.process(SILENCE)

    assert finished.utterance is None
    assert finished.discarded_short_utterance
    assert not segmenter.active


def test_segmenter_enforces_maximum_duration() -> None:
    segmenter = UtteranceSegmenter(
        AUDIO,
        VoiceVadConfig(
            pre_roll_ms=0,
            speech_start_ms=30,
            minimum_speech_ms=30,
            speech_end_silence_ms=600,
            maximum_utterance_ms=150,
        ),
    )

    started = segmenter.process(SPEECH)

    assert started.speech_started

    result = started

    while result.utterance is None:
        result = segmenter.process(SPEECH)

    assert (
        result.utterance.completion_reason
        == "maximum_duration"
    )

    assert result.utterance.duration_ms == 150


def test_segmenter_rejects_wrong_chunk_size() -> None:
    segmenter = UtteranceSegmenter(
        AUDIO,
    )

    with pytest.raises(
        ValueError,
        match="exactly",
    ):
        segmenter.process(
            b"\x00\x00"
        )


def test_reset_clears_active_segmentation_state() -> None:
    segmenter = UtteranceSegmenter(
        AUDIO,
        VoiceVadConfig(
            speech_start_ms=30,
        ),
    )

    result = segmenter.process(SPEECH)

    assert result.speech_started
    assert segmenter.active

    segmenter.reset()

    assert not segmenter.active
