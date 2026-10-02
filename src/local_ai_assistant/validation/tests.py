"""Bounded test generation and deterministic test-validity checks."""

from __future__ import annotations

import ast
import hashlib
import re
import textwrap
from dataclasses import dataclass

from local_ai_assistant.execution.history import redacted_json
from local_ai_assistant.planning.models import ImplementationPlan
from local_ai_assistant.planning.patch_scope import extract_patch_scope, validate_patch_scope

from .errors import TestGenerationError
from .models import FailureCategory, FailureRecord, ReviewFinding, ReviewSeverity


@dataclass(frozen=True, slots=True)
class GeneratedTest:
    patch: str
    patch_hash: str
    target_files: tuple[str, ...]
    rationale: str


def meaningful_tdd_failure(failure: FailureRecord) -> tuple[bool, str]:
    """Accept only behavior failures as a meaningful red phase."""
    if failure.category in {FailureCategory.ASSERTION, FailureCategory.REGRESSION}:
        return True, "Generated test fails on a behavior assertion as intended."
    return False, f"TDD red phase is invalid for {failure.category.value} failure."


def generate_test_patch(
    model,
    plan: ImplementationPlan,
    policy,
    evidence: str,
    *,
    tdd: bool = False,
    existing_test_names: tuple[str, ...] = (),
) -> GeneratedTest:
    if not plan.relevant_tests and not plan.files_to_create:
        raise TestGenerationError("The approved plan contains no test target")
    prompt = redacted_json({"request": plan.original_request, "test_targets": [item.path for item in plan.relevant_tests], "approved_new_files": plan.files_to_create, "symbols": plan.symbols_to_modify, "evidence": evidence[:12000], "tdd": tdd})
    raw = model.chat(prompt=prompt, system_prompt="Generate only a unified diff for a focused regression/feature test. Do not modify production files, use network access, skip/xfail, unconditional assertions, or invented APIs.", temperature=0.0, max_tokens=1800)
    patch = _extract_diff(raw)
    if not patch:
        raise TestGenerationError("Model did not produce a unified test patch")
    scope = extract_patch_scope(patch, ())
    issues = validate_patch_scope(policy, scope)
    if scope.deleted_files or scope.renamed_files:
        issues = (*issues, "Test generation may not delete or rename existing files")
    production = [path for path in scope.changed_files if not is_test_path(path)]
    if production:
        issues = (*issues, "Test generation attempted production-code mutation: " + ", ".join(production))
    validity = validate_test_patch(patch, existing_test_names)
    blocking = [item for item in validity if item.blocking]
    if issues or blocking:
        messages = [*issues, *(item.rationale for item in blocking)]
        raise TestGenerationError("; ".join(messages))
    return GeneratedTest(patch, hashlib.sha256(patch.encode()).hexdigest(), scope.changed_files, "Bounded generated test uses approved test scope.")


