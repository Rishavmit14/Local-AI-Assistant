from dataclasses import replace

import pytest

from local_ai_assistant.agent import code_agent
from local_ai_assistant.common.config import AppConfig, PathConfig


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

        def reindex(self):
            events.append("reindex")

    def fake_proposal(rag, repo_name, request):
        events.append("propose")
        return "INSUFFICIENT_CONTEXT", []

    monkeypatch.setattr(code_agent, "get_config", lambda: config)
    monkeypatch.setattr(code_agent, "CodeRAG", FakeRAG)
    monkeypatch.setattr(code_agent, "propose_patch", fake_proposal)

    with pytest.raises(SystemExit) as exit_info:
        code_agent.main(["demo", "change something"])

    assert exit_info.value.code == 1
    assert events == ["reindex", "propose"]


def test_auto_merge_requires_explicit_safe_option_bundle():
    with pytest.raises(SystemExit) as exit_info:
        code_agent.main(["demo", "change", "--auto-merge"])
    assert exit_info.value.code == 2
