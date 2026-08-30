from __future__ import annotations

import sys
from pathlib import Path
from typing import cast

import pytest

from local_ai_assistant.voice import (
    PersistentWakeDetector,
    PersistentWakeProcessConfig,
    VoiceUtterance,
    WakeRuntimeError,
)


FAKE_WORKER = r"""
from __future__ import annotations

import json
import sys
import wave


def emit(payload):
    print(
        "FRIDAY_JSON:"
        + json.dumps(payload),
        flush=True,
    )


emit({
    "event": "ready",
    "model_load_seconds": 0.001,
})


for raw in sys.stdin:

    request = raw.strip()

    if request == "__QUIT__":

        emit({
            "event": "bye",
        })

        break


    try:

        with wave.open(
            request,
            "rb",
        ) as wav:

            channels = (
                wav.getnchannels()
            )

            width = (
                wav.getsampwidth()
            )

            rate = (
                wav.getframerate()
            )

            frames = (
                wav.getnframes()
            )


        if channels != 1:
            raise RuntimeError(
                "expected mono"
            )

        if width != 2:
            raise RuntimeError(
                "expected S16"
            )

        if rate != 16000:
            raise RuntimeError(
                "expected 16k"
            )

        if frames != 1600:
            raise RuntimeError(
                "unexpected frame count"
            )


        emit({
            "event": "result",
            "text": "Hey Friday",
            "latency_seconds": 0.012,
        })


    except Exception as exc:

        emit({
            "event": "error",
            "error": str(exc),
        })
"""


class FakeUtterance:
    pcm = (
        b"\x00\x00"
        * 1600
    )
    sample_rate = 16000
    channels = 1
    sample_width_bytes = 2


def make_utterance(
) -> VoiceUtterance:

    return cast(
        VoiceUtterance,
        FakeUtterance(),
    )


def make_detector(
    tmp_path: Path,
) -> PersistentWakeDetector:

    worker = (
        tmp_path
        / "fake_wake_worker.py"
    )

    worker.write_text(
        FAKE_WORKER,
        encoding="utf-8",
    )


    return PersistentWakeDetector(
        PersistentWakeProcessConfig(
            name="fake",
            python_path=Path(
                sys.executable
            ),
            worker_path=worker,
            startup_timeout_seconds=5.0,
            request_timeout_seconds=5.0,
        )
    )


def test_worker_is_lazy(
    tmp_path: Path,
) -> None:

    detector = make_detector(
        tmp_path
    )

    assert not detector.is_started
    assert detector.worker_pid is None


def test_start_keeps_process_resident(
    tmp_path: Path,
) -> None:

    detector = make_detector(
        tmp_path
    )


    try:

        detector.start()

        pid = detector.worker_pid

        assert pid is not None
        assert detector.is_started

        detector.start()

        assert (
            detector.worker_pid
            == pid
        )


    finally:

        detector.close()


def test_detect_auto_starts(
    tmp_path: Path,
) -> None:

    detector = make_detector(
        tmp_path
    )


    try:

        result = detector.detect(
            make_utterance()
        )

        assert (
            result.detector
            == "fake"
        )

        assert (
            result.transcript
            == "Hey Friday"
        )

        assert (
            result.elapsed_seconds
            == pytest.approx(
                0.012
            )
        )

        assert detector.is_started


    finally:

        detector.close()


def test_multiple_requests_reuse_pid(
    tmp_path: Path,
) -> None:

    detector = make_detector(
        tmp_path
    )


    try:

        first = detector.detect(
            make_utterance()
        )

        first_pid = (
            detector.worker_pid
        )

        second = detector.detect(
            make_utterance()
        )


        assert (
            first.transcript
            == "Hey Friday"
        )

        assert (
            second.transcript
            == "Hey Friday"
        )

        assert first_pid is not None

        assert (
            detector.worker_pid
            == first_pid
        )


    finally:

        detector.close()


def test_model_load_metric_preserved(
    tmp_path: Path,
) -> None:

    detector = make_detector(
        tmp_path
    )


    try:

        detector.start()

        assert (
            detector.model_load_seconds
            == pytest.approx(
                0.001
            )
        )


    finally:

        detector.close()


