from __future__ import annotations

import ast
import hashlib
import json
import subprocess
from dataclasses import replace

import numpy as np
import pytest

from local_ai_assistant.code_index.symbol_index import SymbolIndex
from local_ai_assistant.common.errors import PatchValidationError
from local_ai_assistant.execution.commands import CommandResult
from local_ai_assistant.execution.errors import (
    ToolArgumentError,
    ToolExecutionError,
    ToolNotFoundError,
    ToolPermissionError,
)
from local_ai_assistant.execution.loop import ExecutionLoop, LoopLimits
from local_ai_assistant.execution.models import (
    ToolObservation,
    ToolPermission,
    ToolRequest,
    ToolSpec,
)
from local_ai_assistant.execution.registry import (
    ToolContext,
    ToolRegistry,
    _enforce_worktree_scope,
    default_registry,
)
from local_ai_assistant.planning.analysis import (
    ScopeAnalyzer,
    assess_confidence,
    assess_risk,
    compare_scope,
    decide_approval,
    detect_migration,
    detect_security,
    is_dependency_file,
    scope_guard_from_plan,
)
from local_ai_assistant.planning.classification import classify_task
from local_ai_assistant.planning.instructions import (
    discover_project_instructions,
    load_project_instructions,
)
from local_ai_assistant.planning.models import (
    ApprovalDecision,
    ApprovalStatus,
    DependencyChange,
    DependencyChangeKind,
    IssueSeverity,
    RiskLevel,
    TaskCategory,
    plan_approval_token,
)
from local_ai_assistant.planning.patch_scope import (
    PatchScope,
    SymbolEffect,
    extract_patch_scope,
    validate_patch_scope,
    worktree_diff,
)
from local_ai_assistant.planning.service import PlanGenerationError, PlannerService
from local_ai_assistant.planning.validation import PlanValidator


class Embedder:
    def encode(self, texts, **kwargs):
        vectors = []
        for text in texts:
            digest = hashlib.sha256(text.encode()).digest()
            vector = np.asarray([value + 1 for value in digest[:8]], dtype=np.float32)
            vectors.append(vector / np.linalg.norm(vector))
        return np.asarray(vectors, dtype=np.float32)


class FakeLLM:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        return json.dumps(self.response) if isinstance(self.response, dict) else self.response


@pytest.fixture
def planning_repo(tmp_path):
    repos = tmp_path / "repos"
    repo = repos / "demo"
    (repo / "app").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "app/service.py").write_text("def login_user(name):\n    return bool(name)\n")
    (repo / "app/api.py").write_text(
        "from app.service import login_user\n\ndef login_endpoint(name):\n    return login_user(name)\n"
    )
    (repo / "tests/test_service.py").write_text(
        "from app.service import login_user\n\ndef test_login():\n    assert login_user('a')\n"
    )
    (repo / "pyproject.toml").write_text("[project]\nname='demo'\n")
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Planner Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "planner@example.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "base"], cwd=repo, check=True, capture_output=True)
    index = SymbolIndex(repos, tmp_path / "index", Embedder())
    index.refresh(full=True)
    return tmp_path, repo, index


def response_for(index, **overrides):
    login = index.find_exact("login_user")[0]
    value = {
        "summary": "Correct login behavior with focused regression coverage.",
        "assumptions": ["Existing API remains stable."],
        "files_to_inspect": ["app/service.py", "tests/test_service.py"],
        "files_to_modify": ["app/service.py", "tests/test_service.py"],
        "files_to_create": [],
        "files_to_delete_or_rename": [],
        "symbols_to_modify": [login.identifier],
        "symbols_to_create": [],
        "steps": [
            {
                "order": 1,
                "description": "Update the existing login implementation.",
                "files": ["app/service.py"],
                "symbols": [login.identifier],
            },
            {
                "order": 2,
                "description": "Update focused regression coverage.",
                "files": ["tests/test_service.py"],
                "symbols": [],
            },
        ],
        "relevant_tests": [
            {
                "path": "tests/test_service.py",
                "reason": "Directly imports login_user.",
                "command": "python -m pytest tests/test_service.py",
                "required_full_suite": False,
            },
            {
                "path": "full-suite",
                "reason": "Required final regression suite.",
                "command": "python -m pytest",
                "required_full_suite": True,
            },
        ],
        "validation_commands": ["python -m pytest"],
        "dependency_changes": [],
        "migration_implications": [],
        "security_implications": [],
        "rollback_considerations": ["Revert the isolated Git branch."],
        "unresolved_questions": [],
    }
    value.update(overrides)
    return value


def test_named_acceptance_contract_is_pinned_in_plan_and_prompt(planning_repo):
    root, repo, index = planning_repo
    contract = "Non-empty strings return True; empty and non-string inputs return False.\n"
    (repo / "ACCEPTANCE.md").write_text(contract)
    model = FakeLLM(response_for(index))
    artifact = PlannerService(repo, index, model, root / "plans").generate(
        "Implement login_user according to ACCEPTANCE.md and correct contradictory tests."
    )
    assert "ACCEPTANCE.md" in artifact.plan.files_to_inspect
    assert contract.strip() in model.calls[0]["prompt"]
    assert "overrides contradictory inherited test expectations" in model.calls[0]["prompt"]


def test_task_classification_is_conservative_and_preserves_request():
    auth = classify_task("Fix login authorization token handling")
    ambiguous = classify_task("Please improve this somehow")
    mixed = classify_task("Document and refactor the module")

    assert auth.category is TaskCategory.AUTHENTICATION_AUTHORIZATION
    assert auth.raw_request == "Fix login authorization token handling"
    assert auth.reasons
    assert ambiguous.category is TaskCategory.UNKNOWN_MIXED
    assert ambiguous.confidence < 0.5
    assert mixed.category is TaskCategory.UNKNOWN_MIXED


@pytest.mark.parametrize(
    ("task_text", "category"),
    [
        ("Explain the cache", TaskCategory.EXPLAIN),
        ("Fix a broken calculation", TaskCategory.BUG_FIX),
        ("Add a reporting feature", TaskCategory.FEATURE),
        ("Refactor the parser", TaskCategory.REFACTOR),
        ("Add pytest coverage", TaskCategory.TEST),
        ("Update README documentation", TaskCategory.DOCUMENTATION),
        ("Change an environment setting", TaskCategory.CONFIGURATION),
        ("Upgrade a dependency", TaskCategory.DEPENDENCY_CHANGE),
        ("Create a schema migration", TaskCategory.DATABASE_MIGRATION),
        ("Fix a security vulnerability", TaskCategory.SECURITY_SENSITIVE),
        ("Change systemd deployment", TaskCategory.DEPLOYMENT_OPERATIONS),
    ],
)
def test_task_categories(task_text, category):
    assert classify_task(task_text).category is category


@pytest.mark.parametrize(
    "path",
    [
        "pyproject.toml",
        "requirements-dev.txt",
        "package.json",
        "pnpm-lock.yaml",
        "Cargo.toml",
        "Cargo.lock",
        "foundry.toml",
        "systemd/demo.service",
        "scripts/bootstrap/packages.sh",
    ],
)
def test_dependency_manifest_detection(path):
    assert is_dependency_file(path)


@pytest.mark.parametrize(
    "task_text",
    ["Make a breaking public API change", "Fix a concurrency-critical race condition"],
)
def test_public_api_and_concurrency_work_is_high_risk(task_text):
    result = assess_risk(task_text, classify_task(task_text), ("app/service.py",))
    assert result.level is RiskLevel.HIGH
    assert result.reasons


def test_scope_analysis_uses_exact_calls_importers_and_tests(planning_repo):
    _, repo, index = planning_repo
    candidates = ScopeAnalyzer(repo, index).analyze("Fix login_user")
    relationships = {item.relationship for item in candidates}

    assert "exact_symbol" in relationships
    assert "caller" in relationships
    assert "reverse_import" in relationships
    assert "relevant_test" in relationships
    assert "unresolved_call" in relationships
    assert not any(
        item.relationship == "reverse_import" and item.path.startswith("tests/")
        for item in candidates
    )
    assert all(not item.path.startswith("demo/") for item in candidates)
    assert all(item.reason and item.provenance["source"] for item in candidates)


def test_repository_map_and_legacy_fallback_are_explicit_scope_evidence(planning_repo):
    _, repo, index = planning_repo
    mapped = ScopeAnalyzer(repo, index).analyze("Inspect api.py")
    assert any(
        item.relationship == "repository_map" and item.path == "app/api.py" for item in mapped
    )

    def legacy(request):
        return [
            {
                "source": "demo/README.md",
                "line_start": 1,
                "line_end": 10,
                "retrieval_method": "line_chunk_fallback",
                "hybrid_score": 0.02,
            }
        ]

    fallback = ScopeAnalyzer(repo, index, legacy).analyze("Investigate a nonpython concern")
    assert any(item.relationship == "legacy_line_chunk" for item in fallback)


