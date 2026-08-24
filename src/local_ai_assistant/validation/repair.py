"""Bounded evidence-driven repair proposal engine."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from local_ai_assistant.execution.history import redact
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
        prompt = redact(json.dumps({"request": plan.original_request, "plan": plan.to_dict(), "failure": {"category": failure.category.value, "command": failure.command, "output": failure.relevant_output, "related_files": failure.related_files, "related_symbols": failure.related_symbols}, "evidence": evidence}))[:24000]
        raw = self.model.chat(prompt=prompt, system_prompt="Produce strict JSON with concise rationale and unified diff patch. Make the smallest evidence-backed repair. Never widen scope, weaken tests, add pass/TODO, disable validation, or invent APIs.", temperature=0.0, max_tokens=1800)
        try:
            value = json.loads(raw)
            rationale, patch = str(value["rationale"]), str(value["patch"])
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            raise ValidationIntelligenceError(f"Malformed repair response: {exc}") from exc
        scope = extract_patch_scope(patch, self.symbols, self.index_prefix)
        issues = validate_patch_scope(self.policy, scope)
        if issues:
            raise ValidationIntelligenceError("Repair requires reapproval: " + "; ".join(issues))
        weakening = [
            item
            for item in validate_test_patch(patch)
            if item.blocking and item.category != "production_mutation"
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
