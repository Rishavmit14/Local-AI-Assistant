import json
import stat

import pytest
from fastapi.testclient import TestClient

from local_ai_assistant.career_forge.service import CareerForgeService
from local_ai_assistant.interface.api import create_presentation_app
from local_ai_assistant.interface.conversation import FridayConversationService
from local_ai_assistant.interface.runtime import FridayRuntime
from local_ai_assistant.learning_paths import (
    CurriculumValidationError,
    CurriculumValidator,
    LearningPathService,
)
from local_ai_assistant.learning_paths.evidence import (
    CareerForgeEvidenceProjection,
    CompetencyEvidence,
)
from local_ai_assistant.learning_paths.service import (
    CurriculumGenerationError,
    LocalCurriculumGenerator,
)
from tests.fixtures.learning_path_curricula import curriculum


@pytest.mark.parametrize("kind", ["dsa", "genai", "nlp_deadline"])
def test_representative_curricula_validate_with_stable_topological_order(kind):
    proposal = curriculum(kind)
    validator = CurriculumValidator()
    assert validator.validate(proposal) == validator.validate(proposal)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p["prerequisites"].append(
            {"prerequisite_node_id": "arrays", "node_id": "arrays"}
        ),
        lambda p: p["prerequisites"].append(
            {"prerequisite_node_id": "missing", "node_id": "arrays"}
        ),
        lambda p: p["nodes"].append(dict(p["nodes"][0])),
        lambda p: p["modules"].append(dict(p["modules"][0])),
        lambda p: p["nodes"][0].update(module_id="missing"),
        lambda p: p["milestones"].append(
            {"milestone_id": "broken", "title": "Broken", "node_id": "missing"}
        ),
        lambda p: p["prerequisites"].extend(
            [
                {"prerequisite_node_id": "arrays", "node_id": "pointers"},
                {"prerequisite_node_id": "pointers", "node_id": "arrays"},
            ]
        ),
    ],
)
def test_invalid_graph_and_references_fail_closed(mutate):
    proposal = curriculum()
    mutate(proposal)
    with pytest.raises(CurriculumValidationError):
        CurriculumValidator().validate(proposal)


def test_empty_oversized_and_malformed_curricula_fail_closed():
    validator = CurriculumValidator()
    with pytest.raises(CurriculumValidationError):
        validator.validate({})
    too_many = curriculum()
    too_many["nodes"] *= 41
    with pytest.raises(CurriculumValidationError):
        validator.validate(too_many)
    too_large = curriculum()
    too_large["nodes"][0]["objectives"] = ["x" * 130_000]
    with pytest.raises(CurriculumValidationError):
        validator.validate(too_large)


def test_untrusted_mastery_fields_pathological_depth_and_effort_fail_closed():
    validator = CurriculumValidator()
    mastery = curriculum()
    mastery["nodes"][0]["mastery"] = "expert"
    with pytest.raises(CurriculumValidationError, match="unsupported node fields"):
        validator.validate(mastery)

    nodes = [
        {
            "node_id": f"n{i}",
            "module_id": "m",
            "title": f"Node {i}",
            "type": "lesson",
            "objectives": ["Learn"],
            "estimated_hours": None,
        }
        for i in range(81)
    ]
    chain = {
        "title": "Long path",
        "goal": "test",
        "target_level": "intermediate",
        "mode": "topic",
        "modules": [{"module_id": "m", "title": "M", "objective": "O"}],
        "nodes": nodes,
        "prerequisites": [
            {"prerequisite_node_id": f"n{i}", "node_id": f"n{i + 1}"} for i in range(80)
        ],
        "milestones": [],
    }
    with pytest.raises(CurriculumValidationError, match="depth"):
        validator.validate(chain)

    effort = curriculum()
    for node in effort["nodes"][:3]:
        node["estimated_hours"] = 10_000
    with pytest.raises(CurriculumValidationError, match="estimated effort"):
        validator.validate(effort)


