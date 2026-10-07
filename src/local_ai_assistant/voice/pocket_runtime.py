from __future__ import annotations

import os
import subprocess
import threading
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from queue import Queue

from local_ai_assistant.voice.piper_runtime import (
    PiperSpeechError,
    PiperSpeechSynthesizer,
)

DEFAULT_POCKET_PYTHON_PATH = Path(
    "/AI/benchmarks/friday-pocket-tts/.venv/bin/python"
)

DEFAULT_POCKET_WORKER_PATH = (
    Path(__file__).with_name(
        "pocket_worker.py"
    )
)

DEFAULT_POCKET_HF_HOME = Path(
    "/AI/benchmarks/friday-pocket-tts/hf-cache"
)


class PocketSpeechError(
    PiperSpeechError
):
    """Friday Pocket TTS runtime error."""


@dataclass(
    frozen=True,
    slots=True,
)
class PocketSpeechConfig:
    python_path: Path = (
        DEFAULT_POCKET_PYTHON_PATH
    )

    worker_path: Path = (
        DEFAULT_POCKET_WORKER_PATH
    )

    hf_home: Path = (
        DEFAULT_POCKET_HF_HOME
    )

    voice: str = "anna"

    cpu_affinity: str = "7"

    nice_level: int = 15

    target_lead_seconds: float = 0.32

    startup_timeout_seconds: float = 30.0
    synthesis_timeout_seconds: float = 30.0
    shutdown_timeout_seconds: float = 3.0
    event_queue_max_items: int = 128

    def __post_init__(
        self,
    ) -> None:
        if not self.voice.strip():
            raise ValueError(
                "voice must not be empty"
            )

        if not self.cpu_affinity.strip():
            raise ValueError(
                "cpu_affinity must not be empty"
            )

        if not (
            0 <= self.nice_level <= 19
        ):
            raise ValueError(
                "nice_level must be between 0 and 19"
            )

        if (
            self.target_lead_seconds
            <= 0
        ):
            raise ValueError(
                "target_lead_seconds must be positive"
            )

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

        if (
            self.event_queue_max_items
            < 1
        ):
            raise ValueError(
                "event_queue_max_items must be positive"
            )


class PocketSpeechSynthesizer(
    PiperSpeechSynthesizer
):
    """
    Persistent Pocket TTS process using Friday's
    existing qualified framed-audio protocol.
    """

    def __init__(
        self,
        config: PocketSpeechConfig | None = None,
    ) -> None:
        self.config = (
            config
            if config is not None
            else PocketSpeechConfig()
        )

        self._process = None

        self._events = Queue(
            maxsize=(
                self.config
                .event_queue_max_items
            )
        )

        self._reader_stop = (
            threading.Event()
        )

        self._stderr_tail = deque(
            maxlen=50
        )

        self._reader_thread = None
        self._stderr_thread = None

        self._lifecycle_lock = (
            threading.Lock()
        )

        self._request_lock = (
            threading.Lock()
        )

        self._request_counter = 0

        self._model_load_seconds = None
        self._last_metrics = None

        self._latency_observer = None

        self._validate_runtime()

    def _validate_runtime(
        self,
    ) -> None:
        if not (
            self.config
            .python_path
            .is_file()
        ):
            raise PocketSpeechError(
                "Pocket Python does not exist: "
                f"{self.config.python_path}"
            )

        if not os.access(
            self.config.python_path,
            os.X_OK,
        ):
            raise PocketSpeechError(
                "Pocket Python is not executable"
            )

        if not (
            self.config
            .worker_path
            .is_file()
        ):
            raise PocketSpeechError(
                "Pocket worker does not exist: "
                f"{self.config.worker_path}"
            )

        if not (
            self.config
            .hf_home
            .is_dir()
        ):
            raise PocketSpeechError(
                "Pocket HF cache does not exist: "
                f"{self.config.hf_home}"
            )

    def start(
        self,
    ) -> None:
        with self._lifecycle_lock:
            existing = self._process

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

            self._reader_stop.clear()

            self._events = Queue(
                maxsize=(
                    self.config
                    .event_queue_max_items
                )
            )

            self._stderr_tail = deque(
                maxlen=50
            )

            env = os.environ.copy()

            env.update(
                {
                    "HF_HOME": str(
                        self.config.hf_home
                    ),
                    "HF_HUB_OFFLINE": "1",
                    "OMP_NUM_THREADS": "1",
                    "MKL_NUM_THREADS": "1",
                    "OPENBLAS_NUM_THREADS": "1",
                    "NUMEXPR_NUM_THREADS": "1",
                    "FRIDAY_POCKET_VOICE":
                        self.config.voice,
                    "FRIDAY_POCKET_TARGET_LEAD_SECONDS":
                        str(
                            self.config
                            .target_lead_seconds
                        ),
                }
            )

            process = subprocess.Popen(
                [
                    "taskset",
                    "-c",
                    self.config.cpu_affinity,

                    "nice",
                    "-n",
                    str(
                        self.config.nice_level
                    ),

                    str(
                        self.config
                        .python_path
                    ),

                    "-I",
                    "-u",

                    str(
                        self.config
                        .worker_path
                    ),
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
                env=env,
            )

            if (
                process.stdin is None
                or process.stdout is None
                or process.stderr is None
            ):
                self._terminate(
                    process
                )

                raise PocketSpeechError(
                    "Pocket worker pipes unavailable"
                )

            self._process = process

            self._reader_thread = (
                threading.Thread(
                    target=self._read_stdout,
                    args=(
                        process.stdout,
                    ),
                    daemon=True,
                    name=(
                        "friday-pocket-stdout"
                    ),
                )
            )

            self._stderr_thread = (
                threading.Thread(
                    target=self._read_stderr,
                    args=(
                        process.stderr,
                    ),
                    daemon=True,
                    name=(
                        "friday-pocket-stderr"
                    ),
                )
            )

            self._reader_thread.start()
            self._stderr_thread.start()

            try:
                ready = self._next_event(
                    self.config
                    .startup_timeout_seconds
                )

                if (
                    ready.get("type")
                    != "ready"
                ):
                    raise PocketSpeechError(
                        "Pocket worker did not become ready: "
                        f"{ready}"
                    )

                self._model_load_seconds = float(
                    ready[
                        "load_seconds"
                    ]
                )

            except Exception:
                self._terminate(
                    process
                )

                self._process = None
                raise
