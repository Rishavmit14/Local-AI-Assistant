from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from local_ai_assistant.voice.piper_runtime import (
    PiperSpeechError,
)
from local_ai_assistant.voice.pocket_runtime import (
    PocketSpeechConfig,
    PocketSpeechSynthesizer,
)

FAKE_WORKER = r"""
from __future__ import annotations

import json
import sys


def write(data: bytes) -> None:
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def send_json(payload: dict) -> None:
    encoded = json.dumps(
        payload,
        separators=(",", ":"),
    ).encode("utf-8")

    write(
        f"J {len(encoded)}\n".encode("ascii")
        + encoded
    )


def send_audio(
    request_id: str,
    pcm: bytes,
) -> None:
    write(
        (
            f"A {request_id} "
            f"24000 2 1 "
            f"{len(pcm)}\n"
        ).encode("ascii")
        + pcm
    )


send_json(
    {
        "type": "ready",
        "load_seconds": 0.01,
        "sample_rate": 24000,
        "voice": "anna",
    }
)


for raw in sys.stdin.buffer:
    request = json.loads(
        raw.decode("utf-8")
    )

    command = request.get(
        "command"
    )

    if command == "quit":
        send_json(
            {
                "type": "bye",
            }
        )
        raise SystemExit(0)

    if command != "synthesize":
        send_json(
            {
                "type": "error",
                "message": "unsupported command",
            }
        )
        continue

    request_id = str(
        request["id"]
    )

    text = str(
        request["text"]
    )

    send_json(
        {
            "type": "accepted",
            "id": request_id,
        }
    )

    if text == "worker-error":
        send_json(
            {
                "type": "error",
                "message": "synthetic Pocket worker error",
            }
        )
        continue

    first = (
        b"\x01\x00"
        * 40
    )

    second = (
        b"\x02\x00"
        * 60
    )

    send_audio(
        request_id,
        first,
    )

    send_audio(
        request_id,
        second,
    )

    send_json(
        {
            "type": "done",
            "id": request_id,
            "chunks": 2,
            "audio_bytes": 200,
            "first_audio_seconds": 0.01,
            "total_seconds": 0.02,
        }
    )
"""


def runtime_config(
    tmp_path: Path,
) -> PocketSpeechConfig:
    worker = (
        tmp_path
        / "pocket-worker.py"
    )

    worker.write_text(
        FAKE_WORKER,
        encoding="utf-8",
    )

    hf_home = (
        tmp_path
        / "hf-cache"
    )

    hf_home.mkdir()

    available_cpus = sorted(
        os.sched_getaffinity(0)
    )

    return PocketSpeechConfig(
        python_path=Path(
            sys.executable
        ),
        worker_path=worker,
        hf_home=hf_home,
        voice="anna",
        cpu_affinity=str(
            available_cpus[0]
        ),
        nice_level=0,
        target_lead_seconds=0.32,
        startup_timeout_seconds=2.0,
        synthesis_timeout_seconds=2.0,
        shutdown_timeout_seconds=1.0,
    )


def test_config_rejects_empty_voice(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValueError,
        match="voice",
    ):
        PocketSpeechConfig(
            python_path=Path(
                sys.executable
            ),
            worker_path=(
                tmp_path
                / "worker.py"
            ),
            hf_home=tmp_path,
            voice="",
        )


def test_persistent_worker_streams_24khz_pcm(
    tmp_path: Path,
) -> None:
    synth = (
        PocketSpeechSynthesizer(
            runtime_config(
                tmp_path
            )
        )
    )

    try:
        chunks = list(
            synth.stream(
                "Friday"
            )
        )

        assert len(chunks) == 2

        assert (
            chunks[0].sample_rate
            == 24_000
        )

        assert (
            chunks[0]
            .sample_width_bytes
            == 2
        )

        assert (
            chunks[0].channels
            == 1
        )

        assert (
            sum(
                len(chunk.pcm)
                for chunk in chunks
            )
            == 200
        )

        assert (
            synth.last_metrics
            is not None
        )

        assert (
            synth.last_metrics
            .chunks
            == 2
        )

    finally:
        synth.close()


def test_worker_is_reused(
    tmp_path: Path,
) -> None:
    synth = (
        PocketSpeechSynthesizer(
            runtime_config(
                tmp_path
            )
        )
    )

    try:
        list(
            synth.stream(
                "first"
            )
        )

        pid = (
            synth.worker_pid
        )

        assert pid is not None

        list(
            synth.stream(
                "second"
            )
        )

        assert (
            synth.worker_pid
            == pid
        )

    finally:
        synth.close()


def test_worker_error_propagates(
    tmp_path: Path,
) -> None:
    synth = (
        PocketSpeechSynthesizer(
            runtime_config(
                tmp_path
            )
        )
    )

    try:
        with pytest.raises(
            PiperSpeechError,
            match=(
                "synthetic Pocket "
                "worker error"
            ),
        ):
            list(
                synth.stream(
                    "worker-error"
                )
            )

    finally:
        synth.close()


def test_close_is_idempotent(
    tmp_path: Path,
) -> None:
    synth = (
        PocketSpeechSynthesizer(
            runtime_config(
                tmp_path
            )
        )
    )

    synth.start()

    assert (
        synth.worker_pid
        is not None
    )

    synth.close()
    synth.close()

    assert (
        synth.worker_pid
        is None
    )
