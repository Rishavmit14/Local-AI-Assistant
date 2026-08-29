from __future__ import annotations

import json
import sys
import time

from piper import PiperVoice


def _write_all(
    data: bytes,
) -> None:
    stream = sys.stdout.buffer
    offset = 0

    while offset < len(data):
        written = stream.write(
            data[offset:]
        )

        if written is None:
            raise RuntimeError(
                "stdout write returned None"
            )

        offset += written


def _send_json(
    payload: dict,
) -> None:
    encoded = json.dumps(
        payload,
        separators=(",", ":"),
    ).encode("utf-8")

    _write_all(
        f"J {len(encoded)}\n".encode(
            "ascii"
        )
    )

    _write_all(
        encoded
    )

    sys.stdout.buffer.flush()


def _send_audio(
    request_id: str,
    sample_rate: int,
    sample_width: int,
    channels: int,
    pcm: bytes,
) -> None:
    header = (
        f"A {request_id} "
        f"{sample_rate} "
        f"{sample_width} "
        f"{channels} "
        f"{len(pcm)}\n"
    ).encode("ascii")

    _write_all(
        header
    )

    _write_all(
        pcm
    )

    sys.stdout.buffer.flush()


def main() -> int:
    if len(
        sys.argv
    ) != 2:
        raise SystemExit(
            "usage: piper_worker.py MODEL"
        )

    model_path = (
        sys.argv[1]
    )

    started = (
        time.monotonic()
    )

    voice = PiperVoice.load(
        model_path,
        use_cuda=False,
    )

    _send_json(
        {
            "type": "ready",
            "load_seconds": (
                time.monotonic()
                - started
            ),
            "sample_rate": (
                voice.config.sample_rate
            ),
        }
    )

    while True:
        raw = (
            sys.stdin.buffer.readline()
        )

        if not raw:
            return 0

        try:
            request = json.loads(
                raw.decode(
                    "utf-8"
                )
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

            if (
                command
                != "synthesize"
            ):
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
            chunks = 0
            audio_bytes = 0

            for chunk in (
                voice.synthesize(
                    text
                )
            ):
                if (
                    first_audio
                    is None
                ):
                    first_audio = (
                        time.monotonic()
                    )

                pcm = (
                    chunk
                    .audio_int16_bytes
                )

                chunks += 1

                audio_bytes += len(
                    pcm
                )

                _send_audio(
                    request_id,
                    int(
                        chunk.sample_rate
                    ),
                    int(
                        chunk.sample_width
                    ),
                    int(
                        chunk.sample_channels
                    ),
                    pcm,
                )

            finished = (
                time.monotonic()
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
                        if (
                            first_audio
                            is not None
                        )
                        else None
                    ),
                    "total_seconds": (
                        finished
                        - synth_started
                    ),
                }
            )

        except Exception as exc:
            _send_json(
                {
                    "type": "error",
                    "error_type": (
                        type(
                            exc
                        ).__name__
                    ),
                    "message": str(
                        exc
                    ),
                }
            )


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
