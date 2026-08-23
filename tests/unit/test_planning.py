from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import replace

import numpy as np
import pytest

from local_ai_assistant.code_index.symbol_index import SymbolIndex
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
from local_ai_assistant.planning.instructions import load_project_instructions
from local_ai_assistant.planning.models import (
    ApprovalStatus,
    DependencyChange,
    DependencyChangeKind,
    IssueSeverity,
    RiskLevel,
    TaskCategory,
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
    (repo / "app/api.py").write_text("from app.service import login_user\n\ndef login_endpoint(name):\n    return login_user(name)\n")
    (repo / "tests/test_service.py").write_text("from app.service import login_user\n\ndef test_login():\n    assert login_user('a')\n")
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
            {"order": 1, "description": "Update the existing login implementation.", "files": ["app/service.py"], "symbols": [login.identifier]},
            {"order": 2, "description": "Update focused regression coverage.", "files": ["tests/test_service.py"], "symbols": []},
        ],
        "relevant_tests": [
            {"path": "tests/test_service.py", "reason": "Directly imports login_user.", "command": "python -m pytest tests/test_service.py", "required_full_suite": False},
            {"path": "full-suite", "reason": "Required final regression suite.", "command": "python -m pytest", "required_full_suite": True},
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
    assert all(not item.path.startswith("demo/") for item in candidates)
    assert all(item.reason and item.provenance["source"] for item in candidates)


def test_repository_map_and_legacy_fallback_are_explicit_scope_evidence(planning_repo):
    _, repo, index = planning_repo
    mapped = ScopeAnalyzer(repo, index).analyze("Inspect api.py")
    assert any(item.relationship == "repository_map" and item.path == "app/api.py" for item in mapped)

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


def test_malformed_planner_response_is_rejected(planning_repo):
    root, repo, index = planning_repo
    service = PlannerService(repo, index, FakeLLM("not JSON"), root / "plans")
    with pytest.raises(PlanGenerationError, match="malformed JSON"):
        service.generate("Fix login_user")


def test_validation_rejects_missing_symbols_files_and_protected_paths(planning_repo):
    root, repo, index = planning_repo
    service = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans")
    artifact = service.generate("Fix login_user")
    invalid = replace(
        artifact.plan,
        files_to_modify=("missing.py", "var/generated.py"),
        symbols_to_modify=("missing.symbol",),
    )
    codes = {item.code for item in PlanValidator(repo, index).validate(invalid, artifact.scope_candidates)}
    assert {"missing_file", "missing_symbol", "protected_path"} <= codes


def test_proposed_new_targets_dependency_and_migration_rules(planning_repo):
    root, repo, index = planning_repo
    service = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans")
    artifact = service.generate("Add login_user feature")
    new_plan = replace(artifact.plan, files_to_create=("app/new_module.py",), symbols_to_create=("app.new_module.created",))
    assert not [item for item in PlanValidator(repo, index).validate(new_plan, artifact.scope_candidates) if item.code in {"missing_file", "missing_symbol"}]

    dependency_plan = replace(artifact.plan, files_to_modify=("pyproject.toml",), dependency_changes=())
    assert "unmarked_dependency_change" in {item.code for item in PlanValidator(repo, index).validate(dependency_plan, artifact.scope_candidates)}
    migration_plan = replace(artifact.plan, original_request="Drop table users", files_to_create=("migrations/001.sql",), migration_implications=())
    assert "unmarked_migration" in {item.code for item in PlanValidator(repo, index).validate(migration_plan, artifact.scope_candidates)}
    marked = replace(
        artifact.plan,
        files_to_modify=("pyproject.toml",),
        dependency_changes=(DependencyChange("pyproject.toml", DependencyChangeKind.VERSION, "Update package version."),),
    )
    assert "invalid_dependency_manifest" not in {item.code for item in PlanValidator(repo, index).validate(marked, artifact.scope_candidates)}


def test_risk_security_dependency_migration_and_approval_policy():
    classification = classify_task("Add ordinary feature")
    confidence = assess_confidence(classification, ())
    critical = assess_risk("Drop table users with production credential", classification, ("migrations/001.sql",))
    dependency = assess_risk("Upgrade package", classification, ("pyproject.toml",), ("version change",))

    assert critical.level is RiskLevel.CRITICAL
    assert dependency.level is RiskLevel.HIGH
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


def test_scope_guard_detects_unplanned_diff(planning_repo):
    root, repo, index = planning_repo
    artifact = PlannerService(repo, index, FakeLLM(response_for(index)), root / "plans").generate("Fix login_user")
    policy = scope_guard_from_plan(artifact.plan)
    issues = compare_scope(policy, ("app/service.py", "unplanned.py"), (artifact.plan.symbols_to_modify[0],))
    assert any("Unplanned files" in item for item in issues)


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
