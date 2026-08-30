"""Persistent Parakeet Full wake-ASR worker.

This file is launched by Friday's PersistentWakeDetector using the
qualified sherpa-onnx environment. It intentionally has no dependency
on Friday's application Python environment.
"""

from __future__ import annotations

from array import array
from pathlib import Path

import json
import os
import sys
import time
import wave

import sherpa_onnx


DEFAULT_MODEL_PATH = Path(
    "/AI/models/friday/stt/"
    "parakeet-tdt-0.6b-v2-full/"
    "sherpa-onnx-nemo-parakeet-tdt-0.6b-v2"
)

MODEL_PATH = Path(
    os.environ.get(
        "FRIDAY_PARAKEET_FULL_MODEL",
        str(DEFAULT_MODEL_PATH),
    )
)


def emit(payload):
    print(
        "FRIDAY_JSON:"
        + json.dumps(
            payload,
            separators=(",", ":"),
        ),
        flush=True,
    )


def read_wav(path):
    with wave.open(
        str(path),
        "rb",
    ) as wav:

        if wav.getnchannels() != 1:
            raise RuntimeError(
                "expected mono"
            )

        if wav.getsampwidth() != 2:
            raise RuntimeError(
                "expected 16-bit PCM"
            )

        if wav.getframerate() != 16000:
            raise RuntimeError(
                "expected 16 kHz"
            )

        frames = wav.readframes(
            wav.getnframes()
        )

    pcm = array("h")
    pcm.frombytes(frames)

    if sys.byteorder != "little":
        pcm.byteswap()

    return [
        value / 32768.0
        for value in pcm
    ]


encoder = (
    MODEL_PATH
    / "encoder.onnx"
)

decoder = (
    MODEL_PATH
    / "decoder.onnx"
)

joiner = (
    MODEL_PATH
    / "joiner.onnx"
)

tokens = (
    MODEL_PATH
    / "tokens.txt"
)


for path in [
    encoder,
    decoder,
    joiner,
    tokens,
]:
    if not path.is_file():
        raise RuntimeError(
            "Parakeet model asset missing: "
            + str(path)
        )


started = time.perf_counter()


recognizer = (
    sherpa_onnx
    .OfflineRecognizer
    .from_transducer(
        encoder=str(encoder),
        decoder=str(decoder),
        joiner=str(joiner),
        tokens=str(tokens),
        num_threads=4,
        sample_rate=16000,
        feature_dim=128,
        decoding_method="greedy_search",
        provider="cpu",
        model_type="nemo_transducer",
        debug=False,
    )
)


load_seconds = (
    time.perf_counter()
    - started
)


emit({
    "event": "ready",
    "engine": "parakeet-full",
    "model_load_seconds":
        load_seconds,
})


for raw in sys.stdin:

    raw = raw.strip()

    if not raw:
        continue

    if raw == "__QUIT__":
        emit({
            "event": "bye",
        })
        break

    path = Path(raw)

    try:
        samples = read_wav(
            path
        )

        stream = (
            recognizer
            .create_stream()
        )

        started = (
            time.perf_counter()
        )

        stream.accept_waveform(
            16000,
            samples,
        )

        recognizer.decode_stream(
            stream
        )

        elapsed = (
            time.perf_counter()
            - started
        )

        emit({
            "event": "result",
            "path": str(path),
            "text":
                stream.result.text.strip(),
            "latency_seconds":
                elapsed,
        })

    except Exception as exc:
        emit({
            "event": "error",
            "path": str(path),
            "error": repr(exc),
        })