def test_versioning_is_atomic_historical_and_restart_safe(tmp_path):
    database = tmp_path / "candidate" / "learning-paths.sqlite3"
    first_service = LearningPathService(database)
    assert stat.S_IMODE(database.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(database.stat().st_mode) == 0o600
    created = first_service.create(curriculum())
    first = first_service.repository.version(created.path_id, 1)
    revised = curriculum()
    revised["title"] = "Revised synthetic DSA"
    current = first_service.revise(created.path_id, revised, reason="owner_edit")
    assert current.current_version == 2
    assert first_service.repository.version(created.path_id, 1) == first
    reconstructed = LearningPathService(database)
    detail = reconstructed.detail(created.path_id)
    assert detail["path"].current_version == 2
    assert detail["current"].modules == first.modules
    assert detail["current"].nodes == first.nodes
    assert detail["current"].prerequisites == first.prerequisites
    assert detail["current"].milestones == first.milestones
    assert reconstructed.repository.versions(created.path_id)[0] == first


def test_invalid_revision_and_duplicate_path_id_leave_canonical_state_unchanged(tmp_path):
    service = LearningPathService(tmp_path / "paths.sqlite3")
    created = service.create(curriculum())
    bad = curriculum()
    bad["prerequisites"].append({"prerequisite_node_id": "window", "node_id": "arrays"})
    with pytest.raises(CurriculumValidationError):
        service.revise(created.path_id, bad, reason="manual_revision")
    assert service.repository.get(created.path_id).current_version == 1
    with pytest.raises(Exception):
        service.create({**curriculum(), "path_id": created.path_id})
    assert len(service.repository.list()) == 1
    repeated = service.create(curriculum())
    assert (
        repeated.path_id != created.path_id
    )  # identical requests create distinct paths unless an explicit ID is supplied


class ProposalModel:
    def __init__(self, output):
        self.output = output
        self.calls = []

    def chat(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        return self.output


def test_generator_is_local_proposal_contract_and_rejects_malformed_output(tmp_path):
    good = curriculum()
    good.update(
        mastery="completed", progress=100, completed=True, state="completed", path_id="model-chosen"
    )
    model = ProposalModel(json.dumps(good))
    service = LearningPathService(
        tmp_path / "paths.sqlite3", generator=LocalCurriculumGenerator(model)
    )
    created = service.generate("SQL optimization", target_level="beginner", mode="topic")
    assert created.goal == "SQL optimization" and created.current_version == 1
    assert created.state == "draft" and created.path_id != "model-chosen"
    assert (
        not hasattr(created, "mastery")
        and "mastery" not in service.repository.version(created.path_id, 1).metadata
    )
    assert (
        len(model.calls) == 1 and "cloud" not in model.calls[0][1].get("system_prompt", "").lower()
    )
    invalid = ProposalModel("not json")
    other = LearningPathService(
        tmp_path / "other.sqlite3", generator=LocalCurriculumGenerator(invalid)
    )
    with pytest.raises(CurriculumGenerationError):
        other.generate("Goal")
    assert other.repository.list() == ()


def test_api_create_read_list_version_and_reject_invalid_model_proposal(tmp_path):
    service = LearningPathService(tmp_path / "candidate.sqlite3")
    runtime = FridayRuntime("learning-path-test")
    app = create_presentation_app(
        runtime, FridayConversationService(object(), runtime), learning_paths=service
    )
    payload = curriculum()
    with TestClient(app) as client:
        openapi = client.get("/openapi.json").json()
        assert openapi["paths"]["/api/v1/learning-paths"]["post"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]["$ref"].endswith("LearningPathCreatedView")
        created = client.post("/api/v1/learning-paths", json=payload)
        path_id = created.json()["path"]["path_id"]
        assert created.status_code == 200
        assert client.get("/api/v1/learning-paths").json()["paths"][0]["current_version"] == 1
        detail = client.get(f"/api/v1/learning-paths/{path_id}")
        assert detail.json()["current"]["topological_order"]
        revised = client.post(
            f"/api/v1/learning-paths/{path_id}/versions",
            json={"reason": "manual_revision", "curriculum": {**payload, "title": "New title"}},
        )
        assert revised.json()["path"]["current_version"] == 2
        assert len(client.get(f"/api/v1/learning-paths/{path_id}/versions").json()["versions"]) == 2
        broken = curriculum()
        broken["prerequisites"].append({"prerequisite_node_id": "arrays", "node_id": "arrays"})
        assert client.post("/api/v1/learning-paths", json=broken).status_code == 422
    assert len(service.repository.list()) == 1


def test_api_generation_failure_does_not_create_path_or_touch_career_forge(tmp_path):
    class UntouchableCareerForge:
        def __getattr__(self, name):
            raise AssertionError(f"DLP attempted Career Forge mutation/access: {name}")

    model = ProposalModel("{malformed")
    service = LearningPathService(
        tmp_path / "candidate.sqlite3", generator=LocalCurriculumGenerator(model)
    )
    runtime = FridayRuntime("learning-path-failure")
    app = create_presentation_app(
        runtime,
        FridayConversationService(object(), runtime),
        learning_paths=service,
        career_forge=UntouchableCareerForge(),
    )
    with TestClient(app) as client:
        response = client.post("/api/v1/learning-paths/generate", json={"goal": "Synthetic goal"})
    assert response.status_code == 502
    assert service.repository.list() == ()


def test_typed_sequence_and_adaptation_api(tmp_path):
    service = LearningPathService(tmp_path / "candidate.sqlite3")
    runtime = FridayRuntime("learning-path-sequence-api")
    app = create_presentation_app(
        runtime, FridayConversationService(object(), runtime), learning_paths=service,
    )
    with TestClient(app) as client:
        created = client.post("/api/v1/learning-paths", json=curriculum()).json()
        path_id = created["path"]["path_id"]
        sequence = client.get(f"/api/v1/learning-paths/{path_id}/sequence")
        assert sequence.status_code == 200
        assert sequence.json()["path_state"] == "draft"
        assert sequence.json()["nodes"][0]["evidence_state"] == "unmapped"
        adapted = client.post(f"/api/v1/learning-paths/{path_id}/adapt")
        assert adapted.status_code == 200
        assert adapted.json()["path"]["current_version"] == 2
        assert adapted.json()["version"]["adaptation"]["evidence_available"] is False


def test_evidence_sequencing_adaptation_is_deterministic_and_versioned(tmp_path):
    class Provider:
        def competency_evidence(self, ids):
            return {
                "se.python": CompetencyEvidence("se.python", "apply_independently", "current", "scheduled", 2, (), False),
                "se.engineering": CompetencyEvidence("se.engineering", "unverified", "unverified", "not_scheduled", 0, (), False),
            }

    proposal = curriculum()
    proposal["nodes"][0]["competency_key"] = "se.python"
    proposal["nodes"][1]["competency_key"] = "se.engineering"
    service = LearningPathService(tmp_path / "paths.sqlite3", evidence_provider=Provider())
    path = service.create(proposal)
    first = service.repository.version(path.path_id, 1)
    projection = service.sequence(path.path_id)
    by_id = {item["node_id"]: item for item in projection["nodes"]}
    assert by_id["arrays"]["decision"] == "SKIP_ALREADY_SUPPORTED"
    assert by_id["arrays"]["evidence"]["independent_correct_attempts"] == 2
    assert by_id["pointers"]["decision"] == "DIAGNOSTIC_FIRST"
    assert by_id["window"]["decision"] == "BLOCKED"
    assert projection["candidate_next_nodes"] == ["pointers", "trees"]
    applied = service.apply_adaptation(path.path_id)
    assert applied.current_version == 2
    assert service.repository.version(path.path_id, 1) == first
    assert service.repository.version(path.path_id, 2).reason == "evidence_adaptation"
    assert service.repository.version(path.path_id, 2).adaptation["decisions"]
    restarted = LearningPathService(tmp_path / "paths.sqlite3", evidence_provider=Provider()).sequence(path.path_id)
    assert restarted["version"] == 2
    assert restarted["nodes"] == projection["nodes"]
    assert restarted["candidate_next_nodes"] == projection["candidate_next_nodes"]


def test_partial_mastery_recommends_diagnostic_instead_of_satisfying(tmp_path):
    class Provider:
        def competency_evidence(self, ids):
            return {"se.python": CompetencyEvidence("se.python", "recognize", "current", "scheduled", 1, (), False)}

    proposal = curriculum()
    proposal["nodes"][0]["competency_key"] = "se.python"
    service = LearningPathService(tmp_path / "partial.sqlite3", evidence_provider=Provider())
    path = service.create(proposal)
    node = service.sequence(path.path_id)["nodes"][0]
    assert node["evidence_state"] == "needs_diagnostic"
    assert node["decision"] == "DIAGNOSTIC_FIRST"


def test_unmapped_and_unavailable_evidence_fail_closed(tmp_path):
    service = LearningPathService(tmp_path / "paths.sqlite3", evidence_provider=object())
    path = service.create(curriculum())
    result = service.sequence(path.path_id)
    assert result["evidence_available"] is False
    assert all(item["evidence_state"] == "unmapped" for item in result["nodes"])
    assert result["candidate_next_nodes"] == ["arrays"]

    class BrokenProvider:
        def competency_evidence(self, ids):
            raise OSError("candidate provider unavailable")

    mapped = curriculum()
    mapped["nodes"][0]["competency_key"] = "se.python"
    other = LearningPathService(tmp_path / "mapped.sqlite3", evidence_provider=BrokenProvider())
    mapped_path = other.create(mapped)
    blocked = other.sequence(mapped_path.path_id)
    assert blocked["nodes"][0]["evidence_state"] == "unavailable"
    assert blocked["nodes"][0]["decision"] == "DEFER"
    assert blocked["candidate_next_nodes"] == []

    class MalformedProvider:
        def competency_evidence(self, ids):
            return {"se.python": {"mastery": "apply_independently"}}

    malformed = LearningPathService(tmp_path / "malformed.sqlite3", evidence_provider=MalformedProvider())
    malformed_path = malformed.create(mapped)
    assert malformed.sequence(malformed_path.path_id)["nodes"][0]["evidence_state"] == "unavailable"


@pytest.mark.parametrize(
    ("confidence", "expected", "dependent"),
    [("weak", "REINFORCE_FIRST", "BLOCKED"), ("stale", "REVIEW_FIRST", "BLOCKED")],
)
def test_weak_or_stale_direct_evidence_changes_local_sequencing(tmp_path, confidence, expected, dependent):
    class Provider:
        def competency_evidence(self, ids):
            due = confidence == "stale"
            return {"se.python": CompetencyEvidence("se.python", "apply_independently", confidence, "due" if due else "failed", 1, ("retention concern",), due)}

    proposal = curriculum()
    proposal["nodes"][0]["competency_key"] = "se.python"
    proposal["prerequisites"] = [edge for edge in proposal["prerequisites"] if edge["node_id"] != "trees"]
    service = LearningPathService(tmp_path / f"{confidence}.sqlite3", evidence_provider=Provider())
    path = service.create(proposal)
    nodes = {item["node_id"]: item for item in service.sequence(path.path_id)["nodes"]}
    assert nodes["arrays"]["decision"] == expected
    assert nodes["pointers"]["decision"] == dependent
    assert "trees" in service.sequence(path.path_id)["candidate_next_nodes"]


def test_career_forge_adapter_and_sequence_do_not_mutate_learner_database(tmp_path):
    db = tmp_path / "cf.sqlite3"
    cf = CareerForgeService(db)
    before = db.read_bytes()
    adapter = CareerForgeEvidenceProjection(cf)
    result = adapter.competency_evidence({"se.python", "unknown.key"})
    assert set(result) == {"se.python"}
    assert result["se.python"].confidence == "unverified"
    service = LearningPathService(tmp_path / "paths.sqlite3", evidence_provider=adapter)
    proposal = curriculum()
    proposal["nodes"][0]["competency_key"] = "se.python"
    path = service.create(proposal)
    service.sequence(path.path_id)
    service.apply_adaptation(path.path_id)
    assert db.read_bytes() == before
