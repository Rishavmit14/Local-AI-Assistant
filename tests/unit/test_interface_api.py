import asyncio
import json
import threading
import hashlib

from fastapi.testclient import TestClient

from local_ai_assistant.autonomy import ObjectiveService
from local_ai_assistant.career_forge import CareerForgeService
from local_ai_assistant.desktop import DesktopControlService
from local_ai_assistant.gateway.auth import GatewayAuth
from local_ai_assistant.gateway.models import GatewayScope
from local_ai_assistant.interface.api import create_presentation_app
from local_ai_assistant.interface.conversation import FridayConversationService
from local_ai_assistant.interface.capabilities import CapabilityStatus, FridayCapability, FridayCapabilityRegistry
from local_ai_assistant.interface.events import FridayEventType
from local_ai_assistant.interface.interaction import FridayInteractionCoordinator
from local_ai_assistant.interface.runtime import FridayRuntime
from local_ai_assistant.interface.states import FridayRuntimeState
from local_ai_assistant.memory import FridayMemoryService, MemoryKind


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


def test_objective_planning_keeps_health_and_cancellation_responsive(tmp_path):
    entered = threading.Event()
    cancelled = threading.Event()
    observed_cancellation = []
    task_id = "task_" + "a" * 20

    def plan(_task_id):
        entered.set()
        observed_cancellation.append(cancelled.wait(3))

    autonomy = ObjectiveService(
        tmp_path / "objectives.sqlite3",
        create_task_for_objective=lambda _text, _repo, reserved_id: reserved_id,
        request_plan_for_task=plan,
        plan_hash_for_task=lambda _task: "b" * 64 if entered.is_set() and not cancelled.is_set() else None,
        cancel_task=lambda _task: cancelled.set(),
    )
    objective = autonomy.resume(autonomy.create("Inspect only").objective_id)
    runtime = FridayRuntime("planning-responsiveness")
    responses = []
    with TestClient(create_presentation_app(
        runtime, FridayConversationService(FakeStreamingLLM(), runtime), autonomy=autonomy,
    )) as client:
        worker = threading.Thread(target=lambda: responses.append(client.post(
            f"/api/v1/objectives/{objective.objective_id}/plan", json={"repository_id": "friday"},
        )))
        worker.start()
        try:
            assert entered.wait(3)
            assert client.get("/health").status_code == 200
            busy = client.post(
                f"/api/v1/objectives/{objective.objective_id}/plan", json={"repository_id": "friday"},
            )
            assert busy.status_code == 409
            assert busy.json()["detail"] == "objective planning is already active"
            assert client.post(f"/api/v1/objectives/{objective.objective_id}/cancel").status_code == 200
        finally:
            cancelled.set()
            worker.join(5)
        retry = client.post(
            f"/api/v1/objectives/{objective.objective_id}/plan", json={"repository_id": "friday"},
        )
        assert retry.status_code == 409
        assert "must be planning" in retry.json()["detail"]
    assert not worker.is_alive()
    assert observed_cancellation == [True]
    assert responses[0].status_code == 409
    assert autonomy.get(objective.objective_id).state == "cancelled"


def test_objective_execution_requires_gateway_auth_scope_and_exact_plan(tmp_path):
    task_id = "task_" + "a" * 20
    dispatched = []
    states = {task_id: "approved"}
    service = ObjectiveService(
        tmp_path / "objectives.sqlite3",
        plan_hash_for_task=lambda _task: "b" * 64,
        task_state_for_task=states.get,
        execute_task=lambda task, token: dispatched.append((task, token)) or {"task_id": task, "accepted": True},
    )
    objective = service.bind_plan(service.create("Exact execution").objective_id, task_id)
    runtime = FridayRuntime("objective-execution")
    conversation = FridayConversationService(FakeStreamingLLM(), runtime)
    route = f"/api/v1/objectives/{objective.objective_id}/execute"
    digest = hashlib.sha256(b"test-execution-token").hexdigest()
    headers = {"Authorization": "Bearer test-execution-token"}
    with TestClient(create_presentation_app(runtime, conversation, autonomy=service)) as client:
        assert client.post(route).status_code == 503
    read_auth = GatewayAuth(digest, frozenset({GatewayScope.READ_STATUS}))
    with TestClient(create_presentation_app(runtime, conversation, autonomy=service, objective_execution_auth=read_auth)) as client:
        assert client.post(route, headers=headers).status_code == 403
    auth = GatewayAuth(digest, frozenset({GatewayScope.REQUEST_EXECUTION}))
    with TestClient(create_presentation_app(runtime, conversation, autonomy=service, objective_execution_auth=auth, objective_execution_requests_per_minute=2)) as client:
        assert client.post(route).status_code == 401
        states[task_id] = "awaiting_approval"
        assert client.post(route, headers=headers).status_code == 409
        assert dispatched == []
        states[task_id] = "approved"
        response = client.post(route, headers=headers)
        assert response.status_code == 202
        assert response.json()["execution"]["task_id"] == task_id
        assert dispatched == [(task_id, "b" * 64)]
        assert client.post(route, headers=headers).status_code == 429


