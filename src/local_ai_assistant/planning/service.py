"""Budgeted Qwen planning over deterministic Stage 2 evidence."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from local_ai_assistant.code_index.symbol_index import SymbolIndex
from local_ai_assistant.common.errors import LocalAIError
from local_ai_assistant.common.logging import get_logger
from local_ai_assistant.common.repository_files import read_repo_file_bounded

from .analysis import ScopeAnalyzer, assess_confidence, assess_risk, decide_approval
from .classification import classify_task
from .instructions import discover_project_instructions
from .models import (
    ApprovalDecision,
    ApprovalStatus,
    ConfidenceAssessment,
    DependencyChange,
    ImplementationPlan,
    IssueSeverity,
    PlannedTest,
    PlanningArtifact,
    PlanStep,
    RiskAssessment,
    RiskLevel,
    ScopeCandidate,
    ValidationIssue,
)
from .validation import PlanValidator

logger = get_logger(__name__)
CONTEXT_CHARACTER_BUDGET = 24_000
REQUIRED_PLAN_FIELDS = {
    "summary",
    "assumptions",
    "files_to_inspect",
    "files_to_modify",
    "files_to_create",
    "files_to_delete_or_rename",
    "symbols_to_modify",
    "symbols_to_create",
    "steps",
    "relevant_tests",
    "validation_commands",
    "dependency_changes",
    "migration_implications",
    "security_implications",
    "rollback_considerations",
    "unresolved_questions",
}


class PlanGenerationError(LocalAIError):
    """Raised when the local planner returns malformed or unusable output."""


class PlannerService:
    def __init__(self, repository: Path, symbol_index: SymbolIndex, llm, plan_dir: Path, legacy_retrieve=None) -> None:
        self.repository = repository.resolve()
        self.symbol_index = symbol_index
        self.llm = llm
        self.plan_dir = plan_dir.resolve()
        self.analyzer = ScopeAnalyzer(self.repository, symbol_index, legacy_retrieve)
        self.validator = PlanValidator(self.repository, symbol_index)

    def analyze(self, request: str):
        classification = classify_task(request)
        candidates = self.analyzer.analyze(request)
        return classification, candidates

    def generate(self, request: str) -> PlanningArtifact:
        classification, candidates = self.analyze(request)
        starting_commit = self._head()
        task_id = hashlib.sha256(f"{self.repository}\0{starting_commit}\0{request}".encode()).hexdigest()[:16]
        prompt, instruction_sources, context_truncated = self._prompt(
            request, classification.category.value, candidates
        )
        response = self.llm.chat(
            prompt=prompt,
            system_prompt="You are a planning-only senior engineer. Return valid JSON and never generate a patch.",
            temperature=0.0,
            max_tokens=3000,
        )
        raw = self._parse_response(response)
        preliminary = self._build_plan(task_id, request, classification, candidates, raw)
        risk = assess_risk(
            request,
            classification,
            tuple((*preliminary.files_to_modify, *preliminary.files_to_create, *preliminary.files_to_delete_or_rename)),
            preliminary.dependency_changes,
            preliminary.files_to_delete_or_rename,
        )
        issues = list(self.validator.validate(preliminary, candidates))
        if risk.level in {RiskLevel.HIGH, RiskLevel.CRITICAL} and not any(
            item.required_full_suite for item in preliminary.relevant_tests
        ):
            issues.append(
                ValidationIssue(
                    IssueSeverity.ERROR,
                    "high_risk_full_suite_required",
                    "High/critical-risk plans must require the full test suite.",
                )
            )
        issues_tuple = tuple(issues)
        confidence = assess_confidence(
            classification,
            candidates,
            sum(issue.severity.value == "warning" for issue in issues_tuple),
            len(preliminary.unresolved_questions),
        )
        approval = decide_approval(
            risk,
            confidence,
            issues_tuple,
            len(set((*preliminary.files_to_modify, *preliminary.files_to_create, *preliminary.files_to_delete_or_rename))),
            len(preliminary.unresolved_questions),
        )
        plan = replace(preliminary, confidence=confidence, risk=risk, approval=approval)
        artifact = PlanningArtifact(
            datetime.now(UTC).isoformat(),
            str(self.repository),
            starting_commit,
            request,
            classification,
            candidates,
            plan,
            issues_tuple,
            instruction_sources,
            context_truncated,
        )
        logger.info("plan_generated", extra={"event": "planning.generated", "task_id": task_id, "risk": risk.level.value, "approval": approval.status.value, "candidate_count": len(candidates), "issue_count": len(issues)})
        return artifact

    def persist(self, artifact: PlanningArtifact, destination: Path | None = None) -> Path:
        output = destination or self.plan_dir / f"{artifact.plan.task_id}.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(f".{output.name}.tmp")
        content = json.dumps(artifact.to_dict(), indent=2, ensure_ascii=False) + "\n"
        with temporary.open("w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output)
        return output

    @staticmethod
    def load(path: Path) -> PlanningArtifact:
        try:
            return PlanningArtifact.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise PlanGenerationError(f"Invalid persisted plan: {exc}") from exc

    def identity_issues(self, artifact: PlanningArtifact) -> tuple[ValidationIssue, ...]:
        issues = []
        if Path(artifact.repository).resolve() != self.repository:
            issues.append(
                ValidationIssue(
                    IssueSeverity.ERROR,
                    "repository_mismatch",
                    "Persisted plan belongs to a different repository.",
                    artifact.repository,
                )
            )
        current_commit = self._head()
        if artifact.starting_commit != current_commit:
            issues.append(
                ValidationIssue(
                    IssueSeverity.ERROR,
                    "starting_commit_mismatch",
                    "Repository HEAD changed after this plan was generated; regenerate the plan.",
                    f"planned={artifact.starting_commit}, current={current_commit}",
                )
            )
        return tuple(issues)

    def _prompt(
        self, request: str, category: str, candidates: tuple[ScopeCandidate, ...]
    ) -> tuple[str, tuple[str, ...], bool]:
        candidate_data = []
        remaining = CONTEXT_CHARACTER_BUDGET
        context_truncated = False
        for candidate in candidates:
            symbol = next((item for item in self.symbol_index.symbols if item.identifier == candidate.symbol_id), None)
            source = symbol.source if symbol else ""
            source_limit = min(4000, remaining)
            if len(source) > source_limit:
                context_truncated = True
            entry = {
                "path": candidate.path,
                "symbol_id": candidate.symbol_id,
                "qualified_name": candidate.qualified_name,
                "relationship": candidate.relationship,
                "reason": candidate.reason,
                "confidence": candidate.confidence,
                "provenance": candidate.provenance,
                "source": source[:source_limit],
            }
            encoded = json.dumps(entry)
            if len(encoded) > remaining:
                context_truncated = True
                break
            candidate_data.append(entry)
            remaining -= len(encoded)
        paths = tuple(dict.fromkeys(item.path for item in candidates))
        instructions, instruction_sources, instructions_truncated = discover_project_instructions(
            self.repository, paths, 8000
        )
        context_truncated = context_truncated or instructions_truncated
        architecture = ""
        architecture_file = self.repository / "ARCHITECTURE.md"
        if remaining > len(instructions):
            architecture_read = read_repo_file_bounded(
                self.repository, architecture_file, max_bytes=4000
            )
            architecture = architecture_read.text or ""
        schema = {
            "summary": "string",
            "assumptions": ["string"],
            "files_to_inspect": ["existing/path"],
            "files_to_modify": ["existing/path"],
            "files_to_create": ["explicit/proposed-new/path"],
            "files_to_delete_or_rename": ["existing/path"],
            "symbols_to_modify": ["existing symbol ID or qualified name"],
            "symbols_to_create": ["explicit proposed-new qualified name"],
            "steps": [{"order": 1, "description": "string", "files": [], "symbols": []}],
            "relevant_tests": [{"path": "tests/test_module.py", "reason": "why relevant", "command": "python -m pytest tests/test_module.py", "required_full_suite": False}],
            "validation_commands": ["command"],
            "dependency_changes": [{"manifest": "pyproject.toml", "kind": "new_dependency|removed_dependency|version_change|unknown_dependency_impact", "description": "string"}],
            "migration_implications": ["string"],
            "security_implications": ["string"],
            "rollback_considerations": ["string"],
            "unresolved_questions": ["string"],
        }
        prompt = f"""Create an implementation plan only. Do not generate code, patches, or commands that mutate the repository.

