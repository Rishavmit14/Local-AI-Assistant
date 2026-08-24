"""Stage 5 validation orchestration without expanding execution authority."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from local_ai_assistant.execution.commands import run_allowed_command
from local_ai_assistant.planning.analysis import scope_guard_from_plan
from local_ai_assistant.planning.models import PlanningArtifact, plan_approval_token
from local_ai_assistant.planning.patch_scope import worktree_diff

from .cache import ValidationCache
from .decision import decide_final
from .detection import build_validation_plan
from .errors import ValidationArtifactError
from .failures import classify_failure
from .models import (
    Requirement,
    ReviewResult,
    ReviewSeverity,
    ValidationPlan,
    ValidationProvenance,
    ValidationReport,
    ValidationResult,
)
from .review import deterministic_review, model_review


class ValidationService:
    def __init__(self, repository: Path, cache_path: Path | None = None) -> None:
        self.repository = repository.resolve()
        self.cache = ValidationCache(cache_path) if cache_path else None

    def build(
        self,
        artifact: PlanningArtifact,
        *,
        tdd: bool = False,
        timeouts: dict[str, int] | None = None,
    ) -> ValidationPlan:
        return build_validation_plan(
            self.repository,
            artifact.plan,
            artifact.starting_commit,
            tdd=tdd,
            timeouts=timeouts,
        )

    def run(
        self,
        artifact: PlanningArtifact,
        validation_plan: ValidationPlan,
        *,
        targeted_only: bool = False,
        required_only: bool = False,
        perform_review: bool = True,
        model=None,
        symbols=(),
        index_prefix: str = "",
    ) -> ValidationReport:
        self._verify_identity(artifact, validation_plan)
        diff = worktree_diff(self.repository)
        if targeted_only and required_only:
            raise ValidationArtifactError("Validation phase cannot be both targeted and required-only")
        steps = (
            validation_plan.targeted_steps
            if targeted_only
            else validation_plan.final_steps
            if required_only
            else (*validation_plan.targeted_steps, *validation_plan.final_steps)
        )
        results = tuple(self._run_step(item, artifact.starting_commit, diff) for item in steps)
        failures = tuple(
            classify_failure(step.command or "", result.return_code, result.output, timed_out="timed out" in result.summary.lower())
            for step, result in zip(steps, results, strict=True)
            if not result.success and not result.skipped
        )
        if perform_review:
            deterministic = deterministic_review(
                self.repository,
                artifact.plan,
                scope_guard_from_plan(artifact.plan),
                diff,
                symbols,
                index_prefix=index_prefix,
            )
            review = model_review(model, artifact.plan, diff, deterministic) if model else deterministic
        else:
            review = ReviewResult(
                validation_plan.plan_hash,
                hashlib.sha256(diff.encode()).hexdigest(),
                (),
            )
        decision_plan = (
            replace(validation_plan, final_steps=())
            if targeted_only
            else replace(validation_plan, targeted_steps=())
            if required_only
            else validation_plan
        )
        decision = decide_final(decision_plan, results, review)
        return ValidationReport(
            1,
            validation_plan,
            results,
            failures,
            review,
            decision,
            metadata={
                "diff_hash": hashlib.sha256(diff.encode()).hexdigest(),
                "phase": "targeted" if targeted_only else "required" if required_only else "all",
            },
        )

    def _run_step(self, step, commit: str, diff: str) -> ValidationResult:
        timestamp = datetime.now(UTC).isoformat()
        if not step.command:
            return ValidationResult(step.step_id, step.requirement is not Requirement.REQUIRED, True, None, "No command configured", provenance=_provenance(step, timestamp, "skipped", ReviewSeverity.MEDIUM, "No command configured"))
        executable = step.command.split()[0]
        if shutil.which(executable) is None:
            success = step.requirement is not Requirement.REQUIRED
            return ValidationResult(step.step_id, success, True, None, f"Validation tool unavailable: {executable}", provenance=_provenance(step, timestamp, "unavailable", ReviewSeverity.HIGH if not success else ReviewSeverity.MEDIUM, f"{executable} was not found"))
        config_identity = self._config_identity()
        cache_key = ValidationCache.key(self.repository, commit, diff, step.command, config_identity)
        if self.cache and (cached := self.cache.get(cache_key)):
            return ValidationResult(step.step_id, True, False, 0, cached["summary"], cached=True, provenance=_provenance(step, timestamp, "cached_pass", ReviewSeverity.INFO, "Diff/config-aware cached success"))
        result = run_allowed_command(step.command, self.repository, step.timeout_seconds)
        success = result.return_code == 0 and not result.timed_out
        if worktree_diff(self.repository) != diff:
            success = False
            self._restore_diff(diff)
            result = type(result)(
                result.command,
                result.return_code,
                result.stdout,
                result.stderr + "\nValidation command changed repository state.",
                result.timed_out,
            )
        summary = "Validation passed" if success else "Validation timed out" if result.timed_out else "Validation failed"
        output = (result.stdout + "\n" + result.stderr)[-20000:]
        if success and self.cache:
            self.cache.put_success(cache_key, summary)
        return ValidationResult(step.step_id, success, False, result.return_code, summary, output, provenance=_provenance(step, timestamp, "pass" if success else "fail", ReviewSeverity.INFO if success else ReviewSeverity.HIGH, output[-500:]))

    def _restore_diff(self, diff: str) -> None:
        """Remove validator side effects and restore the exact pre-command working diff."""
        restored = subprocess.run(
            ["git", "restore", "--staged", "--worktree", "."],
            cwd=self.repository,
            text=True,
            capture_output=True,
        )
        if restored.returncode:
            raise ValidationArtifactError(
                "Could not roll back validation side effects: " + restored.stderr.strip()
            )
        status = subprocess.run(
            ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
            cwd=self.repository,
            text=True,
            capture_output=True,
        )
        for item in status.stdout.split("\0"):
            if not item.startswith("?? "):
                continue
            candidate = (self.repository / item[3:]).resolve()
            if self.repository not in candidate.parents or not candidate.is_file():
                raise ValidationArtifactError("Unsafe untracked validation side effect")
            candidate.unlink()
        if not diff:
            return
        with tempfile.NamedTemporaryFile("w", suffix=".patch", delete=False) as stream:
            stream.write(diff)
            patch_path = Path(stream.name)
        try:
            applied = subprocess.run(
                ["git", "apply", "--binary", "--recount", str(patch_path)],
                cwd=self.repository,
                text=True,
                capture_output=True,
            )
        finally:
            patch_path.unlink(missing_ok=True)
        if applied.returncode or worktree_diff(self.repository) != diff:
            raise ValidationArtifactError(
                "Could not restore the pre-validation repository state: "
                + applied.stderr.strip()
            )

    def _verify_identity(self, artifact, plan):
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.repository, text=True, capture_output=True).stdout.strip()
        if (
            str(self.repository) != str(Path(plan.repository).resolve())
            or artifact.starting_commit != plan.starting_commit
            or head != plan.starting_commit
            or plan.task_id != artifact.plan.task_id
            or plan.plan_hash != plan_approval_token(artifact.plan)
        ):
            raise ValidationArtifactError("Validation plan repository, task, or starting commit is stale")

    def _config_identity(self):
        digest = hashlib.sha256()
        for name in ("pyproject.toml", "pytest.ini", "tox.ini", "mypy.ini", "pyrightconfig.json", "package.json", "tsconfig.json", "Cargo.toml", "foundry.toml"):
            path = self.repository / name
            if path.is_file():
                digest.update(name.encode())
                digest.update(path.read_bytes())
        return digest.hexdigest()


def persist_validation_plan(plan: ValidationPlan, path: Path) -> Path:
    return _persist(plan.to_dict(), path)


def load_validation_plan(path: Path) -> ValidationPlan:
    try:
        return ValidationPlan.from_dict(json.loads(path.read_text()))
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValidationArtifactError(f"Invalid validation plan: {exc}") from exc


def persist_validation_report(report: ValidationReport, path: Path) -> Path:
    return _persist(report.to_dict(), path)


def _persist(value: dict, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("." + path.name + ".tmp")
    with temporary.open("w") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    return path


def _provenance(step, timestamp, result, severity, evidence):
    return ValidationProvenance(step.step_id, step.command, step.related_files[0] if step.related_files else None, step.related_symbols[0] if step.related_symbols else None, None, None, None, timestamp, result, severity, evidence[:500])