def test_context_manager_closes(
    tmp_path: Path,
) -> None:

    detector = make_detector(
        tmp_path
    )


    with detector:

        assert detector.is_started
        assert detector.worker_pid is not None


    assert not detector.is_started
    assert detector.worker_pid is None


def test_missing_worker_rejected(
    tmp_path: Path,
) -> None:

    detector = PersistentWakeDetector(
        PersistentWakeProcessConfig(
            name="missing",
            python_path=Path(
                sys.executable
            ),
            worker_path=(
                tmp_path
                / "does-not-exist.py"
            ),
        )
    )


    with pytest.raises(
        WakeRuntimeError,
        match="worker script",
    ):

        detector.start()


def test_non_mono_audio_rejected(
    tmp_path: Path,
) -> None:

    detector = make_detector(
        tmp_path
    )


    class Stereo:
        pcm = (
            b"\x00\x00"
            * 1600
        )
        sample_rate = 16000
        channels = 2
        sample_width_bytes = 2


    try:

        with pytest.raises(
            WakeRuntimeError,
            match="mono",
        ):

            detector.detect(
                cast(
                    VoiceUtterance,
                    Stereo(),
                )
            )


    finally:

        detector.close()


def test_wrong_sample_width_rejected(
    tmp_path: Path,
) -> None:

    detector = make_detector(
        tmp_path
    )


    class EightBit:
        pcm = (
            b"\x00"
            * 1600
        )
        sample_rate = 16000
        channels = 1
        sample_width_bytes = 1


    try:

        with pytest.raises(
            WakeRuntimeError,
            match="16-bit",
        ):

            detector.detect(
                cast(
                    VoiceUtterance,
                    EightBit(),
                )
            )


    finally:

        detector.close()


def test_empty_pcm_rejected(
    tmp_path: Path,
) -> None:

    detector = make_detector(
        tmp_path
    )


    class Empty:
        pcm = b""
        sample_rate = 16000
        channels = 1
        sample_width_bytes = 2


    try:

        with pytest.raises(
            WakeRuntimeError,
            match="non-empty",
        ):

            detector.detect(
                cast(
                    VoiceUtterance,
                    Empty(),
                )
            )


    finally:

        detector.close()


def test_invalid_config_name_rejected(
    tmp_path: Path,
) -> None:

    with pytest.raises(
        ValueError,
        match="name",
    ):

        PersistentWakeProcessConfig(
            name=" ",
            python_path=Path(
                sys.executable
            ),
            worker_path=(
                tmp_path
                / "worker.py"
            ),
        )


def test_invalid_timeout_rejected(
    tmp_path: Path,
) -> None:

    with pytest.raises(
        ValueError,
        match="request_timeout_seconds",
    ):

        PersistentWakeProcessConfig(
            name="fake",
            python_path=Path(
                sys.executable
            ),
            worker_path=(
                tmp_path
                / "worker.py"
            ),
            request_timeout_seconds=0,
        )



