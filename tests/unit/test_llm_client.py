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
            id="response-test",
            choices=[SimpleNamespace(message=SimpleNamespace(content="answer"), finish_reason="stop")],
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
        "max_retries": 0,
        "http_client": llm._http_client,
    }
    assert llm._http_client.trust_env is False
    assert llm.chat("question", system_prompt="system", max_tokens=17) == "answer"
    call = llm.client.chat.completions.calls[0]
    assert call["model"] == "model.gguf"
    assert call["messages"][-1] == {"role": "user", "content": "question"}
    assert call["max_tokens"] == 17


def test_chat_forwards_optional_json_response_format(monkeypatch):
    monkeypatch.setattr(client_module, "OpenAI", FakeOpenAI)
    llm = client_module.LocalLLM()

    assert llm.chat("{}", response_format={"type": "json_object"}) == "answer"

    assert llm.client.chat.completions.calls[0]["response_format"] == {
        "type": "json_object"
    }


def test_chat_forwards_json_schema_and_records_termination_metadata(monkeypatch):
    monkeypatch.setattr(client_module, "OpenAI", FakeOpenAI)
    llm = client_module.LocalLLM()
    response_format = {"type": "json_schema", "json_schema": {"name": "tool_choice", "strict": True, "schema": {"type": "object"}}}
    assert llm.chat("{}", max_tokens=768, response_format=response_format) == "answer"
    assert llm.client.chat.completions.calls[0]["response_format"] == response_format
    assert llm.last_response_metadata == {
        "finish_reason": "stop", "response_id": "response-test",
        "response_format": response_format, "max_tokens": 768,
    }


def test_stream_chat_yields_only_nonempty_content(monkeypatch):
    monkeypatch.setattr(client_module, "OpenAI", FakeOpenAI)
    llm = client_module.LocalLLM()

    assert "".join(llm.stream_chat("question")) == "hello world"


def test_stream_chat_reports_content_free_local_model_boundary_events(monkeypatch):
    monkeypatch.setattr(client_module, "OpenAI", FakeOpenAI)
    llm = client_module.LocalLLM()
    events = []
    llm.set_latency_observer(lambda stage, details: events.append((stage, dict(details))))

    assert "".join(llm.stream_chat("question")) == "hello world"

    assert events == [
        ("LOCAL_LLM_REQUEST_DISPATCHED", {}),
        ("LOCAL_LLM_REQUEST_ACCEPTED", {}),
        ("LOCAL_LLM_FIRST_TOKEN", {}),
    ]
    call = llm.client.chat.completions.calls[0]
    assert "stream_options" not in call


def test_client_wraps_transport_failures_in_application_error(monkeypatch):
    monkeypatch.setattr(client_module, "OpenAI", FakeOpenAI)
    llm = client_module.LocalLLM()

    def fail(**kwargs):
        raise OSError("connection refused")

    llm.client.chat.completions.create = fail
    with pytest.raises(LLMError, match="connection refused"):
        llm.chat("question")


@pytest.mark.parametrize(
    "failure",
    (OSError("connection refused"), TimeoutError("request timed out"), RuntimeError("HTTP 503 server error")),
)
def test_client_maps_transport_timeout_and_server_failures(monkeypatch, failure):
    monkeypatch.setattr(client_module, "OpenAI", FakeOpenAI)
    llm = client_module.LocalLLM()
    llm.client.chat.completions.create = lambda **kwargs: (_ for _ in ()).throw(failure)

    with pytest.raises(LLMError):
        llm.chat("question")


@pytest.mark.parametrize("context_size", (16, 64))
def test_context_configuration_limits_requested_completion(monkeypatch, context_size):
    monkeypatch.setattr(client_module, "OpenAI", FakeOpenAI)
    config = AppConfig.from_env({"LOCAL_AI_CONTEXT_SIZE": str(context_size)})
    llm = client_module.LocalLLM(config=config)

    with pytest.raises(ConfigurationError, match=f"configured context size {context_size}"):
        llm.chat("question", max_tokens=context_size + 1)


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (SimpleNamespace(choices=[]), "no chat choices"),
        (SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=None))]), "no text chat content"),
        (SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=7))]), "no text chat content"),
    ],
)
def test_chat_rejects_malformed_text_responses(monkeypatch, response, message):
    monkeypatch.setattr(client_module, "OpenAI", FakeOpenAI)
    llm = client_module.LocalLLM()
    llm.client.chat.completions.create = lambda **kwargs: response

    with pytest.raises(LLMError, match=message):
        llm.chat("question")


def test_stream_maps_interrupted_transport_to_llm_error(monkeypatch):
    monkeypatch.setattr(client_module, "OpenAI", FakeOpenAI)
    llm = client_module.LocalLLM()

    def interrupted(**kwargs):
        def chunks():
            yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="partial"))])
            raise TimeoutError("bounded read timeout")
        return chunks()

    llm.client.chat.completions.create = interrupted
    stream = llm.stream_chat("question")
    assert next(stream) == "partial"
    with pytest.raises(LLMError, match="bounded read timeout"):
        next(stream)


@pytest.mark.parametrize(
    "chunks",
    [
        [],
        [SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=7))])],
    ],
)
def test_stream_rejects_empty_or_invalid_output(monkeypatch, chunks):
    monkeypatch.setattr(client_module, "OpenAI", FakeOpenAI)
    llm = client_module.LocalLLM()
    llm.client.chat.completions.create = lambda **kwargs: chunks

    with pytest.raises(LLMError):
        "".join(llm.stream_chat("question"))


def test_model_display_identity_never_exposes_an_absolute_model_path():
    assert client_module.safe_model_display_id(
        "/private/model-cache/Qwen-Local-Q4.gguf"
    ) == "Qwen-Local-Q4.gguf"
    assert client_module.safe_model_display_id("org/model id") == "model_id"


def test_explicit_empty_model_overrides_fail_instead_of_using_defaults(monkeypatch):
    monkeypatch.setattr(client_module, "OpenAI", FakeOpenAI)

    with pytest.raises(ConfigurationError, match="LOCAL_AI_MODEL"):
        client_module.LocalLLM(model="")
    with pytest.raises(ConfigurationError, match="LOCAL_AI_BASE_URL"):
        client_module.LocalLLM(base_url="")
