"""Typed configuration loaded from explicit values or environment variables."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from .errors import ConfigurationError

DEFAULT_MODEL_PATH = Path(
    "/AI/models/qwen3.6-q4/Qwen3.6-35B-A3B-UD-Q4_K_M.gguf"
)
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def _integer(env: Mapping[str, str], name: str, default: int, *, minimum: int = 1) -> int:
    raw = env.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer, got {raw!r}") from exc
    if value < minimum:
        raise ConfigurationError(f"{name} must be at least {minimum}, got {value}")
    return value


def _boolean(env: Mapping[str, str], name: str, default: bool) -> bool:
    raw = env.get(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{name} must be a boolean, got {raw!r}")


def _choice(
    env: Mapping[str, str], name: str, default: str, choices: set[str]
) -> str:
    value = env.get(name, default).strip().lower()
    if value not in choices:
        expected = ", ".join(sorted(choices))
        raise ConfigurationError(f"{name} must be one of {expected}, got {value!r}")
    return value


@dataclass(frozen=True, slots=True)
class LlamaConfig:
    base_url: str = "http://127.0.0.1:8080/v1"
    model: str = str(DEFAULT_MODEL_PATH)
    context_size: int = 262_144
    api_key: str = "local"
    timeout_seconds: int = 120


@dataclass(frozen=True, slots=True)
class PathConfig:
    var_dir: Path = PROJECT_ROOT / "var"
    document_dir: Path = PROJECT_ROOT / "var/documents"
    rag_data_dir: Path = PROJECT_ROOT / "var/rag"
    code_repo_dir: Path = PROJECT_ROOT / "var/repos"
    code_index_dir: Path = PROJECT_ROOT / "var/code-index"
    patch_dir: Path = PROJECT_ROOT / "var/patches"


@dataclass(frozen=True, slots=True)
class EmbeddingConfig:
    model: str = DEFAULT_EMBEDDING_MODEL
    device: str = "cpu"
    batch_size: int = 32


@dataclass(frozen=True, slots=True)
class DocumentRetrievalConfig:
    chunk_size: int = 450
    chunk_overlap: int = 75
    vector_top_k: int = 10
    bm25_top_k: int = 10
    final_top_k: int = 5
    rrf_k: int = 60


@dataclass(frozen=True, slots=True)
class CodeRetrievalConfig:
    chunk_lines: int = 120
    overlap_lines: int = 20
    vector_top_k: int = 12
    bm25_top_k: int = 12
    final_top_k: int = 6
    rrf_k: int = 60


@dataclass(frozen=True, slots=True)
class OCRConfig:
    enabled: bool = True
    language: str = "eng"
    minimum_text_length: int = 80
    dpi: int = 200


@dataclass(frozen=True, slots=True)
class UIConfig:
    host: str = "127.0.0.1"
    port: int = 8501
    headless: bool = True
    gather_usage_stats: bool = False


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    log_level: str = "INFO"
    log_format: str = "json"
    command_timeout_seconds: int = 900
    test_mode: bool = False


@dataclass(frozen=True, slots=True)
class ExecutionConfig:
    inspection_timeout_seconds: int = 15
    lint_timeout_seconds: int = 180
    test_timeout_seconds: int = 900
    build_timeout_seconds: int = 900
    tool_step_timeout_seconds: int = 120
    max_steps: int = 12
    max_mutations: int = 4
    max_repairs: int = 1
    max_replans: int = 1
    context_characters: int = 32_000


@dataclass(frozen=True, slots=True)
class AppConfig:
    llama: LlamaConfig = field(default_factory=LlamaConfig)
    paths: PathConfig = field(default_factory=PathConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    document_retrieval: DocumentRetrievalConfig = field(
        default_factory=DocumentRetrievalConfig
    )
    code_retrieval: CodeRetrievalConfig = field(default_factory=CodeRetrievalConfig)
    ocr: OCRConfig = field(default_factory=OCRConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> AppConfig:
        values = os.environ if env is None else env
        var_dir = _path(values.get("LOCAL_AI_VAR_DIR", str(PROJECT_ROOT / "var")))
        paths = PathConfig(
            var_dir=var_dir,
            document_dir=_path(values.get("LOCAL_AI_DOCUMENT_DIR", str(var_dir / "documents"))),
            rag_data_dir=_path(values.get("LOCAL_AI_RAG_DATA_DIR", str(var_dir / "rag"))),
            code_repo_dir=_path(values.get("LOCAL_AI_CODE_REPO_DIR", str(var_dir / "repos"))),
            code_index_dir=_path(
                values.get("LOCAL_AI_CODE_INDEX_DIR", str(var_dir / "code-index"))
            ),
            patch_dir=_path(values.get("LOCAL_AI_PATCH_DIR", str(var_dir / "patches"))),
        )
        document = DocumentRetrievalConfig(
            chunk_size=_integer(values, "LOCAL_AI_RAG_CHUNK_SIZE", 450),
            chunk_overlap=_integer(values, "LOCAL_AI_RAG_CHUNK_OVERLAP", 75, minimum=0),
            vector_top_k=_integer(values, "LOCAL_AI_RAG_VECTOR_TOP_K", 10),
            bm25_top_k=_integer(values, "LOCAL_AI_RAG_BM25_TOP_K", 10),
            final_top_k=_integer(values, "LOCAL_AI_RAG_FINAL_TOP_K", 5),
            rrf_k=_integer(values, "LOCAL_AI_RRF_K", 60),
        )
        code = CodeRetrievalConfig(
            chunk_lines=_integer(values, "LOCAL_AI_CODE_CHUNK_LINES", 120),
            overlap_lines=_integer(values, "LOCAL_AI_CODE_CHUNK_OVERLAP", 20, minimum=0),
            vector_top_k=_integer(values, "LOCAL_AI_CODE_VECTOR_TOP_K", 12),
            bm25_top_k=_integer(values, "LOCAL_AI_CODE_BM25_TOP_K", 12),
            final_top_k=_integer(values, "LOCAL_AI_CODE_FINAL_TOP_K", 6),
            rrf_k=_integer(values, "LOCAL_AI_RRF_K", 60),
        )
        if document.chunk_overlap >= document.chunk_size:
            raise ConfigurationError("LOCAL_AI_RAG_CHUNK_OVERLAP must be smaller than chunk size")
        if code.overlap_lines >= code.chunk_lines:
            raise ConfigurationError("LOCAL_AI_CODE_CHUNK_OVERLAP must be smaller than chunk lines")
        return cls(
            llama=LlamaConfig(
                base_url=values.get("LOCAL_AI_BASE_URL", "http://127.0.0.1:8080/v1"),
                model=values.get("LOCAL_AI_MODEL", str(DEFAULT_MODEL_PATH)),
                context_size=_integer(values, "LOCAL_AI_CONTEXT_SIZE", 262_144),
                api_key=values.get("LOCAL_AI_API_KEY", "local"),
                timeout_seconds=_integer(values, "LOCAL_AI_LLM_TIMEOUT", 120),
            ),
            paths=paths,
            embedding=EmbeddingConfig(
                model=values.get("LOCAL_AI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
                device=values.get("LOCAL_AI_EMBEDDING_DEVICE", "cpu"),
                batch_size=_integer(values, "LOCAL_AI_EMBEDDING_BATCH_SIZE", 32),
            ),
            document_retrieval=document,
            code_retrieval=code,
            ocr=OCRConfig(
                enabled=_boolean(values, "LOCAL_AI_OCR_ENABLED", True),
                language=values.get("LOCAL_AI_OCR_LANGUAGE", "eng"),
                minimum_text_length=_integer(values, "LOCAL_AI_OCR_MIN_TEXT_LENGTH", 80),
                dpi=_integer(values, "LOCAL_AI_OCR_DPI", 200),
            ),
            ui=UIConfig(
                host=values.get("LOCAL_AI_UI_HOST", "127.0.0.1"),
                port=_integer(values, "LOCAL_AI_UI_PORT", 8501),
                headless=_boolean(values, "LOCAL_AI_UI_HEADLESS", True),
                gather_usage_stats=_boolean(values, "LOCAL_AI_UI_GATHER_USAGE_STATS", False),
            ),
            runtime=RuntimeConfig(
                log_level=values.get("LOCAL_AI_LOG_LEVEL", "INFO").upper(),
                log_format=_choice(
                    values, "LOCAL_AI_LOG_FORMAT", "json", {"json", "text"}
                ),
                command_timeout_seconds=_integer(values, "LOCAL_AI_COMMAND_TIMEOUT", 900),
                test_mode=_boolean(values, "LOCAL_AI_TEST_MODE", False),
            ),
            execution=ExecutionConfig(
                inspection_timeout_seconds=_integer(values, "LOCAL_AI_INSPECTION_TIMEOUT", 15),
                lint_timeout_seconds=_integer(values, "LOCAL_AI_LINT_TIMEOUT", 180),
                test_timeout_seconds=_integer(values, "LOCAL_AI_TEST_TIMEOUT", 900),
                build_timeout_seconds=_integer(values, "LOCAL_AI_BUILD_TIMEOUT", 900),
                tool_step_timeout_seconds=_integer(values, "LOCAL_AI_TOOL_STEP_TIMEOUT", 120),
                max_steps=_integer(values, "LOCAL_AI_EXECUTION_MAX_STEPS", 12),
                max_mutations=_integer(values, "LOCAL_AI_EXECUTION_MAX_MUTATIONS", 4),
                max_repairs=_integer(values, "LOCAL_AI_EXECUTION_MAX_REPAIRS", 1, minimum=0),
                max_replans=_integer(values, "LOCAL_AI_EXECUTION_MAX_REPLANS", 1, minimum=0),
                context_characters=_integer(values, "LOCAL_AI_EXECUTION_CONTEXT_CHARACTERS", 32_000),
            ),
        )


def get_config() -> AppConfig:
    """Load a fresh configuration snapshot from the current environment."""
    return AppConfig.from_env()