def test_plan_generation_parsing_validation_confidence_and_persistence(planning_repo):
    root, repo, index = planning_repo
    (repo / "AGENTS.md").write_text("Keep deterministic facts authoritative.")
    llm = FakeLLM(response_for(index))
    service = PlannerService(repo, index, llm, root / "plans")
    artifact = service.generate("Fix login_user bug")
    saved = service.persist(artifact)
    loaded = service.load(saved)

    assert artifact.plan.task_id == loaded.plan.task_id
    assert artifact.plan.original_request == "Fix login_user bug"
    assert artifact.plan.steps[0].order == 1
    assert artifact.plan.direct_scope
    assert artifact.plan.confidence.factors["exact_symbol_coverage"] > 0
    assert artifact.plan.risk.level is RiskLevel.HIGH
    assert artifact.plan.approval.status is ApprovalStatus.REVIEW
    assert artifact.schema_version == 2
    assert artifact.instruction_sources == ("AGENTS.md",)
    assert not [item for item in artifact.validation_issues if item.severity is IssueSeverity.ERROR]
    assert "DETERMINISTIC SCOPE EVIDENCE" in llm.calls[0]["prompt"]
    assert "never invent fallback filenames or directories" in llm.calls[0]["prompt"]
    assert len(llm.calls[0]["prompt"]) < 40_000


def test_plan_generation_retries_once_when_a_required_field_is_omitted(planning_repo):
    root, repo, index = planning_repo
    incomplete = response_for(index)
    incomplete.pop("rollback_considerations")

    class RepairingLLM:
        def __init__(self):
            self.calls = []

        def chat(self, **kwargs):
            self.calls.append(kwargs)
            return json.dumps(incomplete if len(self.calls) == 1 else response_for(index))

    llm = RepairingLLM()
    artifact = PlannerService(repo, index, llm, root / "plans").generate("Fix login_user bug")

    assert len(llm.calls) == 2
    assert "rollback_considerations" in llm.calls[1]["prompt"]
    assert '"rollback_considerations"' in llm.calls[1]["prompt"]
    assert '"string"' in llm.calls[1]["prompt"]
    assert artifact.plan.rollback_considerations == ("Revert the isolated Git branch.",)


def test_plan_generation_keeps_failing_after_one_invalid_repair(planning_repo):
    root, repo, index = planning_repo
    incomplete = response_for(index)
    incomplete.pop("rollback_considerations")

    class RepeatingLLM:
        def __init__(self):
            self.calls = []

        def chat(self, **kwargs):
            self.calls.append(kwargs)
            return json.dumps(incomplete)

    llm = RepeatingLLM()
    with pytest.raises(PlanGenerationError, match="rollback_considerations"):
        PlannerService(repo, index, llm, root / "plans").generate("Fix login_user bug")
    assert len(llm.calls) == 2


def test_plan_reload_rejects_unknown_schema(planning_repo):
    root, repo, index = planning_repo
    service = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans")
    saved = service.persist(service.generate("Fix login_user bug"))
    content = json.loads(saved.read_text())
    content["schema_version"] = 99
    saved.write_text(json.dumps(content))

    with pytest.raises(PlanGenerationError, match="Unsupported planning artifact schema"):
        service.load(saved)


def test_plan_reload_rejects_truncated_json(planning_repo):
    root, _, _ = planning_repo
    path = root / "truncated-plan.json"
    path.write_text('{"schema_version": 2, "plan":')
    with pytest.raises(PlanGenerationError, match="Invalid persisted plan"):
        PlannerService.load(path)


def test_schema_one_plan_migrates_on_reload(planning_repo):
    root, repo, index = planning_repo
    service = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans")
    content = service.generate("Fix login_user bug").to_dict()
    content["schema_version"] = 1
    content.pop("instruction_sources")
    content.pop("context_truncated")
    path = root / "plans" / "old.json"
    path.parent.mkdir()
    path.write_text(json.dumps(content))

    loaded = service.load(path)
    assert loaded.schema_version == 2
    assert loaded.instruction_sources == ()


