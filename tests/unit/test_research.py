from fastapi.testclient import TestClient

from local_ai_assistant.career_forge import CareerForgeService
from local_ai_assistant.interface.api import create_presentation_app
from local_ai_assistant.interface.conversation import FridayConversationService
from local_ai_assistant.interface.runtime import FridayRuntime
from local_ai_assistant.research import ResearchService


def test_local_research_preserves_provenance_version_and_gap_evidence(tmp_path):
    service = ResearchService(tmp_path / "research.sqlite3")
    item = service.collect("python", "Local guide", "Testing uses pytest.", "owner-selected-note", version="v1")
    assert service.collect("python", "Duplicate", "Testing uses pytest.", "other").source_id == item.source_id
    assert service.gaps("python", ("pytest", "packaging")) == ("packaging",)
    assert "provenance=owner-selected-note" in service.synthesis("python", "testing")
    assert service.curriculum("python", ("pytest", "packaging"))[1]["status"] == "research"
    assert service.evaluate("python", "pytest", "pytest is useful")["passed"] is True


def test_local_research_api_collects_explicit_provenance_only(tmp_path):
    class LLM:
        def stream_chat(self, *_args, **_kwargs): return iter(())
    service, runtime = ResearchService(tmp_path / "research.sqlite3"), FridayRuntime("research")
    with TestClient(create_presentation_app(runtime, FridayConversationService(LLM(), runtime), research=service)) as client:
        response = client.post("/api/v1/research/sources", json={"domain": "local", "title": "Note", "content": "Offline evidence", "provenance": "owner-note"})
        assert response.status_code == 200
        assert client.get("/api/v1/research/synthesis?domain=local&question=x").json()["synthesis"].startswith("[Note;")


def test_career_curriculum_research_is_provenance_bearing_and_advisory(tmp_path):
    class LLM:
        def stream_chat(self, *_args, **_kwargs): return iter(())
    research = ResearchService(tmp_path / "research.sqlite3")
    research.collect(
        "software_engineering", "Owner Python note",
        "Python foundations include explicit mutation reasoning.", "owner-selected-note",
    )
    forge = CareerForgeService(tmp_path / "learner.sqlite3")
    runtime = FridayRuntime("career-research")
    with TestClient(create_presentation_app(
        runtime, FridayConversationService(LLM(), runtime),
        research=research, career_forge=forge,
    )) as client:
        response = client.get(
            "/api/v1/career-forge/curriculum-research?domain=software_engineering",
        )
    assert response.status_code == 200
    body = response.json()
    assert body["authority"] == "advisory_only"
    assert body["topics"][0] == {"topic": "Python foundations", "status": "evidence_available"}
    assert body["sources"][0]["provenance"] == "owner-selected-note"
    assert "content" not in body["sources"][0]