def test_voice_health_is_separate_from_http_liveness():
    runtime = FridayRuntime("voice-health")
    observed = {"enabled": True, "status": "recovering", "recovery_count": 1}
    client = TestClient(create_presentation_app(
        runtime, FridayConversationService(FakeStreamingLLM(), runtime),
        voice_health=lambda: dict(observed),
    ))
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/api/v1/voice/health").json() == observed
    observed["status"] = "running"
    assert client.get("/api/v1/voice/health").json() == observed
    disabled, _ = make_client()
    assert disabled.get("/api/v1/voice/health").json() == {
        "enabled": False, "status": "disabled",
    }


def test_runtime_session_and_capability_projection_are_read_only():
    runtime = FridayRuntime("capability-projection")
    conversation = FridayConversationService(FakeStreamingLLM(["ok"]), runtime)
    registry = FridayCapabilityRegistry((
        FridayCapability("career_forge", "Career Forge", CapabilityStatus.INTEGRATED,
                         True, True, True, "panel", "Practice Lab is not installed"),
    ))
    client = TestClient(create_presentation_app(runtime, conversation, capabilities=registry))

    state = client.get("/api/v1/runtime/state").json()
    assert state["session"] == {
        "active": False, "turn_count": 0, "context_characters": 0,
        "max_turns": 16, "max_characters": 12000, "turns": [], "capability_mode": None,
    }
    capability = client.get("/api/v1/capabilities").json()["capabilities"][0]
    assert capability["key"] == "career_forge"
    assert capability["status"] == "integrated"
    assert capability["limitation"] == "Practice Lab is not installed"


def test_memory_capture_requires_an_explicit_complete_owner_record(tmp_path):
    runtime = FridayRuntime("memory-api")
    memory = FridayMemoryService(tmp_path / "memory.sqlite3")
    client = TestClient(
        create_presentation_app(
            runtime,
            FridayConversationService(FakeStreamingLLM(["Try a prediction first."]), runtime),
            memory=memory,
        )
    )
    rejected = client.post("/api/v1/memory/remember", json={"kind": "fact"})
    assert rejected.status_code == 400
    response = client.post(
        "/api/v1/memory/remember",
        json={
            "kind": MemoryKind.PREFERENCE,
            "subject": "owner",
            "content": "prefers concise answers",
            "provenance": "direct owner request",
            "confidence": 1,
        },
    )
    assert response.status_code == 200
    assert client.get("/api/v1/memory/recall", params={"subject": "owner"}).json()[0][
        "content"
    ] == "prefers concise answers"
    unavailable, _ = make_client()
    assert unavailable.get("/api/v1/memory/recall", params={"subject": "owner"}).status_code == 404


def test_desktop_actions_require_explicit_approval_before_execution(tmp_path):
    calls = []
    control = DesktopControlService(
        tmp_path / "desktop.sqlite3", allowed_apps=("org.gnome.Terminal",),
        runner=lambda command, **_kwargs: calls.append(command) or type("Result", (), {"returncode": 0})(),
    )
    runtime = FridayRuntime("desktop-api")
    client = TestClient(create_presentation_app(
        runtime, FridayConversationService(FakeStreamingLLM(), runtime), desktop_control=control,
    ))
    proposed = client.post("/api/v1/desktop/actions", json={
        "action": "focus_app", "app_id": "org.gnome.Terminal",
    })
    assert proposed.status_code == 200
    action_id = proposed.json()["action"]["action_id"]
    assert client.post(f"/api/v1/desktop/actions/{action_id}/execute").status_code == 409
    assert client.post(f"/api/v1/desktop/actions/{action_id}/approve").status_code == 200
    assert client.post(f"/api/v1/desktop/actions/{action_id}/execute").json()["action"]["state"] == "executed"
    assert calls[0][-2:] == ["org.gnome.Shell.FocusApp", "org.gnome.Terminal"]


