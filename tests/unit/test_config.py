from pathlib import Path

import pytest

from local_ai_assistant.common.config import AppConfig
from local_ai_assistant.common.errors import ConfigurationError


def test_default_configuration_preserves_local_ports_and_model():
    config = AppConfig.from_env({})

    assert config.llama.base_url == "http://127.0.0.1:8080/v1"
    assert config.llama.context_size == 262_144
    assert config.llama.model.endswith("Qwen3.6-35B-A3B-UD-Q4_K_M.gguf")
    assert config.ui.host == "127.0.0.1"
    assert config.ui.port == 8501
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
            "LOCAL_AI_UI_PORT": "8600",
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
    assert config.ui.port == 8600
    assert config.ocr.enabled is False
    assert config.document_retrieval.final_top_k == 7
    assert config.code_retrieval.chunk_lines == 80
    assert config.runtime.log_format == "text"
    assert config.runtime.test_mode is True
    assert config.execution.max_steps == 7
    assert config.paths.worktree_dir == (tmp_path / "worktrees").resolve()
    assert config.isolation.backend == "native"
    assert config.isolation.network_policy == "allowed"
    assert config.isolation.require_strong_isolation is False
    assert config.isolation.max_processes == 12


@pytest.mark.parametrize(
    ("environment", "message"),
    [
        ({"LOCAL_AI_UI_PORT": "not-a-port"}, "LOCAL_AI_UI_PORT"),
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
