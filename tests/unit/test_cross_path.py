"""Canonical relationship resolution, negative controls, and reconstruction."""

import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from local_ai_assistant.career_forge.models import AttemptEvaluation, MasteryLevel, TutorMode
from local_ai_assistant.career_forge.practice_lab import PracticeLabService
from local_ai_assistant.career_forge.service import CareerForgeService
from local_ai_assistant.interface.api import create_presentation_app
from local_ai_assistant.interface.context_attachments import ContextAttachmentStore
from local_ai_assistant.interface.conversation import FridayConversationService
from local_ai_assistant.interface.cross_path import CrossPathResolver
from local_ai_assistant.interface.runtime import FridayRuntime
from local_ai_assistant.learning_paths.evidence import CareerForgeEvidenceProjection
from local_ai_assistant.learning_paths.service import LearningPathService
from local_ai_assistant.projects.service import ProjectService
from tests.fixtures.learning_path_curricula import curriculum


def _services(tmp_path):
    forge = CareerForgeService(tmp_path / "forge.sqlite3")
    paths = LearningPathService(tmp_path / "paths.sqlite3", evidence_provider=CareerForgeEvidenceProjection(forge))
    projects = ProjectService(tmp_path / "projects.sqlite3")
    proposal = curriculum()
    for node in proposal["nodes"]:
        node["competency_key"] = "se.python"
    path = paths.create(proposal)
    return forge, paths, projects, path


def test_learn_competency_and_unrelated_project_are_distinct(tmp_path):
    forge, paths, projects, path = _services(tmp_path)
    resolver = CrossPathResolver(paths, forge, projects)
    project = projects.assign("assigned", "fraudshield", "FraudShield", "Explain the implementation")
    view = resolver.resolve("learning_path", path.path_id)
    assert view["nodes"][0]["competency_id"] == "se.python"
    assert view["nodes"][0]["competency"]["mastery"] == "unverified"
    assert resolver.resolve("project", project.project_id)["accepted_evidence"] == []
    assert resolver.resolve("competency", "se.python")["projects"] == []
    with pytest.raises(KeyError):
        resolver.resolve("competency", "unknown")
    with pytest.raises(ValueError):
        resolver.resolve("unsupported", "se.python")


def test_project_evidence_chain_is_exact_and_persists(tmp_path):
    forge, paths, projects, path = _services(tmp_path)
    project = projects.assign("assigned", "fraudshield", "FraudShield", "Explain the implementation")
    mission = forge.start_project_mission("se.python", "FraudShield", project_id=project.project_id,
                                          path_id=path.path_id, path_version=1, node_id="arrays")
    projects.attach_mission(project.project_id, "se.python", mission.mission_id)
    resolver = CrossPathResolver(paths, forge, projects)
    assigned = resolver.resolve("competency", "se.python")["projects"]
    assert assigned[0]["relation"] == "assigned_practice"
    objective_id = projects.reserve_objective_id(project.project_id)
    projects.attach_task(project.project_id, objective_id, "task_1")
    artifacts = projects.add_task_artifacts(project.project_id, "task_1", ["task:task_1:file:src/main.py"])
    submission = projects.reserve_review_submission(project.project_id, "submission_1", "se.python",
                                                      mission.mission_id, assessment_contract_fingerprint="a" * 64)
    attempt = forge.record_attempt(mission.mission_id, "project-question", "I tested the implementation",
                                   mode=TutorMode.TEACH_BACK, attempt_id=submission["attempt_id"])
    reference = "project:" + project.project_id + ":" + json.dumps({
        "task_id": "task_1", "final_commit": "f" * 40,
        "artifact_ids": [item.artifact_id for item in artifacts],
    }, separators=(",", ":"))
    forge.evaluate_attempt(attempt.attempt_id, AttemptEvaluation.CORRECT, "Correct",
                           evidence_type="project_milestone_assessment", artifact_ref=reference)
    evidence_id = forge.evidence_for_attempt(attempt.attempt_id)
    projects.link_learning_evidence(project.project_id, "se.python", evidence_id, attempt.attempt_id)
    projects.record_review_result(project.project_id, complete=True)
    restarted = CrossPathResolver(
        LearningPathService(tmp_path / "paths.sqlite3", evidence_provider=CareerForgeEvidenceProjection(
            CareerForgeService(tmp_path / "forge.sqlite3"))),
        CareerForgeService(tmp_path / "forge.sqlite3"), ProjectService(tmp_path / "projects.sqlite3"),
    )
    view = restarted.resolve("project", project.project_id)
    assert view["accepted_evidence"][0]["evidence_id"] == evidence_id
    assert view["accepted_evidence"][0]["task_commit"] == "f" * 40
    assert restarted.resolve("competency", "se.python")["projects"][0]["relation"] == "contributed_evidence"
    assert restarted.resolve("evidence", evidence_id)["focus_evidence_id"] == evidence_id
    assert restarted.resolve("project", project.project_id)["competencies"][0]["mastery"] == "unverified"


