import hashlib
import stat
import subprocess
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
from local_ai_assistant.isolation.owner_rollback import OwnerBrowserSessions
from local_ai_assistant.learning_paths import (
    CurriculumValidationError,
    CurriculumValidator,
    LearningPathService,
)
from local_ai_assistant.learning_paths.evidence import CompetencyEvidence
from local_ai_assistant.projects import ProjectService
from local_ai_assistant.projects.assessment import ordered_amount_tier_interpretation
from tests.fixtures.learning_path_curricula import curriculum

OWNER_ORIGIN = "http://127.0.0.1:5193"
OWNER_CREDENTIAL = "isolated-stage30-project-owner-test-credential"


def _owner_sessions():
    return OwnerBrowserSessions(hashlib.sha256(OWNER_CREDENTIAL.encode()).hexdigest())


def _owner_headers(client, sessions):
    session, csrf = sessions.unlock(OWNER_CREDENTIAL)
    assert session and csrf
    client.cookies.set("friday_project_session", session)
    return {"Origin": OWNER_ORIGIN, "X-Friday-CSRF": csrf}


class SatisfiedEvidence:
    def competency_evidence(self, keys):
        return {key: CompetencyEvidence(key, MasteryLevel.APPLY_INDEPENDENTLY.value, "current", "scheduled", 3, (), False) for key in keys}


class SuccessfulProjectTaskHistory:
    def __init__(self, tmp_path):
        repo = tmp_path / "reviewed-task-repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repo, check=True)
        (repo / "src").mkdir()
        (repo / "src/main.py").write_text("raise NotImplementedError\n")
        (repo / "ACCEPTANCE.md").write_text("Amount: 0 points through 50; 15 through 250; 30 through 1,000; otherwise 45.\n")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "baseline"], cwd=repo, check=True)
        base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
        (repo / "src/main.py").write_text("print('ready')\n")
        (repo / "MODEL_CARD.md").write_text("Reviewed model card\n")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "reviewed task"], cwd=repo, check=True)
        final = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
        self.task = SimpleNamespace(task_id="task_project_1", status=TaskStatus.SUCCEEDED,
                                    final_commit=final, starting_commit=base, repository=str(repo),
                                    outcome="Validated capstone implementation", summary="All required checks passed")

    def get(self, task_id):
        return self.task if task_id == self.task.task_id else None

    def artifacts(self, task_id):
        return {"validations": [{"status": "passed"}], "reviews": [{"status": "passed"}]} if task_id == self.task.task_id else {}

    def summary(self, task_id):
        return {"affected_files": ["src/main.py", "tests/test_main.py"]}


class ProjectEvaluator:
    def __init__(self, response):
        self.response = response
        self.prompts = []

    def chat(self, *args, **_kwargs):
        self.prompts.append(args[0])
        return self.response


class ArtifactProjectEvaluator:
    def __init__(self):
        self.prompts = []

    def chat(self, prompt, **_kwargs):
        self.prompts.append(prompt)
        if "return -1" in prompt:
            return "EVIDENCE: The source assigns a negative score to every row instead of evaluating the fraud flag.\nASSESSMENT: incorrect"
        return "EVIDENCE: The source maps the fraud flag to a stable binary score and explains the limitation.\nASSESSMENT: correct"