def validate_test_patch(
    diff: str, existing_test_names: tuple[str, ...] = (), *,
    allow_contract_expectation_updates: bool = False,
) -> tuple[ReviewFinding, ...]:
    findings = []
    added_by_file: dict[str, list[str]] = {}
    deleted_by_file: dict[str, list[str]] = {}
    path = None
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
        elif path and line.startswith("+") and not line.startswith("+++"):
            added_by_file.setdefault(path, []).append(line[1:])
        elif path and line.startswith("-") and not line.startswith("---"):
            deleted_by_file.setdefault(path, []).append(line[1:])
    for deleted_path, lines in deleted_by_file.items():
        if not is_test_path(deleted_path):
            continue
        removed = "\n".join(lines)
        if re.search(r"^\s*(?:async\s+def|def)\s+test_", removed, re.MULTILINE):
            findings.append(
                _finding(
                    "deleted_test_behavior",
                    deleted_path,
                    "Generated patch deletes a test or assertion.",
                )
            )
            continue
        removed_assertions = [line.strip() for line in lines if _is_assertion_line(line)]
        added_assertions = [
            line.strip() for line in added_by_file.get(deleted_path, [])
            if _is_assertion_line(line)
        ]
        if removed_assertions:
            remaining = list(added_assertions)
            for assertion in removed_assertions:
                match = next((index for index, candidate in enumerate(remaining)
                              if _same_assertion_contract_shape(assertion, candidate)), None)
                if not allow_contract_expectation_updates or match is None:
                    findings.append(
                        _finding("deleted_test_behavior", deleted_path,
                                 "Generated patch deletes or changes an assertion outside its expected value.")
                    )
                    break
                remaining.pop(match)
            if not any(f.category == "deleted_test_behavior" and f.file == deleted_path for f in findings) and remaining:
                findings.append(
                    _finding("deleted_test_behavior", deleted_path,
                             "Generated patch adds assertions while replacing existing test behavior.")
                )
    for path, lines in added_by_file.items():
        if not is_test_path(path):
            findings.append(_finding("production_mutation", path, "Generated test patch changes production code."))
            continue
        source = "\n".join(lines)
        if re.search(r"pytest\.(skip|xfail)|@pytest\.mark\.(skip|xfail)", source):
            findings.append(_finding("skip_xfail", path, "Generated test adds skip/xfail."))
        if re.search(r"assert\s+True\b|self\.assertTrue\(True\)", source):
            findings.append(_finding("unconditional_pass", path, "Generated test contains an unconditional passing assertion."))
        if re.search(r"except\s+(?:Exception)?\s*:\s*(?:pass|return)", source, re.DOTALL):
            findings.append(_finding("swallowed_exception", path, "Generated test swallows exceptions."))
        if re.search(r"except\s+(?:Exception|BaseException)\b", source):
            findings.append(_finding("broad_exception", path, "Generated test adds broad exception handling."))
        if re.search(r"\b(requests\.|urllib\.|httpx\.|socket\.)", source):
            findings.append(_finding("network_access", path, "Generated test introduces network access."))
        if re.search(r"\b(?:monkeypatch\.setattr|mock\.patch|patch\s*\()", source):
            findings.append(
                _finding(
                    "behavior_mocked_away",
                    path,
                    "Generated test replaces behavior through monkeypatch/mock patching.",
                )
            )
        if re.search(r"assert\s+([A-Za-z_]\w*\([^\n]+\))\s*==\s*\1", source):
            findings.append(
                _finding(
                    "implementation_derived_expectation",
                    path,
                    "Expected value is derived directly from the same call under test.",
                )
            )
        try:
            tree = ast.parse(textwrap.dedent(source))
        except SyntaxError:
            findings.append(
                _finding(
                    "malformed_test",
                    path,
                    "Generated test additions cannot be parsed independently for validity review.",
                )
            )
            continue
        tests = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test")]
        for test in tests:
            if test.name in existing_test_names:
                findings.append(
                    _finding("duplicate_test", path, f"Generated test duplicates {test.name}.")
                )
            has_assert = any(isinstance(node, ast.Assert) or isinstance(node, ast.Call) and _is_assert_call(node) for node in ast.walk(test))
            if not has_assert:
                findings.append(_finding("assertion_free", path, f"{test.name} has no assertion."))
            mock_calls = sum(isinstance(node, ast.Call) and "mock" in ast.unparse(node.func).lower() for node in ast.walk(test))
            calls = sum(isinstance(node, ast.Call) for node in ast.walk(test))
            if calls and mock_calls / calls > 0.7:
                findings.append(_finding("excessive_mocking", path, f"{test.name} is dominated by mocking."))
            if any(
                isinstance(node, ast.Assert)
                and isinstance(node.test, ast.Compare)
                and isinstance(node.test.left, ast.Constant)
                and all(isinstance(item, ast.Constant) for item in node.test.comparators)
                for node in ast.walk(test)
            ):
                findings.append(
                    _finding("constant_assertion", path, f"{test.name} asserts only constants.")
                )
            if any(
                isinstance(node, ast.Assert)
                and isinstance(node.test, ast.Constant)
                for node in ast.walk(test)
            ):
                findings.append(
                    _finding(
                        "unconditional_assertion",
                        path,
                        f"{test.name} contains an unconditional assertion.",
                    )
                )
            terminated = False
            for statement in test.body:
                if terminated and any(isinstance(node, ast.Assert) for node in ast.walk(statement)):
                    findings.append(
                        _finding(
                            "unreachable_assertion",
                            path,
                            f"{test.name} contains an assertion after unconditional termination.",
                        )
                    )
                if isinstance(statement, (ast.Return, ast.Raise)):
                    terminated = True
    return tuple(findings)


