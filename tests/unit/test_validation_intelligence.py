from __future__ import annotations

import json
import os
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

import local_ai_assistant.validation.service as validation_service_module
from local_ai_assistant.execution.history import redact
from local_ai_assistant.planning.analysis import scope_guard_from_plan
from local_ai_assistant.planning.models import (
    ApprovalDecision,
    ApprovalStatus,
    ConfidenceAssessment,
    DependencyChange,
    DependencyChangeKind,
    ImplementationPlan,
    PlannedTest,
    PlanningArtifact,
    RiskAssessment,
    RiskLevel,
    TaskCategory,
    TaskClassification,
)
from local_ai_assistant.validation.cache import ValidationCache
from local_ai_assistant.validation.cli import build_parser as build_validation_parser
from local_ai_assistant.validation.decision import decide_final, repair_decision
from local_ai_assistant.validation.detection import (
    build_validation_plan,
    detect_validators,
    select_targeted_tests,
)
from local_ai_assistant.validation.errors import (
    TestGenerationError as GeneratedTestError,
)
from local_ai_assistant.validation.errors import (
    ValidationArtifactError,
    ValidationIntelligenceError,
)
from local_ai_assistant.validation.failures import classify_failure
from local_ai_assistant.validation.models import (
    DecisionStatus,
    FailureCategory,
    Requirement,
    ReviewFinding,
    ReviewResult,
    ReviewSeverity,
    ValidationKind,
    ValidationReport,
    ValidationResult,
    ValidationStep,
)
from local_ai_assistant.validation.repair import BoundedRepairEngine
from local_ai_assistant.validation.review import deterministic_review, model_review
from local_ai_assistant.validation.security import (
    enhanced_auth_review,
    scan_changed_content,
)
from local_ai_assistant.validation.service import (
    ValidationService,
    load_validation_plan,
    load_validation_report,
    persist_validation_plan,
    persist_validation_report,
)
from local_ai_assistant.validation.tests import (
    generate_test_patch,
    meaningful_tdd_failure,
    validate_test_patch,
)


class FakeModel:
    def __init__(self, response):
        self.response = response
        self.prompts = []

    def chat(self, **kwargs):
        self.prompts.append(kwargs)
        return json.dumps(self.response) if not isinstance(self.response, str) else self.response


@pytest.fixture
def validation_repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / "app").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "app/service.py").write_text("def login_user(name):\n    return bool(name)\n")
    (repo / "tests/test_service.py").write_text(
        "from app.service import login_user\n\ndef test_login_user():\n    assert login_user('a')\n"
    )
    (repo / "pyproject.toml").write_text(
        "[project]\nname='demo'\n[tool.pytest.ini_options]\n[tool.ruff]\n"
    )
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "base"], cwd=repo, check=True, capture_output=True)
    return repo


def make_plan(repo: Path, risk=RiskLevel.MEDIUM):
    classification = TaskClassification(TaskCategory.BUG_FIX, 0.9, ("bug",), "Fix login_user")
    return ImplementationPlan(
        "task-1",
        "Fix login_user",
        classification,
        "Fix login behavior",
        (),
        (),
        (),
        ("app/service.py", "tests/test_service.py"),
        ("app/service.py", "tests/test_service.py"),
        (),
        (),
        ("app.service.login_user",),
        (),
        (),
        (PlannedTest("tests/test_service.py", "References login_user", "python -m pytest -q tests/test_service.py", risk is not RiskLevel.LOW),),
        ("python -m pytest -q",),
        (),
        (),
        (),
        (),
        (),
        ConfidenceAssessment(0.8, {"exact": 1.0}, ("exact",)),
        RiskAssessment(risk, ("application logic",)),
        ApprovalDecision(ApprovalStatus.AUTOMATIC, ("supported",)),
    )


def make_artifact(repo: Path, plan=None):
    plan = plan or make_plan(repo)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    return PlanningArtifact(
        "2026-08-24T00:00:00Z",
        str(repo),
        head,
        plan.original_request,
        plan.classification,
        (),
        plan,
    )


