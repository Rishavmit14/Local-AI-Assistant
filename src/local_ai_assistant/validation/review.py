"""Deterministic and bounded model-assisted diff review."""

from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

from local_ai_assistant.execution.history import redact
from local_ai_assistant.planning.models import ImplementationPlan, plan_approval_token
from local_ai_assistant.planning.patch_scope import extract_patch_scope, validate_patch_scope

from .models import ReviewFinding, ReviewResult, ReviewSeverity
from .security import enhanced_auth_review, scan_changed_content


def deterministic_review(repository: Path, plan: ImplementationPlan, policy, diff: str, symbols=(), *, index_prefix: str = "") -> ReviewResult:
    findings: list[ReviewFinding] = []
    if not diff.strip():
        return ReviewResult(plan_approval_token(plan), hashlib.sha256(b"").hexdigest(), ())
    scope = extract_patch_scope(diff, tuple(symbols), index_prefix)
    for issue in validate_patch_scope(policy, scope):
        findings.append(_finding("scope_compliance", ReviewSeverity.CRITICAL, None, issue, True))
    changed = set(scope.changed_files)
    planned = set((*plan.files_to_modify, *plan.files_to_create, *plan.files_to_delete_or_rename))
    for path in sorted(changed - planned):
        findings.append(_finding("unrelated_changes", ReviewSeverity.HIGH, path, "Changed file is outside the approved plan.", True))
    findings.extend(_review_added_lines(diff))
    findings.extend(scan_changed_content(diff))
    findings.extend(enhanced_auth_review(diff, tuple(changed)))
    return ReviewResult(plan_approval_token(plan), hashlib.sha256(diff.encode()).hexdigest(), tuple(findings))


def model_review(model, plan: ImplementationPlan, diff: str, deterministic: ReviewResult, *, budget: int = 24_000) -> ReviewResult:
    payload = redact(
        json.dumps(
            {
                "plan": plan.to_dict(),
                "diff": diff,
                "deterministic_findings": [
                    item.evidence for item in deterministic.findings
                ],
            }
        )
    )
    truncated = len(payload) > budget
    raw = model.chat(prompt=payload[:budget], system_prompt="Review bounded code changes. Return JSON object with summary and findings. Findings contain category, severity, file, symbol, evidence, rationale, blocking. Never override deterministic failures.", temperature=0.0, max_tokens=1200)
    try:
        value = json.loads(raw)
        findings = tuple(_model_finding(item) for item in value.get("findings", ()))
        summary = str(value.get("summary", ""))[:2000]
    except (ValueError, TypeError, json.JSONDecodeError):
        findings = (_finding("model_review", ReviewSeverity.MEDIUM, None, "Malformed advisory model review.", False),)
        summary = "Model review could not be parsed; deterministic findings remain authoritative."
    return ReviewResult(deterministic.plan_hash, deterministic.diff_hash, (*deterministic.findings, *findings), summary, truncated)


def _review_added_lines(diff: str):
    findings = []
    path = None
    additions = []
    deletions = []
    added_definitions: dict[tuple[str | None, str], int] = {}
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
        elif line.startswith("+") and not line.startswith("+++"):
            additions.append((path, line[1:]))
        elif line.startswith("-") and not line.startswith("---"):
            deletions.append((path, line[1:]))
    for path, content in additions:
        stripped = content.strip()
        if re.search(r"\b(TODO|FIXME)\b", stripped) or stripped == "pass":
            findings.append(_finding("placeholder_code", ReviewSeverity.HIGH, path, stripped, True))
        if re.search(r"pytest\.(skip|xfail)|@pytest\.mark\.(skip|xfail)", stripped):
            findings.append(_finding("test_weakening", ReviewSeverity.HIGH, path, stripped, True))
        if re.search(r"assert\s+True\b|self\.assertTrue\(True\)", stripped):
            findings.append(_finding("test_weakening", ReviewSeverity.HIGH, path, stripped, True))
        if re.match(r"(?:def|class)\s+", stripped) and path and path.endswith(".py"):
            name_match = re.match(r"(?:async\s+def|def|class)\s+([A-Za-z_]\w*)", stripped)
            if name_match:
                key = (path, name_match.group(1))
                added_definitions[key] = added_definitions.get(key, 0) + 1
            try:
                ast.parse(content if content.endswith("\n") else content + "\n")
            except SyntaxError:
                pass
        if re.search(r"\.read\(\)|read_text\(\)", stripped):
            findings.append(_finding("performance", ReviewSeverity.MEDIUM, path, "Potential unbounded read added.", False))
        if re.search(r"for\s+\w+\s+in\s+.+:\s*for\s+", stripped):
            findings.append(_finding("performance", ReviewSeverity.MEDIUM, path, "Possible nested-loop hot-path regression.", False))
        if path and path.endswith(".py") and "async def" in stripped and re.search(r"requests\.|subprocess\.run|time\.sleep", stripped):
            findings.append(_finding("concurrency", ReviewSeverity.HIGH, path, "Synchronous blocking work added to async code.", True))
    for (definition_path, name), count in added_definitions.items():
        if count > 1:
            findings.append(_finding("duplicate_definition", ReviewSeverity.HIGH, definition_path, f"Duplicate definition added: {name}", True))
    for deletion_path, content in deletions:
        match = re.match(r"\s*(?:async\s+def|def|class)\s+([A-Za-z]\w*)", content)
        if match and not match.group(1).startswith("_"):
            findings.append(_finding("public_api", ReviewSeverity.HIGH, deletion_path, f"Public definition removed: {match.group(1)}", True))
    production_changed = any(path and "/tests/" not in f"/{path}" and not path.rsplit("/", 1)[-1].startswith("test_") for path, _ in additions)
    test_changed = any(path and ("/tests/" in f"/{path}" or path.rsplit("/", 1)[-1].startswith("test_")) for path, _ in additions)
    if production_changed and not test_changed:
        findings.append(_finding("test_adequacy", ReviewSeverity.MEDIUM, None, "Production changed without a test diff; existing targeted tests must provide coverage.", False))
    return findings


def _model_finding(value):
    severity = ReviewSeverity(str(value.get("severity", "info")).lower())
    blocking = bool(value.get("blocking", False)) and severity in {ReviewSeverity.HIGH, ReviewSeverity.CRITICAL}
    return ReviewFinding(str(value.get("category", "model_review")), severity, value.get("file"), value.get("symbol"), None, None, str(value.get("evidence", ""))[:500], str(value.get("rationale", ""))[:1000], "model", blocking, "model.review")


def _finding(category, severity, path, evidence, blocking):
    return ReviewFinding(category, severity, path, None, None, None, evidence, evidence, "deterministic", blocking, "review.deterministic")
