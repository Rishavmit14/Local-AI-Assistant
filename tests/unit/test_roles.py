from threading import Event, Thread

import pytest

from local_ai_assistant.roles import Role, RoleOrchestrator


class FakeModel:
    def __init__(self):
        self.calls = []

    def chat(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        return "ok"

    def stream_chat(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        yield "one"
        yield "two"


def test_roles_use_one_model_with_bounded_prompt_only_context():
    model = FakeModel()
    orchestrator = RoleOrchestrator(model, max_history=2)
    assert orchestrator.client(Role.SECURITY).chat("review", system_prompt="evidence") == "ok"
    assert "do not grant authorization" in model.calls[0][1]["system_prompt"]
    assert "evidence" in model.calls[0][1]["system_prompt"]
    assert orchestrator.recent()[0].role is Role.SECURITY
    assert orchestrator.recent()[0].success is True


def test_stream_failure_is_recorded_and_history_is_bounded():
    model = FakeModel()
    orchestrator = RoleOrchestrator(model, max_history=1)
    assert list(orchestrator.client(Role.CONVERSATION).stream_chat("hello")) == ["one", "two"]
    assert orchestrator.recent()[-1].role is Role.CONVERSATION
    with pytest.raises(ValueError, match="bounds"):
        orchestrator.recent(2)


def test_role_invocations_are_serialized_over_one_model():
    entered, release = Event(), Event()

    class BlockingModel(FakeModel):
        def chat(self, prompt, **kwargs):
            entered.set()
            assert release.wait(2)
            return super().chat(prompt, **kwargs)

    model = BlockingModel()
    orchestrator = RoleOrchestrator(model)
    first = Thread(target=lambda: orchestrator.client(Role.PLANNER).chat("one"))
    second = Thread(target=lambda: orchestrator.client(Role.REVIEWER).chat("two"))
    first.start()
    assert entered.wait(1)
    second.start()
    assert len(model.calls) == 0
    release.set()
    first.join(2)
    second.join(2)
    assert [call[0] for call in model.calls] == ["one", "two"]