def test_validation_plan_detection_selection_and_policy(validation_repo):
    plan = make_plan(validation_repo)
    validation = build_validation_plan(validation_repo, plan, "abc")
    assert validation.schema_version == 1
    assert validation.plan_hash
    assert any(item.step_id == "python-compile" and item.requirement is Requirement.REQUIRED for item in validation.targeted_steps)
    assert any(item.step_id == "pytest-full" and item.requirement is Requirement.REQUIRED for item in validation.final_steps)
    assert any(item.step_id == "ruff" for item in validation.final_steps)
    selected = select_targeted_tests(validation_repo, plan)
    assert selected[0][0] == "tests/test_service.py"


def test_validation_cli_exposes_stage5_workflows():
    parser = build_validation_parser()
    assert (
        parser.parse_args(["build-plan", "plan.json", "--output", "validation.json"]).command
        == "build-plan"
    )
    assert (
        parser.parse_args(["run-targeted", "plan.json", "validation.json"]).command
        == "run-targeted"
    )
    assert (
        parser.parse_args(["run-required", "plan.json", "validation.json"]).command
        == "run-required"
    )
    assert parser.parse_args(["security-scan"]).command == "security-scan"


def test_language_validator_adapters(tmp_path):
    repo = tmp_path
    (repo / "Cargo.toml").write_text("[package]\nname='x'\n")
    (repo / "foundry.toml").write_text("[profile.default]\n")
    (repo / "package.json").write_text('{"scripts":{"test":"vitest"}}')
    (repo / "tsconfig.json").write_text("{}")
    (repo / "eslint.config.js").write_text("export default []")
    steps = {item.step_id for item in detect_validators(repo, ("script.sh",))}
    assert {"cargo-check", "cargo-test", "forge-build", "forge-test", "node-test", "typescript", "eslint", "shellcheck"} <= steps
    unsupported = detect_validators(repo, ("service.go",))
    missing = next(item for item in unsupported if item.step_id == "unsupported-source-validation")
    assert missing.requirement is Requirement.REQUIRED and missing.command is None


def test_missing_required_validator_fails_closed(validation_repo):
    service = ValidationService(validation_repo)
    step = ValidationStep(
        "missing",
        ValidationKind.TEST,
        Requirement.REQUIRED,
        "definitely-not-installed-stage5-validator --check",
        "configured required validation",
    )
    result = service._run_step(step, "abc", "")
    assert not result.success
    assert result.skipped
    assert "unavailable" in result.summary.lower()


def test_missing_recommended_validator_is_observable_but_nonblocking(validation_repo):
    service = ValidationService(validation_repo)
    step = ValidationStep(
        "missing",
        ValidationKind.LINT,
        Requirement.RECOMMENDED,
        "definitely-not-installed-stage5-validator --check",
        "optional local validation",
    )
    result = service._run_step(step, "abc", "")
    assert result.success
    assert result.skipped
    assert result.provenance and result.provenance.result == "unavailable"