def test_ordered_project_tiers_and_final_verdict_are_unambiguous():
    from local_ai_assistant.interface.api import _parse_project_assessment

    tier = ordered_amount_tier_interpretation(
        "Amount: 0 points through 50; 15 through 250; 30 through 1,000; otherwise 45."
    )
    assert tier is not None and "At exact bounds 50, 250, 1000, the scores are 0, 15, 30" in tier
    assert _parse_project_assessment("ASSESSMENT: incorrect\nWait, this is correct.")[0].value == "uncertain"
    assert _parse_project_assessment("EVIDENCE: Exact values agree.\nASSESSMENT: correct")[0].value == "correct"


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
        projects.reserve_review_submission(first.project_id, "submission_1", "se.python", "mission-1",
                                           assessment_contract_fingerprint="0" * 64)
    projects.attach_mission(first.project_id, "se.testing", "mission-2")
    projects.attach_task(first.project_id, objective_id, "task-1")
    projects.add_task_artifacts(first.project_id, "task-1", ["task:task-1:commit:abc:file:src/main.py"])
    fingerprint = hashlib.sha256(b"stable assessment contract").hexdigest()
    submission = projects.reserve_review_submission(first.project_id, "submission_1", "se.python", "mission-1",
                                                    assessment_contract_fingerprint=fingerprint)
    assert projects.reserve_review_submission(first.project_id, "submission_1", "se.python", "mission-1",
                                              assessment_contract_fingerprint=fingerprint) == submission
    stored_submission = projects.review_submissions(first.project_id)[0]
    assert stored_submission["attempt_id"] == submission["attempt_id"]
    assert stored_submission["submission_kind"] == "validated_task"
    assert stored_submission["artifact_name"] is None
    assert stored_submission["artifact_sha256"] is None
    with pytest.raises(ValueError, match="different assessment contract"):
        projects.reserve_review_submission(first.project_id, "submission_1", "se.python", "mission-1",
                                           assessment_contract_fingerprint="1" * 64)
    projects.link_learning_evidence(first.project_id, "se.python", "evidence-1", submission["attempt_id"])
    with pytest.raises(ValueError, match="every assigned competency"):
        projects.record_review_result(first.project_id, complete=True)
    projects.link_learning_evidence(first.project_id, "se.testing", "evidence-2", submission["attempt_id"])
    assert projects.record_review_result(first.project_id, complete=True).state == "completed"
    assert ProjectService(db).get(first.project_id).state == "completed"


def test_project_service_migrates_review_provenance_from_schema_v1(tmp_path):
    import sqlite3

    db_path = tmp_path / "projects-v1.sqlite3"
    with sqlite3.connect(db_path) as db:
        db.executescript("""
            CREATE TABLE projects (project_id TEXT PRIMARY KEY);
            CREATE TABLE project_review_submissions (
                project_id TEXT NOT NULL REFERENCES projects(project_id),
                submission_id TEXT NOT NULL, competency_id TEXT NOT NULL,
                mission_id TEXT NOT NULL, attempt_id TEXT NOT NULL UNIQUE,
                PRIMARY KEY(project_id,submission_id)
            );
            CREATE TABLE project_schema_version (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1), version INTEGER NOT NULL
            );
            INSERT INTO project_schema_version VALUES(1,1);
        """)

    ProjectService(db_path)
    with sqlite3.connect(db_path) as db:
        version = db.execute("SELECT version FROM project_schema_version WHERE singleton=1").fetchone()[0]
        columns = {row[1] for row in db.execute("PRAGMA table_info(project_review_submissions)")}
    assert version == ProjectService.SCHEMA_VERSION == 3
    assert {
        "assessment_contract_version", "assessment_contract_fingerprint", "evaluator",
        "submission_kind", "artifact_name", "artifact_sha256",
    } <= columns


def test_project_service_migrates_schema_v2_owner_artifact_provenance(tmp_path):
    import sqlite3

    db_path = tmp_path / "projects-v2.sqlite3"
    with sqlite3.connect(db_path) as db:
        db.executescript("""
            CREATE TABLE projects (project_id TEXT PRIMARY KEY);
            CREATE TABLE project_review_submissions (
                project_id TEXT NOT NULL REFERENCES projects(project_id),
                submission_id TEXT NOT NULL, competency_id TEXT NOT NULL,
                mission_id TEXT NOT NULL, attempt_id TEXT NOT NULL UNIQUE,
                assessment_contract_version TEXT NOT NULL DEFAULT 'project_milestone_assessment_v1',
                assessment_contract_fingerprint TEXT NOT NULL DEFAULT '',
                evaluator TEXT NOT NULL DEFAULT 'local_qwen_reviewer',
                PRIMARY KEY(project_id,submission_id)
            );
            CREATE TABLE project_schema_version (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1), version INTEGER NOT NULL
            );
            INSERT INTO project_schema_version VALUES(1,2);
        """)

    ProjectService(db_path)
    with sqlite3.connect(db_path) as db:
        version = db.execute("SELECT version FROM project_schema_version WHERE singleton=1").fetchone()[0]
        columns = {row[1] for row in db.execute("PRAGMA table_info(project_review_submissions)")}
    assert version == ProjectService.SCHEMA_VERSION == 3
    assert {"submission_kind", "artifact_name", "artifact_sha256"} <= columns


