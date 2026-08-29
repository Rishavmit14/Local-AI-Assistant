from __future__ import annotations

import hashlib
import struct
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from local_ai_assistant.voice.audio import VoiceAudioConfig
from local_ai_assistant.voice.silero import (
    DEFAULT_SILERO_MODEL_SHA256,
    SileroVad,
    SileroVadConfig,
    SileroVadError,
    verify_model_sha256,
)

AUDIO = VoiceAudioConfig(
    sample_rate=16_000,
    channels=1,
    chunk_ms=30,
)


def pcm_chunk(
    amplitude: int = 1000,
) -> bytes:

    return struct.pack(
        "<"
        + "h"
        * AUDIO.chunk_frames,
        *(
            [amplitude]
            * AUDIO.chunk_frames
        ),
    )


class FakeSession:
    def __init__(
        self,
        probabilities: list[float],
    ) -> None:

        self.probabilities = list(
            probabilities
        )

        self.calls: list[
            dict[str, Any]
        ] = []

    def run(
        self,
        output_names: object,
        feeds: dict[str, Any],
    ) -> list[Any]:

        del output_names

        self.calls.append(
            feeds
        )

        probability = (
            self.probabilities.pop(0)
            if self.probabilities
            else 0.0
        )

        return [
            np.array(
                [[probability]],
                dtype=np.float32,
            ),
            np.asarray(
                feeds["state"],
                dtype=np.float32,
            )
            + 1.0,
        ]


def make_config() -> SileroVadConfig:

    return SileroVadConfig(
        model_path=Path(
            "/not/used/"
            "in/injected-session-tests.onnx"
        ),
        expected_sha256=(
            DEFAULT_SILERO_MODEL_SHA256
        ),
    )


def test_silero_config_uses_validated_defaults() -> None:

    settings = (
        SileroVadConfig()
    )

    assert settings.threshold == 0.50
    assert settings.frame_samples == 512
    assert settings.context_samples == 64
    assert (
        settings.recurrent_state_size
        == 128
    )

    assert (
        settings.expected_sha256
        == DEFAULT_SILERO_MODEL_SHA256
    )


def test_silero_rejects_wrong_sample_rate() -> None:

    audio = VoiceAudioConfig(
        sample_rate=8_000,
    )

    with pytest.raises(
        ValueError,
        match="16000",
    ):
        SileroVad(
            audio_config=audio,
            config=make_config(),
            session=FakeSession(
                [0.9]
            ),
            numpy_module=np,
        )


def test_silero_buffers_480_sample_capture_chunks() -> None:

    session = FakeSession(
        [0.90]
    )

    detector = SileroVad(
        audio_config=AUDIO,
        config=make_config(),
        session=session,
        numpy_module=np,
    )

    first = detector.analyze(
        pcm_chunk()
    )

    assert not first.speech
    assert first.speech_probability == 0.0
    assert len(
        session.calls
    ) == 0

    assert (
        detector.pending_bytes
        == 960
    )

    second = detector.analyze(
        pcm_chunk()
    )

    assert second.speech

    assert (
        second.speech_probability
        == pytest.approx(
            0.90
        )
    )

    assert len(
        session.calls
    ) == 1

    assert (
        detector.pending_bytes
        == 448 * 2
    )


def test_silero_supplies_context_and_state() -> None:

    session = FakeSession(
        [0.75]
    )

    detector = SileroVad(
        audio_config=AUDIO,
        config=make_config(),
        session=session,
        numpy_module=np,
    )

    detector.analyze(
        pcm_chunk()
    )

    result = detector.analyze(
        pcm_chunk()
    )

    assert result.speech

    feeds = (
        session.calls[0]
    )

    assert (
        feeds["input"].shape
        == (
            1,
            576,
        )
    )

    assert (
        feeds["state"].shape
        == (
            2,
            1,
            128,
        )
    )

    assert (
        int(
            feeds["sr"].item()
        )
        == 16_000
    )


def test_silero_threshold_is_configurable() -> None:

    settings = SileroVadConfig(
        model_path=Path(
            "/unused.onnx"
        ),
        expected_sha256=(
            DEFAULT_SILERO_MODEL_SHA256
        ),
        threshold=0.80,
    )

    session = FakeSession(
        [0.70]
    )

    detector = SileroVad(
        audio_config=AUDIO,
        config=settings,
        session=session,
        numpy_module=np,
    )

    detector.analyze(
        pcm_chunk()
    )

    result = detector.analyze(
        pcm_chunk()
    )

    assert (
        result.speech_probability
        == pytest.approx(
            0.70
        )
    )

    assert not result.speech


def test_reset_clears_fifo_probability_and_state() -> None:

    session = FakeSession(
        [0.95]
    )

    detector = SileroVad(
        audio_config=AUDIO,
        config=make_config(),
        session=session,
        numpy_module=np,
    )

    detector.analyze(
        pcm_chunk()
    )

    detector.analyze(
        pcm_chunk()
    )

    assert (
        detector.last_probability
        == pytest.approx(
            0.95
        )
    )

    assert (
        detector.pending_bytes
        > 0
    )

    detector.reset()

    assert (
        detector.last_probability
        == 0.0
    )

    assert (
        detector.pending_bytes
        == 0
    )

    result = detector.analyze(
        pcm_chunk()
    )

    assert not result.speech

    assert (
        result.speech_probability
        == 0.0
    )


def test_model_sha_accepts_exact_digest(
    tmp_path: Path,
) -> None:

    model = (
        tmp_path
        / "model.onnx"
    )

    payload = (
        b"friday-silero-model-test"
    )

    model.write_bytes(
        payload
    )

    expected = (
        hashlib.sha256(
            payload
        ).hexdigest()
    )

    assert (
        verify_model_sha256(
            model,
            expected,
        )
        == expected
    )


def test_model_sha_rejects_mismatch(
    tmp_path: Path,
) -> None:

    model = (
        tmp_path
        / "model.onnx"
    )

    model.write_bytes(
        b"wrong-model"
    )

    with pytest.raises(
        SileroVadError,
        match="SHA256 mismatch",
    ):
        verify_model_sha256(
            model,
            "0" * 64,
        )


def test_model_sha_rejects_missing_file(
    tmp_path: Path,
) -> None:

    with pytest.raises(
        SileroVadError,
        match="does not exist",
    ):
        verify_model_sha256(
            tmp_path
            / "missing.onnx",
            "0" * 64,
        )
