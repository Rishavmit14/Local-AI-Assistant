from pathlib import Path

import pytest

from local_ai_assistant.common.config import AppConfig
from local_ai_assistant.common.errors import ConfigurationError


def test_default_configuration_preserves_local_ports_and_model():
    config = AppConfig.from_env({})

    assert config.llama.base_url == "http://127.0.0.1:8080/v1"
    assert config.llama.context_size == 262_144
    assert config.llama.model.endswith("Qwen3.6-35B-A3B-UD-Q4_K_M.gguf")
    assert config.vision_cortex.enabled is False
    assert config.vision_cortex.model == "friday-vision-qwen2.5-vl-3b"
    assert config.document_retrieval.vector_top_k == 10
    assert config.code_retrieval.vector_top_k == 12
    assert config.ocr.language == "eng"
    assert config.execution.max_steps == 12
    assert config.execution.max_repairs == 1


def test_environment_configuration_resolves_all_runtime_paths(tmp_path):
    config = AppConfig.from_env(
        {
            "LOCAL_AI_VAR_DIR": str(tmp_path),
            "LOCAL_AI_DOCUMENT_DIR": str(tmp_path / "private-docs"),
            "LOCAL_AI_VISION_CACHE_DIR": str(tmp_path / "vision-cache"),
            "LOCAL_AI_DESKTOP_CONTROL_DB": str(tmp_path / "desktop.sqlite3"),
            "LOCAL_AI_DESKTOP_ALLOWED_APPS": "org.gnome.Terminal",
            "LOCAL_AI_DESKTOP_ALLOWED_ORIGINS": "https://docs.python.org",
            "LOCAL_AI_DESKTOP_ALLOWED_FILE_ROOTS": str(tmp_path / "shared"),
            "LOCAL_AI_OCR_ENABLED": "false",
            "LOCAL_AI_RAG_FINAL_TOP_K": "7",
            "LOCAL_AI_CODE_CHUNK_LINES": "80",
            "LOCAL_AI_LOG_FORMAT": "text",
            "LOCAL_AI_TEST_MODE": "true",
            "LOCAL_AI_EXECUTION_MAX_STEPS": "7",
            "LOCAL_AI_SANDBOX_BACKEND": "native",
            "LOCAL_AI_SANDBOX_NETWORK": "allowed",
            "LOCAL_AI_REQUIRE_STRONG_ISOLATION": "false",
            "LOCAL_AI_SANDBOX_MAX_PROCESSES": "12",
        }
    )

    assert config.paths.var_dir == tmp_path.resolve()
    assert config.paths.document_dir == (tmp_path / "private-docs").resolve()
    assert config.paths.code_index_dir == (tmp_path / "code-index").resolve()
    assert config.ocr.enabled is False
    assert config.document_retrieval.final_top_k == 7
    assert config.code_retrieval.chunk_lines == 80
    assert config.runtime.log_format == "text"
    assert config.runtime.test_mode is True
    assert config.execution.max_steps == 7
    assert config.paths.worktree_dir == (tmp_path / "worktrees").resolve()
    assert config.paths.vision_cache_dir == (tmp_path / "vision-cache").resolve()
    assert config.paths.desktop_control_db == (tmp_path / "desktop.sqlite3").resolve()
    assert config.paths.learning_paths_db == (tmp_path / "learning-paths/paths.sqlite3").resolve()
    assert config.desktop_control.allowed_apps == ("org.gnome.Terminal",)
    assert config.desktop_control.allowed_origins == ("https://docs.python.org",)
    assert config.desktop_control.allowed_file_roots == ((tmp_path / "shared").resolve(),)
    assert config.isolation.backend == "native"
    assert config.isolation.network_policy == "allowed"
    assert config.isolation.require_strong_isolation is False
    assert config.isolation.max_processes == 12


@pytest.mark.parametrize(
    ("environment", "message"),
    [
        ({"LOCAL_AI_OCR_ENABLED": "sometimes"}, "LOCAL_AI_OCR_ENABLED"),
        ({"LOCAL_AI_LOG_FORMAT": "xml"}, "LOCAL_AI_LOG_FORMAT"),
        ({"LOCAL_AI_SANDBOX_NETWORK": "maybe"}, "LOCAL_AI_SANDBOX_NETWORK"),
        (
            {"LOCAL_AI_RAG_CHUNK_SIZE": "20", "LOCAL_AI_RAG_CHUNK_OVERLAP": "20"},
            "LOCAL_AI_RAG_CHUNK_OVERLAP",
        ),
    ],
)
def test_invalid_configuration_is_explicit(environment, message):
    with pytest.raises(ConfigurationError, match=message):
        AppConfig.from_env(environment)


@pytest.mark.parametrize(
    ("environment", "message"),
    [
        ({"LOCAL_AI_BASE_URL": ""}, "LOCAL_AI_BASE_URL"),
        ({"LOCAL_AI_BASE_URL": "not-a-url"}, "LOCAL_AI_BASE_URL"),
        ({"LOCAL_AI_BASE_URL": "https://api.openai.com/v1"}, "loopback"),
        ({"LOCAL_AI_BASE_URL": "http://user:secret@127.0.0.1:8080/v1"}, "loopback"),
        ({"LOCAL_AI_MODEL": "  "}, "LOCAL_AI_MODEL"),
        ({"LOCAL_AI_CONTEXT_SIZE": "0"}, "LOCAL_AI_CONTEXT_SIZE"),
        ({"LOCAL_AI_LLM_TIMEOUT": "0"}, "LOCAL_AI_LLM_TIMEOUT"),
    ],
)
def test_model_configuration_fails_closed(environment, message):
    with pytest.raises(ConfigurationError, match=message):
        AppConfig.from_env(environment)


