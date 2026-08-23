import importlib
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_public_packages_and_compatibility_modules_import():
    for module in (
        "local_ai_assistant",
        "local_ai_assistant.common.config",
        "local_ai_assistant.llm",
        "local_ai_assistant.rag",
        "local_ai_assistant.code_index",
        "local_ai_assistant.agent.code_agent",
        "local_llm",
        "rag",
        "code_rag",
        "code_agent",
    ):
        assert importlib.import_module(module) is not None


def test_compatibility_wrappers_export_only_historical_public_api():
    local_llm = importlib.import_module("local_llm")
    rag = importlib.import_module("rag")
    code_rag = importlib.import_module("code_rag")
    code_agent = importlib.import_module("code_agent")

    assert local_llm.__all__ == ["DEFAULT_BASE_URL", "DEFAULT_MODEL", "LocalLLM", "main"]
    assert rag.__all__ == ["DOCUMENT_DIR", "LocalRAG", "main"]
    assert code_rag.__all__ == ["CodeRAG", "main"]
    assert code_agent.__all__ == ["main"]
    assert not hasattr(local_llm, "OpenAI")
    assert not hasattr(code_agent, "subprocess")


def test_pyproject_is_canonical_and_exposes_supported_commands():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    package = importlib.import_module("local_ai_assistant")
    assert project["requires-python"] == ">=3.11"
    assert project["version"] == package.__version__ == "0.5.0"
    assert set(project["scripts"]) == {
        "local-ai-chat",
        "local-ai-code-rag",
        "local-ai-code-agent",
        "local-ai-plan",
        "local-ai-execute",
        "local-ai-ui",
    }
    assert {"rag", "ui", "coding-agent", "dev"} <= set(project["optional-dependencies"])
