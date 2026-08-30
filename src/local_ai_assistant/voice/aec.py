from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO

from .audio import VoiceAudioConfig

DEFAULT_PW_CLI_PATH = Path("/usr/bin/pw-cli")
DEFAULT_PW_DUMP_PATH = Path("/usr/bin/pw-dump")
DEFAULT_PW_RECORD_PATH = Path("/usr/bin/pw-record")


class PipeWireAecError(RuntimeError):
    """Friday PipeWire acoustic echo-cancellation error."""


@dataclass(frozen=True, slots=True)
class PipeWireAecConfig:
    """Ephemeral WebRTC AEC graph owned by Friday."""

    pw_cli_path: Path = DEFAULT_PW_CLI_PATH
    pw_dump_path: Path = DEFAULT_PW_DUMP_PATH

    module_name: str = "libpipewire-module-echo-cancel"
    library_name: str = "aec/libspa-aec-webrtc"

    capture_node_name: str = "friday_aec_capture"
    source_node_name: str = "friday_aec_source"
    sink_node_name: str = "friday_aec_sink"
    playback_node_name: str = "friday_aec_playback"

    monitor_mode: bool = False

    startup_timeout_seconds: float = 8.0
    shutdown_timeout_seconds: float = 3.0
    poll_interval_seconds: float = 0.1

    def __post_init__(self) -> None:
        for name, value in (
            (
                "startup_timeout_seconds",
                self.startup_timeout_seconds,
            ),
            (
                "shutdown_timeout_seconds",
                self.shutdown_timeout_seconds,
            ),
            (
                "poll_interval_seconds",
                self.poll_interval_seconds,
            ),
        ):
            if value <= 0:
                raise ValueError(
                    f"{name} must be positive"
                )

        for name, value in (
            (
                "capture_node_name",
                self.capture_node_name,
            ),
            (
                "source_node_name",
                self.source_node_name,
            ),
            (
                "sink_node_name",
                self.sink_node_name,
            ),
            (
                "playback_node_name",
                self.playback_node_name,
            ),
        ):
            if not value:
                raise ValueError(
                    f"{name} must not be empty"
                )


@dataclass(frozen=True, slots=True)
class PipeWireAecEndpoints:
    """Published targets of Friday's AEC graph."""

    source_target: int
    sink_target: int | None

    source_node_name: str
    sink_node_name: str


@dataclass(frozen=True, slots=True)
class PipeWirePcmCaptureConfig:
    """Raw PCM capture from an explicit PipeWire target."""

    target: str | int

    audio: VoiceAudioConfig = field(
        default_factory=VoiceAudioConfig
    )

    pw_record_path: Path = (
        DEFAULT_PW_RECORD_PATH
    )

    latency_ms: int = 30

    def __post_init__(self) -> None:
        if (
            isinstance(
                self.target,
                str,
            )
            and not self.target
        ):
            raise ValueError(
                "PipeWire capture target "
                "must not be empty"
            )

        if self.latency_ms <= 0:
            raise ValueError(
                "latency_ms must be positive"
            )

        if (
            self.audio.sample_width_bytes
            != 2
        ):
            raise ValueError(
                "PipeWire AEC capture "
                "requires 16-bit PCM"
            )

        if self.audio.channels != 1:
            raise ValueError(
                "PipeWire AEC capture "
                "requires mono PCM"
            )


class PipeWirePcmStream:
    """Managed raw PCM stream from pw-record."""

    def __init__(
        self,
        process: subprocess.Popen[bytes],
        chunk_bytes: int,
    ) -> None:
        if process.stdout is None:
            raise PipeWireAecError(
                "pw-record stdout "
                "pipe unavailable"
            )

        self._process = process
        self._stdout: BinaryIO = (
            process.stdout
        )

        self._chunk_bytes = (
            chunk_bytes
        )

        self._closed = False

    @property
    def running(self) -> bool:
        return (
            not self._closed
            and self._process.poll()
            is None
        )

    def read_chunk(self) -> bytes:
        if self._closed:
            return b""

        pieces: list[bytes] = []
        remaining = (
            self._chunk_bytes
        )

        while remaining:
            chunk = (
                self._stdout.read(
                    remaining
                )
            )

            if not chunk:
                break

            pieces.append(
                chunk
            )

            remaining -= len(
                chunk
            )

        pcm = b"".join(
            pieces
        )

        if (
            len(pcm)
            == self._chunk_bytes
        ):
            return pcm

        return_code = (
            self._process.poll()
        )

        if (
            return_code
            not in (
                None,
                0,
            )
        ):
            raise PipeWireAecError(
                self._failure_message(
                    return_code
                )
            )

        if pcm:
            raise PipeWireAecError(
                "pw-record produced "
                "a partial PCM chunk"
            )

        return b""

    def close(self) -> None:
        if self._closed:
            return

        self._closed = True

        if (
            self._process.poll()
            is None
        ):
            self._process.terminate()

            try:
                self._process.wait(
                    timeout=1.0
                )

            except (
                subprocess.TimeoutExpired
            ):
                self._process.kill()

                self._process.wait(
                    timeout=1.0
                )

        for stream in (
            self._process.stdout,
            self._process.stderr,
        ):
            if (
                stream is not None
                and not stream.closed
            ):
                try:
                    stream.close()

                except OSError:
                    pass

    def _failure_message(
        self,
        return_code: int,
    ) -> str:
        detail = ""

        stderr = (
            self._process.stderr
        )

        if (
            stderr is not None
            and not stderr.closed
        ):
            try:
                raw = stderr.read()

            except (
                OSError,
                ValueError,
            ):
                raw = b""

            detail = raw.decode(
                "utf-8",
                errors="replace",
            ).strip()

        message = (
            "pw-record exited with "
            f"status {return_code}"
        )

        if detail:
            return (
                f"{message}: {detail}"
            )

        return message

    def __enter__(
        self,
    ) -> PipeWirePcmStream:
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