REQUEST: {request}
DETERMINISTIC CLASSIFICATION: {category}

DETERMINISTIC SCOPE EVIDENCE:
{json.dumps(candidate_data, indent=2)}

PROJECT INSTRUCTIONS (root to leaf; later entries take precedence):
{instructions}

RELEVANT ARCHITECTURE:
{architecture}

Return exactly one JSON object matching this shape:
{json.dumps(schema, indent=2)}

Rules: existing targets must come from evidence or be justified in assumptions; new files/symbols must appear only in the explicit proposed-new arrays; keep scope minimal; cite paths/symbol IDs in steps; identify tests, dependency, migration, security, and rollback implications. Unknowns belong in unresolved_questions."""
        return prompt, instruction_sources, context_truncated

    @staticmethod
    def _parse_response(response: str) -> dict[str, Any]:
        text = response.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1])
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise PlanGenerationError(f"Planner returned malformed JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise PlanGenerationError("Planner response must be a JSON object")
        return value

    @staticmethod
    def _build_plan(task_id, request, classification, candidates, raw):
        missing = sorted(REQUIRED_PLAN_FIELDS - raw.keys())
        if missing:
            raise PlanGenerationError(
                "Planner response is missing required fields: " + ", ".join(missing)
            )
        direct = tuple(item for item in candidates if item.role.value == "direct")
        dependent = tuple(item for item in candidates if item.role.value == "dependent")
        try:
            steps = tuple(PlanStep.from_dict(item) for item in raw["steps"])
            return ImplementationPlan(
                task_id, request, classification, str(raw["summary"]),
                tuple(raw.get("assumptions", ())), direct, dependent,
                tuple(dict.fromkeys(raw.get("files_to_inspect", ()))),
                tuple(dict.fromkeys(raw.get("files_to_modify", ()))),
                tuple(dict.fromkeys(raw.get("files_to_create", ()))),
                tuple(dict.fromkeys(raw.get("files_to_delete_or_rename", ()))),
                tuple(dict.fromkeys(raw.get("symbols_to_modify", ()))),
                tuple(dict.fromkeys(raw.get("symbols_to_create", ()))), steps,
                tuple(PlannedTest.from_dict(item) for item in raw.get("relevant_tests", ())), tuple(raw.get("validation_commands", ())),
                tuple(DependencyChange.from_dict(item) for item in raw.get("dependency_changes", ())), tuple(raw.get("migration_implications", ())),
                tuple(raw.get("security_implications", ())), tuple(raw.get("rollback_considerations", ())),
                tuple(raw.get("unresolved_questions", ())), ConfidenceAssessment(0.0, {}, ()),
                RiskAssessment(RiskLevel.MEDIUM, ("Pending deterministic assessment.",)),
                ApprovalDecision(ApprovalStatus.REVIEW, ("Pending deterministic assessment.",)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise PlanGenerationError(f"Planner response does not match plan schema: {exc}") from exc

    def _head(self) -> str:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.repository, text=True, capture_output=True)
        return result.stdout.strip() if result.returncode == 0 else "not-a-git-repository"
