from __future__ import annotations

import json
import os
import sys
import time

import torch
from pocket_tts import TTSModel

VOICE_NAME = os.environ.get(
    "FRIDAY_POCKET_VOICE",
    "anna",
)

TARGET_LEAD_SECONDS = float(
    os.environ.get(
        "FRIDAY_POCKET_TARGET_LEAD_SECONDS",
        "0.32",
    )
)

torch.set_num_threads(1)
torch.set_num_interop_threads(1)


def _write_all(data: bytes) -> None:
    stream = sys.stdout.buffer
    offset = 0

    while offset < len(data):
        written = stream.write(data[offset:])

        if written is None:
            raise RuntimeError(
                "stdout write returned None"
            )

        offset += written


def _send_json(payload: dict) -> None:
    encoded = json.dumps(
        payload,
        separators=(",", ":"),
    ).encode("utf-8")

    _write_all(
        f"J {len(encoded)}\n".encode("ascii")
    )
    _write_all(encoded)
    sys.stdout.buffer.flush()


def _send_audio(
    request_id: str,
    sample_rate: int,
    pcm: bytes,
) -> None:
    # Friday playback expects signed 16-bit mono PCM.
    header = (
        f"A {request_id} "
        f"{sample_rate} "
        f"2 "
        f"1 "
        f"{len(pcm)}\n"
    ).encode("ascii")

    _write_all(header)
    _write_all(pcm)
    sys.stdout.buffer.flush()


def _to_pcm16(chunk: torch.Tensor) -> bytes:
    audio = (
        chunk
        .detach()
        .cpu()
        .flatten()
    )

    if audio.is_floating_point():
        audio = (
            audio
            .to(torch.float32)
            .clamp(-1.0, 1.0)
            .mul(32767.0)
            .round()
            .to(torch.int16)
        )
    else:
        audio = audio.to(torch.int16)

    return (
        audio
        .contiguous()
        .numpy()
        .tobytes()
    )


def main() -> int:
    started = time.monotonic()

    model = TTSModel.load_model()

    voice_state = (
        model.get_state_for_audio_prompt(
            VOICE_NAME
        )
    )

    sample_rate = int(model.sample_rate)

    _send_json(
        {
            "type": "ready",
            "load_seconds": (
                time.monotonic()
                - started
            ),
            "sample_rate": sample_rate,
            "voice": VOICE_NAME,
        }
    )

    while True:
        raw = sys.stdin.buffer.readline()

        if not raw:
            return 0

        try:
            request = json.loads(
                raw.decode("utf-8")
            )

            command = request.get(
                "command"
            )

            if command == "quit":
                _send_json(
                    {
                        "type": "bye",
                    }
                )
                return 0

            if command != "synthesize":
                raise ValueError(
                    "unsupported command"
                )

            request_id = str(
                request["id"]
            )

            text = str(
                request["text"]
            ).strip()

            if not text:
                raise ValueError(
                    "text must not be empty"
                )

            _send_json(
                {
                    "type": "accepted",
                    "id": request_id,
                }
            )

            synth_started = (
                time.monotonic()
            )

            first_audio = None
            playback_clock_start = None

            chunks = 0
            audio_bytes = 0
            audio_seconds = 0.0
            sleep_seconds = 0.0

            for chunk in (
                model.generate_audio_stream(
                    voice_state,
                    text,
                )
            ):
                now = time.monotonic()

                if first_audio is None:
                    first_audio = now
                    playback_clock_start = now

                samples = int(
                    chunk.numel()
                )

                pcm = _to_pcm16(chunk)

                chunks += 1
                audio_bytes += len(pcm)

                audio_seconds += (
                    samples
                    / sample_rate
                )

                _send_audio(
                    request_id,
                    sample_rate,
                    pcm,
                )

                # Pace synthesis instead of allowing Pocket to
                # continuously compete with Codacus. Keep only a
                # small amount of speech ahead of playback.
                assert (
                    playback_clock_start
                    is not None
                )

                played_seconds = (
                    time.monotonic()
                    - playback_clock_start
                )

                lead_seconds = (
                    audio_seconds
                    - played_seconds
                )

                if (
                    lead_seconds
                    > TARGET_LEAD_SECONDS
                ):
                    sleep_for = (
                        lead_seconds
                        - TARGET_LEAD_SECONDS
                    )

                    time.sleep(
                        sleep_for
                    )

                    sleep_seconds += (
                        sleep_for
                    )

            finished = time.monotonic()

            if first_audio is None:
                raise RuntimeError(
                    "Pocket completed without audio"
                )

            _send_json(
                {
                    "type": "done",
                    "id": request_id,
                    "chunks": chunks,
                    "audio_bytes": (
                        audio_bytes
                    ),
                    "first_audio_seconds": (
                        first_audio
                        - synth_started
                    ),
                    "total_seconds": (
                        finished
                        - synth_started
                    ),
                    "audio_seconds": (
                        audio_seconds
                    ),
                    "sleep_seconds": (
                        sleep_seconds
                    ),
                }
            )

        except Exception as exc:
            _send_json(
                {
                    "type": "error",
                    "error_type": (
                        type(exc).__name__
                    ),
                    "message": str(exc),
                }
            )


if __name__ == "__main__":
    raise SystemExit(main())