def test_project_service_reconciles_v2_marker_after_compatible_rollback(tmp_path):
    import sqlite3

    db_path = tmp_path / "projects-v2-rollback.sqlite3"
    with sqlite3.connect(db_path) as db:
        db.executescript("""
            CREATE TABLE projects (project_id TEXT PRIMARY KEY);
            CREATE TABLE project_review_submissions (
                project_id TEXT NOT NULL REFERENCES projects(project_id),
                submission_id TEXT NOT NULL, competency_id TEXT NOT NULL,
                mission_id TEXT NOT NULL, attempt_id TEXT NOT NULL UNIQUE,
                assessment_contract_version TEXT NOT NULL DEFAULT 'project_milestone_assessment_v1',
                assessment_contract_fingerprint TEXT NOT NULL DEFAULT '',
                evaluator TEXT NOT NULL DEFAULT 'local_qwen_reviewer',
                submission_kind TEXT NOT NULL DEFAULT 'validated_task',
                artifact_name TEXT,
                artifact_sha256 TEXT,
                PRIMARY KEY(project_id,submission_id)
            );
            CREATE TABLE project_schema_version (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1), version INTEGER NOT NULL
            );
            INSERT INTO project_schema_version VALUES(1,2);
        """)

    ProjectService(db_path)
    with sqlite3.connect(db_path) as db:
        version = db.execute("SELECT version FROM project_schema_version WHERE singleton=1").fetchone()[0]
        columns = {row[1] for row in db.execute("PRAGMA table_info(project_review_submissions)")}
    assert version == ProjectService.SCHEMA_VERSION == 3
    assert {"submission_kind", "artifact_name", "artifact_sha256"} <= columns


def test_project_v2_migration_rolls_back_all_columns_on_failure(tmp_path):
    import sqlite3

    db_path = tmp_path / "projects-v2-interrupted.sqlite3"
    with sqlite3.connect(db_path) as db:
        db.executescript("""
            CREATE TABLE projects (project_id TEXT PRIMARY KEY);
            CREATE TABLE project_review_submissions (
                project_id TEXT NOT NULL REFERENCES projects(project_id),
                submission_id TEXT NOT NULL, competency_id TEXT NOT NULL,
                mission_id TEXT NOT NULL, attempt_id TEXT NOT NULL UNIQUE,
                assessment_contract_version TEXT NOT NULL DEFAULT 'project_milestone_assessment_v1',
                assessment_contract_fingerprint TEXT NOT NULL DEFAULT '',
                evaluator TEXT NOT NULL DEFAULT 'local_qwen_reviewer',
                PRIMARY KEY(project_id,submission_id)
            );
            CREATE TABLE project_schema_version (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1), version INTEGER NOT NULL
            );
            INSERT INTO project_schema_version VALUES(1,2);
            CREATE TRIGGER reject_version_bump BEFORE UPDATE ON project_schema_version
                BEGIN SELECT RAISE(ABORT, 'injected migration failure'); END;
        """)

    with pytest.raises(sqlite3.IntegrityError, match="injected migration failure"):
        ProjectService(db_path)
    with sqlite3.connect(db_path) as db:
        version = db.execute("SELECT version FROM project_schema_version WHERE singleton=1").fetchone()[0]
        columns = {row[1] for row in db.execute("PRAGMA table_info(project_review_submissions)")}
    assert version == 2
    assert not {"submission_kind", "artifact_name", "artifact_sha256"} & columns


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
    sessions = _owner_sessions()
    app = create_presentation_app(runtime, FridayConversationService(object(), runtime),
                                  learning_paths=paths, career_forge=forge, projects=projects, autonomy=autonomy,
                                  task_history=history, project_execution_sessions=sessions,
                                  project_execution_allowed_origins=(OWNER_ORIGIN,))
    with TestClient(app, base_url=OWNER_ORIGIN) as client:
        milestone_id = "capstone"
        projection = client.get(f"/api/v1/learning-paths/{path.path_id}/milestones/{milestone_id}")
        assert projection.status_code == 200
        assert projection.json()["can_assign"] is True
        owner_headers = _owner_headers(client, sessions)
        assigned = client.post(f"/api/v1/learning-paths/{path.path_id}/milestones/{milestone_id}/assign",
                               json={"path_version": 1}, headers=owner_headers)
        assert assigned.status_code == 200, assigned.text
        project = assigned.json()
        assert project["state"] == "assigned"
        assert project["learning"]["path_version"] == 1
        assert client.post(f"/api/v1/learning-paths/{path.path_id}/milestones/{milestone_id}/assign",
                           json={"path_version": 1}, headers=owner_headers).json()["project_id"] == project["project_id"]
        created = client.post(f"/api/v1/projects/{project['project_id']}/objective", json={}, headers=owner_headers)
        assert created.status_code == 200, created.text
        objective = created.json()["objective"]
        assert objective["state"] == "planning"
        assert created.json()["project"]["objective_id"] == objective["objective_id"]
        assert forge.mission_objective(project["mission_id"]).objective_id == objective["objective_id"]
        assert client.post(f"/api/v1/projects/{project['project_id']}/submit-artifacts", headers=owner_headers).status_code == 409
        assert client.get(f"/api/v1/projects/{project['project_id']}").json()["state"] == "active"