def test_persisted_plan_is_bound_to_repository_head(planning_repo):
    root, repo, index = planning_repo
    service = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans")
    artifact = service.generate("Fix login_user bug")
    (repo / "new.txt").write_text("change")
    subprocess.run(["git", "add", "new.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "move head"], cwd=repo, check=True, capture_output=True)

    assert "starting_commit_mismatch" in {issue.code for issue in service.identity_issues(artifact)}


def test_malformed_planner_response_is_rejected(planning_repo):
    root, repo, index = planning_repo
    service = PlannerService(repo, index, FakeLLM("not JSON"), root / "plans")
    with pytest.raises(PlanGenerationError, match="malformed JSON"):
        service.generate("Fix login_user")


def test_missing_required_planner_fields_are_rejected(planning_repo):
    root, repo, index = planning_repo
    response = response_for(index)
    response.pop("files_to_modify")
    service = PlannerService(repo, index, FakeLLM(response), root / "plans")
    with pytest.raises(PlanGenerationError, match="missing required fields"):
        service.generate("Fix login_user")


def test_model_duplicate_targets_are_normalized(planning_repo):
    root, repo, index = planning_repo
    response = response_for(index)
    response["files_to_modify"] *= 2
    response["symbols_to_modify"] *= 2
    artifact = PlannerService(repo, index, FakeLLM(response), root / "plans").generate(
        "Fix login_user"
    )
    assert len(artifact.plan.files_to_modify) == len(set(artifact.plan.files_to_modify))
    assert len(artifact.plan.symbols_to_modify) == len(set(artifact.plan.symbols_to_modify))


def test_validation_rejects_missing_symbols_files_and_protected_paths(planning_repo):
    root, repo, index = planning_repo
    service = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans")
    artifact = service.generate("Fix login_user")
    invalid = replace(
        artifact.plan,
        files_to_modify=("missing.py", "var/generated.py"),
        symbols_to_modify=("missing.symbol",),
    )
    codes = {
        item.code
        for item in PlanValidator(repo, index).validate(invalid, artifact.scope_candidates)
    }
    assert {"missing_file", "missing_symbol", "protected_path"} <= codes


def test_validation_rejects_symbol_from_another_indexed_repository(planning_repo):
    root, repo, index = planning_repo
    other = root / "repos" / "other"
    other.mkdir()
    (other / "module.py").write_text("def foreign_symbol():\n    return True\n")
    index.refresh()
    foreign = next(item for item in index.find_exact("foreign_symbol"))
    service = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans")
    artifact = service.generate("Fix login_user")
    invalid = replace(artifact.plan, symbols_to_modify=(foreign.identifier,))

    assert "missing_symbol" in {
        item.code
        for item in PlanValidator(repo, index).validate(invalid, artifact.scope_candidates)
    }


def test_proposed_new_targets_dependency_and_migration_rules(planning_repo):
    root, repo, index = planning_repo
    service = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans")
    artifact = service.generate("Add login_user feature")
    new_plan = replace(
        artifact.plan,
        files_to_create=("app/new_module.py",),
        symbols_to_create=("app.new_module.created",),
    )
    assert not [
        item
        for item in PlanValidator(repo, index).validate(new_plan, artifact.scope_candidates)
        if item.code in {"missing_file", "missing_symbol"}
    ]

    dependency_plan = replace(
        artifact.plan, files_to_modify=("pyproject.toml",), dependency_changes=()
    )
    assert "unmarked_dependency_change" in {
        item.code
        for item in PlanValidator(repo, index).validate(dependency_plan, artifact.scope_candidates)
    }
    migration_plan = replace(
        artifact.plan,
        original_request="Drop table users",
        files_to_create=("migrations/001.sql",),
        migration_implications=(),
    )
    assert "unmarked_migration" in {
        item.code
        for item in PlanValidator(repo, index).validate(migration_plan, artifact.scope_candidates)
    }
    marked = replace(
        artifact.plan,
        files_to_modify=("pyproject.toml",),
        dependency_changes=(
            DependencyChange(
                "pyproject.toml", DependencyChangeKind.VERSION, "Update package version."
            ),
        ),
    )
    assert "invalid_dependency_manifest" not in {
        item.code for item in PlanValidator(repo, index).validate(marked, artifact.scope_candidates)
    }
    conflicting = replace(
        artifact.plan,
        files_to_modify=("app/service.py",),
        files_to_delete_or_rename=("app/service.py",),
    )
    assert "conflicting_target_roles" in {
        item.code
        for item in PlanValidator(repo, index).validate(conflicting, artifact.scope_candidates)
    }


def test_risk_security_dependency_migration_and_approval_policy():
    classification = classify_task("Add ordinary feature")
    confidence = assess_confidence(classification, ())
    critical = assess_risk(
        "Drop table users with production credential", classification, ("migrations/001.sql",)
    )
    dependency = assess_risk(
        "Upgrade package", classification, ("pyproject.toml",), ("version change",)
    )
    deletion = assess_risk(
        "Clean up obsolete code",
        classification,
        ("app/legacy.py",),
        (),
        ("app/legacy.py",),
    )

    assert critical.level is RiskLevel.CRITICAL
    assert dependency.level is RiskLevel.HIGH
    assert deletion.level is RiskLevel.HIGH
    assert is_dependency_file("requirements/dev.txt")
    assert detect_migration("rename column", ())
    assert detect_security("rotate auth token", ())
    assert decide_approval(critical, confidence, (), 1, 0).status is ApprovalStatus.BLOCKED
    low = assess_risk("Update docs", classify_task("Update docs"), ("docs/guide.md",))
    medium = assess_risk("Add feature", classification, ("app/service.py",))
    assert low.level is RiskLevel.LOW
    assert medium.level is RiskLevel.MEDIUM
    strong = replace(confidence, score=0.8)
    assert decide_approval(medium, strong, (), 2, 0).status is ApprovalStatus.AUTOMATIC


def test_model_cannot_downgrade_deterministic_risk(planning_repo):
    root, repo, index = planning_repo
    response = response_for(index, risk={"level": "low", "reasons": ["model says safe"]})
    artifact = PlannerService(repo, index, FakeLLM(response), root / "plans").generate(
        "Change login_user authentication"
    )
    assert artifact.plan.risk.level is RiskLevel.HIGH
    assert artifact.plan.approval.status is ApprovalStatus.REVIEW


def test_dependency_migration_and_security_flags_overlap_conservatively():
    result = assess_risk(
        "Drop table storing auth tokens while upgrading a dependency",
        classify_task("Drop table storing auth tokens while upgrading a dependency"),
        ("migrations/001.sql", "pyproject.toml"),
        ("version change",),
    )
    assert result.level is RiskLevel.CRITICAL
    assert result.security_sensitive
    assert result.dependency_change
    assert result.migration


def test_scope_guard_detects_unplanned_diff(planning_repo):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate(
        "Fix login_user"
    )
    policy = scope_guard_from_plan(artifact.plan)
    issues = compare_scope(
        policy, ("app/service.py", "unplanned.py"), (artifact.plan.symbols_to_modify[0],)
    )
    assert any("Unplanned files" in item for item in issues)
    inspect_only = replace(
        artifact.plan,
        files_to_inspect=("app/api.py",),
        files_to_modify=("app/service.py",),
    )
    inspect_policy = scope_guard_from_plan(inspect_only)
    assert "app/api.py" not in inspect_policy.allowed_files
    assert compare_scope(inspect_policy, ("app/api.py",))
    assert compare_scope(inspect_policy, ("var/generated.py",))


def test_generated_patch_is_checked_against_planned_files_and_symbols(planning_repo):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate(
        "Fix login_user"
    )
    diff = """diff --git a/app/service.py b/app/service.py
--- a/app/service.py
+++ b/app/service.py
@@ -1,2 +1,2 @@
-def login_user(name):
+def login_user(username):
     return bool(name)
"""
    scope = extract_patch_scope(diff, tuple(index.symbols), "demo/")
    policy = scope_guard_from_plan(artifact.plan)
    assert scope.modified_files == ("app/service.py",)
    assert artifact.plan.symbols_to_modify[0] in scope.changed_symbols
    assert validate_patch_scope(policy, scope) == ()


def test_explicit_test_expansion_allows_new_test_cases_only_in_approved_test_file(planning_repo):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate(
        "Expand tests/test_service.py with boundary and invalid input cases"
    )
    plan = replace(
        artifact.plan,
        files_to_modify=("tests/test_service.py",),
        original_request="Expand tests/test_service.py with boundary and invalid input cases",
    )
    policy = scope_guard_from_plan(plan)
    added_test = PatchScope(
        modified_files=("tests/test_service.py",),
        created_files=(), deleted_files=(), renamed_files=(), changed_symbols=(),
        symbol_effects=(SymbolEffect("symbol_added", "tests/test_service.py", "test_boundary", "syntactic"),),
    )
    added_helper = replace(
        added_test,
        symbol_effects=(SymbolEffect("symbol_added", "tests/test_service.py", "helper", "syntactic"),),
    )

    assert policy.allow_test_symbol_additions
    assert validate_patch_scope(policy, added_test) == ()
    assert any("Unplanned new symbols" in item for item in validate_patch_scope(policy, added_helper))


def test_patch_scope_matches_reindexed_symbol_by_qualified_name_and_scoped_path(planning_repo):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate(
        "Fix login_user"
    )
    policy = scope_guard_from_plan(artifact.plan)
    alias_scope = PatchScope(
        modified_files=("app/service.py",),
        created_files=(),
        deleted_files=(),
        renamed_files=(),
        changed_symbols=("py:task-worktree-symbol-id",),
        symbol_effects=(
            SymbolEffect(
                "existing_symbol_modified",
                "app/service.py",
                "py:task-worktree-symbol-id",
                "confirmed",
                "app.service.login_user",
            ),
        ),
    )

    assert validate_patch_scope(policy, alias_scope) == ()

    unrelated_scope = replace(
        alias_scope,
        symbol_effects=(
            replace(alias_scope.symbol_effects[0], qualified_name="app.service.logout_user"),
        ),
    )
    assert any("Unplanned symbols" in item for item in validate_patch_scope(policy, unrelated_scope))


def test_generated_patch_rejects_unplanned_file_before_apply(planning_repo):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate(
        "Fix login_user"
    )
    diff = """diff --git a/app/unplanned.py b/app/unplanned.py
new file mode 100644
--- /dev/null
+++ b/app/unplanned.py
@@ -0,0 +1 @@
+value = 1
"""
    scope = extract_patch_scope(diff, tuple(index.symbols), "demo/")
    issues = validate_patch_scope(scope_guard_from_plan(artifact.plan), scope)
    assert any("Unplanned created" in issue for issue in issues)


def test_actual_diff_includes_staged_changes(planning_repo):
    _, repo, index = planning_repo
    (repo / "app/service.py").write_text("def login_user(name):\n    return False\n")
    subprocess.run(["git", "add", "app/service.py"], cwd=repo, check=True)
    scope = extract_patch_scope(worktree_diff(repo), tuple(index.symbols), "demo/")
    assert scope.modified_files == ("app/service.py",)
    subprocess.run(["git", "restore", "--staged", "--worktree", "."], cwd=repo, check=True)


def test_multifile_patch_classifies_create_delete_rename_and_symbols(planning_repo):
    _, _, index = planning_repo
    diff = """diff --git a/app/new.py b/app/new.py
new file mode 100644
--- /dev/null
+++ b/app/new.py
@@ -0,0 +1,2 @@
+def created_symbol():
+    return True
diff --git a/app/old.py b/app/old.py
deleted file mode 100644
--- a/app/old.py
+++ /dev/null
@@ -1 +0,0 @@
-value = 1
diff --git a/app/api.py b/app/routes.py
similarity index 100%
rename from app/api.py
rename to app/routes.py
"""
    scope = extract_patch_scope(diff, tuple(index.symbols), "demo/")
    assert scope.created_files == ("app/new.py",)
    assert scope.deleted_files == ("app/old.py",)
    assert scope.renamed_files == (("app/api.py", "app/routes.py"),)
    assert any(
        item.effect == "symbol_added" and item.symbol == "created_symbol"
        for item in scope.symbol_effects
    )


def test_patch_parser_handles_quoted_spaces_and_rename_with_modify(planning_repo):
    _, _, index = planning_repo
    diff = '''diff --git "a/app/old name.py" "b/app/new name.py"
similarity index 80%
rename from "app/old name.py"
rename to "app/new name.py"
--- "a/app/old name.py"
+++ "b/app/new name.py"
@@ -1 +1 @@
-value = 1
+value = 2
'''
    scope = extract_patch_scope(diff, tuple(index.symbols), "demo/")
    assert scope.renamed_files == (("app/old name.py", "app/new name.py"),)


@pytest.mark.parametrize(
    "diff",
    [
        "diff --git a/file.py b/file.py\n",
        "diff --git a/../outside.py b/../outside.py\n@@ -1 +1 @@\n-a\n+b\n",
        "diff --git a//tmp/outside b//tmp/outside\n@@ -1 +1 @@\n-a\n+b\n",
        "diff --git a/image.bin b/image.bin\nGIT binary patch\nliteral 1\nA\n",
        "not a unified patch",
    ],
)
def test_patch_parser_rejects_malformed_binary_and_unsafe_paths(diff):
    with pytest.raises(PatchValidationError):
        extract_patch_scope(diff, ())


def test_structured_symbol_edit_rejects_stale_ranges(planning_repo):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate(
        "Fix login_user"
    )
    symbol = index.find_exact("login_user")[0]
    (repo / "app/service.py").write_text("# shifted\ndef login_user(name):\n    return bool(name)\n")
    context = ToolContext(
        repo,
        artifact,
        scope_guard_from_plan(artifact.plan),
        index,
        plan_approval_token(artifact.plan),
    )
    with pytest.raises(ToolPermissionError, match="stale"):
        default_registry().invoke(
            "replace_symbol_body",
            {"symbol": symbol.identifier, "content": "def login_user(name):\n    return True"},
            context,
        )


def test_patch_target_cannot_escape_through_repository_symlink(planning_repo):
    root, repo, index = planning_repo
    outside = root / "outside"
    outside.mkdir()
    (repo / "link").symlink_to(outside, target_is_directory=True)
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate(
        "Fix login_user"
    )
    plan = replace(artifact.plan, files_to_create=("link/escape.py",), symbols_to_create=())
    artifact = replace(artifact, plan=plan)
    patch = """diff --git a/link/escape.py b/link/escape.py
new file mode 100644
--- /dev/null
+++ b/link/escape.py
@@ -0,0 +1 @@
+value = 1
"""
    context = ToolContext(repo, artifact, scope_guard_from_plan(plan), index)
    with pytest.raises(ToolPermissionError, match="escapes repository"):
        default_registry().invoke("create_patch", {"patch": patch}, context)
    assert not (outside / "escape.py").exists()
    (repo / "link").unlink()


def test_replace_symbol_body_preserves_signature_and_targets_current_symbol(planning_repo):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate(
        "Fix login_user"
    )
    symbol = index.find_exact("login_user")[0]
    context = ToolContext(
        repo,
        artifact,
        scope_guard_from_plan(artifact.plan),
        index,
        plan_approval_token(artifact.plan),
    )
    result = default_registry().invoke(
        "replace_symbol_body",
        {"symbol": symbol.identifier, "content": "return name == 'allowed'"},
        context,
    )
    source = (repo / "app/service.py").read_text()
    assert result.success
    assert "def login_user(name):" in source
    assert "    return name == 'allowed'" in source
    subprocess.run(["git", "restore", "."], cwd=repo, check=True)


def test_repeat_edit_remains_scoped_after_approved_symbol_expands(planning_repo):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate(
        "Fix login_user"
    )
    symbol = index.find_exact("login_user")[0]
    context = ToolContext(
        repo, artifact, scope_guard_from_plan(artifact.plan), index,
        plan_approval_token(artifact.plan),
    )
    expanded_body = "value = name\n" + "\n".join(
        f"step_{number} = value" for number in range(24)
    ) + "\nreturn bool(step_23)"
    first = default_registry().invoke(
        "replace_symbol_body", {"symbol": symbol.identifier, "content": expanded_body}, context
    )
    assert first.success
    corrected_body = expanded_body.replace("return bool(step_23)", "return step_23 == 'approved'")
    second = default_registry().invoke(
        "replace_symbol_body", {"symbol": symbol.identifier, "content": corrected_body}, context
    )
    assert second.success
    assert "return step_23 == 'approved'" in (repo / "app/service.py").read_text()


def test_replace_symbol_body_dedents_generated_body_and_checks_syntax_before_write(planning_repo):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate(
        "Fix login_user"
    )
    symbol = index.find_exact("login_user")[0]
    context = ToolContext(
        repo, artifact, scope_guard_from_plan(artifact.plan), index,
        plan_approval_token(artifact.plan),
    )
    body = "        # generated body\n        if not name:\n            return False\n        return True"
    result = default_registry().invoke(
        "replace_symbol_body", {"symbol": symbol.identifier, "content": body}, context
    )
    source = (repo / "app/service.py").read_text()
    assert result.success
    assert "    # generated body\n    if not name:\n        return False\n    return True" in source
    ast.parse(source)
    subprocess.run(["git", "restore", "."], cwd=repo, check=True)


def test_replace_symbol_body_rejects_syntax_error_without_mutation(planning_repo):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate(
        "Fix login_user"
    )
    symbol = index.find_exact("login_user")[0]
    context = ToolContext(
        repo, artifact, scope_guard_from_plan(artifact.plan), index,
        plan_approval_token(artifact.plan),
    )
    original = (repo / "app/service.py").read_text()
    observation = default_registry().invoke(
        "replace_symbol_body",
        {"symbol": symbol.identifier, "content": "if name\n    return False"},
        context,
    )
    assert not observation.success and "syntax error" in observation.summary
    assert (repo / "app/service.py").read_text() == original


def test_replace_symbol_body_rejects_model_generated_inconsistent_indentation(planning_repo):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate(
        "Fix login_user"
    )
    symbol = index.find_exact("login_user")[0]
    context = ToolContext(
        repo, artifact, scope_guard_from_plan(artifact.plan), index,
        plan_approval_token(artifact.plan),
    )
    original = (repo / "app/service.py").read_text()
    malformed = (
        "        # Validate inputs\n            if not name:\n"
        "                return False\n        return True"
    )
    observation = default_registry().invoke(
        "replace_symbol_body", {"symbol": symbol.identifier, "content": malformed}, context
    )
    assert not observation.success and "syntax error" in observation.summary
    assert (repo / "app/service.py").read_text() == original


def test_replace_symbol_body_resolves_registered_root_qualified_plan_alias(planning_repo):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate(
        "Fix login_user"
    )
    approved_ids = set(artifact.plan.symbols_to_modify)
    candidate = next(item for item in artifact.plan.direct_scope if item.symbol_id in approved_ids)
    symbol = next(item for item in index.symbols if item.identifier == candidate.symbol_id)
    alias = "registered-root." + symbol.qualified_name
    candidate = replace(candidate, symbol_id=symbol.identifier, qualified_name=alias)
    plan = replace(artifact.plan, direct_scope=(candidate,), symbols_to_modify=(alias,))
    artifact = replace(artifact, plan=plan)
    context = ToolContext(repo, artifact, scope_guard_from_plan(plan), index, plan_approval_token(plan))
    result = default_registry().invoke(
        "replace_symbol_body", {"symbol": alias, "content": "return name == 'approved'"}, context
    )
    assert result.success
    assert set(subprocess.run(
        ["git", "diff", "--name-only"], cwd=repo, check=True, text=True, capture_output=True
    ).stdout.splitlines()) == {candidate.path}
    subprocess.run(["git", "restore", "."], cwd=repo, check=True)


def test_replace_symbol_body_unwraps_only_signature_identical_function(planning_repo):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate(
        "Fix login_user"
    )
    symbol = index.find_exact("login_user")[0]
    context = ToolContext(
        repo, artifact, scope_guard_from_plan(artifact.plan), index, plan_approval_token(artifact.plan)
    )
    result = default_registry().invoke(
        "replace_symbol_body",
        {"symbol": symbol.identifier, "content": "def login_user(name):\n    return name == 'approved'"},
        context,
    )
    assert result.success
    source = (repo / "app/service.py").read_text()
    assert source.count("def login_user(") == 1
    assert "    return name == 'approved'" in source
    second = default_registry().invoke(
        "replace_symbol_body",
        {"symbol": symbol.identifier, "content": "return name.startswith('a')"},
        context,
    )
    assert second.success
    assert "    return name.startswith('a')" in (repo / "app/service.py").read_text()
    subprocess.run(["git", "restore", "."], cwd=repo, check=True)
    rejected = default_registry().invoke(
        "replace_symbol_body",
        {"symbol": symbol.identifier,
         "content": "def login_user(name, is_admin=False):\n    return is_admin"},
        context,
    )
    assert not rejected.success
    assert "cannot change the approved signature" in rejected.summary
    assert "return bool(name)" in (repo / "app/service.py").read_text()


def test_replace_symbol_body_maps_registered_repository_paths_into_task_worktree(planning_repo):
    root, canonical_repo, index = planning_repo
    artifact = PlannerService(
        canonical_repo, index, FakeLLM(response_for(index)), root / "plans"
    ).generate("Fix login_user")
    task_repo = root / "worktrees" / "task-1"
    task_repo.parent.mkdir(parents=True)
    subprocess.run(
        ["git", "clone", "--quiet", str(canonical_repo), str(task_repo)], check=True
    )
    symbol = index.find_exact("login_user")[0]
    assert symbol.path == "demo/app/service.py"
    artifact = replace(
        artifact,
        plan=replace(artifact.plan, symbols_to_modify=(symbol.qualified_name,)),
    )
    context = ToolContext(
        task_repo,
        artifact,
        scope_guard_from_plan(artifact.plan),
        index,
        plan_approval_token(artifact.plan),
        canonical_repository=canonical_repo,
    )

    result = default_registry().invoke(
        "replace_symbol_body",
        {"symbol": symbol.qualified_name, "content": "return name == 'approved'"},
        context,
    )

    source = (task_repo / "app/service.py").read_text()
    assert result.success
    assert "return name == 'approved'" in source
    assert not (task_repo / "demo/app/service.py").exists()


def test_unresolved_static_evidence_reduces_confidence(planning_repo):
    _, repo, index = planning_repo
    classification = classify_task("Fix login_user")
    candidates = ScopeAnalyzer(repo, index).analyze("Fix login_user")
    without_unresolved = tuple(item for item in candidates if item.role.value != "unresolved")
    assert (
        assess_confidence(classification, candidates).score
        < assess_confidence(classification, without_unresolved).score
    )


def test_instruction_precedence_uses_nested_override(tmp_path):
    repo = tmp_path / "repo"
    nested = repo / "app"
    nested.mkdir(parents=True)
    (repo / "AGENTS.md").write_text("root rules")
    (nested / "AGENTS.md").write_text("nested rules")
    (nested / "AGENTS.override.md").write_text("override rules")

    instructions = load_project_instructions(repo, ("app/module.py",))
    assert "root rules" in instructions
    assert "override rules" in instructions
    assert "nested rules" not in instructions
    _, sources, truncated = discover_project_instructions(repo, ("app/module.py",))
    assert sources == ("AGENTS.md", "app/AGENTS.override.md")
    assert truncated is False
    _, bounded_sources, truncated = discover_project_instructions(repo, ("app/module.py",), limit=5)
    assert truncated is True
    assert bounded_sources == ("app/AGENTS.override.md",)


def test_instruction_discovery_caps_input_paths(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    for index in range(257):
        directory = repo / f"pkg{index:03d}"
        directory.mkdir()
        (directory / "module.py").write_text("value = 1\n")

    (repo / "pkg000" / "AGENTS.md").write_text("included\n")
    (repo / "pkg256" / "AGENTS.md").write_text("must-not-be-read\n")

    paths = tuple(f"pkg{index:03d}/module.py" for index in range(257))

    content, sources, truncated = discover_project_instructions(repo, paths)

    assert truncated is True
    assert "included" in content
    assert "must-not-be-read" not in content
    assert "pkg000/AGENTS.md" in sources
    assert "pkg256/AGENTS.md" not in sources


def test_approval_token_changes_with_plan_content(planning_repo):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate(
        "Fix login_user"
    )
    changed = replace(artifact.plan, summary="A different reviewed plan")
    assert plan_approval_token(artifact.plan) != plan_approval_token(changed)


def test_old_approval_token_cannot_authorize_replanned_content(planning_repo):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate(
        "Fix login_user"
    )
    old_token = plan_approval_token(artifact.plan)
    changed_plan = replace(
        artifact.plan,
        summary="Replanned scope",
        approval=ApprovalDecision(ApprovalStatus.REVIEW, ("Review changed plan",)),
    )
    changed_artifact = replace(artifact, plan=changed_plan)
    context = ToolContext(
        repo, changed_artifact, scope_guard_from_plan(changed_plan), index, old_token
    )
    with pytest.raises(ToolPermissionError, match="Exact plan approval token"):
        default_registry().invoke(
            "replace_file",
            {"path": "app/service.py", "content": "def login_user(name):\n    return True\n"},
            context,
        )


def test_bounded_tool_loop_inspects_validates_and_finishes(planning_repo):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate(
        "Fix login_user"
    )
    registry = ToolRegistry()
    registry.register(
        ToolSpec("inspect", "inspect", ToolPermission.READ_ONLY, False, 1),
        lambda context, args: ToolObservation("inspection", True, "inspected"),
    )
    registry.register(
        ToolSpec("run_tests", "validate", ToolPermission.VALIDATION, False, 1, ("command",)),
        lambda context, args: ToolObservation("command", True, "tests passed"),
    )
    actions = iter(
        [
            {
                "tool": "inspect",
                "arguments": {},
                "rationale": "inspect",
                "expected_outcome": "facts",
                "plan_step": 1,
                "mutation_intended": False,
            },
            {
                "tool": "run_tests",
                "arguments": {"command": "python -m pytest"},
                "rationale": "test",
                "expected_outcome": "pass",
                "plan_step": 2,
                "mutation_intended": False,
            },
            {
                "tool": "finish",
                "arguments": {},
                "rationale": "done",
                "expected_outcome": "complete",
                "plan_step": 2,
                "mutation_intended": False,
            },
        ]
    )
    model = FakeLLM(None)
    model.chat = lambda **kwargs: json.dumps(next(actions))
    context = ToolContext(repo, artifact, scope_guard_from_plan(artifact.plan), index)
    result = ExecutionLoop(model, registry, context, LoopLimits(max_steps=4)).run()
    assert result.status == "complete"
    assert result.steps == 3
    assert [event.tool_name for event in context.events] == [
        "inspect", "run_tests", "model_tool_choice"
    ]


def test_tool_loop_passes_bounded_read_results_to_next_model_choice(planning_repo):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate(
        "Fix login_user"
    )
    model = FakeLLM(None)
    model.chat = lambda **kwargs: model.calls.append(kwargs) or json.dumps(
        {
            "tool": "finish",
            "arguments": {},
            "rationale": "source is available",
            "expected_outcome": "implement the reviewed change",
            "plan_step": 1,
            "mutation_intended": False,
        }
    )
    loop = ExecutionLoop(
        model,
        ToolRegistry(),
        ToolContext(repo, artifact, scope_guard_from_plan(artifact.plan), index),
    )

    loop._required_inspections = lambda: ("ACCEPTANCE.md",)
    observations = [
        ToolObservation("file", True, "ACCEPTANCE.md", {"content": "Scores 30 through 64 are review."}),
        *[ToolObservation("note", True, f"observation-{i}") for i in range(9)],
    ]
    loop._next_request(observations)

    prompt = model.calls[0]["prompt"]
    assert "Scores 30 through 64 are review." in prompt
    assert "Do not repeat an unchanged read_file request" in model.calls[0]["system_prompt"]
    assert "use apply_patch for a focused edit within that exact file" in model.calls[0]["system_prompt"]
    assert "Never put a nested def/class with the target name inside a replacement body" in model.calls[0]["system_prompt"]
    assert "under 120 characters each" in model.calls[0]["system_prompt"]
    assert model.calls[0]["response_format"]["type"] == "json_schema"
    schema = model.calls[0]["response_format"]["json_schema"]["schema"]
    assert schema["required"] == ["tool", "arguments", "rationale", "expected_outcome", "plan_step", "mutation_intended"]
    assert schema["additionalProperties"] is False


def test_file_scoped_test_symbol_is_routed_to_patch_tool(planning_repo):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate(
        "Fix login_user"
    )
    test_symbol = next(
        item for item in index.symbols
        if item.path.endswith("tests/test_service.py") and item.name == "test_login"
    )
    artifact = replace(
        artifact,
        plan=replace(
            artifact.plan,
            files_to_modify=tuple(dict.fromkeys((*artifact.plan.files_to_modify, "tests/test_service.py"))),
            original_request="Expand tests/test_service.py with boundary cases",
        ),
    )
    loop = ExecutionLoop(
        FakeLLM(None), ToolRegistry(),
        ToolContext(repo, artifact, scope_guard_from_plan(artifact.plan), index),
    )
    request = ToolRequest(
        "replace_symbol_body", {"symbol": test_symbol.identifier, "content": "pass"},
        "edit test", "update tests", 1, True,
    )

    assert loop._test_symbol_requires_file_patch(request)


def test_nested_python_method_uses_index_normalized_source_for_exact_edit(planning_repo):
    root, repo, index = planning_repo
    path = repo / "tests/test_service.py"
    path.write_text(
        "from app.service import login_user\n\n"
        "class ServiceTests:\n"
        "    def test_login(self):\n"
        "        assert login_user('a') is False\n"
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "nested test fixture"], cwd=repo, check=True)
    index.refresh(full=True)
    method = next(item for item in index.symbols
                  if item.path.endswith("tests/test_service.py") and item.name == "test_login")
    artifact = PlannerService(
        repo, index, FakeLLM(response_for(index,
            files_to_modify=["tests/test_service.py"],
            symbols_to_modify=[method.qualified_name],
        )), root / "plans",
    ).generate("Correct ServiceTests.test_login in tests/test_service.py")
    assert any(candidate.symbol_id == method.identifier for candidate in artifact.scope_candidates)
    context = ToolContext(
        repo, artifact, scope_guard_from_plan(artifact.plan), index,
        plan_approval_token(artifact.plan),
    )
    observation = default_registry().invoke(
        "replace_symbol_body",
        {"symbol": method.qualified_name,
         "content": "assert login_user('a') is True",
         "_mutation_intended": True},
        context,
    )
    assert observation.success
    assert "assert login_user('a') is True" in path.read_text()
    path.write_text(path.read_text().replace("class ServiceTests:", "class ServiceTests(object):"))
    index.refresh()
    scope = extract_patch_scope(worktree_diff(repo), tuple(index.symbols), "demo/")
    assert any("Unplanned symbols" in issue for issue in validate_patch_scope(context.policy, scope))


def test_mutation_waits_for_all_approved_inspections(planning_repo):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate(
        "Fix login_user"
    )
    symbol = artifact.plan.symbols_to_modify[0]
    actions = iter([
        {"tool": "replace_symbol_body", "arguments": {"symbol": symbol, "content": "return bool(name)"},
         "rationale": "edit", "expected_outcome": "fix", "plan_step": 1, "mutation_intended": True},
        {"tool": "read_file", "arguments": {"path": "app/service.py"},
         "rationale": "inspect", "expected_outcome": "source", "plan_step": 1, "mutation_intended": False},
        {"tool": "read_file", "arguments": {"path": "tests/test_service.py"},
         "rationale": "inspect", "expected_outcome": "tests", "plan_step": 1, "mutation_intended": False},
        {"tool": "replace_symbol_body", "arguments": {"symbol": symbol, "content": "return bool(name)"},
         "rationale": "edit", "expected_outcome": "fix", "plan_step": 1, "mutation_intended": True},
        {"tool": "run_tests", "arguments": {"command": "python -m pytest"},
         "rationale": "test", "expected_outcome": "pass", "plan_step": 2, "mutation_intended": False},
        {"tool": "finish", "arguments": {}, "rationale": "done", "expected_outcome": "complete",
         "plan_step": 2, "mutation_intended": False},
    ])
    model = FakeLLM(None)
    model.chat = lambda **kwargs: json.dumps(next(actions))
    context = ToolContext(repo, artifact, scope_guard_from_plan(artifact.plan), index)
    result = ExecutionLoop(model, default_registry(), context, LoopLimits(max_steps=8)).run()
    assert result.status == "complete"
    kinds = [item.kind for item in result.observations]
    assert result.mutations == 1
    assert kinds.index("inspection_required") < kinds.index("file")


def test_tool_loop_blocks_unchanged_duplicate_file_reads(planning_repo):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate(
        "Fix login_user"
    )
    artifact = replace(artifact, plan=replace(artifact.plan, validation_commands=()))
    read = {
        "tool": "read_file", "arguments": {"path": "fraudshield.py"},
        "rationale": "inspect", "expected_outcome": "read source",
        "plan_step": 1, "mutation_intended": False,
    }
    finish = {
        "tool": "finish", "arguments": {}, "rationale": "done",
        "expected_outcome": "complete", "plan_step": 1,
        "mutation_intended": False,
    }
    actions = iter((read, read, finish))
    model = FakeLLM(None)
    model.chat = lambda **kwargs: json.dumps(next(actions))
    context = ToolContext(repo, artifact, scope_guard_from_plan(artifact.plan), index)

    result = ExecutionLoop(
        model, default_registry(), context, LoopLimits(max_steps=4)
    ).run()

    assert result.status == "complete"
    assert sum(item.kind == "duplicate_read" for item in result.observations) == 1
    assert [event.tool_name for event in context.events].count("read_file") == 1


def test_tool_loop_bounds_large_read_results_in_model_context(planning_repo):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate(
        "Fix login_user"
    )
    model = FakeLLM(None)
    model.chat = lambda **kwargs: model.calls.append(kwargs) or json.dumps(
        {
            "tool": "finish",
            "arguments": {},
            "rationale": "source is available",
            "expected_outcome": "implement the reviewed change",
            "plan_step": 1,
            "mutation_intended": False,
        }
    )
    loop = ExecutionLoop(
        model,
        ToolRegistry(),
        ToolContext(repo, artifact, scope_guard_from_plan(artifact.plan), index),
    )

    loop._next_request(
        [ToolObservation("file", True, "large.py", {"content": "x" * 50_000})]
    )

    prompt = model.calls[0]["prompt"]
    assert "truncated_json" in prompt
    assert "...[truncated]" in prompt
    assert len(prompt) <= loop.limits.context_characters


def test_tool_loop_corrects_one_malformed_model_request_without_relaxing_schema(planning_repo):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate(
        "Fix login_user"
    )
    artifact = replace(artifact, plan=replace(artifact.plan, validation_commands=()))
    registry = ToolRegistry()
    responses = iter(
        [
            json.dumps(
                {
                    "tool": "finish", "arguments": {}, "rationale": "done",
                    "expected_outcome": "complete", "plan_step": [],
                    "mutation_intended": False,
                }
            ),
            json.dumps(
                {
                    "tool": "finish", "arguments": {}, "rationale": "done",
                    "expected_outcome": "complete", "plan_step": 1,
                    "mutation_intended": False,
                }
            ),
        ]
    )
    model = FakeLLM(None)
    model.chat = lambda **kwargs: model.calls.append(kwargs) or next(responses)

    result = ExecutionLoop(
        model,
        registry,
        ToolContext(repo, artifact, scope_guard_from_plan(artifact.plan), index),
        LoopLimits(max_steps=1),
    ).run()

    assert result.status == "complete"
    assert len(model.calls) == 2
    assert "plan_step must be a JSON integer" in model.calls[1]["prompt"]


def test_tool_choice_corrects_symbol_scoped_whole_file_replacement(planning_repo):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate(
        "Fix login_user"
    )
    registry = ToolRegistry()
    registry.register(ToolSpec("replace_file", "Replace complete file", ToolPermission.SAFE_MUTATION,
                               True, 30, ("path", "content")),
                      lambda _context, _args: ToolObservation("mutation", True, "replaced"))
    registry.register(ToolSpec("replace_symbol_body", "Replace one symbol body", ToolPermission.SAFE_MUTATION,
                               True, 30, ("symbol", "content")),
                      lambda _context, _args: ToolObservation("mutation", True, "replaced symbol"))
    responses = iter([
        json.dumps({"tool": "replace_file", "arguments": {"path": "app/service.py", "content": "whole file"},
                    "rationale": "replace file", "expected_outcome": "updated file", "plan_step": 1,
                    "mutation_intended": True}),
        json.dumps({"tool": "replace_symbol_body", "arguments": {"symbol": "app.service.login_user", "content": "return None"},
                    "rationale": "replace approved body", "expected_outcome": "updated symbol", "plan_step": 1,
                    "mutation_intended": True}),
    ])
    model = FakeLLM(None)
    model.chat = lambda **kwargs: model.calls.append(kwargs) or next(responses)
    policy = scope_guard_from_plan(artifact.plan)
    assert "app/service.py" in policy.symbol_scoped_files
    loop = ExecutionLoop(model, registry, ToolContext(repo, artifact, policy, index))

    request = loop._next_request([])

    assert request.tool == "replace_symbol_body"
    assert len(model.calls) == 2
    assert "cannot edit symbol-scoped path app/service.py" in model.calls[1]["prompt"]


def test_tool_choice_corrects_unapproved_module_symbol_to_approved_new_symbol(planning_repo):
    root, repo, index = planning_repo
    login = index.find_exact("login_user")[0]
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate(
        "Fix login_user"
    )
    module_candidate = replace(
        artifact.plan.direct_scope[0], symbol_id="py:unapproved-module",
        qualified_name="app.service",
    )
    plan = replace(
        artifact.plan, symbols_to_create=("app.service.login_category",),
        direct_scope=(*artifact.plan.direct_scope, module_candidate),
    )
    artifact = replace(artifact, plan=plan)
    registry = default_registry()
    responses = iter([
        json.dumps({"tool": "replace_symbol_body", "arguments": {
            "symbol": "app.service", "content": "def login_category(name):\n    return bool(name)\n"},
            "rationale": "create helper", "expected_outcome": "helper exists", "plan_step": 1,
            "mutation_intended": True}),
        json.dumps({"tool": "insert_after_symbol", "arguments": {
            "symbol": login.identifier, "content": "\n\ndef login_category(name):\n    return bool(name)\n"},
            "rationale": "create approved helper", "expected_outcome": "helper exists", "plan_step": 1,
            "mutation_intended": True}),
    ])
    model = FakeLLM(None)
    model.chat = lambda **kwargs: model.calls.append(kwargs) or next(responses)
    context = ToolContext(repo, artifact, scope_guard_from_plan(plan), index, plan_approval_token(plan))
    request = ExecutionLoop(model, registry, context)._next_request([])

    assert request.tool == "insert_after_symbol"
    assert len(model.calls) == 2
    assert "outside approved scope" in model.calls[1]["prompt"]
    assert "insert_after_symbol" in model.calls[0]["system_prompt"]
    observation = registry.invoke(request.tool, request.arguments, context)
    assert observation.success
    assert "def login_category(name):" in (repo / "app/service.py").read_text()
    with pytest.raises(ToolPermissionError, match="outside approved scope"):
        registry.invoke("replace_symbol_body", {
            "symbol": "app.service", "content": "return False\n"}, context)


def test_tool_choice_rejects_non_string_registered_arguments(planning_repo):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate(
        "Fix login_user"
    )
    registry = ToolRegistry()
    registry.register(ToolSpec("replace_file", "Replace complete file", ToolPermission.SAFE_MUTATION,
                               True, 30, ("path", "content")),
                      lambda _context, _args: ToolObservation("mutation", True, "replaced"))
    loop = ExecutionLoop(
        FakeLLM(None), registry,
        ToolContext(repo, artifact, scope_guard_from_plan(artifact.plan), index),
    )

    raw = json.dumps({"tool": "replace_file", "arguments": {"path": "app/service.py", "content": {"source": "bad"}},
                      "rationale": "replace", "expected_outcome": "updated", "plan_step": 1,
                      "mutation_intended": True})
    with pytest.raises(ValueError, match="argument 'content' must be a string"):
        loop._decode_tool_request(raw)


def test_report_only_loop_runs_exact_inspection_and_validation_without_model(planning_repo):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate(
        "Inspect login_user"
    )
    artifact = replace(
        artifact,
        plan=replace(
            artifact.plan,
            files_to_modify=(),
            files_to_create=(),
            files_to_delete_or_rename=(),
            files_to_inspect=("app/service.py",),
            validation_commands=("git status --short",),
        ),
    )
    registry = ToolRegistry()
    invoked = []
    registry.register(
        ToolSpec("read_file", "read", ToolPermission.READ_ONLY, False, 1, ("path",)),
        lambda _context, args: invoked.append(("read_file", args["path"]))
        or ToolObservation("file", True, "read"),
    )
    registry.register(
        ToolSpec("run_safe_command", "check", ToolPermission.VALIDATION, False, 1, ("command",)),
        lambda _context, args: invoked.append(("run_safe_command", args["command"]))
        or ToolObservation("command", True, "passed"),
    )

    class ModelMustNotRun:
        def chat(self, **_kwargs):
            raise AssertionError("report-only execution must not call the model")

    context = ToolContext(repo, artifact, scope_guard_from_plan(artifact.plan), index)
    result = ExecutionLoop(ModelMustNotRun(), registry, context).run()

    assert result.status == "complete"
    assert invoked == [("read_file", "app/service.py"), ("run_safe_command", "git status --short")]
    assert [event.tool_name for event in context.events] == ["read_file", "run_safe_command"]


def test_execution_prompt_supplies_exact_registered_tool_arguments(planning_repo):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate(
        "Implement a small parser"
    )

    class CapturingModel:
        def chat(self, **kwargs):
            self.kwargs = kwargs
            return json.dumps(
                {
                    "tool": "read_file",
                    "arguments": {"path": "app/service.py"},
                    "rationale": "Inspect the approved source.",
                    "expected_outcome": "Read the source file.",
                    "plan_step": 1,
                    "mutation_intended": False,
                }
            )

    model = CapturingModel()
    loop = ExecutionLoop(
        model,
        default_registry(),
        ToolContext(repo, artifact, scope_guard_from_plan(artifact.plan), index),
    )

    request = loop._next_request([])
    payload = json.loads(model.kwargs["prompt"])
    read_file = next(item for item in payload["tools"] if item["name"] == "read_file")

    assert read_file["input_fields"] == ["path"]
    assert read_file["permission"] == "read_only"
    assert read_file["mutates"] is False
    assert "must contain exactly that tool's listed input_fields" in model.kwargs["system_prompt"]
    assert request.arguments == {"path": "app/service.py"}


def test_tool_choice_truncated_unterminated_string_uses_bounded_corrective_response(planning_repo, tmp_path):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate("Fix login_user")
    registry = ToolRegistry()
    registry.register(ToolSpec("inspect", "inspect", ToolPermission.READ_ONLY, False, 1),
                      lambda _context, _args: ToolObservation("inspection", True, "read"))
    first = '{"tool":"inspect","arguments":{},"rationale":"read source","expected_outcome":"continue","plan_step":1,"mutation_intended":false}'
    malformed = '{"tool":"inspect","arguments":{},"rationale":"read source","expected_outcome":"unterminated'
    model = FakeLLM(None)
    outputs = iter([malformed, first])
    model.chat = lambda **kwargs: (model.calls.append(kwargs), next(outputs))[1]
    diagnostics = tmp_path / "private-diagnostics"
    loop = ExecutionLoop(model, registry, ToolContext(repo, artifact, scope_guard_from_plan(artifact.plan), index), diagnostics_dir=diagnostics)
    request = loop._next_request([])
    assert request.tool == "inspect"
    assert model.calls[0]["max_tokens"] == model.calls[1]["max_tokens"] == 4096
    assert model.calls[0]["response_format"]["type"] == "json_schema"
    assert list(diagnostics.glob("tool-choice-invalid-*.json")) == []


def test_valid_structured_tool_choice_records_safe_response_and_parsed_decision(planning_repo):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate("Fix login_user")
    context = ToolContext(repo, artifact, scope_guard_from_plan(artifact.plan), index)
    model = FakeLLM({"tool": "finish", "arguments": {}, "rationale": "done",
                     "expected_outcome": "complete", "plan_step": 2, "mutation_intended": False})
    def chat(**_kwargs):
        model.last_response_metadata = {
            "finish_reason": "stop",
            "response_format": {"type": "json_schema", "json_schema": {"name": "friday_tool_choice"}},
        }
        return json.dumps(model.response)
    model.chat = chat
    request = ExecutionLoop(model, default_registry(), context)._next_request([])
    assert request.tool == "finish"
    event = context.events[-1]
    assert event.tool_name == "model_tool_choice"
    assert event.decision_metadata == {
        "finish_reason": "stop", "response_characters": len(json.dumps(model.response)),
        "response_format_type": "json_schema", "schema_name": "friday_tool_choice",
        "corrective_retry": False, "parsed_tool": "finish", "plan_step": 2,
        "argument_names": [], "scope_mapping": {},
    }


def test_two_malformed_tool_choices_are_non_executable_and_capture_exact_raw(planning_repo, tmp_path):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate("Fix login_user")
    registry = ToolRegistry()
    registry.register(ToolSpec("inspect", "inspect", ToolPermission.READ_ONLY, False, 1),
                      lambda _context, _args: ToolObservation("inspection", True, "read"))
    malformed = '{"tool":"inspect","arguments":{},"rationale":"unterminated'
    model = FakeLLM(None)
    model.chat = lambda **_kwargs: malformed
    diagnostics = tmp_path / "private-diagnostics"
    loop = ExecutionLoop(model, registry, ToolContext(repo, artifact, scope_guard_from_plan(artifact.plan), index), diagnostics_dir=diagnostics)
    with pytest.raises(ToolExecutionError, match="Malformed tool choice after bounded corrective retry"):
        loop._next_request([])
    capture = next(diagnostics.glob("tool-choice-invalid-*.json"))
    assert capture.stat().st_mode & 0o777 == 0o600
    saved = json.loads(capture.read_text())
    assert saved["responses"] == [{"raw": malformed, "characters": len(malformed)}] * 2
    assert saved["max_tokens"] == 4096
    assert saved["stop_sequences"] == []


def test_tool_choice_marked_length_is_non_executable_even_when_json_parses(planning_repo, tmp_path):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate("Fix login_user")
    registry = ToolRegistry()
    registry.register(ToolSpec("inspect", "inspect", ToolPermission.READ_ONLY, False, 1),
                      lambda _context, _args: ToolObservation("inspection", True, "read"))
    complete = json.dumps({"tool": "inspect", "arguments": {}, "rationale": "read source",
                           "expected_outcome": "continue", "plan_step": 1,
                           "mutation_intended": False})
    model = FakeLLM(None)
    def truncated(**kwargs):
        model.calls.append(kwargs)
        model.last_response_metadata = {"finish_reason": "length", "max_tokens": 4096}
        return complete
    model.chat = truncated
    diagnostics = tmp_path / "truncated-diagnostics"
    loop = ExecutionLoop(model, registry, ToolContext(repo, artifact, scope_guard_from_plan(artifact.plan), index), diagnostics_dir=diagnostics)
    with pytest.raises(ToolExecutionError, match="corrective tool-choice response was truncated"):
        loop._next_request([])
    capture = json.loads(next(diagnostics.glob("tool-choice-invalid-*.json")).read_text())
    assert [item["finish_reason"] for item in capture["response_metadata"]] == ["length", "length"]
    assert capture["responses"][0]["raw"] == complete


def test_role_routed_tool_choice_reads_finish_reason_and_rejects_truncation(planning_repo):
    from local_ai_assistant.roles.service import Role, RoleOrchestrator

    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate(
        "Fix login_user"
    )

    class Model:
        last_response_metadata = {"finish_reason": "length", "response_format": {"type": "json_schema"}}

        def chat(self, _prompt, **_kwargs):
            return json.dumps({
                "tool": "finish", "arguments": {}, "rationale": "done",
                "expected_outcome": "complete", "plan_step": 1,
                "mutation_intended": False,
            })

    role_client = RoleOrchestrator(Model()).client(Role.CODER)
    loop = ExecutionLoop(
        role_client, default_registry(),
        ToolContext(repo, artifact, scope_guard_from_plan(artifact.plan), index),
    )

    assert loop._last_response_metadata()["finish_reason"] == "length"
    with pytest.raises(ToolExecutionError, match="tool-choice response was truncated"):
        loop._next_request([])


def test_tool_loop_requires_each_plan_validation_command(planning_repo):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate(
        "Fix login_user"
    )
    artifact = replace(
        artifact,
        plan=replace(
            artifact.plan,
            validation_commands=("python -m pytest", "ruff check ."),
        ),
    )
    registry = ToolRegistry()
    registry.register(
        ToolSpec("run_tests", "validate", ToolPermission.VALIDATION, False, 1, ("command",)),
        lambda context, args: ToolObservation("command", True, "tests passed"),
    )
    actions = iter(
        [
            {
                "tool": "run_tests",
                "arguments": {"command": "python -m pytest"},
                "rationale": "test",
                "expected_outcome": "pass",
                "plan_step": 1,
                "mutation_intended": False,
            },
            {
                "tool": "finish",
                "arguments": {},
                "rationale": "done",
                "expected_outcome": "complete",
                "plan_step": 2,
                "mutation_intended": False,
            },
        ]
    )
    model = FakeLLM(None)
    model.chat = lambda **kwargs: json.dumps(next(actions))
    result = ExecutionLoop(
        model,
        registry,
        ToolContext(repo, artifact, scope_guard_from_plan(artifact.plan), index),
        LoopLimits(max_steps=2),
    ).run()
    assert result.status == "max_steps"
    assert result.observations[-1].kind == "validation_required"
    assert "ruff check ." in result.observations[-1].summary


def test_dry_run_skips_validation_commands_that_may_write_caches(planning_repo):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate(
        "Fix login_user"
    )
    invoked = []
    registry = ToolRegistry()
    registry.register(
        ToolSpec("run_tests", "validate", ToolPermission.VALIDATION, False, 1, ("command",)),
        lambda context, args: invoked.append(args) or ToolObservation("command", True, "ran"),
    )
    actions = iter(
        [
            {
                "tool": "run_tests",
                "arguments": {"command": "python -m pytest"},
                "rationale": "preview validation",
                "expected_outcome": "would run",
                "plan_step": 1,
                "mutation_intended": False,
            },
            {
                "tool": "finish",
                "arguments": {},
                "rationale": "done",
                "expected_outcome": "preview complete",
                "plan_step": 1,
                "mutation_intended": False,
            },
        ]
    )
    model = FakeLLM(None)
    model.chat = lambda **kwargs: json.dumps(next(actions))
    result = ExecutionLoop(
        model,
        registry,
        ToolContext(repo, artifact, scope_guard_from_plan(artifact.plan), index),
        LoopLimits(max_steps=2),
    ).run(dry_run=True)
    assert result.status == "dry_run_complete"
    assert invoked == []


def test_tool_loop_stops_at_max_steps(planning_repo):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate(
        "Fix login_user"
    )
    registry = ToolRegistry()
    registry.register(
        ToolSpec("inspect", "inspect", ToolPermission.READ_ONLY, False, 1),
        lambda context, args: ToolObservation("inspection", True, "ok"),
    )
    model = FakeLLM(None)
    model.chat = lambda **kwargs: json.dumps(
        {
            "tool": "inspect",
            "arguments": {},
            "rationale": "again",
            "expected_outcome": "facts",
            "plan_step": 1,
            "mutation_intended": False,
        }
    )
    result = ExecutionLoop(
        model,
        registry,
        ToolContext(repo, artifact, scope_guard_from_plan(artifact.plan), index),
        LoopLimits(max_steps=2),
    ).run()
    assert result.status == "max_steps"


def test_tool_loop_stops_at_max_repairs(planning_repo):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate(
        "Fix login_user"
    )
    registry = ToolRegistry()
    registry.register(
        ToolSpec("validate", "validate", ToolPermission.VALIDATION, False, 1),
        lambda context, args: ToolObservation("command", False, "tests failed"),
    )
    model = FakeLLM(None)
    model.chat = lambda **kwargs: json.dumps(
        {
            "tool": "validate",
            "arguments": {},
            "rationale": "retry",
            "expected_outcome": "pass",
            "plan_step": 2,
            "mutation_intended": False,
        }
    )
    result = ExecutionLoop(
        model,
        registry,
        ToolContext(repo, artifact, scope_guard_from_plan(artifact.plan), index),
        LoopLimits(max_steps=4, max_repairs=1),
    ).run()
    assert result.status == "max_repairs"


def test_execution_loop_honors_cooperative_cancel_before_model_action(planning_repo):
    root, repo, index = planning_repo
    artifact = PlannerService(
        repo, index, FakeLLM(response_for(index)), root / "plans"
    ).generate("Fix login_user")
    context = ToolContext(
        repo, artifact, scope_guard_from_plan(artifact.plan), index
    )

    class ModelMustNotRun:
        def chat(self, **kwargs):
            raise AssertionError("model was called after cancellation")

    result = ExecutionLoop(
        ModelMustNotRun(),
        default_registry(),
        context,
        LoopLimits(max_steps=4),
        cancel_check=lambda: True,
    ).run()

    assert result.status == "cancelled"
    assert result.steps == 0
    assert result.observations[0].kind == "cancelled"


def test_execution_loop_honors_cancel_race_after_tool_completion(planning_repo):
    root, repo, index = planning_repo
    artifact = PlannerService(
        repo, index, FakeLLM(response_for(index)), root / "plans"
    ).generate("Fix login_user")
    registry = ToolRegistry()
    invoked = []
    registry.register(
        ToolSpec("inspect", "inspect", ToolPermission.READ_ONLY, False, 1),
        lambda context, args: invoked.append("inspect")
        or ToolObservation("inspection", True, "finished"),
    )
    model = FakeLLM(None)
    model.chat = lambda **kwargs: json.dumps(
        {
            "tool": "inspect",
            "arguments": {},
            "rationale": "inspect once",
            "expected_outcome": "facts",
            "plan_step": 1,
            "mutation_intended": False,
        }
    )
    checks = iter((False, False, True))
    result = ExecutionLoop(
        model,
        registry,
        ToolContext(repo, artifact, scope_guard_from_plan(artifact.plan), index),
        LoopLimits(max_steps=4),
        cancel_check=lambda: next(checks),
    ).run()

    assert invoked == ["inspect"]
    assert result.status == "cancelled"
    assert [item.kind for item in result.observations] == ["inspection", "cancelled"]


def test_plan_bound_create_file_enforces_scope_and_approval(planning_repo):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate(
        "Fix login_user"
    )
    plan = replace(
        artifact.plan,
        files_to_create=("app/new.py",),
        symbols_to_create=("app.new.created_symbol",),
    )
    artifact = replace(artifact, plan=plan)
    context = ToolContext(
        repo, artifact, scope_guard_from_plan(plan), index, plan_approval_token(plan)
    )
    observation = default_registry().invoke(
        "create_file",
        {"path": "app/new.py", "content": "def created_symbol():\n    return True\n"},
        context,
    )
    assert observation.success
    assert (repo / "app/new.py").is_file()
    (repo / "app/new.py").unlink()

    with pytest.raises(ToolPermissionError):
        default_registry().invoke(
            "create_file",
            {"path": "app/unplanned.py", "content": "value = 1\n"},
            context,
        )


def test_registry_audits_rejections_and_rejects_unknown_arguments(planning_repo):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate(
        "Fix login_user"
    )
    context = ToolContext(repo, artifact, scope_guard_from_plan(artifact.plan), index)
    with pytest.raises(ToolNotFoundError, match="Unknown tool"):
        default_registry().invoke("unknown_mutator", {}, context)
    assert context.events[-1].success is False


def test_validation_command_repository_mutation_rolls_back(planning_repo, monkeypatch):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate(
        "Fix login_user"
    )
    original = (repo / "app/service.py").read_text()

    def mutate(command, repository, timeout):
        (repository / "app/service.py").write_text("corrupted by test\n")
        return CommandResult(("pytest",), 0, "passed", "", False)

    monkeypatch.setattr("local_ai_assistant.execution.registry.run_allowed_command", mutate)
    context = ToolContext(repo, artifact, scope_guard_from_plan(artifact.plan), index)
    result = default_registry().invoke(
        "run_tests", {"command": "python -m pytest"}, context
    )
    assert result.kind == "scope_rejection"
    assert (repo / "app/service.py").read_text() == original
    assert subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo, text=True, capture_output=True
    ).stdout == ""
    with pytest.raises(ToolArgumentError, match="Unexpected arguments"):
        default_registry().invoke("read_file", {"path": "app/service.py", "extra": True}, context)
    assert context.events[-1].success is False
    with pytest.raises(ToolPermissionError, match="Exact plan approval token"):
        default_registry().invoke("revert_current_changes", {}, context)
    assert not (repo / "app/unplanned.py").exists()


def test_mutation_rejects_stale_git_head(planning_repo):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate(
        "Fix login_user"
    )
    (repo / "head.txt").write_text("new head")
    subprocess.run(["git", "add", "head.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "advance"], cwd=repo, check=True, capture_output=True)
    context = ToolContext(
        repo,
        artifact,
        scope_guard_from_plan(artifact.plan),
        index,
        plan_approval_token(artifact.plan),
    )
    with pytest.raises(ToolPermissionError, match="stale"):
        default_registry().invoke(
            "replace_file",
            {"path": "app/service.py", "content": "value = 1\n"},
            context,
        )


def test_post_apply_scope_expansion_rolls_back_immediately(planning_repo):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate(
        "Fix login_user"
    )
    context = ToolContext(repo, artifact, scope_guard_from_plan(artifact.plan), index)
    (repo / "outside.py").write_text("value = 1\n")
    issues = _enforce_worktree_scope(context, "")
    assert any("outside.py" in issue for issue in issues)
    assert not (repo / "outside.py").exists()
