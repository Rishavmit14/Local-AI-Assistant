from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from local_ai_assistant.common.config import AppConfig
from local_ai_assistant.common.repository_files import (
    read_repo_bytes_bounded,
    read_repo_file_bounded,
)
from local_ai_assistant.agent import code_agent
from local_ai_assistant.gateway.execution_service import CodeAgentExecutionService
from local_ai_assistant.history.models import TaskStatus
from local_ai_assistant.history.service import TaskHistoryService
from local_ai_assistant.history.store import TaskHistoryStore
from local_ai_assistant.isolation.worktrees import WorktreeManager
from local_ai_assistant.onboarding import (
    IndexState,
    OnboardingLimits,
    ReadinessStatus,
    RepositoryIdentityMismatch,
    RepositoryIndexNotReady,
    RepositoryNotOnboarded,
    RepositoryOnboardingError,
    RepositoryOnboardingService,
    RepositoryReadinessBlocked,
    RepositoryRegistryCorrupt,
)
from local_ai_assistant.planning.analysis import ScopeAnalyzer
from local_ai_assistant.planning.instructions import discover_project_instructions


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ("git", "-C", str(root), *args), check=True, text=True, capture_output=True
    ).stdout.strip()


def make_repo(parent: Path, name: str = "project") -> Path:
    root = parent / name
    root.mkdir(parents=True)
    subprocess.run(("git", "init", "-q", str(root)), check=True)
    (root / "app.py").write_text("def add(a, b):\n    return a + b\n")
    (root / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")
    git(root, "add", ".")
    git(
        root, "-c", "user.name=Stage10", "-c", "user.email=stage10@example.invalid",
        "commit", "-qm", "initial",
    )
    return root


def configured(tmp_path: Path) -> tuple[AppConfig, Path, Path]:
    repos = tmp_path / "repos"
    index = tmp_path / "index"
    config = AppConfig.from_env(
        {
            "LOCAL_AI_VAR_DIR": str(tmp_path / "runtime"),
            "LOCAL_AI_CODE_REPO_DIR": str(repos),
            "LOCAL_AI_CODE_INDEX_DIR": str(index),
            "LOCAL_AI_ONBOARDING_REGISTRY": str(tmp_path / "runtime/onboarding.json"),
        }
    )
    return config, repos, index


def test_missing_and_corrupt_profiles_fail_closed(tmp_path: Path):
    config, repos, _ = configured(tmp_path)
    root = make_repo(repos)
    onboarding = RepositoryOnboardingService(config, allowed_roots=(repos,))
    task = SimpleNamespace(
        status=TaskStatus.APPROVED, plan_hash="plan", repository=str(root),
        starting_commit=git(root, "rev-parse", "HEAD"), task_id="task", original_request="fix",
    )
    with pytest.raises(RepositoryNotOnboarded):
        CodeAgentExecutionService(config, object(), onboarding).execute_task(task)
    config.paths.onboarding_registry.parent.mkdir(parents=True, exist_ok=True)
    config.paths.onboarding_registry.write_text("{broken")
    with pytest.raises(RepositoryRegistryCorrupt):
        RepositoryOnboardingService(config, allowed_roots=(repos,))


def test_managed_repository_root_is_allowed_but_runtime_paths_are_protected(
    tmp_path: Path,
):
    config, repos, _ = configured(tmp_path)
    root = make_repo(repos)
    service = RepositoryOnboardingService(config)
    assert service.register("project", root).canonical_root == str(root.resolve())

    protected = make_repo(config.paths.worktree_dir, "unsafe")
    with pytest.raises(RepositoryOnboardingError, match="protected runtime"):
        RepositoryOnboardingService(
            config, allowed_roots=(config.paths.var_dir,)
        ).register("unsafe", protected)


def test_local_code_agent_apply_cannot_bypass_missing_profile(
    tmp_path: Path, monkeypatch
):
    config, repos, _ = configured(tmp_path)
    make_repo(repos)
    monkeypatch.setattr(code_agent, "get_config", lambda: config)
    with pytest.raises(RepositoryNotOnboarded):
        code_agent.main(
            [
                "project", "fix add", "--apply", "--branch", "--test", "--validate",
                "--rollback-on-fail", "--tool-loop",
            ]
        )
    assert not config.paths.worktree_dir.exists()


def test_code_agent_rejects_gateway_authorized_commit_after_repository_advances(
    tmp_path: Path, monkeypatch
):
    config, repos, _ = configured(tmp_path)
    root = make_repo(repos)
    onboarding = RepositoryOnboardingService(config, allowed_roots=(repos,))
    profile = onboarding.register("project", root)
    authorized_commit = profile.head

    (root / "next.py").write_text("VALUE = 1\n")
    git(root, "add", ".")
    git(
        root, "-c", "user.name=Stage10", "-c", "user.email=stage10@example.invalid",
        "commit", "-qm", "advanced-before-worker",
    )
    assert git(root, "rev-parse", "HEAD") != authorized_commit

    monkeypatch.setattr(code_agent, "get_config", lambda: config)

    with pytest.raises(RepositoryReadinessBlocked, match="revision changed"):
        code_agent.main(
            [
                "project",
                "fix add",
                "--repository-id",
                "project",
                "--expected-starting-commit",
                authorized_commit,
                "--apply",
                "--branch",
                "--test",
                "--validate",
                "--rollback-on-fail",
                "--tool-loop",
            ]
        )

    assert not config.paths.worktree_dir.exists()



def test_identity_swap_fails_without_mutating_profile_and_head_is_revision(tmp_path: Path):
    first = make_repo(tmp_path / "a")
    second = make_repo(tmp_path / "b")
    service = RepositoryOnboardingService(
        allowed_roots=(tmp_path,), registry_path=tmp_path / "registry.json"
    )
    original = service.register("project", first)
    with pytest.raises(RepositoryIdentityMismatch):
        service.register("project", second)
    assert service.get("project") == original
    (first / "next.py").write_text("VALUE = 1\n")
    git(first, "add", ".")
    git(
        first, "-c", "user.name=Stage10", "-c", "user.email=stage10@example.invalid",
        "commit", "-qm", "next",
    )
    refreshed = service.readiness("project").profile
    assert refreshed.fingerprint == original.fingerprint
    assert refreshed.head != original.head
    assert refreshed.revision_fingerprint != original.revision_fingerprint


def test_registry_reload_preserves_repository_profile_schema(tmp_path: Path):
    root = make_repo(tmp_path)
    registry = tmp_path / "registry.json"

    first = RepositoryOnboardingService(
        allowed_roots=(tmp_path,), registry_path=registry
    )
    original = first.register("project", root)

    reloaded = RepositoryOnboardingService(
        allowed_roots=(tmp_path,), registry_path=registry
    )
    restored = reloaded.get("project")

    assert restored == original
    assert isinstance(restored.root_commits, tuple)
    assert isinstance(restored.remotes, tuple)
    assert isinstance(restored.blockers, tuple)
    assert isinstance(restored.warnings, tuple)
    assert isinstance(restored.missing_tools, tuple)
    assert isinstance(restored.capabilities.languages, tuple)
    assert isinstance(restored.capabilities.manifests, tuple)
    assert isinstance(restored.components, tuple)
    assert all(isinstance(component.languages, tuple) for component in restored.components)
    assert isinstance(restored.validation.commands, tuple)



def test_remote_metadata_change_does_not_replace_repository_identity(tmp_path: Path):
    root = make_repo(tmp_path)
    service = RepositoryOnboardingService(
        allowed_roots=(tmp_path,), registry_path=tmp_path / "registry.json"
    )
    original = service.register("project", root)

    git(root, "remote", "add", "origin", "https://github.com/acme/demo.git")
    refreshed = service.readiness("project").profile

    assert refreshed.fingerprint == original.fingerprint
    assert refreshed.root_commits == original.root_commits
    assert refreshed.remotes == ("origin https://github.com/acme/demo.git",)

    git(root, "remote", "set-url", "origin", "git@github.com:acme/demo.git")
    refreshed_again = service.readiness("project").profile

    assert refreshed_again.fingerprint == original.fingerprint
    assert refreshed_again.root_commits == original.root_commits
    assert refreshed_again.remotes == ("origin github.com:acme/demo.git",)



def test_same_path_repository_replacement_is_rejected_without_overwriting_profile(
    tmp_path: Path,
):
    root = make_repo(tmp_path)
    service = RepositoryOnboardingService(
        allowed_roots=(tmp_path,), registry_path=tmp_path / "registry.json"
    )
    original = service.register("project", root)

    git_dir = root / ".git"
    replacement_marker = tmp_path / "old-git"
    git_dir.rename(replacement_marker)

    subprocess.run(("git", "init", "-q", str(root)), check=True)
    (root / "app.py").write_text("def replacement():\n    return True\n")
    (root / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")
    git(root, "add", ".")
    git(
        root,
        "-c",
        "user.name=Stage10",
        "-c",
        "user.email=stage10@example.invalid",
        "commit",
        "-qm",
        "replacement-root",
    )

    assert tuple(
        sorted(git(root, "rev-list", "--max-parents=0", "HEAD").splitlines())
    ) != original.root_commits

    with pytest.raises(RepositoryIdentityMismatch):
        service.readiness("project")

    assert service.get("project") == original



def test_fresh_authority_detects_revision_change(tmp_path: Path):
    root = make_repo(tmp_path)
    service = RepositoryOnboardingService(
        allowed_roots=(tmp_path,), registry_path=tmp_path / "registry.json"
    )
    profile = service.register("project", root)
    (root / "app.py").write_text("def add(a, b):\n    return a - b\n")
    git(root, "add", ".")
    git(
        root, "-c", "user.name=Stage10", "-c", "user.email=stage10@example.invalid",
        "commit", "-qm", "changed",
    )
    with pytest.raises(RepositoryReadinessBlocked, match="revision changed"):
        service.assert_ready_for_mutation("project", root, profile.head)


def test_repository_scoped_index_identity_and_freshness(tmp_path: Path):
    config, _, _ = configured(tmp_path)
    root = make_repo(tmp_path / "external")
    service = RepositoryOnboardingService(config, allowed_roots=(tmp_path / "external",))
    profile = service.register("project", root)
    assert profile.index_state is IndexState.ABSENT
    with pytest.raises(RepositoryIndexNotReady):
        service.assert_ready_for_mutation("project", root, profile.head, require_index=True)
    repository_index = service.repository_index_dir(profile.fingerprint)
    repository_index.mkdir(parents=True)
    manifest = {}
    for relative in ("app.py",):
        payload = (root / relative).read_bytes()
        manifest[relative] = {
            "sha256": hashlib.sha256(payload).hexdigest(), "size": len(payload)
        }
    (repository_index / "manifest.json").write_text(json.dumps(manifest))
    current = service.readiness("project").profile
    assert current.index_state is IndexState.CURRENT
    service.assert_ready_for_mutation("project", root, current.head, require_index=True)
    (root / "app.py").write_text("def add(a, b):\n    return a - b\n")
    assert service.readiness("project").profile.index_state is IndexState.STALE


def test_remote_credentials_are_removed_everywhere_persisted(tmp_path: Path):
    root = make_repo(tmp_path)
    secret = "SUPER_SECRET_STAGE10_TOKEN"
    git(root, "remote", "add", "origin", f"https://user:{secret}@github.com/acme/demo.git")
    registry = tmp_path / "registry.json"
    service = RepositoryOnboardingService(allowed_roots=(tmp_path,), registry_path=registry)
    profile = service.register("project", root)
    rendered = json.dumps(profile.to_dict()) + registry.read_text() + json.dumps(
        service.dry_run("project", "fix")
    )
    assert secret not in rendered
    assert profile.remotes == ("origin https://github.com/acme/demo.git",)


def test_contained_reader_and_instruction_discovery_skip_symlinks(tmp_path: Path):
    root = make_repo(tmp_path)
    outside = tmp_path / "outside-secret"
    outside.write_text("DO_NOT_READ_STAGE10")
    (root / ".gitattributes").symlink_to(outside)
    (root / "AGENTS.md").symlink_to(outside)
    nested = root / "nested"
    nested.mkdir()
    (nested / "AGENTS.override.md").symlink_to(outside)
    assert not read_repo_file_bounded(root, root / ".gitattributes", max_bytes=100).readable
    content, sources, _ = discover_project_instructions(root, ("nested/app.py",))
    assert "DO_NOT_READ_STAGE10" not in content
    assert sources == ()
    service = RepositoryOnboardingService(
        allowed_roots=(tmp_path,), registry_path=tmp_path / "registry.json"
    )
    profile = service.register("project", root)
    assert profile.status is ReadinessStatus.PARTIAL


def test_index_hashing_rejects_source_symlink_swap_even_when_external_hash_matches(
    tmp_path: Path,
):
    config, _, _ = configured(tmp_path)
    root = make_repo(tmp_path / "external")
    service = RepositoryOnboardingService(
        config,
        allowed_roots=(tmp_path / "external",),
    )
    profile = service.register("project", root)

    payload = (root / "app.py").read_bytes()
    repository_index = service.repository_index_dir(profile.fingerprint)
    repository_index.mkdir(parents=True)
    (repository_index / "manifest.json").write_text(
        json.dumps(
            {
                "app.py": {
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "size": len(payload),
                }
            }
        )
    )

    outside = tmp_path / "outside.py"
    outside.write_bytes(payload)

    (root / "app.py").unlink()
    (root / "app.py").symlink_to(outside)

    direct = read_repo_bytes_bounded(
        root,
        root / "app.py",
        max_bytes=service.limits.max_file_bytes,
    )
    assert not direct.readable
    assert direct.reason == "symlink"

    assert (
        service._index_state(
            root,
            profile.fingerprint,
            ("app.py",),
            False,
        )
        is IndexState.STALE
    )



def test_scope_test_discovery_does_not_follow_external_test_symlink(
    tmp_path: Path,
):
    root = make_repo(tmp_path)
    outside = tmp_path / "test_external.py"
    outside.write_text("TARGET_SYMBOL\n")
    (root / "test_external.py").symlink_to(outside)

    symbols = SimpleNamespace(
        repository=root,
        containing_module=lambda _identifier: None,
    )
    analyzer = ScopeAnalyzer(root, symbols)

    direct_symbol = SimpleNamespace(
        identifier="TARGET_SYMBOL",
        name="TARGET_SYMBOL",
    )
    candidates = {}

    analyzer._add_tests(candidates, (direct_symbol,))

    assert candidates == {}



def test_oversized_manifest_and_discovery_explosions_are_partial(tmp_path: Path):
    root = make_repo(tmp_path)
    (root / "package.json").write_text("x" * 1025)
    service = RepositoryOnboardingService(
        allowed_roots=(tmp_path,), registry_path=tmp_path / "oversized.json",
        limits=OnboardingLimits(max_file_bytes=1024),
    )
    profile = service.register("oversized", root)
    assert profile.status is ReadinessStatus.PARTIAL
    for number in range(10):
        component = root / f"component-{number}"
        component.mkdir()
        (component / "package.json").write_text("{}")
        (component / "file.py").write_text("VALUE = 1\n")
    bounded = RepositoryOnboardingService(
        allowed_roots=(tmp_path,), registry_path=tmp_path / "bounded.json",
        limits=OnboardingLimits(max_manifests=3, max_components=4, max_files=100),
    ).register("bounded", root)
    assert bounded.status is ReadinessStatus.PARTIAL
    assert len(bounded.capabilities.manifests) <= 3
    assert len(bounded.components) <= 4


def test_controlled_onboarding_authority_reaches_stage8_worktree_only(
    tmp_path: Path, monkeypatch
):
    config, repos, _ = configured(tmp_path)
    root = make_repo(repos)
    (root / "app.py").write_text("def add(a, b):\n    return a - b\n")
    (root / "test_app.py").write_text(
        "import unittest\nfrom app import add\n\n"
        "class AddTest(unittest.TestCase):\n"
        "    def test_add(self): self.assertEqual(add(2, 3), 5)\n"
    )
    git(root, "add", ".")
    git(
        root, "-c", "user.name=Stage10", "-c", "user.email=stage10@example.invalid",
        "commit", "-qm", "tests",
    )
    onboarding = RepositoryOnboardingService(config, allowed_roots=(repos,))
    profile = onboarding.register("project", root)
    dry_run = onboarding.dry_run("project", "fix add")
    assert dry_run["status"] in {"ready", "ready_with_warnings"}
    repository_index = onboarding.repository_index_dir(profile.fingerprint)
    repository_index.mkdir(parents=True)
    manifest = {}
    for relative in ("app.py", "test_app.py"):
        payload = (root / relative).read_bytes()
        manifest[relative] = {
            "sha256": hashlib.sha256(payload).hexdigest(), "size": len(payload),
        }
    (repository_index / "manifest.json").write_text(json.dumps(manifest))
    profile = onboarding.readiness("project").profile
    assert profile.index_state is IndexState.CURRENT
    history = TaskHistoryService(TaskHistoryStore(tmp_path / "history.sqlite3"))
    task = history.create_task("fix add", root, profile.head, "main", task_id="stage10-task")
    history.store.update_task(
        task.task_id, task.repository, plan_hash="approved-plan",
        approval_state="explicitly_approved",
    )
    for status in (TaskStatus.PLANNING, TaskStatus.AWAITING_APPROVAL):
        history.store.transition(task.task_id, status, "fixture")
    history.attach_approval(task.task_id, "approved-plan", "explicitly_approved")
    history.store.transition(task.task_id, TaskStatus.APPROVED, "fixture")
    canonical = (root / "app.py").read_bytes()
    evidence = {}

    def deterministic_code_agent(argv):
        onboarding.assert_ready_for_mutation(
            "project", root, profile.head, require_index=True
        )
        identity = WorktreeManager(config.paths.worktree_dir).create(
            root, task.task_id, profile.head, "approved-plan"
        )
        worktree = Path(identity.worktree)
        (worktree / "app.py").write_text("def add(a, b):\n    return a + b\n")
        result = subprocess.run(
            (sys.executable, "-m", "unittest", "-q"),
            cwd=worktree,
            text=True,
            capture_output=True,
            check=False,
        )
        git(worktree, "add", ".")
        git(
            worktree, "-c", "user.name=Stage10", "-c",
            "user.email=stage10@example.invalid", "commit", "-qm", "fix add",
        )
        evidence.update(
            worktree=worktree, validation_returncode=result.returncode,
            commit=git(worktree, "rev-parse", "HEAD"),
        )

    monkeypatch.setattr(
        "local_ai_assistant.gateway.execution_service.code_agent.main",
        deterministic_code_agent,
    )
    execution = CodeAgentExecutionService(config, history, onboarding)
    handle = execution.execute_task(history.get(task.task_id))
    execution._runs[handle.run_id].result(timeout=10)
    assert evidence["validation_returncode"] == 0
    assert (root / "app.py").read_bytes() == canonical
    assert (evidence["worktree"] / "app.py").read_text().endswith("return a + b\n")
    assert evidence["commit"] != profile.head