def test_owner_project_learning_artifact_review_is_authorized_idempotent_and_durable(tmp_path):
    from local_ai_assistant.career_forge.models import TutorMode
    from local_ai_assistant.learning_paths.evidence import CareerForgeEvidenceProjection

    proposal = project_curriculum()
    paths = LearningPathService(tmp_path / "paths.sqlite3")
    path = paths.create(proposal)
    paths.activate(path.path_id)
    paths.evidence_provider = SatisfiedEvidence()
    forge = CareerForgeService(tmp_path / "career.sqlite3")
    projects = ProjectService(tmp_path / "projects.sqlite3")
    autonomy = ObjectiveService(tmp_path / "objectives.sqlite3")
    sessions = _owner_sessions()
    evaluator = ArtifactProjectEvaluator()
    runtime = FridayRuntime("project-artifact-review")
    app = create_presentation_app(
        runtime, FridayConversationService(object(), runtime), learning_paths=paths,
        career_forge=forge, projects=projects, autonomy=autonomy,
        project_execution_sessions=sessions, project_execution_allowed_origins=(OWNER_ORIGIN,),
        career_tutor_clients={TutorMode.REVIEW: evaluator},
    )
    project_id = None
    with TestClient(app, base_url=OWNER_ORIGIN) as client:
        headers = _owner_headers(client, sessions)
        assigned = client.post(
            f"/api/v1/learning-paths/{path.path_id}/milestones/capstone/assign",
            json={"path_version": 1}, headers=headers,
        )
        assert assigned.status_code == 200, assigned.text
        project_id = assigned.json()["project_id"]
        started = client.post(f"/api/v1/projects/{project_id}/objective", json={}, headers=headers)
        assert started.status_code == 200, started.text
        assert started.json()["project"]["state"] == "active"
        assert started.json()["objective"]["task_id"] is None

        body = {
            "competency_key": "se.python", "submission_id": "stage30_wrong_artifact",
            "artifact_name": "fraudshield.py",
            "content": "def fraud_score(row):\n    return -1\n",
            "explanation": "Every record receives a negative score.",
        }
        before = (len(forge.evidence_history(limit=100)), projects.review_submissions(project_id))
        denied = client.post(
            f"/api/v1/projects/{project_id}/submit-learning-artifact", json=body,
            headers={"Origin": OWNER_ORIGIN},
        )
        assert denied.status_code == 401
        assert (len(forge.evidence_history(limit=100)), projects.review_submissions(project_id)) == before

        incorrect = client.post(
            f"/api/v1/projects/{project_id}/submit-learning-artifact", json=body, headers=headers,
        )
        assert incorrect.status_code == 200, incorrect.text
        assert incorrect.json()["evaluation"] == "incorrect"
        assert incorrect.json()["evidence_id"] is None
        assert incorrect.json()["mastery_changed"] is False
        assert incorrect.json()["project"]["state"] == "needs_revision"
        assert incorrect.json()["project"]["career_forge_evidence"] == []

        corrected = {
            **body,
            "submission_id": "stage30_correct_artifact",
            "content": "def fraud_score(row):\n    return 1 if row.get('is_fraud') else 0\n",
            "explanation": "The function maps the fraud flag to a binary score. It has not been executed; a validation test should cover both flag values.",
        }
        accepted = client.post(
            f"/api/v1/projects/{project_id}/submit-learning-artifact", json=corrected, headers=headers,
        )
        assert accepted.status_code == 200, accepted.text
        result = accepted.json()
        assert result["evaluation"] == "correct"
        assert result["mastery_changed"] is False
        assert result["evidence_id"]
        assert result["project"]["state"] == "completed"
        assert len(result["project"]["career_forge_evidence"]) == 1
        saved_review = next(
            item for item in result["project"]["career_forge_reviews"]
            if item["submission_id"] == "stage30_correct_artifact"
        )
        assert saved_review["submission_kind"] == "owner_artifact"
        assert saved_review["artifact_name"] == "fraudshield.py"
        assert saved_review["artifact_sha256"] == hashlib.sha256(corrected["content"].encode()).hexdigest()
        assert projects.get(project_id).task_id is None
        assert len(evaluator.prompts) == 2
        assert "not executed by Friday" in evaluator.prompts[-1]
        assert next(item for item in forge.competencies() if item.competency.competency_id == "se.python").mastery is MasteryLevel.UNVERIFIED

        replay = client.post(
            f"/api/v1/projects/{project_id}/submit-learning-artifact", json=corrected, headers=headers,
        )
        assert replay.status_code == 200, replay.text
        assert replay.json()["attempt"]["attempt_id"] == result["attempt"]["attempt_id"]
        assert replay.json()["evidence_id"] == result["evidence_id"]
        assert len(evaluator.prompts) == 2
        assert len(projects.review_submissions(project_id)) == 2
        assert len(forge.project_evidence(project_id)) == 1
        old_incorrect_replay = client.post(
            f"/api/v1/projects/{project_id}/submit-learning-artifact", json=body, headers=headers,
        )
        assert old_incorrect_replay.status_code == 200, old_incorrect_replay.text
        assert old_incorrect_replay.json()["evaluation"] == "incorrect"
        assert old_incorrect_replay.json()["project"]["state"] == "completed"
        assert len(evaluator.prompts) == 2

    # Recreate every persistence authority and the API app to prove restart recovery.
    recovered_forge = CareerForgeService(tmp_path / "career.sqlite3")
    recovered_paths = LearningPathService(
        tmp_path / "paths.sqlite3", evidence_provider=CareerForgeEvidenceProjection(recovered_forge),
    )
    recovered_projects = ProjectService(tmp_path / "projects.sqlite3")
    recovered_autonomy = ObjectiveService(tmp_path / "objectives.sqlite3")
    recovered_sessions = _owner_sessions()
    recovered_runtime = FridayRuntime("project-artifact-review-restarted")
    recovered_app = create_presentation_app(
        recovered_runtime,
        FridayConversationService(object(), recovered_runtime),
        learning_paths=recovered_paths, career_forge=recovered_forge, projects=recovered_projects,
        autonomy=recovered_autonomy, project_execution_sessions=recovered_sessions,
        project_execution_allowed_origins=(OWNER_ORIGIN,),
        career_tutor_clients={TutorMode.REVIEW: ArtifactProjectEvaluator()},
    )
    with TestClient(recovered_app, base_url=OWNER_ORIGIN) as recovered_client:
        _owner_headers(recovered_client, recovered_sessions)
        recovered = recovered_client.get(f"/api/v1/projects/{project_id}")
        assert recovered.status_code == 200
        assert recovered.json()["state"] == "completed"
        assert recovered.json()["career_forge_reviews"][-1]["artifact_sha256"] == saved_review["artifact_sha256"]
        assert recovered.json()["career_forge_evidence"][-1]["evidence_id"] == result["evidence_id"]
        sequence = recovered_client.get(f"/api/v1/learning-paths/{path.path_id}/sequence")
        assert sequence.status_code == 200 and sequence.json()["evidence_available"] is True


