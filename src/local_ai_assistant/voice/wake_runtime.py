"""Persistent isolated-process wake detector runtime.

Friday itself does not import Parakeet, sherpa-onnx, or Moonshine.
Qualified engines remain in their own isolated Python environments.

Protocol:

Worker startup:
    FRIDAY_JSON:{"event":"ready", ...}

Request:
    /absolute/path/to/utterance.wav

Response:
    FRIDAY_JSON:{
        "event":"result",
        "text":"Hey Friday",
        "latency_seconds":0.123
    }

Shutdown:
    __QUIT__
"""

from __future__ import annotations

import json
import selectors
import subprocess
import tempfile
import threading
import time
import wave
from dataclasses import dataclass
from pathlib import Path

from .vad import VoiceUtterance
from .wake import WakeDetectionResult


_PROTOCOL_PREFIX = "FRIDAY_JSON:"


class WakeRuntimeError(
    RuntimeError
):
    """Failure communicating with an isolated wake worker."""


@dataclass(
    frozen=True,
    slots=True,
)
class PersistentWakeProcessConfig:
    """Configuration for one resident wake worker process."""

    name: str
    python_path: Path
    worker_path: Path
    startup_timeout_seconds: float = 15.0
    request_timeout_seconds: float = 10.0

    def __post_init__(
        self,
    ) -> None:

        if not self.name.strip():

            raise ValueError(
                "name must not be empty"
            )

        if (
            self.startup_timeout_seconds
            <= 0
        ):

            raise ValueError(
                "startup_timeout_seconds "
                "must be positive"
            )

        if (
            self.request_timeout_seconds
            <= 0
        ):

            raise ValueError(
                "request_timeout_seconds "
                "must be positive"
            )