def test_forged_project_evidence_binding_is_not_exposed(tmp_path):
    forge, paths, projects, path = _services(tmp_path)
    project = projects.assign("assigned", "fraudshield", "FraudShield", "Explain")
    mission = forge.start_project_mission("se.python", "FraudShield", project_id=project.project_id,
                                          path_id=path.path_id, path_version=1, node_id="arrays")
    projects.attach_mission(project.project_id, "se.python", mission.mission_id)
    objective_id = projects.reserve_objective_id(project.project_id)
    projects.attach_task(project.project_id, objective_id, "task_1")
    projects.add_task_artifacts(project.project_id, "task_1", ["task:task_1:file:src/main.py"])
    submission = projects.reserve_review_submission(project.project_id, "submission_1", "se.python",
                                                      mission.mission_id, assessment_contract_fingerprint="a" * 64)
    attempt = forge.record_attempt(mission.mission_id, "project-question", "Explanation",
                                   mode=TutorMode.TEACH_BACK, attempt_id=submission["attempt_id"])
    forge.evaluate_attempt(attempt.attempt_id, AttemptEvaluation.CORRECT, "Correct",
                           evidence_type="project_milestone_assessment",
                           artifact_ref=f"project:{project.project_id}:" + json.dumps({
                               "task_id": "task_other", "final_commit": "f" * 40, "artifact_ids": [],
                           }))
    projects.link_learning_evidence(project.project_id, "se.python",
                                    forge.evidence_for_attempt(attempt.attempt_id), attempt.attempt_id)
    assert CrossPathResolver(paths, forge, projects).resolve("project", project.project_id)["accepted_evidence"] == []


def test_selected_file_review_and_interview_keep_distinct_provenance(tmp_path):
    forge, paths, projects, _ = _services(tmp_path)
    source_root = tmp_path / "source"
    source_root.mkdir()
    source = source_root / "defaults.py"
    source.write_text("def value(items=[]):\n    return items\n")
    lab = PracticeLabService(forge, tmp_path / "lab", source_roots=(source_root,))
    canonical, content, version = lab._read_source_file(str(source))
    mission = forge.start_mission("se.python", "Explain selected code")
    attempt = forge.record_attempt(mission.mission_id, "code_file:test", "The list persists",
                                   mode=TutorMode.CHALLENGE)
    source_ref = "local_file:" + json.dumps({
        "path": str(canonical), "version": version,
        "source_hash": hashlib.sha256(content.encode()).hexdigest(),
        "selected_hash": hashlib.sha256("\n".join(content.splitlines()).encode()).hexdigest(),
        "range": [1, 2], "symbol": "value", "question_id": "code_file:test",
    })
    forge.evaluate_attempt(attempt.attempt_id, AttemptEvaluation.CORRECT, "Correct",
                           evidence_type="code_explanation", artifact_ref=source_ref)
    evidence_id = forge.evidence_for_attempt(attempt.attempt_id)
    resolver = CrossPathResolver(paths, forge, projects, lab)
    evidence = resolver.resolve("evidence", evidence_id)["evidence"][0]
    assert evidence["selected_source"]["status"] == "current"
    assert evidence["selected_source"]["range"] == [1, 2]
    forge.advance_mastery("se.python", MasteryLevel.RECOGNIZE, evidence_id=evidence_id)
    review = next(item for item in forge.retention_reviews(limit=100) if item.evidence_id == evidence_id)
    explained = resolver.resolve("review", review.review_id)
    assert explained["focus_review_id"] == review.review_id
    assert explained["reviews"][0]["evidence_id"] == evidence_id
    assert explained["evidence"][0]["mastery_advance_to"] == "recognize"
    assert explained["reviews"][0]["due"] is False
    assert explained["current_due_review_ids"] == []
    store = ContextAttachmentStore(tmp_path / "contexts.sqlite3", paths, projects, resolver)
    selected_attachment = store.create("owner", "evidence", evidence_id)
    assert selected_attachment["snapshot"]["kind"] == "evidence"
    assert selected_attachment["status"] == "current"
    source.write_text("def value(items=None):\n    return items\n")
    assert resolver.resolve("evidence", evidence_id)["evidence"][0]["selected_source"]["status"] == "stale"
    assert store.get("owner", selected_attachment["attachment_id"])["status"] == "stale"
    with pytest.raises(ValueError):
        store.bind("owner", [selected_attachment["attachment_id"]], "Explain this evidence")
    interview = forge.start_mission(forge.next_competency().competency_id, "Interview")
    answer = forge.record_attempt(interview.mission_id, "interview:question", "I isolate state",
                                  mode=TutorMode.INTERVIEW)
    forge.evaluate_attempt(answer.attempt_id, AttemptEvaluation.CORRECT, "Correct",
                           evidence_type="interview_response")
    interview_id = forge.evidence_for_attempt(answer.attempt_id)
    assert resolver.resolve("evidence", interview_id)["evidence"][0]["source_kind"] == "interview"


