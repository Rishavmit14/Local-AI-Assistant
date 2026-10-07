"""Typed configuration loaded from explicit values or environment variables."""

from __future__ import annotations

import ipaddress
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

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

    def __post_init__(self) -> None:
        if not isinstance(self.base_url, str) or not self.base_url.strip():
            raise ConfigurationError("LOCAL_AI_BASE_URL must not be empty")
        try:
            parsed = urlsplit(self.base_url)
            hostname = parsed.hostname
            port = parsed.port
        except ValueError as exc:
            raise ConfigurationError("LOCAL_AI_BASE_URL must be a valid local URL") from exc
        local_host = False
        if hostname:
            normalized_host = hostname.rstrip(".").lower()
            if normalized_host == "localhost":
                local_host = True
            else:
                try:
                    local_host = ipaddress.ip_address(normalized_host).is_loopback
                except ValueError:
                    local_host = False
        if (
            parsed.scheme not in {"http", "https"}
            or not hostname
            or not local_host
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or port == 0
        ):
            raise ConfigurationError(
                "LOCAL_AI_BASE_URL must use HTTP(S) on a loopback host without "
                "URL credentials, query, or fragment"
            )
        if (
            not isinstance(self.model, str)
            or not self.model.strip()
            or self.model != self.model.strip()
            or len(self.model) > 512
            or any(ord(character) < 32 for character in self.model)
        ):
            raise ConfigurationError("LOCAL_AI_MODEL must be a bounded non-empty identifier")
        if type(self.context_size) is not int or self.context_size < 1:
            raise ConfigurationError("LOCAL_AI_CONTEXT_SIZE must be a positive integer")
        if type(self.timeout_seconds) is not int or self.timeout_seconds < 1:
            raise ConfigurationError("LOCAL_AI_LLM_TIMEOUT must be a positive integer")
        if not isinstance(self.api_key, str) or not self.api_key:
            raise ConfigurationError("LOCAL_AI_API_KEY must not be empty")


@dataclass(frozen=True, slots=True)
class VisionCortexConfig:
    """Optional local-only OpenAI-compatible visual model boundary."""

    base_url: str = ""
    model: str = "friday-vision-qwen2.5-vl-3b"
    api_key: str = field(default="", repr=False)
    timeout_seconds: int = 150
    max_image_edge: int = 1024
    max_output_characters: int = 2000

    def __post_init__(self) -> None:
        if not isinstance(self.base_url, str):
            raise ConfigurationError("LOCAL_AI_VISION_BASE_URL must be a local URL")
        if self.base_url:
            try:
                parsed = urlsplit(self.base_url)
                hostname = parsed.hostname
                port = parsed.port
            except ValueError as exc:
                raise ConfigurationError("LOCAL_AI_VISION_BASE_URL must be a valid local URL") from exc
            local_host = False
            if hostname:
                normalized_host = hostname.rstrip(".").lower()
                if normalized_host == "localhost":
                    local_host = True
                else:
                    try:
                        local_host = ipaddress.ip_address(normalized_host).is_loopback
                    except ValueError:
                        local_host = False
            if (
                parsed.scheme != "http"
                or not hostname
                or not local_host
                or parsed.username is not None
                or parsed.password is not None
                or parsed.query
                or parsed.fragment
                or port == 0
                or parsed.path.rstrip("/") != "/v1"
            ):
                raise ConfigurationError(
                    "LOCAL_AI_VISION_BASE_URL must use HTTP on loopback at a /v1 path "
                    "without URL credentials, query, or fragment"
                )
            if (
                not isinstance(self.api_key, str)
                or len(self.api_key) > 256
                or any(ord(character) < 33 or ord(character) > 126 for character in self.api_key)
                or (len(self.api_key) < 32)
            ):
                raise ConfigurationError("LOCAL_AI_VISION_API_KEY must be a private printable token")
        elif not isinstance(self.api_key, str) or len(self.api_key) > 256:
            raise ConfigurationError("LOCAL_AI_VISION_API_KEY is invalid")
        if (
            not isinstance(self.model, str)
            or not self.model.strip()
            or self.model != self.model.strip()
            or len(self.model) > 256
            or any(ord(character) < 32 for character in self.model)
        ):
            raise ConfigurationError("LOCAL_AI_VISION_MODEL must be a bounded non-empty identifier")
        if type(self.timeout_seconds) is not int or not 1 <= self.timeout_seconds <= 180:
            raise ConfigurationError("LOCAL_AI_VISION_TIMEOUT must be between 1 and 180 seconds")
        if type(self.max_image_edge) is not int or not 320 <= self.max_image_edge <= 2048:
            raise ConfigurationError("LOCAL_AI_VISION_MAX_IMAGE_EDGE must be between 320 and 2048")
        if type(self.max_output_characters) is not int or not 256 <= self.max_output_characters <= 4000:
            raise ConfigurationError("LOCAL_AI_VISION_MAX_OUTPUT must be between 256 and 4000")

    @property
    def enabled(self) -> bool:
        return bool(self.base_url)