def test_validation_command_side_effect_is_immediately_restored(validation_repo):
    (validation_repo / "tests/test_mutation.py").write_text(
        "import os\nfrom pathlib import Path\n"
        "def test_mutates_repository():\n"
        "    Path('app/service.py').write_text('contaminated')\n"
        "    Path('pyproject.toml').write_text('contaminated')\n"
        "    Path('notes.txt').unlink()\n"
        "    Path('link').unlink()\n"
        "    Path('link').write_text('not a symlink')\n"
        "    Path('created.txt').write_text('side effect')\n"
        "    Path('.env').write_text('TOKEN=validator-leak')\n"
    )
    (validation_repo / ".gitignore").write_text(".env\n")
    subprocess.run(
        ["git", "add", "tests/test_mutation.py", ".gitignore"],
        cwd=validation_repo,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "validator fixture"],
        cwd=validation_repo,
        check=True,
        capture_output=True,
    )
    intended = validation_repo / "app/service.py"
    intended.write_text("def login_user(name):\n    return bool(name.strip())\n")
    (validation_repo / "pyproject.toml").write_text(
        "[project]\nname='demo'\n[tool.pytest.ini_options]\n[tool.ruff]\n# staged\n"
    )
    subprocess.run(["git", "add", "pyproject.toml"], cwd=validation_repo, check=True)
    notes = validation_repo / "notes.txt"
    notes.write_text("keep me")
    os.chmod(notes, 0o700)
    (validation_repo / "link").symlink_to("notes.txt")
    (validation_repo / ".env").write_text("TOKEN=original-secret")
    status_before = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=validation_repo,
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    staged_before = subprocess.run(
        ["git", "diff", "--cached", "--binary"],
        cwd=validation_repo,
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    before = subprocess.run(
        ["git", "diff", "HEAD", "--binary", "--find-renames"],
        cwd=validation_repo,
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    step = ValidationStep(
        "mutating-test",
        ValidationKind.TEST,
        Requirement.REQUIRED,
        "pytest -q tests/test_mutation.py",
        "validator side-effect fixture",
    )
    result = ValidationService(validation_repo)._run_step(step, "abc", before)
    assert not result.success
    assert "changed repository state" in result.output
    assert intended.read_text() == "def login_user(name):\n    return bool(name.strip())\n"
    assert notes.read_text() == "keep me"
    assert os.stat(notes).st_mode & 0o777 == 0o700
    assert (validation_repo / "link").is_symlink()
    assert os.readlink(validation_repo / "link") == "notes.txt"
    assert not (validation_repo / "created.txt").exists()
    assert (validation_repo / ".env").read_text() == "TOKEN=original-secret"
    assert subprocess.run(
        ["git", "diff", "--cached", "--binary"],
        cwd=validation_repo,
        text=True,
        capture_output=True,
        check=True,
    ).stdout == staged_before
    assert subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=validation_repo,
        text=True,
        capture_output=True,
        check=True,
    ).stdout == status_before


def test_validation_snapshot_rejects_oversized_untracked_file(
    validation_repo, monkeypatch
):
    monkeypatch.setattr(
        validation_service_module,
        "MAX_VALIDATION_REPOSITORY_FILE_BYTES",
        32,
    )
    (validation_repo / "oversized.bin").write_bytes(b"x" * 33)

    with pytest.raises(
        ValidationArtifactError,
        match="Could not safely snapshot untracked validation file.*oversized",
    ):
        ValidationService(validation_repo)._snapshot()


def test_validation_config_identity_does_not_follow_external_symlink(
    validation_repo, tmp_path
):
    outside = tmp_path / "external-config"
    outside.write_text("SECRET_CONFIG_ONE\n")
    (validation_repo / "ruff.toml").symlink_to(outside)

    service = ValidationService(validation_repo)
    first = service._config_identity()

    outside.write_text("SECRET_CONFIG_TWO\n")
    second = service._config_identity()

    assert first == second


def test_sensitive_snapshot_rejects_oversized_repository_file(
    validation_repo, monkeypatch
):
    monkeypatch.setattr(
        validation_service_module,
        "MAX_VALIDATION_REPOSITORY_FILE_BYTES",
        32,
    )
    (validation_repo / ".env").write_bytes(b"x" * 33)

    with pytest.raises(
        ValidationArtifactError,
        match="Sensitive validation snapshot file is too large",
    ):
        validation_service_module._sensitive_entries(validation_repo)


def test_low_risk_can_use_targeted_policy(validation_repo):
    validation = build_validation_plan(validation_repo, make_plan(validation_repo, RiskLevel.LOW), "abc")
    pytest_step = next(item for item in validation.final_steps if item.step_id == "pytest-full")
    assert pytest_step.requirement is Requirement.RECOMMENDED


def test_validation_plan_persistence_and_corruption(validation_repo, tmp_path):
    value = build_validation_plan(validation_repo, make_plan(validation_repo), "abc")
    path = persist_validation_plan(value, tmp_path / "validation.json")
    assert load_validation_plan(path) == value
    path.write_text("{broken")
    with pytest.raises(ValidationArtifactError):
        load_validation_plan(path)


def test_validation_plan_rejects_policy_config_and_risk_tampering(validation_repo):
    artifact = make_artifact(validation_repo)
    service = ValidationService(validation_repo)
    validation = service.build(artifact)
    weakened = replace(
        validation,
        final_steps=tuple(
            replace(item, requirement=Requirement.OPTIONAL)
            for item in validation.final_steps
        ),
    )
    with pytest.raises(ValidationArtifactError, match="commands or requirements"):
        service._verify_identity(artifact, weakened)
    with pytest.raises(ValidationArtifactError, match="stale"):
        service._verify_identity(artifact, replace(validation, risk_level="low"))
    (validation_repo / "ruff.toml").write_text("line-length = 88\n")
    with pytest.raises(ValidationArtifactError, match="stale"):
        service._verify_identity(artifact, validation)


def test_validation_report_persistence_redaction_and_corruption(validation_repo, tmp_path):
    plan = build_validation_plan(validation_repo, make_plan(validation_repo), "abc")
    review = ReviewResult(plan.plan_hash, "diff", ())
    result = ValidationResult("x", False, False, 1, "failed", "Authorization: Bearer abcdefghijkl")
    report = ValidationReport(1, plan, (result,), (), review, decide_final(plan, (result,), review))
    path = persist_validation_report(report, tmp_path / "report.json")
    assert "abcdefghijkl" not in path.read_text()
    assert load_validation_report(path)["schema_version"] == 1
    path.write_text("{broken")
    with pytest.raises(ValidationArtifactError):
        load_validation_report(path)


def test_validation_cache_invalidates_for_diff_command_and_config(tmp_path):
    cache = ValidationCache(tmp_path / "cache.json")
    repo = tmp_path / "repo"
    repo.mkdir()
    first = cache.key(repo, "abc", "diff-one", "pytest", "config")
    cache.put_success(first, "passed")
    assert cache.get(first)
    assert cache.get(cache.key(repo, "abc", "diff-two", "pytest", "config")) is None
    assert cache.get(cache.key(repo, "abc", "diff-one", "ruff", "config")) is None
    assert cache.get(cache.key(repo, "abc", "diff-one", "pytest", "changed")) is None
    other = tmp_path / "other"
    other.mkdir()
    assert cache.get(cache.key(other, "abc", "diff-one", "pytest", "config")) is None
    cache.path.write_text("{broken")
    with pytest.raises(ValidationArtifactError):
        cache.get(first)
    with pytest.raises(ValidationArtifactError):
        cache.put_success(first, "must not silently replace corrupt state")


@pytest.mark.parametrize(
    ("output", "command", "expected"),
    [
        ("SyntaxError: invalid syntax", "python -m compileall .", FailureCategory.SYNTAX),
        ("ModuleNotFoundError: missing", "pytest", FailureCategory.IMPORT),
        ("AssertionError: expected 2 got 1", "pytest", FailureCategory.ASSERTION),
        ("incompatible type", "mypy .", FailureCategory.TYPE),
        ("E501 lint issue", "ruff check .", FailureCategory.LINT),
        ("build failed", "cargo check", FailureCategory.BUILD),
        ("command not found", "pytest", FailureCategory.ENVIRONMENT),
        ("connection refused", "pytest", FailureCategory.INFRASTRUCTURE),
        ("something unusual", "pytest", FailureCategory.UNKNOWN),
    ],
)
def test_failure_classification(output, command, expected):
    assert classify_failure(command, 1, output).category is expected


def test_flaky_requires_repeated_passes():
    uncertain = classify_failure("pytest", 1, "AssertionError", rerun_passes=1, rerun_attempts=1)
    flaky = classify_failure("pytest", 1, "AssertionError", rerun_passes=2, rerun_attempts=2)
    assert uncertain.category is FailureCategory.ASSERTION
    assert uncertain.flaky_evidence
    assert flaky.category is FailureCategory.FLAKY
    assert not flaky.repair_appropriate


def test_unknown_and_infrastructure_failures_do_not_trigger_repair():
    assert not classify_failure("pytest", 1, "unknown failure").repair_appropriate
    assert classify_failure("cargo check", 127, "command not found").category is FailureCategory.ENVIRONMENT


def test_tdd_red_phase_accepts_only_behavior_failure():
    assertion = classify_failure("pytest", 1, "AssertionError expected 2 got 1")
    imported = classify_failure("pytest", 1, "ModuleNotFoundError: missing")
    assert meaningful_tdd_failure(assertion)[0]
    assert not meaningful_tdd_failure(imported)[0]


@pytest.mark.parametrize(
    "body",
    [
        "def test_x():\n    pass",
        "def test_x():\n    assert True",
        "import pytest\n@pytest.mark.skip\ndef test_x():\n    assert value",
        "def test_x():\n    try:\n        target()\n    except Exception:\n        pass",
        "def test_x():\n    requests.get('https://example.invalid')\n    assert 1 == 1",
        "def test_x():\n    assert 1 == 1",
    ],
)
def test_generated_test_validity_rejects_weak_patterns(body):
    patch = "diff --git a/tests/test_x.py b/tests/test_x.py\nnew file mode 100644\n--- /dev/null\n+++ b/tests/test_x.py\n@@ -0,0 +1,10 @@\n" + "\n".join("+" + line for line in body.splitlines()) + "\n"
    assert any(item.blocking for item in validate_test_patch(patch))


def test_generated_test_cannot_mutate_production(validation_repo):
    plan = make_plan(validation_repo)
    response = """diff --git a/app/service.py b/app/service.py
--- a/app/service.py
+++ b/app/service.py
@@ -1,2 +1,2 @@
-def login_user(name):
+def login_user(user):
     return bool(name)
"""
    with pytest.raises(GeneratedTestError, match="production-code"):
        generate_test_patch(FakeModel(response), plan, scope_guard_from_plan(plan), "failure")


def test_generated_test_cannot_delete_existing_assertion(validation_repo):
    plan = replace(make_plan(validation_repo), symbols_to_modify=())
    response = """diff --git a/tests/test_service.py b/tests/test_service.py
deleted file mode 100644
--- a/tests/test_service.py
+++ /dev/null
@@ -1,4 +0,0 @@
-from app.service import login_user
-def test_login_user():
-    assert login_user('a')
"""
    with pytest.raises(GeneratedTestError, match="delete or rename"):
        generate_test_patch(FakeModel(response), plan, scope_guard_from_plan(plan), "failure")


def test_bug_and_feature_test_generation_in_approved_scope(validation_repo):
    plan = replace(
        make_plan(validation_repo),
        symbols_to_modify=(),
        symbols_to_create=("tests.test_service.test_login_user_empty",),
    )
    response = """diff --git a/tests/test_service.py b/tests/test_service.py
--- a/tests/test_service.py
+++ b/tests/test_service.py
@@ -3,2 +3,5 @@
 def test_login_user():
     assert login_user('a')
+
+def test_login_user_empty():
+    assert not login_user('')
"""
    generated = generate_test_patch(FakeModel(response), plan, scope_guard_from_plan(plan), "bug", tdd=True)
    assert generated.target_files == ("tests/test_service.py",)
    assert generated.patch_hash


@pytest.mark.parametrize(
    ("line", "category", "blocking"),
    [
        ('api_key = "123456789-secret"', "credential", True),
        ("eval(user_input)", "unsafe_eval", True),
        ("subprocess.run(cmd, shell=True)", "shell_true", True),
        ('query = f"SELECT * FROM users WHERE id={user}"', "sql_concatenation", True),
        ("path = '../' + name", "path_traversal", False),
        ("hashlib.md5(data)", "weak_crypto", False),
    ],
)
def test_security_scanner_patterns_and_redaction(line, category, blocking):
    diff = f"diff --git a/app/x.py b/app/x.py\n--- a/app/x.py\n+++ b/app/x.py\n@@ -0,0 +1 @@\n+{line}\n"
    findings = scan_changed_content(diff)
    finding = next(item for item in findings if item.category == category)
    assert finding.blocking is blocking
    if category == "credential":
        assert "123456789" not in finding.evidence


def test_provider_token_and_history_redaction_never_retain_secret_value():
    secret = "sk-abcdefghijklmnopqrstuvwxyz"
    diff = f"diff --git a/x.py b/x.py\n+++ b/x.py\n@@ -0,0 +1 @@\n+value = '{secret}'\n"
    finding = next(
        item for item in scan_changed_content(diff) if item.category == "provider_token"
    )
    assert secret not in finding.evidence
    rendered = redact(
        f"Authorization: Bearer {secret}\nDATABASE_URL=postgresql://admin:pw@host/db"
    )
    assert secret not in rendered and "admin:pw" not in rendered


def test_private_key_and_solidity_security():
    diff = """diff --git a/C.sol b/C.sol
--- a/C.sol
+++ b/C.sol
@@ -1 +1,3 @@
+-----BEGIN PRIVATE KEY-----
+x.delegatecall(data);
+selfdestruct(payable(owner));
"""
    categories = {item.category for item in scan_changed_content(diff)}
    assert {"private_key", "solidity_delegatecall", "solidity_selfdestruct"} <= categories


def test_auth_scope_requires_enhanced_review():
    findings = enhanced_auth_review("+def login():\n+    return user", ("app/auth.py",))
    assert findings and findings[0].category == "auth_permission"


def test_deterministic_review_blocks_scope_placeholder_and_test_weakening(validation_repo):
    plan = replace(make_plan(validation_repo), symbols_to_modify=())
    diff = """diff --git a/app/service.py b/app/service.py
--- a/app/service.py
+++ b/app/service.py
@@ -1,2 +1,2 @@
 def login_user(name):
-    return bool(name)
+    pass  # TODO
diff --git a/tests/test_service.py b/tests/test_service.py
--- a/tests/test_service.py
+++ b/tests/test_service.py
@@ -3,2 +3,3 @@
 def test_login_user():
+    pytest.skip('broken')
     assert login_user('a')
"""
    review = deterministic_review(validation_repo, plan, scope_guard_from_plan(plan), diff)
    categories = {item.category for item in review.findings if item.blocking}
    assert {"placeholder_code", "test_weakening"} <= categories


def test_model_review_is_bounded_advisory_and_cannot_remove_deterministic_findings(validation_repo):
    plan = replace(make_plan(validation_repo), symbols_to_modify=())
    deterministic = ReviewResult("hash", "diff", (ReviewFinding("scope", ReviewSeverity.CRITICAL, "x", None, None, None, "bad", "bad", "deterministic", True, "scope"),))
    model = FakeModel({"summary": "reviewed", "findings": [{"category": "naming", "severity": "low", "evidence": "name", "rationale": "style", "blocking": False}]})
    review = model_review(model, plan, "+" + "x" * 30000, deterministic, budget=1000)
    assert review.context_truncated
    assert review.findings[0].blocking
    assert review.findings[-1].origin == "model"
    malformed = model_review(
        FakeModel({"summary": "pretend pass", "findings": [{"blocking": False}]}),
        plan,
        "+safe",
        deterministic,
    )
    assert malformed.findings[0].blocking
    assert malformed.findings[-1].category == "model_review"


def test_final_decision_required_failure_security_and_warnings(validation_repo):
    plan = build_validation_plan(validation_repo, make_plan(validation_repo), "abc")
    required = [item for item in (*plan.targeted_steps, *plan.final_steps) if item.requirement is Requirement.REQUIRED]
    passing = tuple(ValidationResult(item.step_id, True, False, 0, "pass") for item in required)
    clean = ReviewResult(plan.plan_hash, "diff", ())
    assert decide_final(plan, passing, clean).status is DecisionStatus.PASS
    failed = (ValidationResult(required[0].step_id, False, False, 1, "fail"), *passing[1:])
    assert decide_final(plan, failed, clean).status is DecisionStatus.FAILED
    critical = ReviewResult(plan.plan_hash, "diff", (ReviewFinding("secret", ReviewSeverity.CRITICAL, None, None, None, None, "redacted", "secret", "deterministic", True, "security"),))
    assert decide_final(plan, passing, critical).status is DecisionStatus.BLOCKED
    warning = ReviewResult(plan.plan_hash, "diff", (ReviewFinding("docs", ReviewSeverity.LOW, None, None, None, None, "docs", "docs", "deterministic", False, "review"),))
    assert decide_final(plan, passing, warning).status is DecisionStatus.PASS_WITH_WARNINGS
    assert decide_final(plan, passing, clean, reapproval_required=True).status is DecisionStatus.REAPPROVAL_REQUIRED
    optional_failure = ValidationResult("advisory", False, False, 1, "failed")
    assert (
        decide_final(plan, (*passing, optional_failure), clean).status
        is DecisionStatus.PASS_WITH_WARNINGS
    )


def test_repair_termination_policy():
    assert repair_decision(FailureCategory.ASSERTION, 0, 2) is DecisionStatus.REPAIR_REQUIRED
    assert repair_decision(FailureCategory.ASSERTION, 2, 2) is DecisionStatus.FAILED
    assert repair_decision(FailureCategory.ASSERTION, 0, 2, repeated=True) is DecisionStatus.FAILED
    assert repair_decision(FailureCategory.INFRASTRUCTURE, 0, 2) is DecisionStatus.BLOCKED
    assert repair_decision(FailureCategory.ASSERTION, 0, 2, scope_increase=True) is DecisionStatus.REAPPROVAL_REQUIRED


def test_bounded_repair_success_repeat_and_scope_rejection(validation_repo):
    plan = replace(make_plan(validation_repo), symbols_to_modify=())
    patch = """diff --git a/app/service.py b/app/service.py
--- a/app/service.py
+++ b/app/service.py
@@ -1,2 +1,2 @@
 def login_user(name):
-    return bool(name)
+    return bool(name.strip())
"""
    model = FakeModel({"rationale": "minimal fix", "patch": patch})
    engine = BoundedRepairEngine(model, scope_guard_from_plan(plan), max_attempts=2)
    failure = classify_failure("pytest", 1, "AssertionError expected true")
    attempt = engine.propose(plan, failure, {"source": "exact"})
    assert attempt.number == 1
    with pytest.raises(ValidationIntelligenceError, match="failed"):
        engine.propose(plan, failure, {"source": "exact"})
    widened = patch.replace("app/service.py", "app/unplanned.py")
    with pytest.raises(ValidationIntelligenceError, match="reapproval"):
        BoundedRepairEngine(FakeModel({"rationale": "wide", "patch": widened}), scope_guard_from_plan(plan)).propose(plan, classify_failure("pytest", 1, "different AssertionError"), {})


def test_repair_rejects_test_weakening_and_validator_disable(validation_repo):
    plan = replace(make_plan(validation_repo), symbols_to_modify=())
    failure = classify_failure("pytest", 1, "AssertionError expected true")
    weakened = """diff --git a/tests/test_service.py b/tests/test_service.py
--- a/tests/test_service.py
+++ b/tests/test_service.py
@@ -2,3 +2,2 @@
 def test_login_user():
-    assert login_user('a')
+    pass
"""
    with pytest.raises(ValidationIntelligenceError, match="test weakening"):
        BoundedRepairEngine(
            FakeModel({"rationale": "cheat", "patch": weakened}),
            scope_guard_from_plan(plan),
        ).propose(plan, failure, {})
    config_plan = replace(
        plan,
        files_to_modify=(*plan.files_to_modify, "pyproject.toml"),
        dependency_changes=(
            DependencyChange(
                "pyproject.toml",
                DependencyChangeKind.UNKNOWN,
                "approved manifest inspection",
            ),
        ),
    )
    disabled = """diff --git a/pyproject.toml b/pyproject.toml
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -2,3 +2,2 @@
 name='demo'
-[tool.pytest.ini_options]
 [tool.ruff]
"""
    with pytest.raises(ValidationIntelligenceError, match="disable validation"):
        BoundedRepairEngine(
            FakeModel({"rationale": "disable", "patch": disabled}),
            scope_guard_from_plan(config_plan),
        ).propose(config_plan, failure, {})
