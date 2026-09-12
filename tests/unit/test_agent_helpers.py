import re
from types import SimpleNamespace

from local_ai_assistant.agent import code_agent
from local_ai_assistant.agent.code_agent import make_branch_name
from local_ai_assistant.execution.models import ExecutionReport


def test_branch_name_is_namespaced_bounded_and_sanitized():
    branch = make_branch_name(" Add a SAFE feature with spaces & punctuation! ")

    assert re.fullmatch(
        r"agent/add-a-safe-feature-with-spaces-punctuati-\d{8}-\d{6}",
        branch,
    )


def test_execution_persistence_uses_bound_canonical_repository(monkeypatch, tmp_path):
    canonical = tmp_path / "canonical"
    worktree = tmp_path / "worktree"
    canonical.mkdir()
    worktree.mkdir()
    task = SimpleNamespace(repository=str(canonical))
    history = SimpleNamespace(get=lambda task_id: task)
    captured = {}

    class Importer:
        def __init__(self, service):
            assert service is history

        def import_path(self, path, *, repository):
            captured["repository"] = repository

    monkeypatch.setattr(code_agent, "persist_report", lambda report, path: None)
    monkeypatch.setattr(code_agent, "_history_service", lambda config: history)
    monkeypatch.setattr(code_agent, "ArtifactImporter", Importer)
    report = ExecutionReport(
        1, "task-bound", "plan", str(worktree), "a" * 40, "rolled_back", ("plan",), ()
    )

    code_agent._persist_execution(SimpleNamespace(), report, tmp_path / "execution.json")

    assert captured["repository"] == canonical