@pytest.mark.parametrize(
    "base_url",
    (
        "http://localhost:8123/v1",
        "http://127.0.0.9:8123/v1",
        "http://[::1]:8123/v1",
        "https://localhost:8123/v1",
    ),
)
def test_loopback_model_endpoints_are_valid(base_url):
    config = AppConfig.from_env({"LOCAL_AI_BASE_URL": base_url})

    assert config.llama.base_url == base_url


def test_model_and_context_are_configuration_driven():
    first = AppConfig.from_env({"LOCAL_AI_MODEL": "fixture-A", "LOCAL_AI_CONTEXT_SIZE": "16"})
    second = AppConfig.from_env({"LOCAL_AI_MODEL": "fixture-B", "LOCAL_AI_CONTEXT_SIZE": "64"})

    assert (first.llama.model, first.llama.context_size) == ("fixture-A", 16)
    assert (second.llama.model, second.llama.context_size) == ("fixture-B", 64)


def test_visual_cortex_configuration_is_local_and_bounded():
    config = AppConfig.from_env({
        "LOCAL_AI_VISION_BASE_URL": "http://127.0.0.1:8781/v1",
        "LOCAL_AI_VISION_MODEL": "friday-vision-qwen2.5-vl-3b",
        "LOCAL_AI_VISION_API_KEY": "unit-test-vision-key-with-at-least-32-chars",
        "LOCAL_AI_VISION_TIMEOUT": "45",
        "LOCAL_AI_VISION_MAX_IMAGE_EDGE": "1280",
    })
    assert config.vision_cortex.enabled is True
    assert config.vision_cortex.base_url == "http://127.0.0.1:8781/v1"
    assert config.vision_cortex.api_key == "unit-test-vision-key-with-at-least-32-chars"
    assert "unit-test-vision-key" not in repr(config.vision_cortex)
    assert config.vision_cortex.timeout_seconds == 45
    assert config.vision_cortex.max_image_edge == 1280


@pytest.mark.parametrize(
    ("environment", "message"),
    [
        ({"LOCAL_AI_VISION_BASE_URL": "https://api.example.com/v1"}, "loopback"),
        ({"LOCAL_AI_VISION_BASE_URL": "http://user:secret@127.0.0.1:8781/v1"}, "loopback"),
        ({"LOCAL_AI_VISION_BASE_URL": "http://127.0.0.1:8781"}, "/v1"),
        ({"LOCAL_AI_VISION_BASE_URL": "http://127.0.0.1:8781/custom/v1"}, "/v1"),
        ({"LOCAL_AI_VISION_BASE_URL": "http://127.0.0.1:8781/v1"}, "API_KEY"),
        ({"LOCAL_AI_VISION_TIMEOUT": "181"}, "LOCAL_AI_VISION_TIMEOUT"),
        ({"LOCAL_AI_VISION_MAX_IMAGE_EDGE": "200"}, "LOCAL_AI_VISION_MAX_IMAGE_EDGE"),
    ],
)
def test_visual_cortex_configuration_rejects_remote_or_unbounded_values(environment, message):
    with pytest.raises(ConfigurationError, match=message):
        AppConfig.from_env(environment)


def test_github_keyring_publication_requires_exact_repository_and_write_scope():
    config = AppConfig.from_env({
        "LOCAL_AI_GITHUB_ENABLED": "true",
        "LOCAL_AI_GITHUB_CREDENTIAL_REF": "gh-keyring:github.com:Rishavmit14",
        "LOCAL_AI_GITHUB_ALLOWED_REPOSITORY": "Rishavmit14/ML-AI-Engineering",
        "LOCAL_AI_GITHUB_PUBLICATION_PURPOSE": "learner_project_public_proof",
        "LOCAL_AI_GATEWAY_SCOPES": "read_status,github_write",
    })
    assert config.gateway.github_credential_ref == "gh-keyring:github.com:Rishavmit14"
    assert config.gateway.github_allowed_repository == "Rishavmit14/ML-AI-Engineering"
    for override in (
        {"LOCAL_AI_GATEWAY_SCOPES": "read_status"},
        {"LOCAL_AI_GITHUB_ALLOWED_REPOSITORY": ""},
        {"LOCAL_AI_GITHUB_ENABLED": "false"},
    ):
        invalid = {
            "LOCAL_AI_GITHUB_ENABLED": "true",
            "LOCAL_AI_GITHUB_CREDENTIAL_REF": "gh-keyring:github.com:Rishavmit14",
            "LOCAL_AI_GITHUB_ALLOWED_REPOSITORY": "Rishavmit14/ML-AI-Engineering",
            "LOCAL_AI_GITHUB_PUBLICATION_PURPOSE": "learner_project_public_proof",
            "LOCAL_AI_GATEWAY_SCOPES": "read_status,github_write",
            **override,
        }
        with pytest.raises(ConfigurationError, match="keyring GitHub publication"):
            AppConfig.from_env(invalid)


def test_default_path_types_are_paths():
    paths = AppConfig.from_env({}).paths
    assert all(
        isinstance(value, Path)
        for value in (
            paths.var_dir,
            paths.document_dir,
            paths.rag_data_dir,
            paths.code_repo_dir,
            paths.code_index_dir,
            paths.patch_dir,
            paths.worktree_dir,
            paths.isolation_dir,
        )
    )
