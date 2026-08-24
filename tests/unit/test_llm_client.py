from types import SimpleNamespace

import pytest

from local_ai_assistant.common.config import AppConfig
from local_ai_assistant.common.errors import ConfigurationError, LLMError
from local_ai_assistant.llm import client as client_module


class FakeCompletions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("stream"):
            return [
                SimpleNamespace(choices=[]),
                SimpleNamespace(
                    choices=[SimpleNamespace(delta=SimpleNamespace(content="hello"))]
                ),
                SimpleNamespace(
                    choices=[SimpleNamespace(delta=SimpleNamespace(content=None))]
                ),
                SimpleNamespace(
                    choices=[SimpleNamespace(delta=SimpleNamespace(content=" world"))]
                ),
            ]
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="answer"))]
        )


class FakeOpenAI:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.chat = SimpleNamespace(completions=FakeCompletions())


def test_chat_preserves_local_openai_client_contract(monkeypatch):
    monkeypatch.setattr(client_module, "OpenAI", FakeOpenAI)
    llm = client_module.LocalLLM(base_url="http://localhost:9999/v1", model="model.gguf")

    assert llm.client.kwargs == {
        "base_url": "http://localhost:9999/v1",
        "api_key": "local",
        "timeout": 120,
    }
    assert llm.chat("question", system_prompt="system", max_tokens=17) == "answer"
    call = llm.client.chat.completions.calls[0]
    assert call["model"] == "model.gguf"
    assert call["messages"][-1] == {"role": "user", "content": "question"}
    assert call["max_tokens"] == 17


def test_stream_chat_yields_only_nonempty_content(monkeypatch):
    monkeypatch.setattr(client_module, "OpenAI", FakeOpenAI)
    llm = client_module.LocalLLM()

    assert "".join(llm.stream_chat("question")) == "hello world"


def test_client_wraps_transport_failures_in_application_error(monkeypatch):
    monkeypatch.setattr(client_module, "OpenAI", FakeOpenAI)
    llm = client_module.LocalLLM()

    def fail(**kwargs):
        raise OSError("connection refused")

    llm.client.chat.completions.create = fail
    with pytest.raises(LLMError, match="connection refused"):
        llm.chat("question")


def test_context_configuration_limits_requested_completion(monkeypatch):
    monkeypatch.setattr(client_module, "OpenAI", FakeOpenAI)
    config = AppConfig.from_env({"LOCAL_AI_CONTEXT_SIZE": "16"})
    llm = client_module.LocalLLM(config=config)

    with pytest.raises(ConfigurationError, match="configured context size 16"):
        llm.chat("question", max_tokens=17)