@dataclass(frozen=True, slots=True)
class PathConfig:
    var_dir: Path = PROJECT_ROOT / "var"
    document_dir: Path = PROJECT_ROOT / "var/documents"
    rag_data_dir: Path = PROJECT_ROOT / "var/rag"
    code_repo_dir: Path = PROJECT_ROOT / "var/repos"
    code_index_dir: Path = PROJECT_ROOT / "var/code-index"
    patch_dir: Path = PROJECT_ROOT / "var/patches"
    task_history_db: Path = PROJECT_ROOT / "var/history/tasks.sqlite3"
    memory_db: Path = PROJECT_ROOT / "var/memory/friday.sqlite3"
    worktree_dir: Path = PROJECT_ROOT / "var/worktrees"
    isolation_dir: Path = PROJECT_ROOT / "var/isolation"
    onboarding_registry: Path = PROJECT_ROOT / "var/onboarding/repositories.json"
    career_forge_db: Path = PROJECT_ROOT / "var/career-forge/learner.sqlite3"
    career_forge_lab_dir: Path = PROJECT_ROOT / "var/career-forge/lab"
    learning_paths_db: Path = PROJECT_ROOT / "var/learning-paths/paths.sqlite3"
    projects_db: Path = PROJECT_ROOT / "var/projects/projects.sqlite3"
    perception_dir: Path = PROJECT_ROOT / "var/perception"
    vision_cache_dir: Path = Path("/AI/cache/huggingface")
    desktop_control_db: Path = PROJECT_ROOT / "var/desktop-control/actions.sqlite3"
    autonomy_db: Path = PROJECT_ROOT / "var/autonomy/objectives.sqlite3"
    proactive_db: Path = PROJECT_ROOT / "var/proactive/events.sqlite3"
    research_db: Path = PROJECT_ROOT / "var/research/knowledge.sqlite3"


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
class WakeConfig:
    """Friday wake-phrase feature policy."""

    enabled: bool = False
    phrase: str = "hey friday"
    session_idle_seconds: int = 60


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
    github_credential_ref: str = ""
    github_allowed_repository: str = ""
    github_publication_purpose: str = ""


@dataclass(frozen=True, slots=True)
class DesktopControlConfig:
    allowed_apps: tuple[str, ...] = ()
    allowed_origins: tuple[str, ...] = ()
    allowed_file_roots: tuple[Path, ...] = ()
    allowed_accessibility_targets: tuple[str, ...] = ()
    approval_seconds: int = 60


@dataclass(frozen=True, slots=True)
class ProactiveConfig:
    enabled: bool = True
    poll_seconds: int = 30
    max_notifications_per_hour: int = 20


