"""Evidence-based validation-failure and flaky-candidate classification."""

from __future__ import annotations

import re

from local_ai_assistant.execution.history import redact

from .models import FailureCategory, FailureRecord


def classify_failure(command: str, exit_code: int | None, output: str, *, timed_out: bool = False, rerun_passes: int = 0, rerun_attempts: int = 0) -> FailureRecord:
    text = output[-20000:]
    lower = text.lower()
    reasons = []
    category = FailureCategory.UNKNOWN
    confidence = 0.45
    # Policy and infrastructure evidence outrank incidental traceback text.
    if "scope violation" in lower or "outside approved scope" in lower:
        category, confidence = FailureCategory.SCOPE_VIOLATION, 0.98
    elif re.search(r"secret detected|security finding|vulnerability", lower):
        category, confidence = FailureCategory.SECURITY, 0.9
    elif re.search(r"connection refused|network is unreachable|connection reset", lower):
        category, confidence = FailureCategory.TRANSPORT, 0.9
    elif re.search(r"disk full|no space left on device|permission denied", lower):
        category, confidence = FailureCategory.INFRASTRUCTURE, 0.9
    elif re.search(r"command not found|bwrap: execvp|not installed", lower):
        category, confidence = FailureCategory.ENVIRONMENT, 0.9
    elif timed_out or "timed out" in lower:
        category, confidence = FailureCategory.TIMEOUT, 0.95
        reasons.append("Command exceeded its timeout.")
    elif re.search(r"syntaxerror|indentationerror|cannot compile", lower):
        category, confidence = FailureCategory.SYNTAX, 0.95
    elif re.search(r"modulenotfounderror|importerror|cannot import", lower):
        category, confidence = FailureCategory.IMPORT, 0.92
    elif re.search(r"(?:^|\n)[^\n]*\bnameerror:\s*name .+ is not defined", lower):
        category, confidence = FailureCategory.RUNTIME, 0.9
    elif re.search(r"(?:^|\n)[^\n]*\battributeerror:", lower):
        category, confidence = FailureCategory.ATTRIBUTE, 0.9
    elif re.search(r"(?:^|\n)[^\n]*\btypeerror:", lower):
        category, confidence = FailureCategory.TYPE, 0.9
    elif re.search(r"malformed (?:llm|model|repair) response|truncated (?:llm|model) response", lower):
        category, confidence = FailureCategory.MODEL_RESPONSE, 0.9
    elif "schema validation" in lower or "schema-invalid" in lower:
        category, confidence = FailureCategory.SCHEMA, 0.9
    elif re.search(r"assertionerror|\bfailed\b.*assert|expected .* (?:but|got)", lower):
        category, confidence = FailureCategory.ASSERTION, 0.88
    elif "scope violation" in lower or "outside approved scope" in lower:
        category, confidence = FailureCategory.SCOPE_VIOLATION, 0.98
    elif re.search(r"secret detected|security finding|vulnerability", lower):
        category, confidence = FailureCategory.SECURITY, 0.9
    elif re.search(r"dependency conflict|resolution failed|lockfile", lower):
        category, confidence = FailureCategory.DEPENDENCY, 0.85
    elif re.search(r"command not found|no such file or directory|not installed", lower):
        category, confidence = FailureCategory.ENVIRONMENT, 0.9
    elif re.search(r"connection refused|network is unreachable|disk full|permission denied", lower):
        category, confidence = FailureCategory.INFRASTRUCTURE, 0.85
    elif re.search(r"regression|previously passing", lower):
        category, confidence = FailureCategory.REGRESSION, 0.8
    elif "mypy" in command or "pyright" in command or re.search(r"type error|incompatible type", lower):
        category, confidence = FailureCategory.TYPE, 0.85
    elif any(tool in command for tool in ("ruff", "eslint", "clippy", "shellcheck")):
        category, confidence = FailureCategory.LINT, 0.85
    elif any(tool in command for tool in ("cargo check", "forge build", "tsc")) or "build failed" in lower:
        category, confidence = FailureCategory.BUILD, 0.85
    elif exit_code not in {None, 0}:
        category, confidence = FailureCategory.SUBPROCESS, 0.6
    affected_tests = tuple(dict.fromkeys(re.findall(r"(?:tests?/[^\s:]+|[A-Za-z0-9_./-]+::test_[A-Za-z0-9_]+)", text)))
    flaky_evidence = []
    if rerun_attempts >= 2 and rerun_passes >= 2:
        category = FailureCategory.FLAKY
        confidence = min(0.8, 0.55 + rerun_passes * 0.1)
        flaky_evidence.append(f"Passed {rerun_passes}/{rerun_attempts} immediate reruns without code changes.")
    elif rerun_passes:
        flaky_evidence.append("A single passing rerun is insufficient to classify the failure as flaky.")
    repair = category not in {FailureCategory.ENVIRONMENT, FailureCategory.INFRASTRUCTURE, FailureCategory.SCOPE_VIOLATION, FailureCategory.SECURITY, FailureCategory.FLAKY, FailureCategory.TIMEOUT, FailureCategory.UNKNOWN, FailureCategory.TRANSPORT, FailureCategory.MODEL_RESPONSE, FailureCategory.SCHEMA, FailureCategory.SUBPROCESS}
    if not reasons:
        reasons.append(f"Output signals classify this as {category.value}.")
    disposition = "repairable" if repair else "fatal"
    if category in {FailureCategory.SCOPE_VIOLATION, FailureCategory.SECURITY}:
        disposition = "policy-blocked"
    elif category in {FailureCategory.INFRASTRUCTURE, FailureCategory.ENVIRONMENT, FailureCategory.TRANSPORT}:
        disposition = "infrastructure-recoverable"
    elif category in {FailureCategory.MODEL_RESPONSE, FailureCategory.SCHEMA}:
        disposition = "retryable"
    exception = re.search(r"\b(NameError|TypeError|AttributeError|SyntaxError|IndentationError|ImportError|ModuleNotFoundError|AssertionError):", text)
    diagnostic = exception.group(1) if exception else category.value
    return FailureRecord(category, command, exit_code, _redact(text), affected_tests, (), (), confidence, repair, tuple(reasons), tuple(flaky_evidence), diagnostic, disposition)


def _redact(text: str) -> str:
    return redact(text)
