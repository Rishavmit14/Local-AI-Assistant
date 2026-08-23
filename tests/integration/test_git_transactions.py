from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from local_ai_assistant.agent.code_agent import (
    apply_patch,
    check_patch,
    create_agent_branch,
    finalize_agent_run,
    git_current_branch,
    git_is_clean,
    validate_python_structure,
)
from local_ai_assistant.common.errors import DirtyRepositoryError


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


@pytest.fixture
def repository(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.name", "Stage One Tests")
    git(repo, "config", "user.email", "stage-one@example.invalid")
    (repo / "module.py").write_text("def value():\n    return 1\n", encoding="utf-8")
    git(repo, "add", "module.py")
    git(repo, "commit", "-m", "baseline")
    return repo


def test_dirty_tree_protection_blocks_agent_branch(repository):
    (repository / "module.py").write_text("changed\n", encoding="utf-8")
    with pytest.raises(DirtyRepositoryError):
        create_agent_branch(repository, "unsafe request")


def test_patch_preflight_and_application_are_preserved(repository, tmp_path):
    (repository / "module.py").write_text("def value():\n    return 2\n", encoding="utf-8")
    diff = git(repository, "diff") + "\n"
    (repository / "module.py").write_text("def value():\n    return 1\n", encoding="utf-8")
    patch_file = tmp_path / "change.patch"
    patch_file.write_text(diff, encoding="utf-8")

    assert check_patch(repository, patch_file) is True
    assert apply_patch(repository, patch_file) is True
    assert "return 2" in (repository / "module.py").read_text()


def test_successful_transaction_commits_and_verifies_clean_tree(repository):
    original, starting, branch = create_agent_branch(repository, "change value")
    (repository / "module.py").write_text("def value():\n    return 2\n", encoding="utf-8")

    summary = finalize_agent_run(
        repository,
        "change value",
        tests_passed=True,
        auto_commit=True,
        rollback_on_fail=True,
        starting_commit=starting,
        original_branch=original,
        agent_branch=branch,
    )

    assert summary.outcome == "committed"
    assert summary.resulting_commit == git(repository, "rev-parse", "HEAD")
    assert git_current_branch(repository) == branch
    assert git_is_clean(repository)


def test_failed_transaction_rolls_back_switches_and_cleans_branch(repository):
    original, starting, branch = create_agent_branch(repository, "broken value")
    (repository / "module.py").write_text("broken\n", encoding="utf-8")
    (repository / "new.py").write_text("untracked\n", encoding="utf-8")

    summary = finalize_agent_run(
        repository,
        "broken value",
        tests_passed=False,
        auto_commit=False,
        rollback_on_fail=True,
        starting_commit=starting,
        original_branch=original,
        agent_branch=branch,
    )

    assert summary.outcome == "rolled_back"
    assert git_current_branch(repository) == original
    assert git_is_clean(repository)
    assert git(repository, "branch", "--list", branch) == ""
    assert "return 1" in (repository / "module.py").read_text()
    assert not (repository / "new.py").exists()


def test_failed_branch_can_be_preserved_for_human_review(repository):
    original, starting, branch = create_agent_branch(repository, "inspect failure")
    (repository / "module.py").write_text("def value():\n    return 99\n", encoding="utf-8")

    summary = finalize_agent_run(
        repository,
        "inspect failure",
        tests_passed=False,
        auto_commit=False,
        rollback_on_fail=True,
        starting_commit=starting,
        original_branch=original,
        agent_branch=branch,
        keep_failed_branch=True,
    )

    assert summary.outcome == "failed_preserved"
    assert summary.failed_branch_kept is True
    assert git_current_branch(repository) == original
    assert git(repository, "branch", "--list", branch)
    assert "return 1" in (repository / "module.py").read_text()
    assert "return 99" in git(repository, "show", f"{branch}:module.py")


def test_approved_auto_merge_is_fast_forward_only(repository):
    original, starting, branch = create_agent_branch(repository, "approved value")
    (repository / "module.py").write_text("def value():\n    return 3\n", encoding="utf-8")

    summary = finalize_agent_run(
        repository,
        "approved value",
        tests_passed=True,
        auto_commit=True,
        rollback_on_fail=True,
        starting_commit=starting,
        original_branch=original,
        agent_branch=branch,
        auto_merge=True,
        merge_approved=True,
    )

    assert summary.outcome == "merged"
    assert git_current_branch(repository) == original
    assert git(repository, "branch", "--list", branch) == ""
    assert "return 3" in (repository / "module.py").read_text()


def test_structural_validation_rejects_duplicate_top_level_function(repository):
    (repository / "module.py").write_text(
        "def value():\n    return 1\n\ndef value():\n    return 2\n",
        encoding="utf-8",
    )
    valid, report = validate_python_structure(repository)
    assert valid is False
    assert "duplicate top-level function 'value'" in report