@dataclass(frozen=True, slots=True)
class AppConfig:
    llama: LlamaConfig = field(default_factory=LlamaConfig)
    vision_cortex: VisionCortexConfig = field(default_factory=VisionCortexConfig)
    paths: PathConfig = field(default_factory=PathConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    document_retrieval: DocumentRetrievalConfig = field(
        default_factory=DocumentRetrievalConfig
    )
    code_retrieval: CodeRetrievalConfig = field(default_factory=CodeRetrievalConfig)
    ocr: OCRConfig = field(default_factory=OCRConfig)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    wake: WakeConfig = field(default_factory=WakeConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    isolation: IsolationConfig = field(default_factory=IsolationConfig)
    gateway: GatewayConfig = field(default_factory=GatewayConfig)
    desktop_control: DesktopControlConfig = field(default_factory=DesktopControlConfig)
    proactive: ProactiveConfig = field(default_factory=ProactiveConfig)

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
            memory_db=_path(values.get("LOCAL_AI_MEMORY_DB", str(var_dir / "memory/friday.sqlite3"))),
            worktree_dir=_path(
                values.get("LOCAL_AI_WORKTREE_ROOT", str(var_dir / "worktrees"))
            ),
            isolation_dir=_path(
                values.get("LOCAL_AI_ISOLATION_ROOT", str(var_dir / "isolation"))
            ),
            onboarding_registry=_path(
                values.get("LOCAL_AI_ONBOARDING_REGISTRY", str(var_dir / "onboarding/repositories.json"))
            ),
            career_forge_db=_path(
                values.get("LOCAL_AI_CAREER_FORGE_DB", str(var_dir / "career-forge/learner.sqlite3"))
            ),
            career_forge_lab_dir=_path(
                values.get("LOCAL_AI_CAREER_FORGE_LAB_DIR", str(var_dir / "career-forge/lab"))
            ),
            learning_paths_db=_path(
                values.get("LOCAL_AI_LEARNING_PATHS_DB", str(var_dir / "learning-paths/paths.sqlite3"))
            ),
            projects_db=_path(values.get("LOCAL_AI_PROJECTS_DB", str(var_dir / "projects/projects.sqlite3"))),
            perception_dir=_path(values.get("LOCAL_AI_PERCEPTION_DIR", str(var_dir / "perception"))),
            vision_cache_dir=_path(values.get("LOCAL_AI_VISION_CACHE_DIR", "/AI/cache/huggingface")),
            desktop_control_db=_path(values.get("LOCAL_AI_DESKTOP_CONTROL_DB", str(var_dir / "desktop-control/actions.sqlite3"))),
            autonomy_db=_path(values.get("LOCAL_AI_AUTONOMY_DB", str(var_dir / "autonomy/objectives.sqlite3"))),
            proactive_db=_path(values.get("LOCAL_AI_PROACTIVE_DB", str(var_dir / "proactive/events.sqlite3"))),
            research_db=_path(values.get("LOCAL_AI_RESEARCH_DB", str(var_dir / "research/knowledge.sqlite3"))),
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
        desktop_control = DesktopControlConfig(
            allowed_apps=tuple(item.strip() for item in values.get("LOCAL_AI_DESKTOP_ALLOWED_APPS", "").split(",") if item.strip()),
            allowed_origins=tuple(item.strip().rstrip("/") for item in values.get("LOCAL_AI_DESKTOP_ALLOWED_ORIGINS", "").split(",") if item.strip()),
            allowed_file_roots=tuple(_path(item.strip()) for item in values.get("LOCAL_AI_DESKTOP_ALLOWED_FILE_ROOTS", "").split(",") if item.strip()),
            allowed_accessibility_targets=tuple(item.strip() for item in values.get("LOCAL_AI_DESKTOP_ALLOWED_ACCESSIBILITY_TARGETS", "").split("|") if item.strip()),
            approval_seconds=_integer(values, "LOCAL_AI_DESKTOP_APPROVAL_SECONDS", 60, maximum=600),
        )
        if document.chunk_overlap >= document.chunk_size:
            raise ConfigurationError("LOCAL_AI_RAG_CHUNK_OVERLAP must be smaller than chunk size")
        if code.overlap_lines >= code.chunk_lines:
            raise ConfigurationError("LOCAL_AI_CODE_CHUNK_OVERLAP must be smaller than chunk lines")
        gateway_host = values.get("LOCAL_AI_GATEWAY_HOST", "127.0.0.1").strip()
        github_api_host = values.get("LOCAL_AI_GITHUB_API_HOST", "https://api.github.com").strip()
        gateway_scopes = tuple(item.strip().lower() for item in values.get("LOCAL_AI_GATEWAY_SCOPES", "read_status,read_history").split(",") if item.strip())
        allowed_gateway_scopes = {"read_status", "read_history", "create_task", "request_plan", "submit_approval", "request_execution", "request_rollback", "request_cancel", "github_read", "github_write"}
        if not gateway_scopes or not set(gateway_scopes) <= allowed_gateway_scopes:
            raise ConfigurationError("LOCAL_AI_GATEWAY_SCOPES contains an invalid or empty scope")
        github_credential_ref = values.get("LOCAL_AI_GITHUB_CREDENTIAL_REF", "").strip()
        github_allowed_repository = values.get("LOCAL_AI_GITHUB_ALLOWED_REPOSITORY", "").strip()
        github_publication_purpose = values.get("LOCAL_AI_GITHUB_PUBLICATION_PURPOSE", "").strip()
        github_enabled = _boolean(values, "LOCAL_AI_GITHUB_ENABLED", False)
        if github_credential_ref and not re.fullmatch(
            r"gh-keyring:github\.com:[A-Za-z0-9-]{1,39}", github_credential_ref,
        ):
            raise ConfigurationError("LOCAL_AI_GITHUB_CREDENTIAL_REF must identify a GitHub CLI keyring account")
        if github_allowed_repository and not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}", github_allowed_repository,
        ):
            raise ConfigurationError("LOCAL_AI_GITHUB_ALLOWED_REPOSITORY must be OWNER/REPOSITORY")
        if github_credential_ref and (
            not github_enabled or "github_write" not in gateway_scopes or not github_allowed_repository
            or github_publication_purpose != "learner_project_public_proof"
        ):
            raise ConfigurationError(
                "keyring GitHub publication requires enabled GitHub, github_write scope, one exact repository, and the learner-public-proof purpose"
            )
        if github_publication_purpose and github_publication_purpose != "learner_project_public_proof":
            raise ConfigurationError("unsupported GitHub publication purpose")
        wake_phrase = values.get(
            "LOCAL_AI_WAKE_PHRASE",
            "hey friday",
        ).strip().lower()

        if not wake_phrase:
            raise ConfigurationError(
                "LOCAL_AI_WAKE_PHRASE "
                "must not be empty"
            )

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
            vision_cortex=VisionCortexConfig(
                base_url=values.get("LOCAL_AI_VISION_BASE_URL", "").strip(),
                model=values.get("LOCAL_AI_VISION_MODEL", "friday-vision-qwen2.5-vl-3b"),
                api_key=values.get("LOCAL_AI_VISION_API_KEY", ""),
                timeout_seconds=_integer(values, "LOCAL_AI_VISION_TIMEOUT", 150, maximum=180),
                max_image_edge=_integer(values, "LOCAL_AI_VISION_MAX_IMAGE_EDGE", 1024, maximum=2048),
                max_output_characters=_integer(values, "LOCAL_AI_VISION_MAX_OUTPUT", 2000, maximum=4000),
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
            wake=WakeConfig(
                enabled=_boolean(
                    values,
                    "LOCAL_AI_WAKE_ENABLED",
                    False,
                ),
                phrase=wake_phrase,
                session_idle_seconds=_integer(
                    values, "LOCAL_AI_SESSION_IDLE_SECONDS", 60, minimum=15, maximum=300
                ),
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
                github_enabled=github_enabled,
                github_api_host=github_api_host,
                github_credential_ref=github_credential_ref,
                github_allowed_repository=github_allowed_repository,
                github_publication_purpose=github_publication_purpose,
            ),
            desktop_control=desktop_control,
            proactive=ProactiveConfig(
                enabled=_boolean(values, "LOCAL_AI_PROACTIVE_ENABLED", True),
                poll_seconds=_integer(values, "LOCAL_AI_PROACTIVE_POLL_SECONDS", 30, maximum=3600),
                max_notifications_per_hour=_integer(values, "LOCAL_AI_PROACTIVE_MAX_NOTIFICATIONS_PER_HOUR", 20, maximum=10_000),
            ),
        )


def get_config() -> AppConfig:
    """Load a fresh configuration snapshot from the current environment."""
    return AppConfig.from_env()