def test_timeout_invalidates_worker_before_next_request(
    tmp_path: Path,
) -> None:
    """A delayed A response must never be consumed by request B."""

    import textwrap

    state_path = (
        tmp_path
        / "timeout-state"
    )

    worker = (
        tmp_path
        / "timeout-worker.py"
    )

    worker.write_text(
        textwrap.dedent(
            f"""
            from __future__ import annotations

            import json
            import pathlib
            import sys
            import time


            PREFIX = "FRIDAY_JSON:"
            STATE = pathlib.Path({str(state_path)!r})


            def emit(payload):
                print(
                    PREFIX
                    + json.dumps(
                        payload,
                        separators=(",", ":"),
                    ),
                    flush=True,
                )


            emit(
                {{
                    "event": "ready",
                    "engine": "fake-timeout",
                    "model_load_seconds": 0.001,
                }}
            )


            for raw in sys.stdin:

                request = raw.strip()

                if request == "__QUIT__":
                    emit(
                        {{
                            "event": "bye",
                            "engine": "fake-timeout",
                        }}
                    )
                    break


                if not STATE.exists():

                    # Persist before sleeping so a freshly restarted
                    # worker knows request A already failed.
                    STATE.write_text(
                        "request-a-timed-out",
                        encoding="utf-8",
                    )

                    time.sleep(0.60)

                    emit(
                        {{
                            "event": "result",
                            "engine": "fake-timeout",
                            "text": "Hey Friday stale request A",
                            "latency_seconds": 0.60,
                        }}
                    )

                else:

                    emit(
                        {{
                            "event": "result",
                            "engine": "fake-timeout",
                            "text": "definitely not a wake phrase",
                            "latency_seconds": 0.001,
                        }}
                    )
            """
        ),
        encoding="utf-8",
    )


    detector = PersistentWakeDetector(
        PersistentWakeProcessConfig(
            name="fake-timeout",
            python_path=Path(
                sys.executable
            ),
            worker_path=worker,
            startup_timeout_seconds=2.0,
            request_timeout_seconds=0.20,
        )
    )


    try:

        detector.start()

        first_pid = detector.worker_pid

        assert first_pid is not None


        with pytest.raises(
            WakeRuntimeError,
            match="timed out",
        ):

            detector.detect(
                make_utterance()
            )


        # Critical R4 guarantee:
        # the poisoned worker is immediately gone.
        assert detector.worker_pid is None
        assert not detector.is_started


        second = detector.detect(
            make_utterance()
        )

        second_pid = detector.worker_pid


        assert second.transcript == (
            "definitely not a wake phrase"
        )

        assert second_pid is not None
        assert second_pid != first_pid


    finally:

        detector.close()



def test_invalid_json_invalidates_worker_before_next_request(
    tmp_path: Path,
) -> None:
    """Malformed protocol must discard the child before another request."""

    import textwrap

    state_path = (
        tmp_path
        / "json-state"
    )

    worker = (
        tmp_path
        / "json-worker.py"
    )

    worker.write_text(
        textwrap.dedent(
            f"""
            from __future__ import annotations

            import json
            import pathlib
            import sys


            PREFIX = "FRIDAY_JSON:"
            STATE = pathlib.Path({str(state_path)!r})


            def emit(payload):
                print(
                    PREFIX
                    + json.dumps(
                        payload,
                        separators=(",", ":"),
                    ),
                    flush=True,
                )


            emit(
                {{
                    "event": "ready",
                    "engine": "fake-json",
                    "model_load_seconds": 0.001,
                }}
            )


            for raw in sys.stdin:

                request = raw.strip()

                if request == "__QUIT__":
                    emit(
                        {{
                            "event": "bye",
                            "engine": "fake-json",
                        }}
                    )
                    break


                if not STATE.exists():

                    STATE.write_text(
                        "bad-json-emitted",
                        encoding="utf-8",
                    )

                    print(
                        "FRIDAY_JSON:{{not-valid-json",
                        flush=True,
                    )

                else:

                    emit(
                        {{
                            "event": "result",
                            "engine": "fake-json",
                            "text": "fresh response",
                            "latency_seconds": 0.001,
                        }}
                    )
            """
        ),
        encoding="utf-8",
    )


    detector = PersistentWakeDetector(
        PersistentWakeProcessConfig(
            name="fake-json",
            python_path=Path(
                sys.executable
            ),
            worker_path=worker,
            startup_timeout_seconds=2.0,
            request_timeout_seconds=1.0,
        )
    )


    try:

        detector.start()

        first_pid = detector.worker_pid

        assert first_pid is not None


        with pytest.raises(
            WakeRuntimeError,
            match="invalid JSON",
        ):

            detector.detect(
                make_utterance()
            )


        assert detector.worker_pid is None
        assert not detector.is_started


        second = detector.detect(
            make_utterance()
        )

        second_pid = detector.worker_pid


        assert second.transcript == (
            "fresh response"
        )

        assert second_pid is not None
        assert second_pid != first_pid


    finally:

        detector.close()
