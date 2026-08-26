import json

from fastapi.testclient import TestClient

from local_ai_assistant.interface.api import create_presentation_app
from local_ai_assistant.interface.conversation import FridayConversationService
from local_ai_assistant.interface.events import FridayEventType
from local_ai_assistant.interface.runtime import FridayRuntime
from local_ai_assistant.interface.states import FridayRuntimeState


class FakeStreamingLLM:
    def __init__(self, chunks=None):
        self.chunks = list(chunks or [])

    def stream_chat(
        self,
        prompt,
        system_prompt="",
        temperature=0.2,
        max_tokens=1024,
    ):
        yield from self.chunks


def make_client(chunks=None):
    runtime = FridayRuntime("session-api")
    conversation = FridayConversationService(
        FakeStreamingLLM(chunks),
        runtime,
    )
    app = create_presentation_app(runtime, conversation)
    return TestClient(app), runtime


def test_health_identifies_presentation_service():
    client, _ = make_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "friday-presentation",
        "api_version": "v1",
    }


def test_runtime_state_is_read_only_projection():
    client, runtime = make_client()

    runtime.transition(FridayRuntimeState.THINKING)

    response = client.get("/api/v1/runtime/state")

    assert response.status_code == 200
    assert response.json() == {
        "session_id": "session-api",
        "state": "thinking",
    }


def test_runtime_events_support_cursor_replay():
    client, runtime = make_client()

    runtime.emit(
        FridayEventType.SYSTEM_HEALTH,
        metadata={"sample": 1},
    )
    runtime.emit(
        FridayEventType.SYSTEM_HEALTH,
        metadata={"sample": 2},
    )

    response = client.get(
        "/api/v1/runtime/events",
        params={"cursor": 1, "limit": 10},
    )

    assert response.status_code == 200
    payload = response.json()

    assert len(payload) == 1
    assert payload[0]["sequence"] == 2
    assert payload[0]["metadata"]["sample"] == 2


def test_runtime_events_reject_invalid_limit():
    client, _ = make_client()

    response = client.get(
        "/api/v1/runtime/events",
        params={"limit": 0},
    )

    assert response.status_code == 400


def test_conversation_stream_returns_model_chunks_and_drives_runtime():
    client, runtime = make_client(["Hello", " ", "Kumar"])

    with client.stream(
        "POST",
        "/api/v1/conversation/stream",
        json={"prompt": "Hello Friday"},
    ) as response:
        assert response.status_code == 200
        output = "".join(response.iter_text())

    assert output == "Hello Kumar"
    assert runtime.state is FridayRuntimeState.COMPLETED

    events = runtime.events_since()

    assert any(
        event.event_type is FridayEventType.CONVERSATION_ASSISTANT_DELTA
        for event in events
    )
    assert any(
        event.event_type is FridayEventType.CONVERSATION_ASSISTANT_COMPLETED
        for event in events
    )


def test_conversation_rejects_empty_prompt_without_llm_activity():
    client, runtime = make_client(["unused"])

    response = client.post(
        "/api/v1/conversation/stream",
        json={"prompt": "   "},
    )

    assert response.status_code == 400
    assert runtime.state is FridayRuntimeState.IDLE
    assert runtime.events_since() == ()


def test_presentation_api_has_no_execution_routes():
    client, _ = make_client()

    schema = client.get("/openapi.json").json()
    paths = set(schema["paths"])

    assert "/api/v1/tasks/{task_id}/execute" not in paths
    assert "/api/v1/tasks/{task_id}/approval" not in paths
    assert "/api/v1/tasks/{task_id}/publish" not in paths

    assert paths == {
        "/health",
        "/api/v1/runtime/state",
        "/api/v1/runtime/events",
        "/api/v1/runtime/events/stream",
        "/api/v1/conversation/stream",
    }


def test_sse_route_is_exposed_without_execution_authority():
    client, _ = make_client()

    schema = client.get("/openapi.json")

    assert schema.status_code == 200
    assert "/api/v1/runtime/events/stream" in schema.json()["paths"]
