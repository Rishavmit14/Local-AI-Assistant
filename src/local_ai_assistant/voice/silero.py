from __future__ import annotations

import hashlib
import importlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .audio import VoiceAudioConfig
from .vad import VadFrame, pcm16_dbfs

DEFAULT_SILERO_MODEL_PATH = Path(
    "/AI/models/friday/vad/silero_vad_16k_op15.onnx"
)

DEFAULT_SILERO_MODEL_SHA256 = (
    "7ed98ddbad84ccac4cd0aeb3099049280713df825c610a8ed34543318f1b2c49"
)


class SileroVadError(RuntimeError):
    """Raised when Friday cannot initialize or run Silero VAD."""


@dataclass(frozen=True, slots=True)
class SileroVadConfig:
    """Configuration for Friday's local Silero ONNX VAD."""

    model_path: Path = DEFAULT_SILERO_MODEL_PATH
    expected_sha256: str = DEFAULT_SILERO_MODEL_SHA256
    threshold: float = 0.50
    frame_samples: int = 512
    context_samples: int = 64
    recurrent_state_size: int = 128
    intra_op_threads: int = 1
    inter_op_threads: int = 1

    def __post_init__(self) -> None:
        if not 0.0 < self.threshold < 1.0:
            raise ValueError(
                "Silero threshold must be in the range (0, 1)"
            )

        if self.frame_samples != 512:
            raise ValueError(
                "Qualified Silero model requires 512-sample frames"
            )

        if self.context_samples != 64:
            raise ValueError(
                "Qualified Silero model requires 64 context samples"
            )

        if self.recurrent_state_size != 128:
            raise ValueError(
                "Qualified Silero model requires state size 128"
            )

        if self.intra_op_threads <= 0:
            raise ValueError(
                "intra_op_threads must be positive"
            )

        if self.inter_op_threads <= 0:
            raise ValueError(
                "inter_op_threads must be positive"
            )

        digest = self.expected_sha256.lower()

        if (
            len(digest) != 64
            or any(
                character not in "0123456789abcdef"
                for character in digest
            )
        ):
            raise ValueError(
                "expected_sha256 must be a valid SHA256 digest"
            )

    @classmethod
    def from_env(cls) -> SileroVadConfig:
        return cls(
            model_path=Path(
                os.getenv(
                    "FRIDAY_SILERO_MODEL_PATH",
                    str(DEFAULT_SILERO_MODEL_PATH),
                )
            ),
            expected_sha256=os.getenv(
                "FRIDAY_SILERO_MODEL_SHA256",
                DEFAULT_SILERO_MODEL_SHA256,
            ),
            threshold=_env_float(
                "FRIDAY_SILERO_THRESHOLD",
                0.50,
            ),
            intra_op_threads=_env_int(
                "FRIDAY_SILERO_INTRA_OP_THREADS",
                1,
            ),
            inter_op_threads=_env_int(
                "FRIDAY_SILERO_INTER_OP_THREADS",
                1,
            ),
        )


