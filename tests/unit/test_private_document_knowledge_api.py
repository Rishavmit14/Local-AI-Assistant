from fastapi.testclient import TestClient

from local_ai_assistant.interface.api import create_presentation_app
from local_ai_assistant.interface.conversation import FridayConversationService
from local_ai_assistant.interface.runtime import FridayRuntime


class Knowledge:
    def __init__(self):
        self.queries = []

    def list_sources(self):
        return {"index_status": "available", "sources_truncated": False, "sources": [
            {"source_id": "doc_0123456789abcdef0123456789abcdef", "display_name": "lesson.txt",
             "source_sha256": "a" * 64, "supported_type": "txt", "chunk_count": 1},
        ]}

    def ask(self, source_ids, question):
        self.queries.append((source_ids, question))
        return {"mode": "no_local_document_evidence", "answer": None, "evidence": []}


def test_private_document_api_is_read_only_and_requires_explicit_sources():
    runtime = FridayRuntime("private-document-api")
    conversation = FridayConversationService(object(), runtime)
    service = Knowledge()
    with TestClient(create_presentation_app(runtime, conversation, document_knowledge=service)) as client:
        inventory = client.get("/api/v1/knowledge/documents")
        no_selection = client.post("/api/v1/knowledge/ask", json={"source_ids": [], "question": "What is this?"})
        query = client.post("/api/v1/knowledge/ask", json={
            "source_ids": ["doc_0123456789abcdef0123456789abcdef"], "question": "What is this?",
        })

    assert inventory.status_code == 200
    assert inventory.json()["sources"][0]["display_name"] == "lesson.txt"
    assert no_selection.status_code == 422
    assert query.status_code == 200
    assert service.queries == [(["doc_0123456789abcdef0123456789abcdef"], "What is this?")]
