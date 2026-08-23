from types import SimpleNamespace

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