class SileroVad:
    """
    Stateful Silero ONNX VAD.

    Friday's microphone abstraction emits 480 samples every 30 ms.
    Silero consumes 512-sample frames, so this adapter bridges
    the two frame sizes with a small PCM FIFO.
    """

    def __init__(
        self,
        audio_config: VoiceAudioConfig | None = None,
        config: SileroVadConfig | None = None,
        *,
        session: Any | None = None,
        numpy_module: Any | None = None,
    ) -> None:
        self.audio_config = (
            audio_config
            if audio_config is not None
            else VoiceAudioConfig.from_env()
        )

        self.config = (
            config
            if config is not None
            else SileroVadConfig.from_env()
        )

        self._validate_audio_config()

        try:
            self._np = (
                numpy_module
                if numpy_module is not None
                else importlib.import_module("numpy")
            )
        except ModuleNotFoundError as exc:
            raise SileroVadError(
                "Silero VAD requires Friday's voice dependencies. "
                'Install with pip install -e ".[voice]".'
            ) from exc

        if session is None:
            verify_model_sha256(
                self.config.model_path,
                self.config.expected_sha256,
            )

            self._session = (
                self._create_session()
            )
        else:
            self._session = session

        self._frame_bytes = (
            self.config.frame_samples
            * self.audio_config.sample_width_bytes
        )

        self._pending = bytearray()
        self._last_probability = 0.0

        self._state: Any
        self._context: Any

        self.reset()

    @property
    def last_probability(self) -> float:
        return self._last_probability

    @property
    def pending_bytes(self) -> int:
        return len(self._pending)

    def reset(self) -> None:
        self._pending.clear()
        self._last_probability = 0.0

        self._state = self._np.zeros(
            (
                2,
                1,
                self.config.recurrent_state_size,
            ),
            dtype=self._np.float32,
        )

        self._context = self._np.zeros(
            (
                1,
                self.config.context_samples,
            ),
            dtype=self._np.float32,
        )

    def analyze(
        self,
        pcm: bytes,
    ) -> VadFrame:

        if (
            len(pcm)
            % self.audio_config.sample_width_bytes
        ):
            raise ValueError(
                "PCM byte length is not aligned "
                "to the sample width"
            )

        level = pcm16_dbfs(
            pcm
        )

        self._pending.extend(
            pcm
        )

        while (
            len(self._pending)
            >= self._frame_bytes
        ):

            frame = bytes(
                self._pending[
                    : self._frame_bytes
                ]
            )

            del self._pending[
                : self._frame_bytes
            ]

            self._last_probability = (
                self._infer(
                    frame
                )
            )

        return VadFrame(
            dbfs=level,
            noise_floor_dbfs=None,
            threshold_dbfs=None,
            speech=(
                self._last_probability
                >= self.config.threshold
            ),
            speech_probability=(
                self._last_probability
            ),
        )

    def _infer(
        self,
        pcm: bytes,
    ) -> float:

        samples = self._np.frombuffer(
            pcm,
            dtype="<i2",
        ).astype(
            self._np.float32,
        )

        samples /= 32768.0

        samples = samples.reshape(
            1,
            self.config.frame_samples,
        )

        model_input = (
            self._np.concatenate(
                (
                    self._context,
                    samples,
                ),
                axis=1,
            )
        )

        try:
            outputs = self._session.run(
                None,
                {
                    "input": model_input,
                    "state": self._state,
                    "sr": self._np.array(
                        self.audio_config.sample_rate,
                        dtype=self._np.int64,
                    ),
                },
            )

        except Exception as exc:
            raise SileroVadError(
                f"Silero ONNX inference failed: {exc}"
            ) from exc

        if len(outputs) < 2:
            raise SileroVadError(
                "Silero model returned "
                "an unexpected output set"
            )

        probability = float(
            self._np.asarray(
                outputs[0]
            ).reshape(-1)[0]
        )

        self._state = (
            self._np.asarray(
                outputs[1],
                dtype=self._np.float32,
            )
        )

        self._context = (
            model_input[
                :,
                -self.config.context_samples :,
            ].copy()
        )

        return probability

    def _create_session(
        self,
    ) -> Any:

        try:
            ort = importlib.import_module(
                "onnxruntime"
            )

        except ModuleNotFoundError as exc:
            raise SileroVadError(
                "Silero VAD requires ONNX Runtime. "
                'Install with pip install -e ".[voice]".'
            ) from exc

        options = (
            ort.SessionOptions()
        )

        options.intra_op_num_threads = (
            self.config.intra_op_threads
        )

        options.inter_op_num_threads = (
            self.config.inter_op_threads
        )

        try:
            session = (
                ort.InferenceSession(
                    str(
                        self.config.model_path
                    ),
                    sess_options=options,
                    providers=[
                        "CPUExecutionProvider",
                    ],
                )
            )

        except Exception as exc:
            raise SileroVadError(
                f"Unable to load Silero model: {exc}"
            ) from exc

        input_names = {
            item.name
            for item
            in session.get_inputs()
        }

        required_inputs = {
            "input",
            "state",
            "sr",
        }

        if not (
            required_inputs
            <= input_names
        ):
            raise SileroVadError(
                "Silero model has "
                "unexpected inputs: "
                + repr(
                    sorted(
                        input_names
                    )
                )
            )

        if (
            len(
                session.get_outputs()
            )
            < 2
        ):
            raise SileroVadError(
                "Silero model must expose "
                "probability and recurrent state"
            )

        return session

    def _validate_audio_config(
        self,
    ) -> None:

        if (
            self.audio_config.sample_rate
            != 16_000
        ):
            raise ValueError(
                "Silero VAD requires 16000 Hz audio"
            )

        if (
            self.audio_config.channels
            != 1
        ):
            raise ValueError(
                "Silero VAD requires mono audio"
            )

        if (
            self.audio_config.sample_width_bytes
            != 2
        ):
            raise ValueError(
                "Silero VAD requires 16-bit PCM"
            )


def verify_model_sha256(
    path: Path,
    expected_sha256: str,
) -> str:

    path = Path(
        path
    )

    if not path.is_file():
        raise SileroVadError(
            f"Silero model does not exist: {path}"
        )

    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as handle:

        while True:

            chunk = handle.read(
                1024 * 1024
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
        != expected_sha256.lower()
    ):
        raise SileroVadError(
            "Silero model SHA256 mismatch: "
            f"expected {expected_sha256}, "
            f"got {actual}"
        )

    return actual


def _env_int(
    name: str,
    default: int,
) -> int:

    raw = os.getenv(
        name
    )

    if raw is None:
        return default

    try:
        return int(
            raw
        )

    except ValueError as exc:
        raise ValueError(
            f"{name} must be an integer"
        ) from exc


def _env_float(
    name: str,
    default: float,
) -> float:

    raw = os.getenv(
        name
    )

    if raw is None:
        return default

    try:
        return float(
            raw
        )

    except ValueError as exc:
        raise ValueError(
            f"{name} must be a number"
        ) from exc