def _is_assertion_line(line: str) -> bool:
    return bool(re.match(r"\s*assert\b|.*\.assert[A-Z]\w*\s*\(", line))


def _same_assertion_contract_shape(before: str, after: str) -> bool:
    """Allow expected literals to follow a binding contract, preserving the tested expression."""
    class NormalizeExpected(ast.NodeTransformer):
        def visit_Constant(self, node):
            return ast.copy_location(ast.Constant(type(node.value).__name__), node)

    try:
        old, new = ast.parse(before).body[0], ast.parse(after).body[0]
        if isinstance(old, ast.Expr) and isinstance(old.value, ast.Call):
            old = old.value
        if isinstance(new, ast.Expr) and isinstance(new.value, ast.Call):
            new = new.value
        if isinstance(old, ast.Assert) and isinstance(new, ast.Assert):
            if ast.dump(old.test.left, include_attributes=False) != ast.dump(new.test.left, include_attributes=False):
                return False
            old_expected, new_expected = old.test.comparators[-1], new.test.comparators[-1]
        elif (isinstance(old, ast.Call) and isinstance(new, ast.Call)
              and ast.unparse(old.func).split(".")[-1].startswith("assert")
              and ast.unparse(old.func) == ast.unparse(new.func)
              and len(old.args) == len(new.args) and len(old.args) >= 2):
            if ast.dump(old.args[0], include_attributes=False) != ast.dump(new.args[0], include_attributes=False):
                return False
            if len(old.args) > 2 and ast.dump(old.args[2:], include_attributes=False) != ast.dump(new.args[2:], include_attributes=False):
                return False
            old_expected, new_expected = old.args[1], new.args[1]
        else:
            return False
        old = NormalizeExpected().visit(old)
        new = NormalizeExpected().visit(new)
        # Normalize only the expected side; the assertion operator and actual
        # expression remain byte-for-byte equivalent at the AST level.
        if isinstance(old, ast.Assert):
            old.test.comparators[-1] = NormalizeExpected().visit(old_expected)
            new.test.comparators[-1] = NormalizeExpected().visit(new_expected)
        else:
            old.args[1] = NormalizeExpected().visit(old_expected)
            new.args[1] = NormalizeExpected().visit(new_expected)
        return ast.dump(old, include_attributes=False) == ast.dump(new, include_attributes=False)
    except (SyntaxError, IndexError, ValueError, TypeError):
        return False


def is_test_path(path: str) -> bool:
    value = path.lower().replace("\\", "/")
    name = value.rsplit("/", 1)[-1]
    return "/tests/" in f"/{value}" or name.startswith("test_") or name.endswith(("_test.py", ".test.js", ".test.ts", ".spec.js", ".spec.ts"))


def _is_assert_call(node: ast.Call) -> bool:
    try:
        name = ast.unparse(node.func).lower()
    except Exception:
        return False
    return name.startswith(("self.assert", "pytest.raises"))


def _finding(category, path, rationale):
    return ReviewFinding(category, ReviewSeverity.HIGH, path, None, None, None, "Generated test content", rationale, "deterministic", True, "test.validity")


def _extract_diff(text: str) -> str:
    fenced = re.search(r"```(?:diff)?\s*\n(.*?)```", text, re.DOTALL)
    value = fenced.group(1) if fenced else text
    start = value.find("diff --git ")
    return value[start:].strip() + "\n" if start >= 0 else ""