def test_relationship_api_requires_owner_session(tmp_path):
    forge, paths, projects, path = _services(tmp_path)

    class Sessions:
        @staticmethod
        def principal(session, csrf=None):
            return "owner" if session == "session" else None

    class Model:
        def stream_chat(self, *_args, **_kwargs):
            yield "ok"

    runtime = FridayRuntime("cross-path")
    client = TestClient(create_presentation_app(
        runtime, FridayConversationService(Model(), runtime),
        cross_path=CrossPathResolver(paths, forge, projects), project_execution_sessions=Sessions(),
    ), base_url="http://127.0.0.1:8766")
    url = f"/api/v1/relationships/learning_path/{path.path_id}"
    assert client.get(url).status_code == 401
    client.cookies.set("friday_project_session", "session")
    assert client.get(url).json()["nodes"][0]["competency_id"] == "se.python"
    assert client.get("/api/v1/relationships/competency/unknown").status_code == 404


def test_attached_learn_context_passes_bounded_canonical_relations_to_conversation(tmp_path):
    forge, paths, projects, path = _services(tmp_path)
    resolver = CrossPathResolver(paths, forge, projects)
    store = ContextAttachmentStore(tmp_path / "contexts.sqlite3", paths, projects, resolver)

    class Sessions:
        @staticmethod
        def principal(session, csrf=None):
            return "owner" if session == "session" and csrf in {None, "csrf"} else None

    class Model:
        def __init__(self):
            self.prompts = []

        def stream_chat(self, prompt, system_prompt="", **_kwargs):
            self.prompts.append((prompt, system_prompt))
            yield "No assessed evidence is recorded yet."

    model = Model()
    runtime = FridayRuntime("cross-path-conversation")
    client = TestClient(create_presentation_app(
        runtime, FridayConversationService(model, runtime), context_attachments=store,
        cross_path=resolver, project_execution_sessions=Sessions(),
        project_execution_allowed_origins=("http://127.0.0.1:5191",),
    ), base_url="http://127.0.0.1:8766")
    client.cookies.set("friday_project_session", "session")
    headers = {"Origin": "http://127.0.0.1:5191", "X-Friday-CSRF": "csrf"}
    attachment = client.post("/api/v1/conversation/attachments", headers=headers,
                             json={"kind": "learning_path", "source_id": path.path_id}).json()
    response = client.post("/api/v1/conversation/stream", headers=headers,
                           json={"prompt": "Explain this path to me.",
                                 "attachment_ids": [attachment["attachment_id"]]})
    assert response.status_code == 200
    assert "se.python" in model.prompts[0][1]
    assert "Relationship fields are server-resolved read-only provenance" in model.prompts[0][1]
    assert "No assessed evidence" in response.text
    assert store.history("owner")[0]["attachments"][0]["source_id"] == path.path_id
    assert resolver.resolve("competency", "se.python")["mastery"] == "unverified"
    fresh = client.post("/api/v1/conversation/attachments", headers=headers,
                        json={"kind": "learning_path", "source_id": path.path_id}).json()
    factual = client.post("/api/v1/conversation/stream", headers=headers,
                          json={"prompt": "What evidence supports this competency?",
                                "attachment_ids": [fresh["attachment_id"]]})
    assert factual.status_code == 200
    assert "No assessed Career Forge evidence" in factual.text
    assert len(model.prompts) == 1
