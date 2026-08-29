from __future__ import annotations

import gc
import hashlib
import sys
import threading
import time
from pathlib import Path

import pytest

from local_ai_assistant.voice.piper_runtime import (
    PiperAudioChunk,
    PiperSpeechConfig,
    PiperSpeechError,
    PiperSpeechSynthesizer,
    PipeWirePlayerConfig,
    PipeWireSpeechPlayer,
    SpeechPlaybackError,
    verify_piper_model_sha256,
)

FAKE_WORKER = r"""
from __future__ import annotations

import json
import sys


def write(data):
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def send_json(payload):
    encoded = json.dumps(
        payload,
        separators=(",", ":"),
    ).encode("utf-8")

    write(
        f"J {len(encoded)}\n".encode(
            "ascii"
        )
        + encoded
    )


def send_audio(
    request_id,
    pcm,
):
    write(
        (
            f"A {request_id} "
            f"22050 2 1 "
            f"{len(pcm)}\n"
        ).encode("ascii")
        + pcm
    )


send_json(
    {
        "type": "ready",
        "load_seconds": 0.01,
        "sample_rate": 22050,
    }
)

for raw in sys.stdin.buffer:
    request = json.loads(
        raw.decode("utf-8")
    )

    if (
        request.get("command")
        == "quit"
    ):
        send_json(
            {"type": "bye"}
        )
        raise SystemExit(0)

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

    if (
        text
        == "worker-error"
    ):
        send_json(
            {
                "type": "error",
                "message": (
                    "synthetic worker error"
                ),
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
) -> PiperSpeechConfig:
    model = (
        tmp_path
        / "voice.onnx"
    )

    payload = b"model"

    model.write_bytes(
        payload
    )

    Path(
        str(model)
        + ".json"
    ).write_text(
        "{}",
        encoding="utf-8",
    )

    worker = (
        tmp_path
        / "worker.py"
    )

    worker.write_text(
        FAKE_WORKER,
        encoding="utf-8",
    )

    return PiperSpeechConfig(
        python_path=Path(
            sys.executable
        ),
        model_path=model,
        expected_model_sha256=(
            hashlib.sha256(
                payload
            ).hexdigest()
        ),
        worker_path=worker,
        startup_timeout_seconds=2.0,
        synthesis_timeout_seconds=2.0,
        shutdown_timeout_seconds=1.0,
    )


def fake_player(
    tmp_path: Path,
    *,
    slow: bool = False,
) -> Path:
    path = (
        tmp_path
        / "fake-player"
    )

    delay = (
        "time.sleep(0.02)"
        if slow
        else "pass"
    )

    path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import sys",
                "import time",
                "while True:",
                "    data = sys.stdin.buffer.read(1024)",
                "    if not data:",
                "        break",
                f"    {delay}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    path.chmod(
        0o755
    )

    return path


def finalize() -> None:
    gc.collect()
    gc.collect()


def test_model_hash(
    tmp_path: Path,
) -> None:
    model = (
        tmp_path
        / "model.onnx"
    )

    payload = b"model"

    model.write_bytes(
        payload
    )

    digest = (
        hashlib.sha256(
            payload
        ).hexdigest()
    )

    assert (
        verify_piper_model_sha256(
            model,
            digest,
        )
        == digest
    )


def test_missing_model_fails_first(
    tmp_path: Path,
) -> None:
    worker = (
        tmp_path
        / "worker.py"
    )

    worker.write_text(
        "",
        encoding="utf-8",
    )

    with pytest.raises(
        PiperSpeechError,
        match="model does not exist",
    ):
        PiperSpeechSynthesizer(
            PiperSpeechConfig(
                python_path=Path(
                    sys.executable
                ),
                model_path=(
                    tmp_path
                    / "missing.onnx"
                ),
                expected_model_sha256=(
                    "0" * 64
                ),
                worker_path=worker,
            )
        )


def test_persistent_worker_streams(
    tmp_path: Path,
) -> None:
    synth = (
        PiperSpeechSynthesizer(
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

        assert (
            len(chunks)
            == 2
        )

        assert (
            chunks[0]
            .sample_rate
            == 22_050
        )

        assert (
            chunks[0]
            .sample_width_bytes
            == 2
        )

        assert (
            chunks[0]
            .channels
            == 1
        )

        assert (
            synth.last_metrics
            is not None
        )

    finally:
        synth.close()

    finalize()


def test_worker_reused(
    tmp_path: Path,
) -> None:
    synth = (
        PiperSpeechSynthesizer(
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

        list(
            synth.stream(
                "second"
            )
        )

        assert pid is not None

        assert (
            synth.worker_pid
            == pid
        )

    finally:
        synth.close()

    finalize()


def test_worker_error(
    tmp_path: Path,
) -> None:
    synth = (
        PiperSpeechSynthesizer(
            runtime_config(
                tmp_path
            )
        )
    )

    try:
        with pytest.raises(
            PiperSpeechError,
            match=(
                "synthetic worker error"
            ),
        ):
            list(
                synth.stream(
                    "worker-error"
                )
            )

    finally:
        synth.close()

    finalize()


def test_empty_text_rejected(
    tmp_path: Path,
) -> None:
    synth = (
        PiperSpeechSynthesizer(
            runtime_config(
                tmp_path
            )
        )
    )

    with pytest.raises(
        ValueError,
        match="non-empty",
    ):
        list(
            synth.stream(
                "   "
            )
        )

    assert not synth.is_started


def test_close_is_idempotent(
    tmp_path: Path,
) -> None:
    synth = (
        PiperSpeechSynthesizer(
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

    finalize()


def test_player_normal(
    tmp_path: Path,
) -> None:
    player = (
        PipeWireSpeechPlayer(
            PipeWirePlayerConfig(
                player_path=(
                    fake_player(
                        tmp_path
                    )
                )
            )
        )
    )

    result = player.play(
        iter(
            [
                PiperAudioChunk(
                    pcm=(
                        b"\x01\x00"
                        * 50
                    ),
                    sample_rate=(
                        22_050
                    ),
                    sample_width_bytes=2,
                    channels=1,
                ),
            ]
        )
    )

    assert (
        not result.interrupted
    )

    assert (
        result.pcm_bytes_written
        == 100
    )

    finalize()


def test_player_interruptible(
    tmp_path: Path,
) -> None:
    player = (
        PipeWireSpeechPlayer(
            PipeWirePlayerConfig(
                player_path=(
                    fake_player(
                        tmp_path,
                        slow=True,
                    )
                ),
                stop_timeout_seconds=0.5,
            )
        )
    )

    huge = PiperAudioChunk(
        pcm=(
            b"\x00\x00"
            * 500_000
        ),
        sample_rate=22_050,
        sample_width_bytes=2,
        channels=1,
    )

    results = []
    errors = []

    def play() -> None:
        try:
            results.append(
                player.play(
                    iter(
                        [
                            huge,
                            huge,
                        ]
                    )
                )
            )

        except BaseException as exc:
            errors.append(
                exc
            )

    thread = (
        threading.Thread(
            target=play
        )
    )

    thread.start()

    deadline = (
        time.monotonic()
        + 2.0
    )

    while (
        not player.is_playing
        and time.monotonic()
        < deadline
    ):
        time.sleep(
            0.005
        )

    assert (
        player.is_playing
    )

    stop = player.stop()

    thread.join(
        timeout=3.0
    )

    assert (
        not thread.is_alive()
    )

    assert errors == []

    assert stop.stopped

    assert (
        stop.elapsed_seconds
        < 0.5
    )

    assert (
        len(results)
        == 1
    )

    assert (
        results[0]
        .interrupted
    )

    finalize()


def test_player_rejects_bad_pcm(
    tmp_path: Path,
) -> None:
    player = (
        PipeWireSpeechPlayer(
            PipeWirePlayerConfig(
                player_path=(
                    fake_player(
                        tmp_path
                    )
                )
            )
        )
    )

    with pytest.raises(
        SpeechPlaybackError,
        match="16-bit",
    ):
        player.play(
            iter(
                [
                    PiperAudioChunk(
                        pcm=b"x",
                        sample_rate=(
                            22_050
                        ),
                        sample_width_bytes=1,
                        channels=1,
                    )
                ]
            )
        )
