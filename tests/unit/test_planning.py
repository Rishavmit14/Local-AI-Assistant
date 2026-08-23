from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import replace

import numpy as np
import pytest

from local_ai_assistant.code_index.symbol_index import SymbolIndex
from local_ai_assistant.execution.loop import ExecutionLoop, LoopLimits
from local_ai_assistant.execution.models import ToolObservation, ToolPermission, ToolSpec
from local_ai_assistant.execution.registry import ToolContext, ToolRegistry
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
    ApprovalStatus,
    DependencyChange,
    DependencyChangeKind,
    IssueSeverity,
    RiskLevel,
    TaskCategory,
    plan_approval_token,
)
from local_ai_assistant.planning.patch_scope import extract_patch_scope, validate_patch_scope
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
    assert len(llm.calls[0]["prompt"]) < 40_000


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


def test_approval_token_changes_with_plan_content(planning_repo):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate(
        "Fix login_user"
    )
    changed = replace(artifact.plan, summary="A different reviewed plan")
    assert plan_approval_token(artifact.plan) != plan_approval_token(changed)


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
        ToolSpec("validate", "validate", ToolPermission.VALIDATION, False, 1),
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
                "tool": "validate",
                "arguments": {},
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
    assert len(context.events) == 2


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