def test_objective_api_persists_lifecycle_without_execution_authority(tmp_path):
    runtime = FridayRuntime("objective-api")
    task_id = "task_" + "a" * 20
    client = TestClient(create_presentation_app(
        runtime, FridayConversationService(FakeStreamingLLM(), runtime),
        autonomy=ObjectiveService(
            tmp_path / "objectives.sqlite3",
            plan_hash_for_task=lambda value: "b" * 64 if value == task_id else None,
            plan_review_for_task=lambda value, token: {"task_id": value, "plan_hash": token},
            cancel_task=lambda _value: None,
            task_state_for_task=lambda value: "awaiting_approval" if value == task_id else None,
        ),
    ))
    created = client.post("/api/v1/objectives", json={"text": "Inspect project status"})
    assert created.status_code == 200
    objective_id = created.json()["objective"]["objective_id"]
    assert client.get("/api/v1/objectives").json()["objectives"][0]["objective_id"] == objective_id
    assert client.post(f"/api/v1/objectives/{objective_id}/resume").json()["objective"]["state"] == "planning"
    planned = client.post(f"/api/v1/objectives/{objective_id}/plan", json={"task_id": task_id})
    assert planned.json()["objective"]["state"] == "planned"
    assert planned.json()["objective"]["task_id"] == task_id
    assert planned.json()["objective"]["task_state"] == "awaiting_approval"
    assert client.get(f"/api/v1/objectives/{objective_id}/plan").json()["plan"]["plan_hash"] == "b" * 64
    assert client.post(f"/api/v1/objectives/{objective_id}/cancel").json()["objective"]["state"] == "cancelled"


def test_objective_api_requests_only_the_configured_canonical_planner(tmp_path):
    runtime = FridayRuntime("objective-plan-api")
    task_id = "task_" + "a" * 20
    created: list[tuple[str, str]] = []
    requested: list[str] = []
    def create_task(text, repository_id, reserved_id):
        nonlocal task_id
        task_id = reserved_id
        created.append((text, repository_id))
        return reserved_id
    client = TestClient(create_presentation_app(
        runtime, FridayConversationService(FakeStreamingLLM(), runtime),
        autonomy=ObjectiveService(
            tmp_path / "objectives.sqlite3",
            plan_hash_for_task=lambda value: "b" * 64 if value == task_id and requested else None,
            create_task_for_objective=create_task,
            request_plan_for_task=requested.append,
        ),
    ))
    objective_id = client.post("/api/v1/objectives", json={"text": "Inspect project status"}).json()["objective"]["objective_id"]
    assert client.post(f"/api/v1/objectives/{objective_id}/resume").status_code == 200
    planned = client.post(f"/api/v1/objectives/{objective_id}/plan", json={"repository_id": "r1"})
    assert planned.status_code == 200
    assert planned.json()["objective"]["task_id"] == task_id
    assert created == [("Inspect project status", "r1")]
    assert requested == [task_id]


def test_presentation_shutdown_runs_configured_local_cleanup():
    runtime = FridayRuntime("shutdown-cleanup")
    closed: list[bool] = []
    with TestClient(create_presentation_app(
        runtime,
        FridayConversationService(FakeStreamingLLM(), runtime),
        on_shutdown=lambda: closed.append(True),
    )):
        pass
    assert closed == [True]


