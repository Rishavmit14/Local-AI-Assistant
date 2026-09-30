import stat
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from local_ai_assistant.autonomy.service import ObjectiveService
from local_ai_assistant.career_forge.models import MasteryLevel
from local_ai_assistant.career_forge.service import CareerForgeService
from local_ai_assistant.history.models import TaskStatus
from local_ai_assistant.history.service import TaskHistoryService
from local_ai_assistant.history.store import TaskHistoryStore
from local_ai_assistant.interface.api import create_presentation_app
from local_ai_assistant.interface.conversation import FridayConversationService
from local_ai_assistant.interface.runtime import FridayRuntime
from local_ai_assistant.learning_paths import (
    CurriculumValidationError,
    CurriculumValidator,
    LearningPathService,
)
from local_ai_assistant.learning_paths.evidence import CompetencyEvidence
from local_ai_assistant.projects import ProjectService
from tests.fixtures.learning_path_curricula import curriculum


class SatisfiedEvidence:
    def competency_evidence(self, keys):
        return {key: CompetencyEvidence(key, MasteryLevel.APPLY_INDEPENDENTLY.value, "current", "scheduled", 3, (), False) for key in keys}


class SuccessfulProjectTaskHistory:
    def __init__(self):
        self.task = SimpleNamespace(task_id="task_project_1", status=TaskStatus.SUCCEEDED,
                                    final_commit="deadbeef", outcome="Validated capstone implementation",
                                    summary="All required checks passed")

    def get(self, task_id):
        return self.task if task_id == self.task.task_id else None

    def artifacts(self, task_id):
        return {"validations": [{"status": "passed"}], "reviews": [{"status": "passed"}]} if task_id == self.task.task_id else {}

    def summary(self, task_id):
        return {"affected_files": ["src/main.py", "tests/test_main.py"]}


class ProjectEvaluator:
    def __init__(self, response):
        self.response = response

    def chat(self, *_args, **_kwargs):
        return self.response


def project_curriculum():
    proposal = curriculum()
    for item in proposal["nodes"]:
        item["competency_key"] = "se.python"
    target = proposal["nodes"][-1]
    target["type"] = "capstone"
    target["competency_key"] = "se.python"
    proposal["milestones"] = [{
        "milestone_id": "capstone", "title": "Learning capstone", "node_id": target["node_id"],
        "project_ref": "fraudshield", "description": "Implement the assessed project.",
        "kind": "capstone", "assignment_reason": "Combine the taught concepts.",
        "competency_keys": ["se.python"], "prerequisite_node_ids": [proposal["prerequisites"][-1]["prerequisite_node_id"]],
        "expected_outcome": "A tested project artifact.", "evidence_expectations": ["Explain design and validation."],
    }]
    return proposal


