"""Bounded evidence-driven repair proposal engine."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from local_ai_assistant.common.errors import PatchValidationError
from local_ai_assistant.execution.history import redacted_json
from local_ai_assistant.planning.models import ImplementationPlan
from local_ai_assistant.planning.patch_scope import extract_patch_scope, validate_patch_scope

from .decision import repair_decision
from .errors import ValidationIntelligenceError
from .models import DecisionStatus, FailureRecord
from .security import scan_changed_content
from .tests import validate_test_patch


@dataclass(frozen=True, slots=True)
class RepairAttempt:
    number: int
    rationale: str
    patch: str
    patch_hash: str
    status: DecisionStatus


class BoundedRepairEngine:
    def __init__(self, model, policy, *, symbols=(), index_prefix: str = "", max_attempts: int = 2) -> None:
        self.model = model
        self.policy = policy
        self.max_attempts = max(0, max_attempts)
        self.symbols = tuple(symbols)
        self.index_prefix = index_prefix
        self.attempts: list[RepairAttempt] = []
        self.failure_fingerprints: list[str] = []

    def propose(self, plan: ImplementationPlan, failure: FailureRecord, evidence: dict) -> RepairAttempt:
        fingerprint = hashlib.sha256((failure.category.value + "\0" + failure.relevant_output).encode()).hexdigest()
        repeated = fingerprint in self.failure_fingerprints
        status = repair_decision(failure.category, len(self.attempts), self.max_attempts, repeated=repeated)
        if status is not DecisionStatus.REPAIR_REQUIRED or not failure.repair_appropriate:
            raise ValidationIntelligenceError(f"Repair stopped: {status.value}")
        self.failure_fingerprints.append(fingerprint)
        plan_context = {
            "task_id": plan.task_id,
            "request": plan.original_request[:2_000],
            "summary": plan.summary[:1_000],
            "files_to_modify": [str(item)[:120] for item in plan.files_to_modify[:20]],
            "files_to_create": [str(item)[:120] for item in plan.files_to_create[:20]],
            "symbols_to_modify": [str(item)[:160] for item in plan.symbols_to_modify[:20]],
            "validation_commands": [str(item)[:240] for item in plan.validation_commands[:10]],
        }
        evidence_context = {
            "current_diff": str(evidence.get("current_diff", ""))[-3_000:],
            "affected_source_context": str(evidence.get("affected_source_context", ""))[:6_000],
            "binding_contracts": str(evidence.get("binding_contracts", ""))[:2_500],
            "previous_rejected_patch": str(evidence.get("previous_rejected_patch", ""))[-6_000:],
            "git_preflight_error": str(evidence.get("git_preflight_error", ""))[:1_000],
        }
        prompt = redacted_json({
            "request": plan.original_request[:2_000],
            "plan": plan_context,
            "failure": {
                "category": failure.category.value,
                "command": failure.command[:300],
                "output": failure.relevant_output[-2_000:],
                "related_files": [str(item)[:120] for item in failure.related_files[:20]],
                "related_symbols": [str(item)[:160] for item in failure.related_symbols[:20]],
            },
            "evidence": evidence_context,
        })
        raw = self.model.chat(
            prompt=prompt,
            system_prompt=(
                "Produce strict JSON with concise rationale and one unified diff patch. "
                "Make the smallest evidence-backed repair within the listed plan scope. "
                "The owner's original request and supplied acceptance contract are authoritative. "
                "Never alter tests to hide failures. When an existing expected value contradicts "
                "the explicit acceptance contract, preserve every tested expression and assertion "
                "and correct only the expected literal to the contract; implement the contract exactly. "
                "Never change the actual expression or inputs in an existing assertion. "
                "Return a valid git unified diff with one `diff --git a/path b/path` header, "
                "matching `--- a/path` and `+++ b/path` headers, and at least one `@@` hunk "
                "for every changed file. Do not return a summary, empty patch, or Markdown fences. "
                "If a previous patch and Git preflight error are supplied, correct the patch "
                "format/context using that evidence while preserving the intended change. "
                "If explicitly requested, correct contradictory test expectations to that contract "
                "while preserving and expanding meaningful coverage. When the task names an "
                "acceptance contract as authoritative, correct only assertions that contradict "
                "its formula; never change scoring components to satisfy an inconsistent test. "
                "For symbol-scoped source, "
                "keep edits inside the approved symbol; do not add module-level imports or other "
                "unknown effects. Prefer a function-local standard-library import when needed. "
                "Never widen scope, weaken tests, add pass/TODO, disable validation, or invent APIs."
            ),
            temperature=0.0,
            max_tokens=7000,
            response_format={"type": "json_schema", "json_schema": {
                "name": "bounded_repair", "strict": True,
                "schema": {"type": "object", "properties": {
                    "rationale": {"type": "string"}, "patch": {"type": "string"}},
                    "required": ["rationale", "patch"], "additionalProperties": False},
            }},
        )
        model = getattr(getattr(self.model, "_orchestrator", None), "model", self.model)
        if getattr(model, "last_response_metadata", {}).get("finish_reason") == "length":
            raise ValidationIntelligenceError("Truncated model response; repair was not applied")
        try:
            value = json.loads(raw)
            if (not isinstance(value, dict) or set(value) != {"rationale", "patch"}
                    or not all(isinstance(item, str) and item.strip() for item in value.values())):
                raise ValueError("repair schema validation failed")
            rationale, patch = value["rationale"], value["patch"]
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            raise ValidationIntelligenceError(f"Malformed repair response: {exc}") from exc
        try:
            scope = extract_patch_scope(patch, self.symbols, self.index_prefix)
        except PatchValidationError as exc:
            if "no deterministic file changes" not in str(exc):
                raise ValidationIntelligenceError(
                    f"Repair rejected because its patch is malformed: {exc}"
                ) from exc
            # Give the local model one bounded format-correction attempt when it
            # returned a non-patch instead of abandoning an otherwise repairable
            # validation failure. The original plan scope and contract are repeated.
            correction = self.model.chat(
                prompt=redacted_json({
                    "task": plan_context,
                    "acceptance_contract": evidence_context["binding_contracts"],
                    "prior_rationale": rationale[:1_000],
                    "rejected_patch": patch[:6_000],
                    "parser_error": str(exc)[:500],
                    "required_output": (
                        "Return one strict JSON object with rationale and a real unified diff. "
                        "Include diff --git, --- a/path, +++ b/path, and @@ hunk headers."
                    ),
                }),
                system_prompt=(
                    "Correct the formatting of the rejected bounded repair. Preserve its intended "
                    "contract-correct change, stay within the listed files and symbols, and return "
                    "strict JSON with rationale and a valid git unified diff. Do not return prose, "
                    "an empty patch, or Markdown fences. Never weaken tests or widen scope."
                ),
                temperature=0.0,
                max_tokens=7000,
                response_format={"type": "json_schema", "json_schema": {
                    "name": "bounded_repair", "strict": True,
                    "schema": {"type": "object", "properties": {
                        "rationale": {"type": "string"}, "patch": {"type": "string"}},
                        "required": ["rationale", "patch"], "additionalProperties": False},
                }},
            )
            if getattr(model, "last_response_metadata", {}).get("finish_reason") == "length":
                raise ValidationIntelligenceError(
                    "Truncated model response while correcting patch format"
                )
            try:
                corrected = json.loads(correction)
                if (not isinstance(corrected, dict)
                        or set(corrected) != {"rationale", "patch"}
                        or not all(isinstance(item, str) and item.strip()
                                   for item in corrected.values())):
                    raise ValueError("repair format correction schema validation failed")
                rationale, patch = corrected["rationale"], corrected["patch"]
            except (ValueError, TypeError, KeyError, json.JSONDecodeError) as correction_error:
                raise ValidationIntelligenceError(
                    f"Malformed repair format correction: {correction_error}"
                ) from correction_error
            try:
                scope = extract_patch_scope(patch, self.symbols, self.index_prefix)
            except PatchValidationError as correction_error:
                raise ValidationIntelligenceError(
                    f"Repair rejected because corrected patch is malformed: {correction_error}"
                ) from correction_error
        issues = validate_patch_scope(self.policy, scope)
        if issues:
            raise ValidationIntelligenceError("Repair requires reapproval: " + "; ".join(issues))
        weakening = [
            item
            for item in validate_test_patch(patch)
            if item.blocking and item.category != "production_mutation"
        ]
        if evidence_context["binding_contracts"]:
            # A contract-backed expected-value correction is allowed only when
            # the assertion structure and actual expression are unchanged.
            weakening = [
                item for item in validate_test_patch(
                    patch, allow_contract_expectation_updates=True,
                ) if item.blocking and item.category != "production_mutation"
            ]
        if weakening:
            raise ValidationIntelligenceError(
                "Repair rejected for test weakening: "
                + "; ".join(item.rationale for item in weakening)
            )
        risky = [item for item in scan_changed_content(patch) if item.blocking]
        if risky:
            raise ValidationIntelligenceError(
                "Repair requires reapproval for increased security risk: "
                + "; ".join(item.category for item in risky)
            )
        if _disables_validation(patch):
            raise ValidationIntelligenceError("Repair may not disable validation configuration")
        if _repair_shortcut(patch):
            raise ValidationIntelligenceError("Repair contains placeholder or exception-swallowing shortcut")
        attempt = RepairAttempt(len(self.attempts) + 1, rationale[:1000], patch, hashlib.sha256(patch.encode()).hexdigest(), DecisionStatus.REPAIR_REQUIRED)
        self.attempts.append(attempt)
        return attempt


def _disables_validation(patch: str) -> bool:
    validation_files = (
        "pyproject.toml", "pytest.ini", "tox.ini", "ruff.toml", "mypy.ini",
        "pyrightconfig.json", "package.json", "tsconfig.json", "Cargo.toml",
        "foundry.toml", ".gitleaks.toml",
    )
    current = ""
    for line in patch.splitlines():
        if line.startswith("--- a/"):
            current = line[6:]
        elif current.endswith(validation_files) and line.startswith("-") and not line.startswith("---"):
            if re.search(r"pytest|test|ruff|mypy|pyright|eslint|lint|build|security|gitleaks", line, re.I):
                return True
    return False


def _repair_shortcut(patch: str) -> bool:
    additions = "\n".join(
        line[1:]
        for line in patch.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    )
    return bool(
        re.search(r"(?m)^\s*pass\s*(?:#.*)?$|\b(?:TODO|FIXME)\b", additions)
        or re.search(r"except\s+(?:Exception|BaseException)\b[^:]*:\s*(?:pass|return)", additions, re.DOTALL)
    )