def test_career_journey_starts_only_the_dependency_ready_mission(tmp_path):
    runtime = FridayRuntime("career-api")
    forge = CareerForgeService(tmp_path / "learner.sqlite3")
    client = TestClient(
        create_presentation_app(
            runtime,
            FridayConversationService(FakeStreamingLLM(["Try a prediction first."]), runtime),
            career_forge=forge,
        )
    )
    journey = client.get("/api/v1/career-forge/journey").json()
    assert journey["next_competency"]["competency_id"] == "se.python"
    assert journey["recommended_mission"]["title"] == "Verify Python state and functions"
    rejected = client.post(
        "/api/v1/career-forge/missions",
        json={"competency_id": "dl.pytorch", "title": "Skip ahead"},
    )
    assert rejected.status_code == 400
    started = client.post(
        "/api/v1/career-forge/missions",
        json={},
    )
    assert started.status_code == 200
    assert started.json()["mission"]["competency_id"] == "se.python"
    assert "teach_back" in started.json()["loop"]
    mission_id = started.json()["mission"]["mission_id"]
    help_response = client.post(
        f"/api/v1/career-forge/missions/{mission_id}/assistance",
        json={"mode": "hint", "level": "prompt", "content": "Predict before running."},
    )
    assert help_response.status_code == 200
    evidence = client.post(
        f"/api/v1/career-forge/missions/{mission_id}/evidence",
        json={"evidence_type": "teach_back", "content": "I explained the mutation risk."},
    )
    assert evidence.status_code == 200
    resumed = client.post(
        f"/api/v1/career-forge/missions/{mission_id}/resume",
        json={"resume_point": {"phase": "teach_back"}, "assistance_level": "prompt"},
    )
    assert resumed.json()["resume_point"] == {"phase": "teach_back"}
    tutor = client.post(
        f"/api/v1/career-forge/missions/{mission_id}/tutor",
        json={"mode": "hint", "assistance_level": "prompt", "message": "I am stuck."},
    )
    assert tutor.json() == {"response": "Try a prediction first.", "recorded_assistance": True}
    advanced = client.post(
        "/api/v1/career-forge/competencies/se.python/advance",
        json={"mastery": "recognize", "evidence_id": evidence.json()["evidence_id"]},
    )
    assert advanced.json()["mastery"] == "recognize"
    assert client.post(f"/api/v1/career-forge/missions/{mission_id}/project").status_code == 409


def test_busy_voice_rejects_http_before_runtime_events():
    runtime = FridayRuntime("busy-voice")
    conversation = FridayConversationService(FakeStreamingLLM(["unused"]), runtime)
    interactions = FridayInteractionCoordinator()
    lease = interactions.try_acquire("voice")
    client = TestClient(create_presentation_app(
        runtime, conversation, interactions=interactions,
    ))
    try:
        response = client.post("/api/v1/conversation/stream", json={"prompt": "Hi"})
        assert response.status_code == 409
        assert response.json()["detail"] == {
            "code": "interaction_busy", "owner": "voice",
        }
        assert runtime.events_since() == ()
        assert conversation.llm.chunks == ["unused"]
    finally:
        lease.release()


def test_presentation_pauses_wake_and_releases_lease_after_stream():
    runtime = FridayRuntime("presentation-owner")
    interactions = FridayInteractionCoordinator()
    lifecycle = []
    client = TestClient(create_presentation_app(
        runtime, FridayConversationService(FakeStreamingLLM(["ok"]), runtime),
        interactions=interactions,
        presentation_pause=lambda: lifecycle.append("pause"),
        presentation_resume=lambda: lifecycle.append("resume"),
    ))
    response = client.post("/api/v1/conversation/stream", json={"prompt": "Hi"})
    assert response.status_code == 200
    assert response.text == "ok"
    assert lifecycle == ["pause", "resume"]
    assert interactions.snapshot().owner is None


def test_interaction_state_is_read_only_projection():
    runtime = FridayRuntime("interaction-state")
    interactions = FridayInteractionCoordinator()
    client = TestClient(create_presentation_app(
        runtime, FridayConversationService(FakeStreamingLLM(), runtime),
        interactions=interactions,
    ))
    assert client.get("/api/v1/interaction/state").json() == {
        "busy": False, "owner": None, "generation": 0,
    }
    lease = interactions.try_acquire("voice")
    assert client.get("/api/v1/interaction/state").json()["owner"] == "voice"
    lease.release()


def test_overlapping_http_stream_is_rejected_without_phantom_prompt():
    entered = threading.Event()
    release = threading.Event()

    class BlockingLLM(FakeStreamingLLM):
        def stream_chat(self, prompt, **kwargs):
            del kwargs
            self.calls = getattr(self, "calls", [])
            self.calls.append(prompt)
            entered.set()
            assert release.wait(2)
            yield "done"

    runtime = FridayRuntime("overlap")
    llm = BlockingLLM()
    app = create_presentation_app(runtime, FridayConversationService(llm, runtime))
    first_client = TestClient(app)
    second_client = TestClient(app)
    first = {}

    thread = threading.Thread(
        target=lambda: first.setdefault(
            "response",
            first_client.post("/api/v1/conversation/stream", json={"prompt": "first"}),
        ),
        daemon=True,
    )
    thread.start()
    assert entered.wait(1)
    try:
        rejected = second_client.post(
            "/api/v1/conversation/stream", json={"prompt": "second"},
        )
        assert rejected.status_code == 409
        assert llm.calls == ["first"]
        assert [
            event.text for event in runtime.events_since()
            if event.event_type is FridayEventType.CONVERSATION_USER_TEXT
        ] == ["first"]
    finally:
        release.set()
        thread.join(2)
    assert not thread.is_alive()
    assert first["response"].text == "done"


