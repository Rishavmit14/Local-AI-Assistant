"""Persistent Moonshine Medium wake-ASR worker.

This is the production form of the exact Moonshine Voice 0.1.5
qualification helper used by Friday's successful strict cascade.
"""

from __future__ import annotations

from array import array
from pathlib import Path

import json
import os
import sys
import time
import wave

from moonshine_voice import (
    ModelArch,
    Transcriber,
)


DEFAULT_MODEL_PATH = Path(
    "/AI/models/friday/stt/"
    "moonshine-medium-streaming/"
    "download.moonshine.ai/model/"
    "medium-streaming-en/"
    "quantized_26_08_21"
)

MODEL_PATH = Path(
    os.environ.get(
        "FRIDAY_MOONSHINE_MEDIUM_MODEL",
        str(DEFAULT_MODEL_PATH),
    )
)

UPDATE_INTERVAL = 0.25
CHUNK_SECONDS = 0.10


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


def transcript_text(
    transcript,
):
    if transcript is None:
        return ""

    lines = getattr(
        transcript,
        "lines",
        None,
    )

    if not lines:
        return ""

    parts = []

    for line in lines:
        text = str(
            getattr(
                line,
                "text",
                "",
            )
        ).strip()

        if text:
            parts.append(text)

    return " ".join(
        parts
    ).strip()


if not MODEL_PATH.is_dir():
    raise RuntimeError(
        "Moonshine Medium model missing: "
        + str(MODEL_PATH)
    )


started = time.perf_counter()


transcriber = Transcriber(
    model_path=MODEL_PATH,
    model_arch=(
        ModelArch.MEDIUM_STREAMING
    ),
    update_interval=(
        UPDATE_INTERVAL
    ),
)


load_seconds = (
    time.perf_counter()
    - started
)


emit({
    "event": "ready",
    "engine": "moonshine-medium",
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

        chunk_size = int(
            CHUNK_SECONDS
            * 16000
        )

        stream = (
            transcriber
            .create_stream(
                update_interval=(
                    UPDATE_INTERVAL
                )
            )
        )

        started = (
            time.perf_counter()
        )

        try:
            stream.start()

            for offset in range(
                0,
                len(samples),
                chunk_size,
            ):
                stream.add_audio(
                    samples[
                        offset:
                        offset
                        + chunk_size
                    ],
                    16000,
                )

            transcript = (
                stream.stop()
            )

        finally:
            stream.close()

        elapsed = (
            time.perf_counter()
            - started
        )

        emit({
            "event": "result",
            "path": str(path),
            "text":
                transcript_text(
                    transcript
                ),
            "latency_seconds":
                elapsed,
        })

    except Exception as exc:
        emit({
            "event": "error",
            "path": str(path),
            "error": repr(exc),
        })