class PipeWirePcmCapture:
    """Capture raw PCM from an explicit PipeWire target."""

    def __init__(
        self,
        config: PipeWirePcmCaptureConfig,
    ) -> None:
        self.config = config
        self.audio_config = (
            config.audio
        )

        path = (
            self.config
            .pw_record_path
        )

        if not path.is_file():
            raise PipeWireAecError(
                "pw-record does not exist: "
                f"{path}"
            )

        if not os.access(
            path,
            os.X_OK,
        ):
            raise PipeWireAecError(
                "pw-record is not executable: "
                f"{path}"
            )

    def open_stream(
        self,
    ) -> PipeWirePcmStream:
        audio = (
            self.audio_config
        )

        command = [
            str(
                self.config
                .pw_record_path
            ),
            "--raw",
            (
                "--target="
                f"{self.config.target}"
            ),
            (
                "--latency="
                f"{self.config.latency_ms}ms"
            ),
            (
                f"--rate="
                f"{audio.sample_rate}"
            ),
            (
                f"--channels="
                f"{audio.channels}"
            ),
            "--channel-map=mono",
            "--format=s16",
            "-",
        ]

        try:
            process = (
                subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=0,
                )
            )

        except OSError as exc:
            raise PipeWireAecError(
                "unable to start "
                f"pw-record: {exc}"
            ) from exc

        return PipeWirePcmStream(
            process,
            audio.chunk_bytes,
        )


