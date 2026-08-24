"""Deterministic validator detection and targeted-test selection."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path, PurePosixPath

from local_ai_assistant.planning.models import ImplementationPlan, RiskLevel, plan_approval_token

from .models import Requirement, ValidationKind, ValidationPlan, ValidationStep


def build_validation_plan(
    repository: Path,
    plan: ImplementationPlan,
    starting_commit: str,
    *,
    tdd: bool = False,
    timeouts: dict[str, int] | None = None,
) -> ValidationPlan:
    repository = repository.resolve()
    files = tuple(
        dict.fromkeys(
            (*plan.files_to_modify, *plan.files_to_create, *plan.files_to_delete_or_rename)
        )
    )
    targeted_tests = select_targeted_tests(repository, plan)
    detected = detect_validators(repository, files)
    targeted: list[ValidationStep] = []
    final: list[ValidationStep] = []
    for path, reason, command in targeted_tests:
        targeted.append(
            _step(
                "target-test-" + _slug(path),
                ValidationKind.TEST,
                Requirement.REQUIRED,
                command,
                reason,
                True,
                (path,),
                plan.symbols_to_modify,
            )
        )
    for step in detected:
        if step.kind is ValidationKind.STRUCTURAL:
            targeted.insert(0, step)
        else:
            final.append(step)
    full_required = plan.risk.level in {RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL}
    if full_required:
        final = [
            _required(item) if item.kind in {ValidationKind.TEST, ValidationKind.SECURITY} else item
            for item in final
        ]
    elif not targeted:
        final = [_required(item) if item.kind is ValidationKind.TEST else item for item in final]
    payload = {
        "task": plan.task_id,
        "plan": plan_approval_token(plan),
        "commit": starting_commit,
        "files": files,
        "targeted": [item.step_id for item in targeted],
        "final": [item.step_id for item in final],
    }
    validation_id = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:24]
    timeout_policy = timeouts or {"structural": 60, "lint": 180, "typecheck": 300, "test": 900, "build": 900}
    targeted = [
        replace(item, timeout_seconds=timeout_policy.get(item.kind.value, item.timeout_seconds))
        for item in targeted
    ]
    final = [
        replace(item, timeout_seconds=timeout_policy.get(item.kind.value, item.timeout_seconds))
        for item in final
    ]
    return ValidationPlan(
        1,
        validation_id,
        plan.task_id,
        plan_approval_token(plan),
        str(repository),
        starting_commit,
        plan.risk.level.value,
        files,
        plan.symbols_to_modify,
        tuple(targeted),
        tuple(final),
        "Targeted selection is evidence-based but not claimed complete; final policy depends on risk.",
        timeout_policy,
        "Required steps fail closed; environment/infrastructure failures stop repair.",
        tdd,
    )


def detect_validators(repository: Path, affected_files: tuple[str, ...]) -> tuple[ValidationStep, ...]:
    steps: list[ValidationStep] = []
    suffixes = {PurePosixPath(path).suffix.lower() for path in affected_files}
    has_python = ".py" in suffixes or (repository / "pyproject.toml").is_file()
    if has_python:
        pyproject = _read(repository / "pyproject.toml")
        steps.append(
            _step(
                "python-compile",
                ValidationKind.STRUCTURAL,
                Requirement.REQUIRED,
                "python -m compileall -q .",
                "Python files require deterministic syntax compilation.",
            )
        )
        if _has_pytest(repository):
            coverage = "[tool.coverage" in pyproject or (repository / ".coveragerc").is_file()
            steps.append(
                _step(
                    "pytest-full",
                    ValidationKind.TEST,
                    Requirement.RECOMMENDED,
                    "python -m pytest -q --cov" if coverage else "python -m pytest -q",
                    "Pytest configuration or tests were detected; configured coverage is included."
                    if coverage
                    else "Pytest configuration or tests were detected.",
                )
            )
        if "[tool.ruff" in pyproject or (repository / "ruff.toml").is_file():
            steps.append(_step("ruff", ValidationKind.LINT, Requirement.REQUIRED, "ruff check .", "Ruff is configured."))
        if "[tool.mypy" in pyproject or (repository / "mypy.ini").is_file():
            steps.append(_step("mypy", ValidationKind.TYPECHECK, Requirement.REQUIRED, "mypy .", "mypy is configured."))
        if (repository / "pyrightconfig.json").is_file():
            steps.append(_step("pyright", ValidationKind.TYPECHECK, Requirement.REQUIRED, "pyright", "Pyright is configured."))
    if (repository / "Cargo.toml").is_file():
        steps.extend(
            (
                _step("cargo-check", ValidationKind.BUILD, Requirement.REQUIRED, "cargo check", "Cargo manifest detected."),
                _step("cargo-test", ValidationKind.TEST, Requirement.REQUIRED, "cargo test", "Cargo manifest detected."),
            )
        )
        if "clippy" in _read(repository / "Cargo.toml").lower() or (repository / "clippy.toml").is_file():
            steps.append(_step("cargo-clippy", ValidationKind.LINT, Requirement.RECOMMENDED, "cargo clippy", "Clippy configuration detected."))
    if (repository / "foundry.toml").is_file():
        steps.extend(
            (
                _step("forge-build", ValidationKind.BUILD, Requirement.REQUIRED, "forge build", "Foundry configuration detected."),
                _step("forge-test", ValidationKind.TEST, Requirement.REQUIRED, "forge test", "Foundry configuration detected."),
            )
        )
    package = _package_json(repository)
    manager = _node_manager(repository)
    if package:
        scripts = package.get("scripts", {})
        if "test" in scripts:
            steps.append(_step("node-test", ValidationKind.TEST, Requirement.REQUIRED, f"{manager} test", "Node test script detected."))
        if (repository / "tsconfig.json").is_file():
            steps.append(_step("typescript", ValidationKind.TYPECHECK, Requirement.REQUIRED, "tsc --noEmit", "TypeScript configuration detected."))
        if any((repository / name).exists() for name in ("eslint.config.js", ".eslintrc", ".eslintrc.json")):
            steps.append(_step("eslint", ValidationKind.LINT, Requirement.REQUIRED, "eslint .", "ESLint configuration detected."))
    if any(path.endswith((".sh", ".bash")) for path in affected_files):
        steps.append(_step("shellcheck", ValidationKind.LINT, Requirement.RECOMMENDED, "shellcheck " + " ".join(path for path in affected_files if path.endswith((".sh", ".bash"))), "Shell sources changed."))
    if (repository / ".gitleaks.toml").is_file():
        steps.append(
            _step(
                "gitleaks",
                ValidationKind.SECURITY,
                Requirement.RECOMMENDED,
                "gitleaks detect --no-git --redact",
                "A local gitleaks configuration was detected.",
            )
        )
    supported = {".py", ".rs", ".sol", ".js", ".jsx", ".ts", ".tsx", ".sh", ".bash"}
    source_like = {
        ".go", ".java", ".c", ".cc", ".cpp", ".h", ".hpp", ".sql", ".rb", ".php",
    }
    unsupported = sorted(suffixes.intersection(source_like) - supported)
    if unsupported:
        steps.append(
            _step(
                "unsupported-source-validation",
                ValidationKind.STRUCTURAL,
                Requirement.REQUIRED,
                None,
                "No configured deterministic validator for affected source extensions: "
                + ", ".join(unsupported),
            )
        )
    return tuple(_dedupe(steps))


def select_targeted_tests(
    repository: Path, plan: ImplementationPlan
) -> tuple[tuple[str, str, str], ...]:
    selected: dict[str, tuple[str, str, str]] = {}
    for test in plan.relevant_tests:
        if test.path not in {".", "full-suite"} and (repository / test.path).is_file():
            selected[test.path] = (
                test.path,
                "Approved plan test candidate; path existence verified deterministically. "
                + test.reason,
                _target_command(repository, test.path),
            )
    production = [PurePosixPath(path) for path in plan.files_to_modify if not _is_test(path)]
    tests = sorted(
        path.relative_to(repository).as_posix()
        for path in repository.rglob("*")
        if path.is_file() and _is_test(path.relative_to(repository).as_posix())
    )
    for source in production:
        stem = source.stem.removeprefix("test_")
        for test in tests:
            test_path = PurePosixPath(test)
            text = _read(repository / test)
            module = source.with_suffix("").as_posix().replace("/", ".")
            names = [item.rsplit(".", 1)[-1] for item in plan.symbols_to_modify]
            evidence = []
            if stem in test_path.stem or test_path.stem in {f"test_{stem}", f"{stem}_test"}:
                evidence.append("matching test/module naming")
            if module in text or any(name and name in text for name in names):
                evidence.append("static module/symbol reference")
            if evidence and test not in selected:
                command = _target_command(repository, test)
                selected[test] = (test, "; ".join(evidence), command)
    return tuple(selected.values())


def _step(step_id, kind, requirement, command, reason, targeted=False, files=(), symbols=()):
    return ValidationStep(step_id, kind, requirement, command, reason, targeted, command.split()[0] if command else None, 900 if kind in {ValidationKind.TEST, ValidationKind.BUILD} else 300, tuple(files), tuple(symbols))


def _required(step: ValidationStep) -> ValidationStep:
    return ValidationStep(**{**asdict_step(step), "requirement": Requirement.REQUIRED})


def asdict_step(step: ValidationStep) -> dict:
    return {name: getattr(step, name) for name in step.__dataclass_fields__}


def _dedupe(steps):
    return list({item.step_id: item for item in steps}.values())


def _has_pytest(repository):
    return (repository / "tests").is_dir() or any((repository / name).is_file() for name in ("pytest.ini", "tox.ini")) or "pytest" in _read(repository / "pyproject.toml")


def _is_test(path: str) -> bool:
    value = PurePosixPath(path)
    return "tests" in value.parts or value.name.startswith("test_") or value.stem.endswith("_test")


def _target_command(repository: Path, path: str) -> str:
    if path.endswith(".py"):
        return f"python -m pytest -q {path}"
    return "python -m pytest -q" if _has_pytest(repository) else path


def _node_manager(repository: Path) -> str:
    if (repository / "pnpm-lock.yaml").is_file():
        return "pnpm"
    if (repository / "yarn.lock").is_file():
        return "yarn"
    return "npm"


def _package_json(repository: Path) -> dict:
    try:
        return json.loads((repository / "package.json").read_text())
    except (OSError, ValueError):
        return {}


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _slug(value: str) -> str:
    return "".join(character if character.isalnum() else "-" for character in value).strip("-")
