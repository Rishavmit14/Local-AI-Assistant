from __future__ import annotations

import hashlib
import json
import os
import subprocess
import threading
import time
from collections import deque
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Queue
from typing import Any, BinaryIO

DEFAULT_PIPER_PYTHON_PATH = Path(
    "/AI/tools/piper/.venv/bin/python"
)

DEFAULT_PIPER_MODEL_PATH = Path(
    "/AI/models/friday/tts/"
    "en_US-ljspeech-medium.onnx"
)

DEFAULT_PIPER_MODEL_SHA256 = (
    "6f52a751e2349abe7a76735eb09dc187"
    "5298c77ea2342ffd2fef79ff81b87f22"
)

DEFAULT_PW_PLAY_PATH = Path(
    "/usr/bin/pw-play"
)

DEFAULT_PIPER_WORKER_PATH = (
    Path(__file__).with_name(
        "piper_worker.py"
    )
)


class PiperSpeechError(
    RuntimeError
):
    """Friday Piper runtime error."""


class SpeechPlaybackError(
    RuntimeError
):
    """Friday speaker playback error."""


@dataclass(
    frozen=True,
    slots=True,
)
class PiperSpeechConfig:
    python_path: Path = (
        DEFAULT_PIPER_PYTHON_PATH
    )

    model_path: Path = (
        DEFAULT_PIPER_MODEL_PATH
    )

    expected_model_sha256: str = (
        DEFAULT_PIPER_MODEL_SHA256
    )

    worker_path: Path = (
        DEFAULT_PIPER_WORKER_PATH
    )

    startup_timeout_seconds: float = 10.0
    synthesis_timeout_seconds: float = 20.0
    shutdown_timeout_seconds: float = 3.0

    def __post_init__(
        self,
    ) -> None:
        for name, value in (
            (
                "startup_timeout_seconds",
                self.startup_timeout_seconds,
            ),
            (
                "synthesis_timeout_seconds",
                self.synthesis_timeout_seconds,
            ),
            (
                "shutdown_timeout_seconds",
                self.shutdown_timeout_seconds,
            ),
        ):
            if value <= 0:
                raise ValueError(
                    f"{name} must be positive"
                )

        digest = (
            self.expected_model_sha256
            .lower()
        )

        if (
            len(digest) != 64
            or any(
                character
                not in "0123456789abcdef"
                for character in digest
            )
        ):
            raise ValueError(
                "expected_model_sha256 "
                "must be a valid SHA256 digest"
            )


@dataclass(
    frozen=True,
    slots=True,
)
class PiperAudioChunk:
    pcm: bytes
    sample_rate: int
    sample_width_bytes: int
    channels: int

    def __post_init__(
        self,
    ) -> None:
        if not self.pcm:
            raise ValueError(
                "pcm must not be empty"
            )

        if self.sample_rate <= 0:
            raise ValueError(
                "sample_rate must be positive"
            )

        if (
            self.sample_width_bytes
            <= 0
        ):
            raise ValueError(
                "sample_width_bytes "
                "must be positive"
            )

        if self.channels <= 0:
            raise ValueError(
                "channels must be positive"
            )


@dataclass(
    frozen=True,
    slots=True,
)
class PiperSynthesisMetrics:
    parent_first_audio_seconds: float
    parent_total_seconds: float
    worker_first_audio_seconds: float
    worker_total_seconds: float
    chunks: int
    audio_bytes: int


@dataclass(
    frozen=True,
    slots=True,
)
class PipeWirePlayerConfig:
    player_path: Path = (
        DEFAULT_PW_PLAY_PATH
    )

    target: str | int | None = None

    stop_timeout_seconds: float = 1.0

    def __post_init__(
        self,
    ) -> None:
        if (
            self.stop_timeout_seconds
            <= 0
        ):
            raise ValueError(
                "stop_timeout_seconds "
                "must be positive"
            )


@dataclass(
    frozen=True,
    slots=True,
)
class SpeechPlaybackResult:
    interrupted: bool
    elapsed_seconds: float
    pcm_bytes_written: int
    sample_rate: int


@dataclass(
    frozen=True,
    slots=True,
)
class SpeechStopResult:
    stopped: bool
    elapsed_seconds: float


