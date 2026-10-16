import hashlib
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from local_ai_assistant.career_forge.service import CareerForgeService
from local_ai_assistant.interface.api import create_presentation_app
from local_ai_assistant.interface.capabilities import (
    CapabilityStatus,
    FridayCapability,
    FridayCapabilityRegistry,
)
from local_ai_assistant.interface.capability_routing import FridayConversationCapabilityRouter
from local_ai_assistant.interface.conversation import FridayConversationService
from local_ai_assistant.interface.runtime import FridayRuntime
from local_ai_assistant.isolation.owner_rollback import OwnerBrowserSessions
from local_ai_assistant.learning_paths import LearningPathService
from local_ai_assistant.learning_paths.service import LocalCurriculumGenerator
from local_ai_assistant.memory import FridayMemoryService
from local_ai_assistant.projects import ProjectService
from tests.fixtures.learning_path_curricula import curriculum

OWNER_ORIGIN = "http://127.0.0.1:5193"
OWNER_CREDENTIAL = "isolated-learning-path-owner-test-credential"


class ProposalModel:
    def __init__(self):
        self.calls = []

    def chat(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        return json.dumps(curriculum())


class StreamingModel:
    def __init__(self):
        self.calls = []

    def stream_chat(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        yield "normal conversation reply"


def _make_app(tmp_path, *, lifetime=600, conversation_routes=False):
    db = tmp_path / "learning-paths.sqlite3"
    proposal_model = ProposalModel()
    paths = LearningPathService(db, generator=LocalCurriculumGenerator(proposal_model))
    career_forge = CareerForgeService(tmp_path / "career-forge.sqlite3")
    projects = ProjectService(tmp_path / "projects.sqlite3")
    runtime = FridayRuntime("learning-path-owner-security")
    stream_model = StreamingModel()
    capability_router = None
    if conversation_routes:
        registry = FridayCapabilityRegistry((FridayCapability(
            "learning_paths", "Learning Paths", CapabilityStatus.INTEGRATED,
            True, True, True, "explicit local path creation",
        ),))
        capability_router = FridayConversationCapabilityRouter(
            registry, career_forge=career_forge,
            memory=FridayMemoryService(tmp_path / "memory.sqlite3"),
            learning_paths=paths,
        )
    conversation = FridayConversationService(
        stream_model, runtime, capability_router=capability_router,
    )
    sessions = OwnerBrowserSessions(
        hashlib.sha256(OWNER_CREDENTIAL.encode()).hexdigest(),
        lifetime_seconds=lifetime,
    )
    app = create_presentation_app(
        runtime, conversation, learning_paths=paths, career_forge=career_forge,
        projects=projects, project_execution_sessions=sessions,
        project_execution_allowed_origins=(OWNER_ORIGIN,),
    )
    return app, sessions, paths, proposal_model, career_forge, projects, stream_model, db


def _session_headers(client, sessions, *, csrf=True, expired=False):
    session, token = sessions.unlock(OWNER_CREDENTIAL)
    assert session and token
    client.cookies.set("friday_project_session", session)
    if expired:
        token = "expired-session-csrf"
    return {
        "Origin": OWNER_ORIGIN,
        **({"X-Friday-CSRF": token} if csrf else {}),
    }


def _domain_counts(path):
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
        return {
            table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("learning_paths", "learning_path_versions", "learning_path_project_assignments")
        }


@pytest.mark.parametrize(
    ("route", "payload"),
    [
        ("/api/v1/learning-paths/generate", {"goal": "Build FraudShield"}),
        ("/api/v1/learning-paths", None),
    ],
)
@pytest.mark.parametrize(
    ("auth_case", "expected_status"),
    [
        ("missing_session", 401),
        ("invalid_session", 401),
        ("expired_session", 401),
        ("missing_csrf", 401),
        ("mismatched_csrf", 401),
        ("expired_csrf", 401),
        ("missing_origin", 403),
        ("unsupported_origin", 403),
    ],
)
def test_path_creation_routes_reject_invalid_owner_origin_or_csrf_without_writes(
    tmp_path, route, payload, auth_case, expected_status,
):
    app, sessions, paths, model, _, _, _, db = _make_app(
        tmp_path, lifetime=0 if auth_case in {"expired_session", "expired_csrf"} else 600,
    )
    body = payload if payload is not None else curriculum()
    before_hash = hashlib.sha256(db.read_bytes()).hexdigest()
    before_counts = _domain_counts(db)
    with TestClient(app, base_url=OWNER_ORIGIN) as client:
        headers = {"Origin": OWNER_ORIGIN}
        if auth_case not in {"missing_session", "invalid_session"}:
            headers.update(_session_headers(client, sessions, csrf=auth_case != "missing_csrf"))
        if auth_case == "invalid_session":
            client.cookies.set("friday_project_session", "not-a-session")
            headers["X-Friday-CSRF"] = "not-a-csrf-token"
        if auth_case == "mismatched_csrf":
            headers["X-Friday-CSRF"] = "different-valid-looking-csrf"
        if auth_case == "missing_origin":
            headers.pop("Origin")
        if auth_case == "unsupported_origin":
            headers["Origin"] = "https://attacker.invalid"
        response = client.post(route, json=body, headers=headers)
        retry = client.post(route, json=body, headers=headers)

    assert response.status_code == expected_status
    assert retry.status_code == expected_status
    assert paths.repository.list() == ()
    assert not model.calls
    assert _domain_counts(db) == before_counts == {
        "learning_paths": 0,
        "learning_path_versions": 0,
        "learning_path_project_assignments": 0,
    }
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before_hash


def test_lifecycle_and_assessment_handoffs_require_owner_csrf_and_exact_origin(tmp_path):
    app, sessions, paths, _, _, _, _, db = _make_app(tmp_path)
    with TestClient(app, base_url=OWNER_ORIGIN) as client:
        authorized = _session_headers(client, sessions)
        created = client.post("/api/v1/learning-paths", json=curriculum(), headers=authorized)
        assert created.status_code == 200
        path_id = created.json()["path"]["path_id"]
        payloads = [
            (f"/api/v1/learning-paths/{path_id}/select", {}),
            (f"/api/v1/learning-paths/{path_id}/activate", {}),
            (f"/api/v1/learning-paths/{path_id}/archive", {}),
            (f"/api/v1/learning-paths/{path_id}/adapt", {}),
            (f"/api/v1/learning-paths/{path_id}/versions", {"reason":"test", "curriculum":curriculum()}),
            (f"/api/v1/learning-paths/{path_id}/manual-edits", {
                "expected_version":1,"operation":{"type":"add_node","node":{
                    "node_id":"unauthorized-node","module_id":"foundations","title":"Extra",
                    "type":"lesson","objectives":["Demonstrate"],"evidence_requirements":[],
                    "competency_key":None,"estimated_hours":1,
                }},
            }),
            (f"/api/v1/learning-paths/{path_id}/handoff", {
                "node_id":"arrays", "action":"diagnostic", "path_version":1,
            }),
        ]
        before_hash = hashlib.sha256(db.read_bytes()).hexdigest()
        before_counts = _domain_counts(db)
        for route, body in payloads:
            missing_csrf = client.post(route, json=body, headers={"Origin":OWNER_ORIGIN})
            wrong_origin = client.post(route, json=body, headers={
                "Origin":"https://attacker.invalid", "X-Friday-CSRF":authorized["X-Friday-CSRF"],
            })
            assert missing_csrf.status_code == 401, (route, missing_csrf.status_code)
            assert wrong_origin.status_code == 403, (route, wrong_origin.status_code)
        assert hashlib.sha256(db.read_bytes()).hexdigest() == before_hash
        assert _domain_counts(db) == before_counts
        assert paths.repository.get(path_id).state == "draft"


def test_expired_owner_session_rejects_generation_before_model_or_database_write(tmp_path):
    app, sessions, paths, model, _, _, _, db = _make_app(tmp_path, lifetime=0)
    before_hash = hashlib.sha256(db.read_bytes()).hexdigest()
    with TestClient(app, base_url=OWNER_ORIGIN) as client:
        headers = _session_headers(client, sessions)
        response = client.post(
            "/api/v1/learning-paths/generate",
            json={"goal": "Build FraudShield"}, headers=headers,
        )
    assert response.status_code == 401
    assert paths.repository.list() == () and not model.calls
    assert _domain_counts(db)["learning_paths"] == 0
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before_hash


def test_authorized_owner_generation_persists_only_a_dlp_draft(tmp_path):
    app, sessions, paths, model, forge, projects, _, _ = _make_app(tmp_path)
    competencies_before = forge.competencies()
    evidence_before = forge.evidence_history(limit=100)
    reviews_before = forge.retention_reviews(limit=100)
    projects_before = projects.list()
    with TestClient(app, base_url=OWNER_ORIGIN) as client:
        headers = _session_headers(client, sessions)
        response = client.post(
            "/api/v1/learning-paths/generate",
            json={"goal": "Build FraudShield"}, headers=headers,
        )
    assert response.status_code == 200
    path_id = response.json()["path"]["path_id"]
    recovered = LearningPathService(paths.repository.path)
    detail = recovered.detail(path_id)
    assert detail["path"].state == "draft"
    assert detail["path"].current_version == 1
    assert recovered.repository.current_path_id() is None
    assert len(recovered.repository.list()) == 1
    assert len(model.calls) == 1
    assert projects.list() == projects_before == ()
    assert forge.competencies() == competencies_before
    assert forge.evidence_history(limit=100) == evidence_before == ()
    assert forge.retention_reviews(limit=100) == reviews_before == ()


def test_missing_generation_goal_fails_schema_validation_without_generation(tmp_path):
    app, sessions, paths, model, _, _, _, _ = _make_app(tmp_path)
    with TestClient(app, base_url=OWNER_ORIGIN) as client:
        headers = _session_headers(client, sessions)
        response = client.post("/api/v1/learning-paths/generate", json={}, headers=headers)
    assert response.status_code == 422
    assert paths.repository.list() == ()
    assert not model.calls


def test_conversation_creation_intent_cannot_bypass_owner_boundary(tmp_path):
    app, sessions, paths, model, forge, projects, stream_model, db = _make_app(
        tmp_path, conversation_routes=True,
    )
    before_hash = hashlib.sha256(db.read_bytes()).hexdigest()
    with TestClient(app, base_url=OWNER_ORIGIN) as client:
        ordinary = client.post("/api/v1/conversation/stream", json={"prompt": "What is 2 plus 2?"})
        rejected = client.post(
            "/api/v1/conversation/stream",
            json={"prompt": "Friday, create a learning path for DSA."},
            headers={"Origin": OWNER_ORIGIN},
        )
        assert ordinary.status_code == 200
        assert rejected.status_code == 401
        assert paths.repository.list() == ()
        assert not model.calls
        assert len(stream_model.calls) == 1
        assert hashlib.sha256(db.read_bytes()).hexdigest() == before_hash

        valid = _session_headers(client, sessions)
        cross_origin = {**valid, "Origin": "https://attacker.invalid"}
        rejected_cross_origin = client.post(
            "/api/v1/conversation/stream",
            json={"prompt": "Create a learning path for DSA."}, headers=cross_origin,
        )
        assert rejected_cross_origin.status_code == 403
        assert not model.calls and paths.repository.list() == ()

        accepted = client.post(
            "/api/v1/conversation/stream",
            json={"prompt": "Friday, create a learning path for DSA."}, headers=valid,
        )
    assert accepted.status_code == 200
    assert "Created" in accepted.text and len(paths.repository.list()) == 1
    assert len(model.calls) == 1
    assert projects.list() == ()
    assert forge.evidence_history(limit=100) == ()
