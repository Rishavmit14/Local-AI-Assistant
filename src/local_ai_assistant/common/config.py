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


def _integer(
    env: Mapping[str, str], name: str, default: int, *, minimum: int = 1,
    maximum: int | None = None,
) -> int:
    raw = env.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer, got {raw!r}") from exc
    if value < minimum:
        raise ConfigurationError(f"{name} must be at least {minimum}, got {value}")
    if maximum is not None and value > maximum:
        raise ConfigurationError(f"{name} must be at most {maximum}, got {value}")
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
    task_history_db: Path = PROJECT_ROOT / "var/history/tasks.sqlite3"
    worktree_dir: Path = PROJECT_ROOT / "var/worktrees"
    isolation_dir: Path = PROJECT_ROOT / "var/isolation"
    onboarding_registry: Path = PROJECT_ROOT / "var/onboarding/repositories.json"


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
class IsolationConfig:
    backend: str = "auto"
    network_policy: str = "deny"
    max_processes: int = 64
    max_output_bytes: int = 20_000
    cpu_seconds: int = 600
    wall_seconds: int = 900
    memory_bytes: int = 4 * 1024**3
    max_open_files: int = 256
    max_file_bytes: int = 512 * 1024**2
    cache_policy: str = "task_local"
    cleanup_policy: str = "on_failure"
    recovery_policy: str = "manual"
    require_strong_isolation: bool = True


@dataclass(frozen=True, slots=True)
class GatewayConfig:
    """Local, authenticated integration-gateway policy."""
    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 8765
    token_hash: str = ""
    max_body_bytes: int = 1_048_576
    max_task_text: int = 20_000
    max_page_size: int = 100
    max_events: int = 1000
    request_rate: int = 30
    scopes: tuple[str, ...] = ("read_status", "read_history")
    github_enabled: bool = False
    github_api_host: str = "https://api.github.com"


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
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    isolation: IsolationConfig = field(default_factory=IsolationConfig)
    gateway: GatewayConfig = field(default_factory=GatewayConfig)

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
            task_history_db=_path(
                values.get("LOCAL_AI_TASK_HISTORY_DB", str(var_dir / "history/tasks.sqlite3"))
            ),
            worktree_dir=_path(
                values.get("LOCAL_AI_WORKTREE_ROOT", str(var_dir / "worktrees"))
            ),
            isolation_dir=_path(
                values.get("LOCAL_AI_ISOLATION_ROOT", str(var_dir / "isolation"))
            ),
            onboarding_registry=_path(
                values.get("LOCAL_AI_ONBOARDING_REGISTRY", str(var_dir / "onboarding/repositories.json"))
            ),
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
        gateway_host = values.get("LOCAL_AI_GATEWAY_HOST", "127.0.0.1").strip()
        github_api_host = values.get("LOCAL_AI_GITHUB_API_HOST", "https://api.github.com").strip()
        gateway_scopes = tuple(item.strip().lower() for item in values.get("LOCAL_AI_GATEWAY_SCOPES", "read_status,read_history").split(",") if item.strip())
        allowed_gateway_scopes = {"read_status", "read_history", "create_task", "request_plan", "submit_approval", "request_execution", "request_cancel", "github_read", "github_write"}
        if not gateway_scopes or not set(gateway_scopes) <= allowed_gateway_scopes:
            raise ConfigurationError("LOCAL_AI_GATEWAY_SCOPES contains an invalid or empty scope")
        if not gateway_host or not github_api_host.startswith("https://"):
            raise ConfigurationError("Gateway host and HTTPS GitHub API host must be valid")
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
            isolation=IsolationConfig(
                backend=_choice(
                    values, "LOCAL_AI_SANDBOX_BACKEND", "auto", {"auto", "bubblewrap", "native"}
                ),
                network_policy=_choice(
                    values, "LOCAL_AI_SANDBOX_NETWORK", "deny",
                    {"deny", "loopback_only", "allowed"},
                ),
                max_processes=_integer(values, "LOCAL_AI_SANDBOX_MAX_PROCESSES", 64, maximum=4096),
                max_output_bytes=_integer(values, "LOCAL_AI_SANDBOX_MAX_OUTPUT", 20_000, maximum=100 * 1024**2),
                cpu_seconds=_integer(values, "LOCAL_AI_SANDBOX_CPU_SECONDS", 600, maximum=86_400),
                wall_seconds=_integer(values, "LOCAL_AI_SANDBOX_WALL_SECONDS", 900, maximum=86_400),
                memory_bytes=_integer(values, "LOCAL_AI_SANDBOX_MEMORY_BYTES", 4 * 1024**3, maximum=1024**4),
                max_open_files=_integer(values, "LOCAL_AI_SANDBOX_MAX_OPEN_FILES", 256, maximum=1_048_576),
                max_file_bytes=_integer(
                    values, "LOCAL_AI_SANDBOX_MAX_FILE_BYTES", 512 * 1024**2,
                    maximum=1024**4,
                ),
                cache_policy=_choice(
                    values, "LOCAL_AI_SANDBOX_CACHE_POLICY", "task_local",
                    {"task_local", "read_only_shared", "disabled"},
                ),
                cleanup_policy=_choice(
                    values, "LOCAL_AI_WORKTREE_CLEANUP_POLICY", "on_failure",
                    {"manual", "on_failure", "always"},
                ),
                recovery_policy=_choice(
                    values, "LOCAL_AI_WORKTREE_RECOVERY_POLICY", "manual",
                    {"manual", "cleanup_only"},
                ),
                require_strong_isolation=_boolean(
                    values, "LOCAL_AI_REQUIRE_STRONG_ISOLATION", True
                ),
            ),
            gateway=GatewayConfig(
                enabled=_boolean(values, "LOCAL_AI_GATEWAY_ENABLED", False),
                host=gateway_host,
                port=_integer(values, "LOCAL_AI_GATEWAY_PORT", 8765, maximum=65535),
                token_hash=values.get("LOCAL_AI_GATEWAY_TOKEN_HASH", ""),
                max_body_bytes=_integer(values, "LOCAL_AI_GATEWAY_MAX_BODY", 1_048_576, maximum=10 * 1024 * 1024),
                max_task_text=_integer(values, "LOCAL_AI_GATEWAY_MAX_TASK_TEXT", 20_000, maximum=200_000),
                max_page_size=_integer(values, "LOCAL_AI_GATEWAY_MAX_PAGE", 100, maximum=1000),
                max_events=_integer(values, "LOCAL_AI_GATEWAY_MAX_EVENTS", 1000, maximum=10_000),
                request_rate=_integer(values, "LOCAL_AI_GATEWAY_REQUEST_RATE", 30, maximum=10_000),
                scopes=gateway_scopes,
                github_enabled=_boolean(values, "LOCAL_AI_GITHUB_ENABLED", False),
                github_api_host=github_api_host,
            ),
        )


def get_config() -> AppConfig:
    """Load a fresh configuration snapshot from the current environment."""
    return AppConfig.from_env()
