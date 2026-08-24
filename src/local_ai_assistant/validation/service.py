"""Stage 5 validation orchestration without expanding execution authority."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from local_ai_assistant.execution.commands import run_allowed_command
from local_ai_assistant.execution.history import redact, redacted_json
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
        return replace(
            build_validation_plan(
                self.repository,
                artifact.plan,
                artifact.starting_commit,
                tdd=tdd,
                timeouts=timeouts,
            ),
            configuration_identity=self._config_identity(),
        )

    def run(
        self,
        artifact: PlanningArtifact,
        validation_plan: ValidationPlan,
        *,
        targeted_only: bool = False,
        required_only: bool = False,
        perform_review: bool = True,
        prior_results=(),
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
        if worktree_diff(self.repository) != diff:
            raise ValidationArtifactError("Repository diff changed during validation")
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
            review = (
                model_review(
                    model,
                    artifact.plan,
                    diff,
                    deterministic,
                    validation_results=(*prior_results, *results),
                )
                if model
                else deterministic
            )
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
                "original_request": artifact.plan.original_request,
                "plan_summary": artifact.plan.summary,
                "risk": artifact.plan.risk.level.value,
                "approval": artifact.plan.approval.status.value,
                "affected_files": validation_plan.affected_files,
                "affected_symbols": validation_plan.affected_symbols,
                "configuration_identity": validation_plan.configuration_identity,
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
        config_identity = self._config_identity() + ":" + self._environment_identity(executable)
        cache_key = ValidationCache.key(self.repository, commit, diff, step.command, config_identity)
        if self.cache and (cached := self.cache.get(cache_key)):
            return ValidationResult(step.step_id, True, False, 0, cached["summary"], cached=True, provenance=_provenance(step, timestamp, "cached_pass", ReviewSeverity.INFO, "Diff/config-aware cached success"))
        snapshot = self._snapshot()
        result = run_allowed_command(step.command, self.repository, step.timeout_seconds)
        success = result.return_code == 0 and not result.timed_out
        if (
            worktree_diff(self.repository) != diff
            or _sensitive_entries(self.repository) != snapshot.sensitive
        ):
            success = False
            self._restore_snapshot(snapshot)
            result = type(result)(
                result.command,
                result.return_code,
                result.stdout,
                result.stderr + "\nValidation command changed repository state.",
                result.timed_out,
            )
        summary = "Validation passed" if success else "Validation timed out" if result.timed_out else "Validation failed"
        output = redact((result.stdout + "\n" + result.stderr)[-20000:])
        if success and self.cache:
            self.cache.put_success(cache_key, summary)
        return ValidationResult(step.step_id, success, False, result.return_code, summary, output, provenance=_provenance(step, timestamp, "pass" if success else "fail", ReviewSeverity.INFO if success else ReviewSeverity.HIGH, output[-500:]))

    def _snapshot(self) -> _WorktreeSnapshot:
        staged = _git_patch(self.repository, "--cached")
        unstaged = _git_patch(self.repository)
        untracked: list[_UntrackedEntry] = []
        for relative in _untracked_paths(self.repository):
            candidate = self.repository / relative
            parent = candidate.parent.resolve()
            if parent != self.repository and self.repository not in parent.parents:
                raise ValidationArtifactError("Unsafe untracked path in validation snapshot")
            metadata = os.lstat(candidate)
            if stat.S_ISLNK(metadata.st_mode):
                untracked.append(
                    _UntrackedEntry(relative, "symlink", os.readlink(candidate).encode(), metadata.st_mode)
                )
            elif stat.S_ISREG(metadata.st_mode):
                untracked.append(
                    _UntrackedEntry(relative, "file", candidate.read_bytes(), metadata.st_mode)
                )
            else:
                raise ValidationArtifactError("Unsupported untracked filesystem entry")
        return _WorktreeSnapshot(staged, unstaged, tuple(untracked), _sensitive_entries(self.repository))

    def _restore_snapshot(self, snapshot: _WorktreeSnapshot) -> None:
        """Restore tracked, staged, untracked, mode, and symlink state exactly."""
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
        for relative in _untracked_paths(self.repository):
            candidate = self.repository / relative
            if candidate.is_symlink() or candidate.is_file():
                candidate.unlink()
        _apply_patch(self.repository, snapshot.staged_patch, index=True)
        _apply_patch(self.repository, snapshot.unstaged_patch, index=False)
        for entry in snapshot.untracked:
            candidate = self.repository / entry.path
            candidate.parent.mkdir(parents=True, exist_ok=True)
            if entry.kind == "symlink":
                candidate.symlink_to(entry.content.decode())
            else:
                candidate.write_bytes(entry.content)
                os.chmod(candidate, stat.S_IMODE(entry.mode))
        for entry in _sensitive_entries(self.repository):
            candidate = self.repository / entry.path
            if candidate.is_symlink() or candidate.is_file():
                candidate.unlink()
        for entry in snapshot.sensitive:
            candidate = self.repository / entry.path
            candidate.parent.mkdir(parents=True, exist_ok=True)
            if entry.kind == "symlink":
                candidate.symlink_to(entry.content.decode())
            else:
                candidate.write_bytes(entry.content)
                os.chmod(candidate, stat.S_IMODE(entry.mode))
        if self._snapshot() != snapshot:
            raise ValidationArtifactError("Could not restore exact pre-validation repository state")

    def _verify_identity(self, artifact, plan):
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.repository, text=True, capture_output=True).stdout.strip()
        if (
            str(self.repository) != str(Path(plan.repository).resolve())
            or artifact.starting_commit != plan.starting_commit
            or head != plan.starting_commit
            or plan.task_id != artifact.plan.task_id
            or plan.plan_hash != plan_approval_token(artifact.plan)
            or plan.risk_level != artifact.plan.risk.level.value
            or plan.configuration_identity != self._config_identity()
        ):
            raise ValidationArtifactError("Validation plan repository, task, or starting commit is stale")
        expected = self.build(
            artifact,
            tdd=plan.tdd_enabled,
            timeouts=plan.timeout_policy,
        )
        if plan != expected:
            raise ValidationArtifactError("Validation commands or requirements differ from detection policy")

    def _config_identity(self):
        digest = hashlib.sha256()
        for name in (
            "pyproject.toml", "pytest.ini", "tox.ini", "mypy.ini", "pyrightconfig.json",
            "ruff.toml", ".coveragerc", "package.json", "package-lock.json", "pnpm-lock.yaml",
            "yarn.lock", "tsconfig.json", "eslint.config.js", ".eslintrc", ".eslintrc.json",
            "Cargo.toml", "Cargo.lock", "clippy.toml", "foundry.toml", ".gitleaks.toml",
        ):
            path = self.repository / name
            if path.is_file():
                digest.update(name.encode())
                digest.update(path.read_bytes())
        return digest.hexdigest()

    def _environment_identity(self, executable: str) -> str:
        resolved = shutil.which(executable) or executable
        payload = "\0".join(
            (
                str(Path(resolved).resolve()),
                sys.version,
                platform.platform(),
                os.environ.get("VIRTUAL_ENV", ""),
                os.environ.get("PYTHONPATH", ""),
            )
        )
        return hashlib.sha256(payload.encode()).hexdigest()


def persist_validation_plan(plan: ValidationPlan, path: Path) -> Path:
    return _persist(plan.to_dict(), path)


def load_validation_plan(path: Path) -> ValidationPlan:
    try:
        return ValidationPlan.from_dict(json.loads(path.read_text()))
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValidationArtifactError(f"Invalid validation plan: {exc}") from exc


def persist_validation_report(report: ValidationReport, path: Path) -> Path:
    return _persist(report.to_dict(), path)


def load_validation_report(path: Path) -> dict:
    try:
        value = json.loads(path.read_text())
        if value.get("schema_version") != 1 or not isinstance(value.get("plan"), dict):
            raise ValueError("unsupported validation report schema")
        ValidationPlan.from_dict(value["plan"])
        if not isinstance(value.get("results"), list) or not isinstance(value.get("decision"), dict):
            raise ValueError("validation report is missing required records")
        return value
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValidationArtifactError(f"Invalid validation report: {exc}") from exc


def _persist(value: dict, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("." + path.name + ".tmp")
    with temporary.open("w") as stream:
        stream.write(redacted_json(value, indent=2, ensure_ascii=False))
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    return path


def _provenance(step, timestamp, result, severity, evidence):
    return ValidationProvenance(step.step_id, step.command, step.related_files[0] if step.related_files else None, step.related_symbols[0] if step.related_symbols else None, None, None, None, timestamp, result, severity, evidence[:500])


@dataclass(frozen=True, slots=True)
class _UntrackedEntry:
    path: str
    kind: str
    content: bytes
    mode: int


@dataclass(frozen=True, slots=True)
class _WorktreeSnapshot:
    staged_patch: str
    unstaged_patch: str
    untracked: tuple[_UntrackedEntry, ...]
    sensitive: tuple[_UntrackedEntry, ...]


def _git_patch(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "diff", *arguments, "--binary", "--find-renames"],
        cwd=repository,
        text=True,
        capture_output=True,
    )
    if result.returncode:
        raise ValidationArtifactError("Could not snapshot repository diff: " + result.stderr)
    return result.stdout


def _untracked_paths(repository: Path) -> tuple[str, ...]:
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=repository,
        text=True,
        capture_output=True,
    )
    if result.returncode:
        raise ValidationArtifactError("Could not inspect untracked validation state")
    return tuple(item[3:] for item in result.stdout.split("\0") if item.startswith("?? "))


def _sensitive_entries(repository: Path) -> tuple[_UntrackedEntry, ...]:
    entries = []
    for candidate in repository.rglob("*"):
        if ".git" in candidate.relative_to(repository).parts:
            continue
        name = candidate.name.lower()
        if not (
            name == ".env"
            or name.startswith(".env.")
            or name in {"id_rsa", "id_ed25519", "credentials"}
            or name.endswith((".pem", ".key"))
        ):
            continue
        metadata = os.lstat(candidate)
        relative = candidate.relative_to(repository).as_posix()
        if stat.S_ISLNK(metadata.st_mode):
            entries.append(
                _UntrackedEntry(relative, "symlink", os.readlink(candidate).encode(), metadata.st_mode)
            )
        elif stat.S_ISREG(metadata.st_mode):
            if metadata.st_size > 2_000_000:
                raise ValidationArtifactError("Sensitive validation snapshot file is too large")
            entries.append(_UntrackedEntry(relative, "file", candidate.read_bytes(), metadata.st_mode))
    return tuple(entries)


def _apply_patch(repository: Path, patch: str, *, index: bool) -> None:
    if not patch:
        return
    with tempfile.NamedTemporaryFile("w", suffix=".patch", delete=False) as stream:
        stream.write(patch)
        patch_path = Path(stream.name)
    command = ["git", "apply", "--binary", "--recount"]
    if index:
        command.append("--index")
    command.append(str(patch_path))
    try:
        applied = subprocess.run(command, cwd=repository, text=True, capture_output=True)
    finally:
        patch_path.unlink(missing_ok=True)
    if applied.returncode:
        raise ValidationArtifactError(
            "Could not restore pre-validation repository state: " + applied.stderr.strip()
        )