class PersistentWakeDetector:
    """Wake detector backed by one resident isolated worker."""

    def __init__(
        self,
        config: PersistentWakeProcessConfig,
    ) -> None:

        self.config = config

        self._process: (
            subprocess.Popen[str]
            | None
        ) = None

        # detect() may need to invoke start().
        # RLock prevents self-deadlock.
        self._io_lock = (
            threading.RLock()
        )

        self._model_load_seconds: (
            float
            | None
        ) = None


    @property
    def name(
        self,
    ) -> str:

        return self.config.name


    @property
    def is_started(
        self,
    ) -> bool:

        process = self._process

        return (
            process is not None
            and process.poll()
            is None
        )


    @property
    def worker_pid(
        self,
    ) -> int | None:

        process = self._process

        if (
            process is None
            or process.poll()
            is not None
        ):

            return None

        return process.pid


    @property
    def model_load_seconds(
        self,
    ) -> float | None:

        return self._model_load_seconds


    def __enter__(
        self,
    ) -> PersistentWakeDetector:

        self.start()

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

        self.close()


    def start(
        self,
    ) -> None:
        """Start worker exactly once and require a ready event."""

        with self._io_lock:

            if self.is_started:
                return

            python_path = (
                self.config
                .python_path
            )

            worker_path = (
                self.config
                .worker_path
            )


            if not python_path.is_file():

                raise WakeRuntimeError(
                    "wake worker Python "
                    "does not exist: "
                    f"{python_path}"
                )


            if not worker_path.is_file():

                raise WakeRuntimeError(
                    "wake worker script "
                    "does not exist: "
                    f"{worker_path}"
                )


            process = subprocess.Popen(
                [
                    str(
                        python_path
                    ),
                    str(
                        worker_path
                    ),
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=None,
                text=True,
                bufsize=1,
            )

            self._process = (
                process
            )


            try:

                ready = (
                    self._read_message(
                        timeout_seconds=(
                            self.config
                            .startup_timeout_seconds
                        )
                    )
                )

            except Exception:

                self._terminate_process()

                raise


            if (
                ready.get(
                    "event"
                )
                != "ready"
            ):

                self._terminate_process()

                raise WakeRuntimeError(
                    "wake worker did not "
                    "report ready"
                )


            raw_load = (
                ready.get(
                    "model_load_seconds"
                )
            )


            if raw_load is not None:

                try:

                    load_seconds = float(
                        raw_load
                    )

                except (
                    TypeError,
                    ValueError,
                ) as exc:

                    self._terminate_process()

                    raise WakeRuntimeError(
                        "invalid worker "
                        "model load time"
                    ) from exc


                if load_seconds < 0:

                    self._terminate_process()

                    raise WakeRuntimeError(
                        "negative worker "
                        "model load time"
                    )


                self._model_load_seconds = (
                    load_seconds
                )


    def detect(
        self,
        utterance: VoiceUtterance,
    ) -> WakeDetectionResult:
        """Serialize one utterance and send it to the resident worker.

        Once a request has been written, any transport, protocol, worker,
        or response-validation failure invalidates the resident child.
        The next detect() therefore starts a completely fresh worker and
        can never consume a delayed response from the failed request.
        """

        with self._io_lock:

            if not self.is_started:

                self.start()


            process = (
                self._require_process()
            )

            stdin = (
                process.stdin
            )


            if stdin is None:

                self._terminate_process()

                raise WakeRuntimeError(
                    "wake worker stdin "
                    "is unavailable"
                )


            with tempfile.TemporaryDirectory(
                prefix=(
                    "friday-wake-"
                    f"{self.name}-"
                )
            ) as directory:

                wav_path = (
                    Path(
                        directory
                    )
                    / "utterance.wav"
                )


                # Local utterance validation happens before touching
                # the worker protocol. A bad local utterance therefore
                # does not unnecessarily discard a healthy resident.
                self._write_wav(
                    utterance,
                    wav_path,
                )


                wall_started = (
                    time.perf_counter()
                )


                try:

                    try:

                        stdin.write(
                            str(
                                wav_path
                            )
                            + "\n"
                        )

                        stdin.flush()

                    except (
                        BrokenPipeError,
                        OSError,
                    ) as exc:

                        raise WakeRuntimeError(
                            "wake worker request "
                            "pipe failed"
                        ) from exc


                    response = (
                        self._read_message(
                            timeout_seconds=(
                                self.config
                                .request_timeout_seconds
                            )
                        )
                    )


                    wall_seconds = (
                        time.perf_counter()
                        - wall_started
                    )


                    event = response.get(
                        "event"
                    )


                    if event == "error":

                        raise WakeRuntimeError(
                            str(
                                response.get(
                                    "error",
                                    "wake worker error",
                                )
                            )
                        )


                    if event != "result":

                        raise WakeRuntimeError(
                            "unexpected wake worker "
                            f"event: {event!r}"
                        )


                    text = str(
                        response.get(
                            "text",
                            "",
                        )
                    )


                    raw_latency = (
                        response.get(
                            "latency_seconds"
                        )
                    )


                    if raw_latency is None:

                        elapsed_seconds = (
                            wall_seconds
                        )

                    else:

                        try:

                            elapsed_seconds = (
                                float(
                                    raw_latency
                                )
                            )

                        except (
                            TypeError,
                            ValueError,
                        ) as exc:

                            raise WakeRuntimeError(
                                "invalid worker "
                                "latency"
                            ) from exc


                    if elapsed_seconds < 0:

                        raise WakeRuntimeError(
                            "negative worker latency"
                        )


                except Exception:

                    # Fail closed. Once a request was sent, the byte/
                    # message stream can no longer be trusted after any
                    # incomplete or invalid transaction.
                    self._terminate_process()

                    raise


            return WakeDetectionResult(
                detector=self.name,
                transcript=text,
                elapsed_seconds=(
                    elapsed_seconds
                ),
            )



    def close(
        self,
    ) -> None:
        """Stop worker and release all local pipe resources."""

        with self._io_lock:

            process = (
                self._process
            )


            if process is None:
                return


            if process.poll() is None:

                stdin = (
                    process.stdin
                )

                if stdin is not None:

                    try:

                        stdin.write(
                            "__QUIT__\n"
                        )

                        stdin.flush()

                    except (
                        BrokenPipeError,
                        OSError,
                    ):
                        pass


                try:

                    process.wait(
                        timeout=5.0
                    )

                except subprocess.TimeoutExpired:

                    self._terminate_process()


            self._close_pipes()

            self._process = None


    def _require_process(
        self,
    ) -> subprocess.Popen[str]:

        process = (
            self._process
        )


        if (
            process is None
            or process.poll()
            is not None
        ):

            raise WakeRuntimeError(
                "wake worker is not running"
            )


        return process


    def _read_message(
        self,
        *,
        timeout_seconds: float,
    ) -> dict[str, object]:
        """Read one protocol message with a real pipe timeout."""

        process = (
            self._require_process()
        )

        stdout = (
            process.stdout
        )


        if stdout is None:

            raise WakeRuntimeError(
                "wake worker stdout "
                "is unavailable"
            )


        deadline = (
            time.monotonic()
            + timeout_seconds
        )


        selector = (
            selectors.DefaultSelector()
        )


        try:

            selector.register(
                stdout,
                selectors.EVENT_READ,
            )


            while True:

                if process.poll() is not None:

                    raise WakeRuntimeError(
                        "wake worker exited "
                        "before response"
                    )


                remaining = (
                    deadline
                    - time.monotonic()
                )


                if remaining <= 0:

                    raise WakeRuntimeError(
                        "wake worker response "
                        "timed out"
                    )


                events = selector.select(
                    timeout=remaining
                )


                if not events:

                    raise WakeRuntimeError(
                        "wake worker response "
                        "timed out"
                    )


                line = (
                    stdout.readline()
                )


                if line == "":

                    raise WakeRuntimeError(
                        "wake worker stdout "
                        "closed"
                    )


                line = (
                    line.strip()
                )


                if not line.startswith(
                    _PROTOCOL_PREFIX
                ):

                    continue


                payload = line[
                    len(
                        _PROTOCOL_PREFIX
                    ):
                ]


                try:

                    parsed = (
                        json.loads(
                            payload
                        )
                    )

                except json.JSONDecodeError as exc:

                    raise WakeRuntimeError(
                        "wake worker returned "
                        "invalid JSON"
                    ) from exc


                if not isinstance(
                    parsed,
                    dict,
                ):

                    raise WakeRuntimeError(
                        "wake worker JSON "
                        "must be an object"
                    )


                return parsed


        finally:

            selector.close()


    @staticmethod
    def _write_wav(
        utterance: VoiceUtterance,
        path: Path,
    ) -> None:
        """Serialize Friday PCM without changing its samples."""

        pcm = utterance.pcm

        sample_rate = int(
            utterance.sample_rate
        )

        channels = int(
            getattr(
                utterance,
                "channels",
                1,
            )
        )

        sample_width = int(
            getattr(
                utterance,
                "sample_width_bytes",
                2,
            )
        )


        if sample_rate <= 0:

            raise WakeRuntimeError(
                "utterance sample rate "
                "must be positive"
            )


        if channels != 1:

            raise WakeRuntimeError(
                "wake runtime requires "
                "mono PCM"
            )


        if sample_width != 2:

            raise WakeRuntimeError(
                "wake runtime requires "
                "16-bit PCM"
            )


        if not pcm:

            raise WakeRuntimeError(
                "wake runtime requires "
                "non-empty PCM"
            )


        with wave.open(
            str(path),
            "wb",
        ) as wav:

            wav.setnchannels(
                channels
            )

            wav.setsampwidth(
                sample_width
            )

            wav.setframerate(
                sample_rate
            )

            wav.writeframes(
                pcm
            )


    def _terminate_process(
        self,
    ) -> None:

        process = (
            self._process
        )


        if process is None:
            return


        if process.poll() is None:

            process.terminate()


            try:

                process.wait(
                    timeout=2.0
                )

            except subprocess.TimeoutExpired:

                process.kill()

                process.wait(
                    timeout=2.0
                )


        self._close_pipes()

        self._process = None


    def _close_pipes(
        self,
    ) -> None:

        process = (
            self._process
        )


        if process is None:
            return


        for pipe in [
            process.stdin,
            process.stdout,
        ]:

            if pipe is not None:

                try:

                    pipe.close()

                except OSError:
                    pass


__all__ = [
    "PersistentWakeDetector",
    "PersistentWakeProcessConfig",
    "WakeRuntimeError",
]