def test_failed_http_stream_resumes_wake_and_releases_owner():
    class FailingLLM:
        def stream_chat(self, *args, **kwargs):
            del args, kwargs
            raise RuntimeError("generation failed")
            yield  # pragma: no cover

    runtime = FridayRuntime("failed-http")
    interactions = FridayInteractionCoordinator()
    lifecycle = []
    client = TestClient(create_presentation_app(
        runtime, FridayConversationService(FailingLLM(), runtime),
        interactions=interactions,
        presentation_pause=lambda: lifecycle.append("pause"),
        presentation_resume=lambda: lifecycle.append("resume"),
    ))
    try:
        client.post("/api/v1/conversation/stream", json={"prompt": "fail"})
    except Exception:
        pass
    assert lifecycle == ["pause", "resume"]
    assert interactions.snapshot().owner is None


def test_presentation_pause_failure_releases_owner_before_streaming():
    runtime = FridayRuntime("pause-failure")
    interactions = FridayInteractionCoordinator()

    def fail_pause():
        raise RuntimeError("pause failed")

    client = TestClient(create_presentation_app(
        runtime,
        FridayConversationService(FakeStreamingLLM(["unused"]), runtime),
        interactions=interactions,
        presentation_pause=fail_pause,
    ))

    try:
        client.post("/api/v1/conversation/stream", json={"prompt": "fail"})
    except RuntimeError as exc:
        assert str(exc) == "pause failed"
    else:
        raise AssertionError("presentation pause failure was not surfaced")

    assert interactions.snapshot().owner is None
    assert runtime.events_since() == ()


def test_presentation_resume_failure_still_releases_owner():
    runtime = FridayRuntime("resume-failure")
    interactions = FridayInteractionCoordinator()

    def fail_resume():
        raise RuntimeError("resume failed")

    client = TestClient(create_presentation_app(
        runtime,
        FridayConversationService(FakeStreamingLLM(["ok"]), runtime),
        interactions=interactions,
        presentation_resume=fail_resume,
    ))

    try:
        client.post("/api/v1/conversation/stream", json={"prompt": "fail"})
    except RuntimeError as exc:
        assert str(exc) == "resume failed"
    else:
        raise AssertionError("presentation resume failure was not surfaced")

    assert interactions.snapshot().owner is None


def test_disconnect_before_body_iteration_resumes_wake_and_releases_owner():
    runtime = FridayRuntime("early-disconnect")
    interactions = FridayInteractionCoordinator()
    lifecycle = []
    llm = FakeStreamingLLM(["must not start"])
    app = create_presentation_app(
        runtime,
        FridayConversationService(llm, runtime),
        interactions=interactions,
        presentation_pause=lambda: lifecycle.append("pause"),
        presentation_resume=lambda: lifecycle.append("resume"),
    )
    body = json.dumps({"prompt": "disconnect"}).encode()
    incoming = [
        {"type": "http.request", "body": body, "more_body": False},
        {"type": "http.disconnect"},
    ]

    async def receive():
        if incoming:
            return incoming.pop(0)
        await asyncio.sleep(1)
        return {"type": "http.disconnect"}

    async def send(_message):
        return None

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/v1/conversation/stream",
        "raw_path": b"/api/v1/conversation/stream",
        "query_string": b"",
        "root_path": "",
        "headers": [(b"content-type", b"application/json")],
        "client": ("test", 1),
        "server": ("test", 80),
        "state": {},
    }

    asyncio.run(app(scope, receive, send))

    assert lifecycle == ["pause", "resume"]
    assert interactions.snapshot().owner is None
    assert runtime.events_since() == ()
    assert llm.chunks == ["must not start"]