class PiperSpeechSynthesizer:
    """
    Persistent process boundary around
    Friday's isolated Piper environment.
    """

    def __init__(
        self,
        config: (
            PiperSpeechConfig
            | None
        ) = None,
    ) -> None:
        self.config = (
            config
            if config is not None
            else PiperSpeechConfig()
        )

        self._process: (
            subprocess.Popen[bytes]
            | None
        ) = None

        self._events: (
            Queue[
                dict[
                    str,
                    Any,
                ]
            ]
        ) = Queue()

        self._stderr_tail: (
            deque[str]
        ) = deque(
            maxlen=50
        )

        self._reader_thread: (
            threading.Thread
            | None
        ) = None

        self._stderr_thread: (
            threading.Thread
            | None
        ) = None

        self._lifecycle_lock = (
            threading.Lock()
        )

        self._request_lock = (
            threading.Lock()
        )

        self._request_counter = 0

        self._model_load_seconds: (
            float
            | None
        ) = None

        self._last_metrics: (
            PiperSynthesisMetrics
            | None
        ) = None

        self._validate_runtime()

    @property
    def model_load_seconds(
        self,
    ) -> float | None:
        return (
            self._model_load_seconds
        )

    @property
    def last_metrics(
        self,
    ) -> (
        PiperSynthesisMetrics
        | None
    ):
        return (
            self._last_metrics
        )

    @property
    def worker_pid(
        self,
    ) -> int | None:
        process = (
            self._process
        )

        if (
            process is None
            or process.poll()
            is not None
        ):
            return None

        return process.pid

    @property
    def is_started(
        self,
    ) -> bool:
        return (
            self.worker_pid
            is not None
        )

    def __enter__(
        self,
    ) -> PiperSpeechSynthesizer:
        self.start()
        return self

    def __exit__(
        self,
        exc_type,
        exc,
        traceback,
    ) -> None:
        del (
            exc_type,
            exc,
            traceback,
        )

        self.close()

    def start(
        self,
    ) -> None:
        with self._lifecycle_lock:
            existing = (
                self._process
            )

            if (
                existing is not None
                and existing.poll()
                is None
            ):
                return

            if existing is not None:
                self._close_handles(
                    existing
                )

                self._process = None

            self._events = Queue()

            self._stderr_tail = deque(
                maxlen=50
            )

            process = subprocess.Popen(
                [
                    str(
                        self.config
                        .python_path
                    ),

                    # Important:
                    # isolated mode prevents
                    # worker-directory imports
                    # from shadowing Piper.
                    "-I",

                    "-u",

                    str(
                        self.config
                        .worker_path
                    ),

                    str(
                        self.config
                        .model_path
                    ),
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
            )

            if (
                process.stdin is None
                or process.stdout
                is None
                or process.stderr
                is None
            ):
                self._terminate(
                    process
                )

                raise PiperSpeechError(
                    "Piper worker pipes "
                    "unavailable"
                )

            self._process = (
                process
            )

            self._reader_thread = (
                threading.Thread(
                    target=(
                        self._read_stdout
                    ),
                    args=(
                        process.stdout,
                    ),
                    daemon=True,
                    name=(
                        "friday-piper-stdout"
                    ),
                )
            )

            self._stderr_thread = (
                threading.Thread(
                    target=(
                        self._read_stderr
                    ),
                    args=(
                        process.stderr,
                    ),
                    daemon=True,
                    name=(
                        "friday-piper-stderr"
                    ),
                )
            )

            self._reader_thread.start()
            self._stderr_thread.start()

            try:
                ready = (
                    self._next_event(
                        self.config
                        .startup_timeout_seconds
                    )
                )

                if (
                    ready.get(
                        "type"
                    )
                    != "ready"
                ):
                    raise PiperSpeechError(
                        "Piper worker did "
                        "not become ready: "
                        f"{ready}"
                    )

                self._model_load_seconds = (
                    float(
                        ready[
                            "load_seconds"
                        ]
                    )
                )

            except Exception:
                self._terminate(
                    process
                )

                self._process = None

                raise

    def stream(
        self,
        text: str,
    ) -> Iterator[
        PiperAudioChunk
    ]:
        normalized = (
            text.strip()
        )

        if not normalized:
            raise ValueError(
                "speech text must "
                "be non-empty"
            )

        self.start()

        with self._request_lock:
            process = (
                self._require_process()
            )

            if (
                process.stdin
                is None
            ):
                raise PiperSpeechError(
                    "Piper worker stdin "
                    "unavailable"
                )

            self._request_counter += 1

            request_id = (
                "speech-"
                f"{self._request_counter}"
            )

            started = (
                time.monotonic()
            )

            request = (
                json.dumps(
                    {
                        "command": (
                            "synthesize"
                        ),
                        "id": (
                            request_id
                        ),
                        "text": (
                            normalized
                        ),
                    },
                    separators=(
                        ",",
                        ":",
                    ),
                ).encode(
                    "utf-8"
                )
                + b"\n"
            )

            try:
                process.stdin.write(
                    request
                )

                process.stdin.flush()

            except (
                BrokenPipeError,
                OSError,
            ) as exc:
                raise PiperSpeechError(
                    "unable to send "
                    "Piper request"
                ) from exc

            accepted = (
                self._next_event(
                    self.config
                    .synthesis_timeout_seconds
                )
            )

            if (
                accepted.get(
                    "type"
                )
                != "accepted"
                or accepted.get(
                    "id"
                )
                != request_id
            ):
                raise PiperSpeechError(
                    "unexpected Piper "
                    "request acknowledgement: "
                    f"{accepted}"
                )

            first_audio = None
            terminal_seen = False

            try:
                while True:
                    event = (
                        self._next_event(
                            self.config
                            .synthesis_timeout_seconds
                        )
                    )

                    event_type = (
                        event.get(
                            "type"
                        )
                    )

                    if (
                        event_type
                        == "error"
                    ):
                        terminal_seen = True

                        raise PiperSpeechError(
                            "Piper synthesis "
                            "failed: "
                            f"{event.get('message')}"
                        )

                    if (
                        event_type
                        == "audio"
                    ):
                        if (
                            event.get(
                                "id"
                            )
                            != request_id
                        ):
                            raise PiperSpeechError(
                                "Piper audio "
                                "correlation mismatch"
                            )

                        if (
                            first_audio
                            is None
                        ):
                            first_audio = (
                                time.monotonic()
                            )

                        yield PiperAudioChunk(
                            pcm=(
                                event[
                                    "pcm"
                                ]
                            ),
                            sample_rate=int(
                                event[
                                    "sample_rate"
                                ]
                            ),
                            sample_width_bytes=int(
                                event[
                                    "sample_width"
                                ]
                            ),
                            channels=int(
                                event[
                                    "channels"
                                ]
                            ),
                        )

                        continue

                    if (
                        event_type
                        == "done"
                    ):
                        if (
                            event.get(
                                "id"
                            )
                            != request_id
                        ):
                            raise PiperSpeechError(
                                "Piper completion "
                                "correlation mismatch"
                            )

                        terminal_seen = True

                        if (
                            first_audio
                            is None
                        ):
                            raise PiperSpeechError(
                                "Piper completed "
                                "without audio"
                            )

                        self._last_metrics = (
                            PiperSynthesisMetrics(
                                parent_first_audio_seconds=(
                                    first_audio
                                    - started
                                ),
                                parent_total_seconds=(
                                    time.monotonic()
                                    - started
                                ),
                                worker_first_audio_seconds=float(
                                    event[
                                        "first_audio_seconds"
                                    ]
                                ),
                                worker_total_seconds=float(
                                    event[
                                        "total_seconds"
                                    ]
                                ),
                                chunks=int(
                                    event[
                                        "chunks"
                                    ]
                                ),
                                audio_bytes=int(
                                    event[
                                        "audio_bytes"
                                    ]
                                ),
                            )
                        )

                        return

                    raise PiperSpeechError(
                        "unexpected Piper "
                        "worker event: "
                        f"{event}"
                    )

            finally:
                if (
                    not terminal_seen
                ):
                    self._drain_request(
                        request_id
                    )

    def close(
        self,
    ) -> None:
        with self._request_lock:
            with self._lifecycle_lock:
                process = (
                    self._process
                )

                if process is None:
                    return

                try:
                    if (
                        process.poll()
                        is None
                    ):
                        if (
                            process.stdin
                            is None
                        ):
                            raise (
                                PiperSpeechError(
                                    "Piper stdin "
                                    "unavailable"
                                )
                            )

                        process.stdin.write(
                            b'{"command":"quit"}\n'
                        )

                        process.stdin.flush()

                        event = (
                            self._next_event(
                                self.config
                                .shutdown_timeout_seconds
                            )
                        )

                        if (
                            event.get(
                                "type"
                            )
                            != "bye"
                        ):
                            raise (
                                PiperSpeechError(
                                    "unexpected Piper "
                                    "shutdown response"
                                )
                            )

                        process.wait(
                            timeout=(
                                self.config
                                .shutdown_timeout_seconds
                            )
                        )

                except (
                    BrokenPipeError,
                    OSError,
                    subprocess.TimeoutExpired,
                    PiperSpeechError,
                ):
                    self._terminate(
                        process
                    )

                finally:
                    if (
                        process.poll()
                        is None
                    ):
                        self._terminate(
                            process
                        )

                    else:
                        self._close_handles(
                            process
                        )

                    self._process = None

    def _validate_runtime(
        self,
    ) -> None:
        if not (
            self.config
            .python_path
            .is_file()
        ):
            raise PiperSpeechError(
                "Piper Python "
                "does not exist: "
                f"{self.config.python_path}"
            )

        if not os.access(
            self.config.python_path,
            os.X_OK,
        ):
            raise PiperSpeechError(
                "Piper Python "
                "is not executable"
            )

        if not (
            self.config
            .worker_path
            .is_file()
        ):
            raise PiperSpeechError(
                "Piper worker "
                "does not exist: "
                f"{self.config.worker_path}"
            )

        # Deliberately verify the actual
        # model before the sidecar config.
        verify_piper_model_sha256(
            self.config.model_path,
            self.config
            .expected_model_sha256,
        )

        sidecar = Path(
            str(
                self.config
                .model_path
            )
            + ".json"
        )

        if not sidecar.is_file():
            raise PiperSpeechError(
                "Piper voice configuration "
                "does not exist: "
                f"{sidecar}"
            )

    def _require_process(
        self,
    ) -> subprocess.Popen[
        bytes
    ]:
        process = (
            self._process
        )

        if (
            process is None
            or process.poll()
            is not None
        ):
            raise PiperSpeechError(
                "Piper worker "
                "is not running"
            )

        return process

    def _read_stdout(
        self,
        stream: BinaryIO,
    ) -> None:
        try:
            while True:
                header = (
                    stream.readline()
                )

                if not header:
                    self._events.put(
                        {
                            "type": "_eof",
                        }
                    )

                    return

                parts = (
                    header.decode(
                        "ascii"
                    )
                    .rstrip(
                        "\n"
                    )
                    .split(
                        " "
                    )
                )

                if (
                    parts[0]
                    == "J"
                ):
                    if (
                        len(parts)
                        != 2
                    ):
                        raise (
                            PiperSpeechError(
                                "invalid JSON "
                                "frame header"
                            )
                        )

                    payload = (
                        _read_exact(
                            stream,
                            int(
                                parts[1]
                            ),
                        )
                    )

                    self._events.put(
                        json.loads(
                            payload.decode(
                                "utf-8"
                            )
                        )
                    )

                    continue

                if (
                    parts[0]
                    == "A"
                ):
                    if (
                        len(parts)
                        != 6
                    ):
                        raise (
                            PiperSpeechError(
                                "invalid audio "
                                "frame header"
                            )
                        )

                    (
                        _,
                        request_id,
                        rate,
                        width,
                        channels,
                        size,
                    ) = parts

                    pcm = _read_exact(
                        stream,
                        int(
                            size
                        ),
                    )

                    self._events.put(
                        {
                            "type": "audio",
                            "id": request_id,
                            "sample_rate": (
                                int(rate)
                            ),
                            "sample_width": (
                                int(width)
                            ),
                            "channels": (
                                int(channels)
                            ),
                            "pcm": pcm,
                        }
                    )

                    continue

                raise PiperSpeechError(
                    "unknown Piper frame"
                )

        except (
            ValueError,
            OSError,
        ) as exc:
            process = (
                self._process
            )

            if (
                process is not None
                and process.poll()
                is None
            ):
                self._events.put(
                    {
                        "type": (
                            "_reader_error"
                        ),
                        "message": (
                            repr(exc)
                        ),
                    }
                )

        except BaseException as exc:
            self._events.put(
                {
                    "type": (
                        "_reader_error"
                    ),
                    "message": (
                        repr(exc)
                    ),
                }
            )

    def _read_stderr(
        self,
        stream: BinaryIO,
    ) -> None:
        try:
            while True:
                line = (
                    stream.readline()
                )

                if not line:
                    return

                self._stderr_tail.append(
                    line.decode(
                        "utf-8",
                        errors="replace",
                    ).rstrip()
                )

        except (
            ValueError,
            OSError,
        ):
            return

    def _next_event(
        self,
        timeout: float,
    ) -> dict[str, Any]:
        try:
            event = (
                self._events.get(
                    timeout=timeout
                )
            )

        except Empty as exc:
            detail = "\n".join(
                self._stderr_tail
            )

            raise PiperSpeechError(
                "timed out waiting "
                "for Piper worker"
                + (
                    f"\n{detail}"
                    if detail
                    else ""
                )
            ) from exc

        if (
            event.get(
                "type"
            )
            == "_eof"
        ):
            detail = "\n".join(
                self._stderr_tail
            )

            raise PiperSpeechError(
                "Piper worker "
                "closed stdout"
                + (
                    f"\n{detail}"
                    if detail
                    else ""
                )
            )

        if (
            event.get(
                "type"
            )
            == "_reader_error"
        ):
            raise PiperSpeechError(
                "Piper protocol "
                "reader failed: "
                f"{event.get('message')}"
            )

        return event

    def _drain_request(
        self,
        request_id: str,
    ) -> None:
        deadline = (
            time.monotonic()
            + self.config
            .synthesis_timeout_seconds
        )

        while True:
            remaining = (
                deadline
                - time.monotonic()
            )

            if remaining <= 0:
                return

            try:
                event = (
                    self._next_event(
                        remaining
                    )
                )

            except PiperSpeechError:
                return

            if (
                event.get(
                    "type"
                )
                == "done"
                and event.get(
                    "id"
                )
                == request_id
            ):
                return

            if (
                event.get(
                    "type"
                )
                == "error"
            ):
                return

    def _terminate(
        self,
        process: subprocess.Popen[
            bytes
        ],
    ) -> None:
        if (
            process.poll()
            is None
        ):
            process.terminate()

            try:
                process.wait(
                    timeout=(
                        self.config
                        .shutdown_timeout_seconds
                    )
                )

            except (
                subprocess
                .TimeoutExpired
            ):
                process.kill()

                process.wait(
                    timeout=(
                        self.config
                        .shutdown_timeout_seconds
                    )
                )

        self._close_handles(
            process
        )

    def _close_handles(
        self,
        process: subprocess.Popen[
            bytes
        ],
    ) -> None:
        for thread in (
            self._reader_thread,
            self._stderr_thread,
        ):
            if (
                thread is not None
                and thread
                is not threading
                .current_thread()
            ):
                thread.join(
                    timeout=0.5
                )

        for stream in (
            process.stdin,
            process.stdout,
            process.stderr,
        ):
            if (
                stream is not None
                and not stream.closed
            ):
                try:
                    stream.close()

                except OSError:
                    pass

        for thread in (
            self._reader_thread,
            self._stderr_thread,
        ):
            if (
                thread is not None
                and thread
                is not threading
                .current_thread()
            ):
                thread.join(
                    timeout=0.5
                )

        self._reader_thread = None
        self._stderr_thread = None


class PipeWireSpeechPlayer:
    """Interruptible Friday raw PCM playback."""

    def __init__(
        self,
        config: (
            PipeWirePlayerConfig
            | None
        ) = None,
    ) -> None:
        self.config = (
            config
            if config is not None
            else PipeWirePlayerConfig()
        )

        if not (
            self.config
            .player_path
            .is_file()
        ):
            raise SpeechPlaybackError(
                "pw-play does not exist: "
                f"{self.config.player_path}"
            )

        self._active_lock = (
            threading.Lock()
        )

        self._play_lock = (
            threading.Lock()
        )

        self._stop_requested = (
            threading.Event()
        )

        self._active_process: (
            subprocess.Popen[bytes]
            | None
        ) = None

    @property
    def is_playing(
        self,
    ) -> bool:
        with self._active_lock:
            process = (
                self._active_process
            )

            return (
                process is not None
                and process.poll()
                is None
            )

    def play(
        self,
        chunks: Iterator[
            PiperAudioChunk
        ],
    ) -> SpeechPlaybackResult:
        with self._play_lock:
            self._stop_requested.clear()

            started = (
                time.monotonic()
            )

            process = None
            sample_rate = 0
            written = 0
            interrupted = False
            produced = False

            try:
                for chunk in chunks:
                    produced = True

                    if process is None:
                        if (
                            chunk
                            .sample_width_bytes
                            != 2
                        ):
                            raise (
                                SpeechPlaybackError(
                                    "PipeWire speech "
                                    "requires 16-bit PCM"
                                )
                            )

                        if (
                            chunk.channels
                            != 1
                        ):
                            raise (
                                SpeechPlaybackError(
                                    "PipeWire speech "
                                    "requires mono PCM"
                                )
                            )

                        sample_rate = (
                            chunk.sample_rate
                        )

                        process = (
                            subprocess.Popen(
                                self._command(
                                    sample_rate
                                ),
                                stdin=(
                                    subprocess.PIPE
                                ),
                                stdout=(
                                    subprocess
                                    .DEVNULL
                                ),
                                stderr=(
                                    subprocess.PIPE
                                ),
                                bufsize=0,
                            )
                        )

                        with (
                            self._active_lock
                        ):
                            self._active_process = (
                                process
                            )

                    if (
                        self._stop_requested
                        .is_set()
                    ):
                        interrupted = True
                        continue

                    if (
                        process.stdin
                        is None
                    ):
                        raise (
                            SpeechPlaybackError(
                                "pw-play stdin "
                                "unavailable"
                            )
                        )

                    try:
                        process.stdin.write(
                            chunk.pcm
                        )

                        process.stdin.flush()

                        written += len(
                            chunk.pcm
                        )

                    except (
                        BrokenPipeError,
                        OSError,
                    ) as exc:
                        if (
                            self._stop_requested
                            .is_set()
                        ):
                            interrupted = True
                            continue

                        raise (
                            SpeechPlaybackError(
                                "pw-play input "
                                "pipe failed"
                            )
                        ) from exc

                if not produced:
                    raise SpeechPlaybackError(
                        "speech stream "
                        "produced no audio"
                    )

                if process is None:
                    return (
                        SpeechPlaybackResult(
                            interrupted=True,
                            elapsed_seconds=(
                                time.monotonic()
                                - started
                            ),
                            pcm_bytes_written=0,
                            sample_rate=0,
                        )
                    )

                if (
                    self._stop_requested
                    .is_set()
                ):
                    interrupted = True

                    self._stop_process(
                        process
                    )

                else:
                    if (
                        process.stdin
                        is not None
                        and not process
                        .stdin.closed
                    ):
                        process.stdin.close()

                    code = (
                        process.wait(
                            timeout=60.0
                        )
                    )

                    if code != 0:
                        stderr = b""

                        if (
                            process.stderr
                            is not None
                            and not process
                            .stderr.closed
                        ):
                            stderr = (
                                process
                                .stderr.read()
                            )

                        raise (
                            SpeechPlaybackError(
                                "pw-play failed: "
                                + stderr.decode(
                                    "utf-8",
                                    errors=(
                                        "replace"
                                    ),
                                ).strip()
                            )
                        )

                return (
                    SpeechPlaybackResult(
                        interrupted=(
                            interrupted
                        ),
                        elapsed_seconds=(
                            time.monotonic()
                            - started
                        ),
                        pcm_bytes_written=(
                            written
                        ),
                        sample_rate=(
                            sample_rate
                        ),
                    )
                )

            finally:
                if process is not None:
                    if (
                        process.poll()
                        is None
                    ):
                        self._stop_process(
                            process
                        )

                    self._close_player(
                        process
                    )

                with self._active_lock:
                    if (
                        self._active_process
                        is process
                    ):
                        self._active_process = (
                            None
                        )

    def stop(
        self,
    ) -> SpeechStopResult:
        started = (
            time.monotonic()
        )

        self._stop_requested.set()

        with self._active_lock:
            process = (
                self._active_process
            )

        if (
            process is None
            or process.poll()
            is not None
        ):
            return (
                SpeechStopResult(
                    stopped=False,
                    elapsed_seconds=(
                        time.monotonic()
                        - started
                    ),
                )
            )

        self._stop_process(
            process
        )

        return SpeechStopResult(
            stopped=True,
            elapsed_seconds=(
                time.monotonic()
                - started
            ),
        )

    def _command(
        self,
        sample_rate: int,
    ) -> list[str]:
        command = [
            str(
                self.config.player_path
            ),
            "--raw",
            f"--rate={sample_rate}",
            "--channels=1",
            "--channel-map=mono",
            "--format=s16",
            "-",
        ]

        if (
            self.config.target
            is not None
        ):
            command.insert(
                1,
                (
                    "--target="
                    f"{self.config.target}"
                ),
            )

        return command

    def _stop_process(
        self,
        process: subprocess.Popen[
            bytes
        ],
    ) -> None:
        if (
            process.poll()
            is not None
        ):
            return

        process.terminate()

        try:
            process.wait(
                timeout=(
                    self.config
                    .stop_timeout_seconds
                )
            )

        except (
            subprocess.TimeoutExpired
        ):
            process.kill()

            process.wait(
                timeout=(
                    self.config
                    .stop_timeout_seconds
                )
            )

    def _close_player(
        self,
        process: subprocess.Popen[
            bytes
        ],
    ) -> None:
        for stream in (
            process.stdin,
            process.stdout,
            process.stderr,
        ):
            if (
                stream is not None
                and not stream.closed
            ):
                try:
                    stream.close()

                except OSError:
                    pass


def verify_piper_model_sha256(
    path: Path,
    expected_sha256: str,
) -> str:
    path = Path(
        path
    )

    if not path.is_file():
        raise PiperSpeechError(
            "Piper model does not exist: "
            f"{path}"
        )

    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as handle:
        while True:
            chunk = (
                handle.read(
                    1024
                    * 1024
                )
            )

            if not chunk:
                break

            digest.update(
                chunk
            )

    actual = (
        digest.hexdigest()
    )

    if (
        actual.lower()
        != expected_sha256
        .lower()
    ):
        raise PiperSpeechError(
            "Piper model SHA256 "
            "mismatch"
        )

    return actual


def _read_exact(
    stream: BinaryIO,
    count: int,
) -> bytes:
    result: list[bytes] = []
    remaining = count

    while remaining:
        chunk = stream.read(
            remaining
        )

        if not chunk:
            raise EOFError(
                "Piper stdout closed "
                "during frame"
            )

        result.append(
            chunk
        )

        remaining -= len(
            chunk
        )

    return b"".join(
        result
    )


__all__ = [
    "DEFAULT_PIPER_MODEL_PATH",
    "DEFAULT_PIPER_MODEL_SHA256",
    "DEFAULT_PIPER_PYTHON_PATH",
    "DEFAULT_PIPER_WORKER_PATH",
    "DEFAULT_PW_PLAY_PATH",
    "PipeWirePlayerConfig",
    "PipeWireSpeechPlayer",
    "PiperAudioChunk",
    "PiperSpeechConfig",
    "PiperSpeechError",
    "PiperSpeechSynthesizer",
    "PiperSynthesisMetrics",
    "SpeechPlaybackError",
    "SpeechPlaybackResult",
    "SpeechStopResult",
    "verify_piper_model_sha256",
]