def test_project_milestone_prerequisite_declaration_must_match_dag():
    proposal = project_curriculum()
    proposal["milestones"][0]["prerequisite_node_ids"] = [proposal["nodes"][0]["node_id"]]
    with pytest.raises(CurriculumValidationError, match="exactly match"):
        CurriculumValidator().validate(proposal)


@pytest.mark.parametrize(("assessment", "expected_state", "expected_evidence"), [
    ("EVIDENCE: The explanation connects outcome, implementation, and tests.\nASSESSMENT: correct", "completed", 1),
    ("EVIDENCE: The explanation does not describe the implementation.\nASSESSMENT: incorrect", "needs_revision", 0),
    ("EVIDENCE: The explanation is too vague to assess.\nASSESSMENT: uncertain", "needs_revision", 0),
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
    history = SuccessfulProjectTaskHistory(tmp_path)
    runtime = FridayRuntime("project-evidence")
    sessions = _owner_sessions()
    evaluator = ProjectEvaluator(assessment)
    app = create_presentation_app(runtime, FridayConversationService(object(), runtime),
                                  learning_paths=paths, career_forge=forge, projects=projects,
                                  autonomy=autonomy, task_history=history,
                                  project_execution_sessions=sessions,
                                  project_execution_allowed_origins=(OWNER_ORIGIN,),
                                  career_tutor_clients={TutorMode.REVIEW: evaluator})
    with TestClient(app, base_url=OWNER_ORIGIN) as client:
        owner_headers = _owner_headers(client, sessions)
        assigned = client.post(f"/api/v1/learning-paths/{path.path_id}/milestones/capstone/assign",
                               json={"path_version": 1}, headers=owner_headers)
        assert assigned.status_code == 200, assigned.text
        project = assigned.json()
        objective = client.post(f"/api/v1/projects/{project['project_id']}/objective", json={}, headers=owner_headers).json()["objective"]
        with autonomy._db() as db:
            db.execute("UPDATE objectives SET task_id=? WHERE objective_id=?", (history.task.task_id, objective["objective_id"]))
        submitted = client.post(f"/api/v1/projects/{project['project_id']}/submit-artifacts", headers=owner_headers)
        assert submitted.status_code == 200, submitted.text
        assert {item["artifact_ref"].rsplit(":file:", 1)[-1] for item in submitted.json()["artifacts"]} == {
            "src/main.py", "MODEL_CARD.md",
        }
        response = client.post(f"/api/v1/projects/{project['project_id']}/review", json={
            "competency_key": "se.python", "submission_id": "submission_capstone_1",
            "explanation": "The tests cover expected behavior and the implementation satisfies the project outcome.",
        }, headers=owner_headers)
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["evaluation"] == assessment.rsplit(":", 1)[1].strip()
        assert result["mastery_changed"] is False
        assert "15 through 250" in evaluator.prompts[0]
        assert "At exact bounds" in evaluator.prompts[0]
        assert result["project"]["state"] == expected_state
        assert len(result["project"]["career_forge_evidence"]) == expected_evidence
        assert len(result["project"]["career_forge_reviews"]) == 1
        reviewer_record = result["project"]["career_forge_reviews"][0]
        assert reviewer_record["evaluation"] == result["evaluation"]
        assert reviewer_record["feedback"] == result["feedback"]
        assert reviewer_record["assessment_contract_version"] == "project_milestone_assessment_v1"
        assert len(reviewer_record["assessment_contract_fingerprint"]) == 64
        assert reviewer_record["evaluator"] == "local_qwen_reviewer"
        assert reviewer_record["attempt_id"] == result["attempt"]["attempt_id"]
        if expected_evidence:
            evidence = result["project"]["career_forge_evidence"][0]
            assert evidence["evidence_type"] == "project_milestone_assessment"
            assert history.task.final_commit in evidence["artifact_ref"]
            assert reviewer_record["evidence_id"] == evidence["evidence_id"] == result["evidence_id"]
        else:
            assert reviewer_record["evidence_id"] is None
            assert result["evidence_id"] is None
        assert next(item for item in forge.competencies() if item.competency.competency_id == "se.python").mastery is MasteryLevel.UNVERIFIED
        replay = client.post(f"/api/v1/projects/{project['project_id']}/review", json={
            "competency_key": "se.python", "submission_id": "submission_capstone_1",
            "explanation": "The tests cover expected behavior and the implementation satisfies the project outcome.",
        }, headers=owner_headers)
        assert replay.status_code == 200
        assert replay.json()["attempt"]["attempt_id"] == result["attempt"]["attempt_id"]
        recovered = client.get(f"/api/v1/projects/{project['project_id']}").json()
        assert recovered["career_forge_reviews"] == result["project"]["career_forge_reviews"]
        assert len(forge.project_evidence(project["project_id"])) == expected_evidence
        assert projects.review_submissions(project["project_id"])[0]["assessment_contract_fingerprint"] == reviewer_record["assessment_contract_fingerprint"]