class PipeWireAecSession:
    """
    Own an ephemeral PipeWire WebRTC AEC graph.

    No persistent PipeWire or WirePlumber
    configuration is created.
    """

    def __init__(
        self,
        config: (
            PipeWireAecConfig
            | None
        ) = None,
    ) -> None:
        self.config = (
            config
            if config is not None
            else PipeWireAecConfig()
        )

        self._process: (
            subprocess.Popen[bytes]
            | None
        ) = None

        self._endpoints: (
            PipeWireAecEndpoints
            | None
        ) = None

        self._validate_runtime()

    @property
    def running(self) -> bool:
        return (
            self._process is not None
            and self._process.poll()
            is None
            and self._endpoints
            is not None
        )

    @property
    def endpoints(
        self,
    ) -> PipeWireAecEndpoints:
        if self._endpoints is None:
            raise PipeWireAecError(
                "AEC graph is not running"
            )

        return self._endpoints

    @property
    def module_arguments(
        self,
    ) -> str:
        config = self.config

        lines = [
            "{",
            (
                '    library.name = '
                f'"{config.library_name}"'
            ),
        ]

        if config.monitor_mode:
            lines.append(
                "    monitor.mode = true"
            )

        lines.extend(
            [
                "",
                "    capture.props = {",
                (
                    '        node.name = '
                    f'"{config.capture_node_name}"'
                ),
                "    }",
                "",
                "    source.props = {",
                (
                    '        node.name = '
                    f'"{config.source_node_name}"'
                ),
                (
                    '        node.description = '
                    '"Friday AEC Source"'
                ),
                "    }",
            ]
        )

        if not config.monitor_mode:
            lines.extend(
                [
                    "",
                    "    sink.props = {",
                    (
                        '        node.name = '
                        f'"{config.sink_node_name}"'
                    ),
                    (
                        '        node.description = '
                        '"Friday AEC Sink"'
                    ),
                    "    }",
                ]
            )

        lines.extend(
            [
                "",
                "    playback.props = {",
                (
                    '        node.name = '
                    f'"{config.playback_node_name}"'
                ),
                "    }",
                "}",
            ]
        )

        return "\n".join(
            lines
        )

    def start(
        self,
    ) -> PipeWireAecEndpoints:
        if self.running:
            return self.endpoints

        names = (
            self._all_node_names()
        )

        existing = (
            names
            & set(
                self._nodes()
            )
        )

        if existing:
            raise PipeWireAecError(
                "Friday AEC nodes "
                "already exist: "
                + ", ".join(
                    sorted(
                        existing
                    )
                )
            )

        process = subprocess.Popen(
            [
                str(
                    self.config
                    .pw_cli_path
                ),
                "-m",
                "load-module",
                self.config.module_name,
                self.module_arguments,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        self._process = process

        deadline = (
            time.monotonic()
            + self.config
            .startup_timeout_seconds
        )

        while (
            time.monotonic()
            < deadline
        ):
            if (
                process.poll()
                is not None
            ):
                self._process = None

                raise PipeWireAecError(
                    "PipeWire echo-cancel "
                    "module exited during startup"
                )

            nodes = (
                self._nodes()
            )

            source = nodes.get(
                self.config
                .source_node_name
            )

            sink = nodes.get(
                self.config
                .sink_node_name
            )

            sink_ready = (
                self.config.monitor_mode
                or sink is not None
            )

            if (
                source is not None
                and sink_ready
            ):
                try:
                    source_serial = int(
                        source[
                            "serial"
                        ]
                    )

                    sink_serial = (
                        int(
                            sink[
                                "serial"
                            ]
                        )
                        if sink is not None
                        else None
                    )

                except (
                    KeyError,
                    TypeError,
                    ValueError,
                ) as exc:
                    self.close()

                    raise PipeWireAecError(
                        "AEC nodes did not "
                        "publish valid "
                        "object.serial values"
                    ) from exc

                endpoints = (
                    PipeWireAecEndpoints(
                        source_target=(
                            source_serial
                        ),
                        sink_target=(
                            sink_serial
                        ),
                        source_node_name=(
                            self.config
                            .source_node_name
                        ),
                        sink_node_name=(
                            self.config
                            .sink_node_name
                        ),
                    )
                )

                self._endpoints = (
                    endpoints
                )

                return endpoints

            time.sleep(
                self.config
                .poll_interval_seconds
            )

        self.close()

        raise PipeWireAecError(
            "timed out waiting "
            "for Friday AEC nodes"
        )

    def close(self) -> None:
        process = (
            self._process
        )

        self._process = None
        self._endpoints = None

        if (
            process is not None
            and process.poll()
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
                subprocess.TimeoutExpired
            ):
                process.kill()

                process.wait(
                    timeout=(
                        self.config
                        .shutdown_timeout_seconds
                    )
                )

        names = (
            self._all_node_names()
        )

        deadline = (
            time.monotonic()
            + self.config
            .shutdown_timeout_seconds
        )

        while (
            time.monotonic()
            < deadline
        ):
            if not (
                names
                & set(
                    self._nodes()
                )
            ):
                return

            time.sleep(
                self.config
                .poll_interval_seconds
            )

        remaining = (
            names
            & set(
                self._nodes()
            )
        )

        if remaining:
            raise PipeWireAecError(
                "Friday AEC nodes "
                "remained after shutdown: "
                + ", ".join(
                    sorted(
                        remaining
                    )
                )
            )

    def _validate_runtime(
        self,
    ) -> None:
        for label, path in (
            (
                "pw-cli",
                self.config
                .pw_cli_path,
            ),
            (
                "pw-dump",
                self.config
                .pw_dump_path,
            ),
        ):
            if not path.is_file():
                raise PipeWireAecError(
                    f"{label} does not exist: "
                    f"{path}"
                )

            if not os.access(
                path,
                os.X_OK,
            ):
                raise PipeWireAecError(
                    f"{label} is not executable: "
                    f"{path}"
                )

    def _all_node_names(
        self,
    ) -> set[str]:
        config = self.config

        return {
            config.capture_node_name,
            config.source_node_name,
            config.sink_node_name,
            config.playback_node_name,
        }

    def _nodes(
        self,
    ) -> dict[
        str,
        dict[str, object],
    ]:
        # UP022-safe: use capture_output
        # rather than separate PIPE args.
        result = subprocess.run(
            [
                str(
                    self.config
                    .pw_dump_path
                )
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise PipeWireAecError(
                "pw-dump failed: "
                + result.stderr.strip()
            )

        try:
            data = json.loads(
                result.stdout
            )

        except (
            json.JSONDecodeError
        ) as exc:
            raise PipeWireAecError(
                "pw-dump returned invalid JSON"
            ) from exc

        nodes: dict[
            str,
            dict[str, object],
        ] = {}

        for item in data:
            if (
                item.get("type")
                != "PipeWire:Interface:Node"
            ):
                continue

            props = (
                item.get(
                    "info",
                    {},
                ).get(
                    "props",
                    {},
                )
            )

            name = props.get(
                "node.name"
            )

            if not isinstance(
                name,
                str,
            ):
                continue

            nodes[name] = {
                "id": item.get(
                    "id"
                ),
                "serial": props.get(
                    "object.serial"
                ),
                "media_class": props.get(
                    "media.class"
                ),
            }

        return nodes

    def __enter__(
        self,
    ) -> PipeWireAecSession:
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


__all__ = [
    "DEFAULT_PW_CLI_PATH",
    "DEFAULT_PW_DUMP_PATH",
    "DEFAULT_PW_RECORD_PATH",
    "PipeWireAecConfig",
    "PipeWireAecEndpoints",
    "PipeWireAecError",
    "PipeWireAecSession",
    "PipeWirePcmCapture",
    "PipeWirePcmCaptureConfig",
    "PipeWirePcmStream",
]
