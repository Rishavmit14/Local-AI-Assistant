import re
import subprocess
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


def test_task_artifact_paths_are_immutable_per_execution_attempt(tmp_path):
    first = code_agent._attempt_artifact_path(
        tmp_path, "executions", "task_123", "a" * 32
    )
    second = code_agent._attempt_artifact_path(
        tmp_path, "executions", "task_123", "b" * 32
    )
    assert first == tmp_path / "executions" / "task_123" / f"{'a' * 32}.json"
    assert second == tmp_path / "executions" / "task_123" / f"{'b' * 32}.json"
    assert first != second
    assert code_agent._attempt_artifact_path(
        tmp_path, "validations", "task_123", None
    ) == tmp_path / "validations" / "task_123.json"


def test_interrupted_worktree_preflight_requires_clean_ignored_state_and_exact_head(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    def git(*args):
        return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()

    git("init", "-q")
    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "Test")
    (repo / ".gitignore").write_text("generated/\n")
    (repo / "README.md").write_text("clean\n")
    git("add", ".gitignore", "README.md")
    git("commit", "-qm", "baseline")
    head = git("rev-parse", "HEAD")

    assert code_agent._interrupted_worktree_is_clean(repo, head)
    (repo / "generated").mkdir()
    (repo / "generated" / "cache.bin").write_bytes(b"ignored side effect")
    assert not code_agent._interrupted_worktree_is_clean(repo, head)
    (repo / "generated" / "cache.bin").unlink()
    (repo / "generated").rmdir()
    (repo / "README.md").write_text("changed\n")
    assert not code_agent._interrupted_worktree_is_clean(repo, head)


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
