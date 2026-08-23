from dataclasses import replace
from types import SimpleNamespace

import pytest

from local_ai_assistant.agent import code_agent
from local_ai_assistant.common.config import AppConfig, PathConfig
from local_ai_assistant.planning.models import ApprovalStatus, IssueSeverity, RiskLevel


def init_repo(path):
    import subprocess

    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Regression Test"],
        cwd=path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "regression@example.invalid"],
        cwd=path,
        check=True,
    )
    (path / "file.py").write_text("value = 1\n")
    subprocess.run(["git", "add", "file.py"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "base"], cwd=path, check=True, capture_output=True)


def fake_artifact(*, approval=ApprovalStatus.AUTOMATIC, errors=False):
    issue = SimpleNamespace(
        severity=IssueSeverity.ERROR,
        code="invalid_scope",
        message="invalid plan",
    )
    plan = SimpleNamespace(
        task_id="task-1",
        summary="A focused plan.",
        risk=SimpleNamespace(level=RiskLevel.HIGH if approval is not ApprovalStatus.AUTOMATIC else RiskLevel.MEDIUM),
        confidence=SimpleNamespace(score=0.8),
        approval=SimpleNamespace(status=approval),
        steps=(SimpleNamespace(order=1, description="Inspect and update."),),
    )
    return SimpleNamespace(plan=plan, validation_issues=(issue,) if errors else ())


def test_fresh_index_precedes_every_patch_proposal(monkeypatch, tmp_path):
    repo_root = tmp_path / "repos"
    init_repo(repo_root / "demo")
    defaults = AppConfig.from_env({})
    config = replace(
        defaults,
        paths=PathConfig(
            var_dir=tmp_path,
            document_dir=tmp_path / "documents",
            rag_data_dir=tmp_path / "rag",
            code_repo_dir=repo_root,
            code_index_dir=tmp_path / "index",
            patch_dir=tmp_path / "patches",
        ),
    )
    events = []

    class FakeRAG:
        def __init__(self, config):
            self.config = config
            self.symbol_index = object()
            self.llm = object()

        def reindex(self):
            events.append("reindex")

    def fake_proposal(rag, repo_name, request):
        events.append("propose")
        return "INSUFFICIENT_CONTEXT", []

    class FakePlanner:
        def __init__(self, *args):
            pass

        def generate(self, request):
            events.append("plan")
            return fake_artifact()

        def persist(self, artifact, destination):
            return tmp_path / "plan.json"

    monkeypatch.setattr(code_agent, "get_config", lambda: config)
    monkeypatch.setattr(code_agent, "CodeRAG", FakeRAG)
    monkeypatch.setattr(code_agent, "propose_patch", fake_proposal)
    monkeypatch.setattr(code_agent, "PlannerService", FakePlanner)
    monkeypatch.setattr(code_agent, "plan_approval_token", lambda plan: "reviewed-token")

    with pytest.raises(SystemExit) as exit_info:
        code_agent.main(["demo", "change something"])

    assert exit_info.value.code == 1
    assert events == ["reindex", "plan", "propose"]


@pytest.mark.parametrize(
    ("artifact", "extra_args", "expected_code", "proposal_count"),
    [
        (fake_artifact(errors=True), (), 1, 0),
        (fake_artifact(approval=ApprovalStatus.REVIEW), (), 1, 0),
        (
            fake_artifact(approval=ApprovalStatus.REVIEW),
            ("--approve-risk", "different-plan-token"),
            1,
            0,
        ),
        (
            fake_artifact(approval=ApprovalStatus.REVIEW),
            ("--approve-risk", "reviewed-token"),
            1,
            1,
        ),
    ],
)
def test_agent_blocks_invalid_or_unapproved_high_risk_plan(
    monkeypatch, tmp_path, artifact, extra_args, expected_code, proposal_count
):
    repo_root = tmp_path / "repos"
    init_repo(repo_root / "demo")
    defaults = AppConfig.from_env({})
    config = replace(
        defaults,
        paths=PathConfig(
            var_dir=tmp_path,
            document_dir=tmp_path / "documents",
            rag_data_dir=tmp_path / "rag",
            code_repo_dir=repo_root,
            code_index_dir=tmp_path / "index",
            patch_dir=tmp_path / "patches",
        ),
    )
    proposals = []

    class FakeRAG:
        symbol_index = object()
        llm = object()

        def __init__(self, config):
            pass

        def reindex(self):
            pass

    class FakePlanner:
        def __init__(self, *args):
            pass

        def generate(self, request):
            return artifact

        def persist(self, value, destination):
            return tmp_path / "plan.json"

    monkeypatch.setattr(code_agent, "get_config", lambda: config)
    monkeypatch.setattr(code_agent, "CodeRAG", FakeRAG)
    monkeypatch.setattr(code_agent, "PlannerService", FakePlanner)
    monkeypatch.setattr(code_agent, "plan_approval_token", lambda plan: "reviewed-token")
    def proposal(*args):
        proposals.append(True)
        return "INSUFFICIENT_CONTEXT", []

    monkeypatch.setattr(code_agent, "propose_patch", proposal)

    with pytest.raises(SystemExit) as exit_info:
        code_agent.main(["demo", "change something", *extra_args])

    assert exit_info.value.code == expected_code
    assert len(proposals) == proposal_count


def test_agent_planning_only_mode_stops_before_patch_generation(monkeypatch, tmp_path):
    repo_root = tmp_path / "repos"
    init_repo(repo_root / "demo")
    config = replace(
        AppConfig.from_env({}),
        paths=PathConfig(tmp_path, tmp_path / "documents", tmp_path / "rag", repo_root, tmp_path / "index", tmp_path / "patches"),
    )
    proposals = []

    class FakeRAG:
        symbol_index = object()
        llm = object()

        def __init__(self, config):
            pass

        def reindex(self):
            pass

    class FakePlanner:
        def __init__(self, *args):
            pass

        def generate(self, request):
            return fake_artifact()

        def persist(self, value, destination):
            return tmp_path / "plan.json"

    monkeypatch.setattr(code_agent, "get_config", lambda: config)
    monkeypatch.setattr(code_agent, "CodeRAG", FakeRAG)
    monkeypatch.setattr(code_agent, "PlannerService", FakePlanner)
    monkeypatch.setattr(code_agent, "plan_approval_token", lambda plan: "reviewed-token")
    monkeypatch.setattr(code_agent, "propose_patch", lambda *args: proposals.append(True))

    assert code_agent.main(["demo", "change something", "--plan-only"]) is None
    assert proposals == []


def test_auto_merge_requires_explicit_safe_option_bundle():
    with pytest.raises(SystemExit) as exit_info:
        code_agent.main(["demo", "change", "--auto-merge"])
    assert exit_info.value.code == 2