def test_project_service_is_durable_idempotent_and_fail_closed(tmp_path):
    db = tmp_path / "private" / "projects.sqlite3"
    projects = ProjectService(db)
    assert stat.S_IMODE(db.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(db.stat().st_mode) == 0o600
    first = projects.assign("path:p1:v1:m1", "fraudshield", "Capstone", "Build it")
    assert projects.assign("path:p1:v1:m1", "fraudshield", "Capstone", "Build it") == first
    with pytest.raises(ValueError, match="bound"):
        projects.assign("path:p1:v1:m1", "fraudshield", "Different", "Build it")
    objective_id = projects.reserve_objective_id(first.project_id)
    assert ProjectService(db).reserve_objective_id(first.project_id) == objective_id
    projects.attach_mission(first.project_id, "se.python", "mission-1")
    with pytest.raises(ValueError, match="submitted"):
        projects.reserve_review_submission(first.project_id, "submission_1", "se.python", "mission-1")
    projects.attach_mission(first.project_id, "se.testing", "mission-2")
    projects.attach_task(first.project_id, objective_id, "task-1")
    projects.add_task_artifacts(first.project_id, "task-1", ["task:task-1:commit:abc:file:src/main.py"])
    submission = projects.reserve_review_submission(first.project_id, "submission_1", "se.python", "mission-1")
    assert projects.reserve_review_submission(first.project_id, "submission_1", "se.python", "mission-1") == submission
    projects.link_learning_evidence(first.project_id, "se.python", "evidence-1", submission["attempt_id"])
    with pytest.raises(ValueError, match="every assigned competency"):
        projects.record_review_result(first.project_id, complete=True)
    projects.link_learning_evidence(first.project_id, "se.testing", "evidence-2", submission["attempt_id"])
    assert projects.record_review_result(first.project_id, complete=True).state == "completed"
    assert ProjectService(db).get(first.project_id).state == "completed"


def test_learning_project_assignment_requires_valid_dlp_and_keeps_objectives_canonical(tmp_path):
    proposal = project_curriculum()
    CurriculumValidator().validate(proposal)
    paths = LearningPathService(tmp_path / "paths.sqlite3")
    path = paths.create(proposal)
    paths.activate(path.path_id)
    paths.evidence_provider = SatisfiedEvidence()
    forge = CareerForgeService(tmp_path / "career.sqlite3")
    projects = ProjectService(tmp_path / "projects.sqlite3")
    autonomy = ObjectiveService(tmp_path / "objectives.sqlite3")
    history = TaskHistoryService(TaskHistoryStore(tmp_path / "history.sqlite3"))
    runtime = FridayRuntime("project-lifecycle")
    app = create_presentation_app(runtime, FridayConversationService(object(), runtime),
                                  learning_paths=paths, career_forge=forge, projects=projects, autonomy=autonomy, task_history=history)
    with TestClient(app) as client:
        milestone_id = "capstone"
        projection = client.get(f"/api/v1/learning-paths/{path.path_id}/milestones/{milestone_id}")
        assert projection.status_code == 200
        assert projection.json()["can_assign"] is True
        assigned = client.post(f"/api/v1/learning-paths/{path.path_id}/milestones/{milestone_id}/assign",
                               json={"path_version": 1})
        assert assigned.status_code == 200, assigned.text
        project = assigned.json()
        assert project["state"] == "assigned"
        assert project["learning"]["path_version"] == 1
        assert client.post(f"/api/v1/learning-paths/{path.path_id}/milestones/{milestone_id}/assign",
                           json={"path_version": 1}).json()["project_id"] == project["project_id"]
        created = client.post(f"/api/v1/projects/{project['project_id']}/objective", json={})
        assert created.status_code == 200, created.text
        objective = created.json()["objective"]
        assert objective["state"] == "planning"
        assert created.json()["project"]["objective_id"] == objective["objective_id"]
        assert forge.mission_objective(project["mission_id"]).objective_id == objective["objective_id"]
        assert client.post(f"/api/v1/projects/{project['project_id']}/submit-artifacts").status_code == 409
        assert client.get(f"/api/v1/projects/{project['project_id']}").json()["state"] == "active"


def test_project_milestone_prerequisite_declaration_must_match_dag():
    proposal = project_curriculum()
    proposal["milestones"][0]["prerequisite_node_ids"] = [proposal["nodes"][0]["node_id"]]
    with pytest.raises(CurriculumValidationError, match="exactly match"):
        CurriculumValidator().validate(proposal)


@pytest.mark.parametrize(("assessment", "expected_state", "expected_evidence"), [
    ("ASSESSMENT: correct\nThe explanation connects outcome, implementation, and tests.", "completed", 1),
    ("ASSESSMENT: incorrect\nThe explanation does not describe the implementation.", "needs_revision", 0),
    ("ASSESSMENT: uncertain\nThe explanation is too vague to assess.", "needs_revision", 0),
])
def test_project_review_records_only_qualified_provenance_without_mastery_inflation(
    tmp_path, assessment, expected_state, expected_evidence,
):
    from local_ai_assistant.career_forge.models import TutorMode

    paths = LearningPathService(tmp_path / "paths.sqlite3")
    path = paths.create(project_curriculum())
    paths.activate(path.path_id)
    paths.evidence_provider = SatisfiedEvidence()
    forge = CareerForgeService(tmp_path / "career.sqlite3")
    projects = ProjectService(tmp_path / "projects.sqlite3")
    autonomy = ObjectiveService(tmp_path / "objectives.sqlite3")
    history = SuccessfulProjectTaskHistory()
    runtime = FridayRuntime("project-evidence")
    app = create_presentation_app(runtime, FridayConversationService(object(), runtime),
                                  learning_paths=paths, career_forge=forge, projects=projects,
                                  autonomy=autonomy, task_history=history,
                                  career_tutor_clients={TutorMode.REVIEW: ProjectEvaluator(assessment)})
    with TestClient(app) as client:
        assigned = client.post(f"/api/v1/learning-paths/{path.path_id}/milestones/capstone/assign",
                               json={"path_version": 1})
        assert assigned.status_code == 200, assigned.text
        project = assigned.json()
        objective = client.post(f"/api/v1/projects/{project['project_id']}/objective", json={}).json()["objective"]
        with autonomy._db() as db:
            db.execute("UPDATE objectives SET task_id=? WHERE objective_id=?", (history.task.task_id, objective["objective_id"]))
        submitted = client.post(f"/api/v1/projects/{project['project_id']}/submit-artifacts")
        assert submitted.status_code == 200, submitted.text
        response = client.post(f"/api/v1/projects/{project['project_id']}/review", json={
            "competency_key": "se.python", "submission_id": "submission_capstone_1",
            "explanation": "The tests cover expected behavior and the implementation satisfies the project outcome.",
        })
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["evaluation"] == assessment.split(":", 1)[1].splitlines()[0].strip()
        assert result["mastery_changed"] is False
        assert result["project"]["state"] == expected_state
        assert len(result["project"]["career_forge_evidence"]) == expected_evidence
        if expected_evidence:
            evidence = result["project"]["career_forge_evidence"][0]
            assert evidence["evidence_type"] == "project_milestone_assessment"
            assert "deadbeef" in evidence["artifact_ref"]
        assert next(item for item in forge.competencies() if item.competency.competency_id == "se.python").mastery is MasteryLevel.UNVERIFIED
        replay = client.post(f"/api/v1/projects/{project['project_id']}/review", json={
            "competency_key": "se.python", "submission_id": "submission_capstone_1",
            "explanation": "The tests cover expected behavior and the implementation satisfies the project outcome.",
        })
        assert replay.status_code == 200
        assert replay.json()["attempt"]["attempt_id"] == result["attempt"]["attempt_id"]