def test_disconnect_during_blocked_generation_holds_owner_until_safe_cancel():
    first_chunk = threading.Event()
    finish_next = threading.Event()

    class BlockingAfterFirstChunk(FakeStreamingLLM):
        def stream_chat(self, *args, **kwargs):
            del args, kwargs
            yield "first"
            first_chunk.set()
            assert finish_next.wait(2)
            yield "must not send"

    runtime = FridayRuntime("started-disconnect")
    interactions = FridayInteractionCoordinator()
    lifecycle = []
    app = create_presentation_app(
        runtime,
        FridayConversationService(BlockingAfterFirstChunk(), runtime),
        interactions=interactions,
        presentation_pause=lambda: lifecycle.append("pause"),
        presentation_resume=lambda: lifecycle.append("resume"),
    )
    body = json.dumps({"prompt": "disconnect"}).encode()
    request_sent = False

    async def receive():
        nonlocal request_sent
        if not request_sent:
            request_sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        while not first_chunk.is_set():
            await asyncio.sleep(0.001)
        return {"type": "http.disconnect"}

    async def send(_message):
        return None

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/v1/conversation/stream",
        "raw_path": b"/api/v1/conversation/stream",
        "query_string": b"",
        "root_path": "",
        "headers": [(b"content-type", b"application/json")],
        "client": ("test", 1),
        "server": ("test", 80),
        "state": {},
    }

    observed_during_block = {}

    async def release_blocked_generation():
        while not first_chunk.is_set():
            await asyncio.sleep(0.001)
        await asyncio.sleep(0.01)
        observed_during_block["owner"] = interactions.snapshot().owner
        observed_during_block["lifecycle"] = list(lifecycle)
        finish_next.set()

    async def run_disconnected_request():
        await asyncio.gather(
            app(scope, receive, send),
            release_blocked_generation(),
        )

    asyncio.run(run_disconnected_request())

    assert observed_during_block == {
        "owner": "presentation",
        "lifecycle": ["pause"],
    }
    assert interactions.snapshot().owner is None
    assert lifecycle == ["pause", "resume"]
    assert runtime.state is FridayRuntimeState.CANCELLED


def test_runtime_state_is_read_only_projection():
    client, runtime = make_client()

    runtime.transition(FridayRuntimeState.THINKING)

    response = client.get("/api/v1/runtime/state")

    assert response.status_code == 200
    assert response.json() == {
        "session_id": "session-api",
        "state": "thinking",
        "session": {
            "active": False,
            "turn_count": 0,
            "context_characters": 0,
            "max_turns": 16,
            "max_characters": 12000,
            "turns": [],
            "capability_mode": None,
        },
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


def test_presentation_api_has_no_unbounded_execution_routes():
    client, _ = make_client()

    schema = client.get("/openapi.json").json()
    paths = set(schema["paths"])

    assert "/api/v1/tasks/{task_id}/execute" not in paths
    assert "/api/v1/tasks/{task_id}/approval" not in paths
    assert "/api/v1/tasks/{task_id}/publish" not in paths

    assert paths == {
        "/health",
        "/api/v1/runtime/state",
        "/api/v1/capabilities",
        "/api/v1/voice/health",
        "/api/v1/interaction/state",
        "/api/v1/research/sources",
        "/api/v1/research/synthesis",
        "/api/v1/proactive/notifications",
        "/api/v1/proactive/notifications/{notification_id}/acknowledge",
        "/api/v1/objectives",
        "/api/v1/objectives/{objective_id}",
        "/api/v1/objectives/{objective_id}/resume",
        "/api/v1/objectives/{objective_id}/plan",
        "/api/v1/objectives/{objective_id}/cancel",
        "/api/v1/objectives/{objective_id}/execute",
        "/api/v1/desktop/actions",
        "/api/v1/desktop/actions/{action_id}/approve",
        "/api/v1/desktop/actions/{action_id}/execute",
        "/api/v1/perception/screen/capture",
        "/api/v1/perception/active-window",
        "/api/v1/perception/screen/captures",
        "/api/v1/perception/screen/captures/{capture_id}/ocr",
        "/api/v1/perception/screen/captures/{capture_id}/ui-state",
        "/api/v1/perception/screen/captures/{capture_id}/visual-labels",
        "/api/v1/career-forge/journey",
        "/api/v1/career-forge/missions",
        "/api/v1/career-forge/missions/{mission_id}/project",
        "/api/v1/career-forge/missions/{mission_id}/resume",
        "/api/v1/career-forge/missions/{mission_id}/assistance",
        "/api/v1/career-forge/missions/{mission_id}/evidence",
        "/api/v1/career-forge/missions/{mission_id}/tutor",
        "/api/v1/career-forge/competencies/{competency_id}/advance",
        "/api/v1/memory/recall",
        "/api/v1/memory/remember",
        "/api/v1/runtime/events",
        "/api/v1/runtime/events/stream",
        "/api/v1/conversation/stream",
    }


def test_sse_route_is_exposed_without_execution_authority():
    client, _ = make_client()

    schema = client.get("/openapi.json")

    assert schema.status_code == 200
    assert "/api/v1/runtime/events/stream" in schema.json()["paths"]
