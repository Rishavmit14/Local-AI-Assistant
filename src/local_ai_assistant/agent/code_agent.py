from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import time
from dataclasses import replace
from functools import partial
from pathlib import Path

from local_ai_assistant.code_index import CodeRAG
from local_ai_assistant.common.config import AppConfig, get_config
from local_ai_assistant.common.errors import (
    DirtyRepositoryError,
    GitTransactionError,
    RepositoryError,
)
from local_ai_assistant.common.logging import configure_logging, get_logger
from local_ai_assistant.common.models import GitTransactionSummary
from local_ai_assistant.execution.errors import ToolExecutionError
from local_ai_assistant.execution.history import persist_report
from local_ai_assistant.execution.loop import ExecutionLoop, LoopLimits
from local_ai_assistant.execution.models import ExecutionReport
from local_ai_assistant.execution.registry import ToolContext, default_registry
from local_ai_assistant.history.importer import ArtifactImporter
from local_ai_assistant.history.models import TaskStatus
from local_ai_assistant.history.service import TaskHistoryService
from local_ai_assistant.history.store import TaskHistoryStore
from local_ai_assistant.isolation.checkpoints import CheckpointManager
from local_ai_assistant.isolation.errors import IsolationError
from local_ai_assistant.isolation.models import (
    CapabilityState,
    NetworkPolicy,
    ResourcePolicy,
    WorktreeState,
)
from local_ai_assistant.isolation.sandbox import select_backend
from local_ai_assistant.isolation.worktrees import WorktreeManager
from local_ai_assistant.planning import PlannerService
from local_ai_assistant.planning.analysis import scope_guard_from_plan
from local_ai_assistant.planning.models import (
    ApprovalStatus,
    IssueSeverity,
    plan_approval_token,
)
from local_ai_assistant.planning.patch_scope import (
    extract_patch_scope,
    render_patch_scope,
    validate_patch_scope,
    worktree_diff,
)
from local_ai_assistant.validation.decision import decide_final
from local_ai_assistant.validation.errors import TestGenerationError, ValidationIntelligenceError
from local_ai_assistant.validation.models import DecisionStatus, ValidationReport
from local_ai_assistant.validation.repair import BoundedRepairEngine
from local_ai_assistant.validation.service import (
    ValidationService,
    persist_validation_report,
)
from local_ai_assistant.validation.tests import (
    generate_test_patch,
    meaningful_tdd_failure,
)

_DEFAULT_CONFIG = get_config()
REPO_ROOT = _DEFAULT_CONFIG.paths.code_repo_dir
PATCH_DIR = _DEFAULT_CONFIG.paths.patch_dir
logger = get_logger(__name__)

PATCH_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


def _history_service(config: AppConfig) -> TaskHistoryService:
    return TaskHistoryService(
        TaskHistoryStore(config.paths.task_history_db),
        artifact_roots=(config.paths.code_index_dir, config.paths.task_history_db.parent),
    )


def _record_plan(config: AppConfig, artifact, path: Path, repo: Path, branch: str) -> None:
    """Index a canonical plan without changing planner/execution authority."""
    try:
        service = _history_service(config)
        task = service.get(artifact.plan.task_id)
        if task is None:
            service.create_task(
                artifact.request,
                repo,
                artifact.starting_commit,
                branch,
                task_id=artifact.plan.task_id,
                created_at=artifact.timestamp,
                metadata={
                    "runtime": {
                        "model": Path(config.llama.model).name,
                        "endpoint_profile": config.llama.base_url,
                        "context_size": config.llama.context_size,
                    }
                },
            )
            service.transition(
                artifact.plan.task_id, TaskStatus.PLANNING, "Plan generation completed",
                subsystem="planning",
            )
        service.attach_plan(artifact.plan.task_id, artifact, path)
        task = service.get(artifact.plan.task_id)
        if task and task.status is TaskStatus.PLANNING:
            target = (
                TaskStatus.APPROVED
                if artifact.plan.approval.status is ApprovalStatus.AUTOMATIC
                else TaskStatus.AWAITING_APPROVAL
            )
            service.transition(
                task.task_id, target, artifact.plan.approval.status.value,
                subsystem="approval",
            )
    except Exception as exc:
        logger.error(
            "task_history_plan_failed",
            extra={"event": "history.plan.failed", "error": str(exc)},
        )


def _persist_execution(config: AppConfig, report: ExecutionReport, path: Path) -> None:
    persist_report(report, path)
    try:
        ArtifactImporter(_history_service(config)).import_path(
            path, repository=Path(report.repository)
        )
    except Exception as exc:
        logger.error(
            "task_history_execution_failed",
            extra={"event": "history.execution.failed", "error": str(exc)},
        )


def _cancel_requested(config: AppConfig, task_id: str) -> bool:
    try:
        return _history_service(config).cancel_requested(task_id)
    except Exception:
        return False


def _record_isolation(config: AppConfig, task_id: str, event: str, summary: str, **metadata) -> None:
    try:
        _history_service(config).record_isolation_event(
            task_id, event, summary, status=event, metadata=metadata
        )
    except Exception as exc:
        raise IsolationError(f"Cannot persist required isolation audit event: {exc}") from exc


def _bind_history_worktree(
    config: AppConfig, task_id: str, repository: Path, branch: str
) -> None:
    try:
        service = _history_service(config)
        service.store.update_task(task_id, str(repository.resolve()), branch=branch)
    except Exception as exc:
        raise IsolationError(f"Cannot bind task history to isolated branch: {exc}") from exc


def _mark_execution_started(
    config: AppConfig,
    task_id: str,
    approval_token: str,
    explicit_approval: str | None,
) -> None:
    """Expose lifecycle progress without becoming an execution authority."""
    try:
        service = _history_service(config)
        task = service.get(task_id)
        if task is None:
            return
        if task.status in {TaskStatus.AWAITING_APPROVAL, TaskStatus.REAPPROVAL_REQUIRED}:
            if explicit_approval != approval_token:
                return
            service.attach_approval(
                task_id,
                approval_token,
                "explicitly_approved",
                actor="code_agent",
                reason="Execution started with the exact approved plan hash",
            )
            service.transition(
                task_id,
                TaskStatus.APPROVED,
                "Exact-plan approval accepted by the existing code-agent policy",
                subsystem="approval",
            )
            task = service.get(task_id)
        if task and task.status is TaskStatus.APPROVED:
            service.transition(
                task_id,
                TaskStatus.EXECUTING,
                "Tool-driven execution started",
                subsystem="execution",
            )
    except Exception as exc:
        logger.error(
            "task_history_execution_start_failed",
            extra={"event": "history.execution.start_failed", "error": str(exc)},
        )


def _mark_validation_started(config: AppConfig, task_id: str) -> None:
    try:
        service = _history_service(config)
        task = service.get(task_id)
        if task and task.status is TaskStatus.EXECUTING:
            service.transition(
                task_id,
                TaskStatus.VALIDATING,
                "Intelligent validation started",
                subsystem="validation",
            )
    except Exception as exc:
        logger.error(
            "task_history_validation_start_failed",
            extra={"event": "history.validation.start_failed", "error": str(exc)},
        )


def run_intelligent_validation(
    repo,
    artifact,
    rag,
    config,
    *,
    context: ToolContext | None = None,
    max_repairs: int = 0,
) -> tuple[bool, str, str]:
    """Run targeted checks, bounded repair, final checks, and review in that order."""
    _mark_validation_started(config, artifact.plan.task_id)
    service = ValidationService(
        repo,
        config.paths.code_index_dir / "validation-cache.json",
        sandbox=context.sandbox if context else None,
        sandbox_task_root=context.sandbox_task_root if context else None,
        sandbox_resources=context.sandbox_resources if context else None,
        sandbox_network=context.sandbox_network if context else None,
        cancel_check=context.cancel_check if context else None,
    )
    validation_plan = service.build(
        artifact,
        timeouts={
            "structural": config.execution.inspection_timeout_seconds,
            "lint": config.execution.lint_timeout_seconds,
            "typecheck": config.execution.lint_timeout_seconds,
            "test": config.execution.test_timeout_seconds,
            "build": config.execution.build_timeout_seconds,
        },
    )
    try:
        relative = repo.resolve().relative_to(rag.symbol_index.repository.resolve()).as_posix()
        index_prefix = "" if relative == "." else relative + "/"
    except ValueError:
        index_prefix = ""
    targeted = service.run(
        artifact,
        validation_plan,
        targeted_only=True,
        perform_review=False,
        symbols=tuple(rag.symbol_index.symbols),
        index_prefix=index_prefix,
    )
    repair_engine = BoundedRepairEngine(
        rag.llm,
        scope_guard_from_plan(artifact.plan),
        symbols=tuple(rag.symbol_index.symbols),
        index_prefix=index_prefix,
        max_attempts=max_repairs,
    )
    repair_stop_reason = None
    while targeted.failures and context is not None and len(repair_engine.attempts) < max_repairs:
        failure = targeted.failures[0]
        try:
            repair_context = rag.build_context(
                rag.retrieve(
                    artifact.plan.original_request + "\n" + failure.relevant_output[-4000:]
                )
            )[:10_000]
            attempt = repair_engine.propose(
                artifact.plan,
                failure,
                {
                    "current_diff": worktree_diff(repo)[-12_000:],
                    "affected_source_context": repair_context,
                },
            )
            observation = default_registry(config.execution).invoke(
                "apply_patch",
                {
                    "patch": attempt.patch,
                    "_rationale": attempt.rationale,
                    "_expected_outcome": "Targeted validation passes",
                    "_plan_step": "validation-repair",
                    "_mutation_intended": True,
                },
                context,
            )
            if not observation.success:
                repair_stop_reason = observation.summary
                break
        except (ToolExecutionError, ValidationIntelligenceError) as exc:
            repair_stop_reason = str(exc)
            break
        targeted = service.run(
            artifact,
            validation_plan,
            targeted_only=True,
            perform_review=False,
            symbols=tuple(rag.symbol_index.symbols),
            index_prefix=index_prefix,
        )
    if targeted.decision.status not in {DecisionStatus.PASS, DecisionStatus.PASS_WITH_WARNINGS}:
        report = ValidationReport(
            1,
            validation_plan,
            targeted.results,
            targeted.failures,
            targeted.review,
            targeted.decision,
            repair_attempts=len(repair_engine.attempts),
            metadata={
                **targeted.metadata,
                "phase": "targeted",
                "repair_history": [
                    {
                        "number": item.number,
                        "rationale": item.rationale,
                        "patch_hash": item.patch_hash,
                        "status": item.status.value,
                    }
                    for item in repair_engine.attempts
                ],
                "repair_stop_reason": repair_stop_reason,
            },
        )
    else:
        required = service.run(
            artifact,
            validation_plan,
            required_only=True,
            prior_results=targeted.results,
            model=rag.llm,
            symbols=tuple(rag.symbol_index.symbols),
            index_prefix=index_prefix,
        )
        results = (*targeted.results, *required.results)
        failures = (*targeted.failures, *required.failures)
        decision = decide_final(validation_plan, results, required.review)
        report = ValidationReport(
            1,
            validation_plan,
            results,
            failures,
            required.review,
            decision,
            repair_attempts=len(repair_engine.attempts),
            metadata={
                **required.metadata,
                "phase": "final",
                "sequence_enforced": True,
                "repair_history": [
                    {
                        "number": item.number,
                        "rationale": item.rationale,
                        "patch_hash": item.patch_hash,
                        "status": item.status.value,
                    }
                    for item in repair_engine.attempts
                ],
                "repair_stop_reason": repair_stop_reason,
            },
        )
    validation_path = (
        config.paths.code_index_dir / "validations" / f"{artifact.plan.task_id}.json"
    )
    persist_validation_report(report, validation_path)
    try:
        ArtifactImporter(_history_service(config)).import_path(
            validation_path, repository=Path(artifact.repository)
        )
    except Exception as exc:
        logger.error(
            "task_history_validation_failed",
            extra={"event": "history.validation.failed", "error": str(exc)},
        )
    allowed = {DecisionStatus.PASS, DecisionStatus.PASS_WITH_WARNINGS}
    return (
        report.decision.status in allowed,
        "; ".join(report.decision.reasons),
        report.review.diff_hash,
    )


def prepare_generated_test(
    repo,
    artifact,
    rag,
    config,
    context: ToolContext,
    *,
    tdd: bool,
) -> tuple[bool, str]:
    """Generate/apply an approved test mutation and optionally prove a meaningful RED phase."""
    evidence = rag.build_context(rag.retrieve(artifact.plan.original_request))[:12_000]
    try:
        generated = generate_test_patch(
            rag.llm,
            artifact.plan,
            context.policy,
            evidence,
            tdd=tdd,
        )
        observation = default_registry(config.execution).invoke(
            "apply_patch",
            {
                "patch": generated.patch,
                "_rationale": generated.rationale,
                "_expected_outcome": "Approved regression/feature test is added",
                "_plan_step": "test-generation",
                "_mutation_intended": True,
            },
            context,
        )
    except (TestGenerationError, ToolExecutionError) as exc:
        return False, f"Generated test rejected: {exc}"
    if not observation.success:
        return False, observation.summary
    if not tdd:
        return True, f"Generated test patch applied: {generated.patch_hash}"
    service = ValidationService(repo)
    validation_plan = service.build(artifact, tdd=True)
    red = service.run(
        artifact,
        validation_plan,
        targeted_only=True,
        perform_review=False,
    )
    if not red.failures:
        return False, "TDD RED phase failed: generated test did not fail before implementation"
    meaningful = [meaningful_tdd_failure(item) for item in red.failures]
    if not all(item[0] for item in meaningful):
        return False, "TDD RED phase failed: " + "; ".join(item[1] for item in meaningful)
    target_failure = any(
        any(
            path in failure.command
            or any(path in affected for affected in failure.affected_tests)
            for path in generated.target_files
        )
        for failure in red.failures
    )
    if not target_failure:
        return False, "TDD RED phase failed outside the generated test target"
    return True, "TDD RED phase confirmed by behavior assertion failure"


# ============================================================
# SHELL / GIT HELPERS
# ============================================================


def run_command(
    command: list[str],
    cwd: Path,
    *,
    timeout: int | None = None,
) -> subprocess.CompletedProcess:
    logger.info(
        "command_started",
        extra={"event": "command.started", "command": command, "cwd": cwd},
    )
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=timeout or get_config().runtime.command_timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        logger.error(
            "command_timed_out",
            extra={"event": "command.timed_out", "command": command, "cwd": cwd},
        )
        raise GitTransactionError(f"Command timed out: {' '.join(command)}") from exc
    logger.info(
        "command_completed",
        extra={
            "event": "command.completed",
            "command": command,
            "cwd": cwd,
            "return_code": result.returncode,
        },
    )
    return result


def ensure_git_repo(
    repo: Path,
):
    result = run_command(
        [
            "git",
            "rev-parse",
            "--is-inside-work-tree",
        ],
        repo,
    )

    if result.returncode != 0:
        raise RepositoryError(f"{repo} is not a Git repository.")


def get_repo(
    name: str,
    repo_root: Path | None = None,
) -> Path:

    repo = (repo_root or REPO_ROOT) / name

    if not repo.exists():
        raise RepositoryError(f"Repository not found: {repo}")

    ensure_git_repo(repo)

    return repo


def git_status(
    repo: Path,
) -> str:

    result = run_command(
        [
            "git",
            "status",
            "--short",
        ],
        repo,
    )

    return result.stdout.strip()


def git_current_branch(repo: Path) -> str:
    result = run_command(
        ["git", "branch", "--show-current"],
        repo,
    )
    return result.stdout.strip()


def git_head(repo: Path) -> str:
    result = run_command(
        ["git", "rev-parse", "HEAD"],
        repo,
    )
    return result.stdout.strip()


def git_is_clean(repo: Path) -> bool:
    result = run_command(
        ["git", "status", "--porcelain"],
        repo,
    )
    return not result.stdout.strip()


def make_branch_name(request: str) -> str:
    import re

    slug = request.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    slug = slug[:40].rstrip("-")

    if not slug:
        slug = "task"

    stamp = time.strftime("%Y%m%d-%H%M%S")

    return f"agent/{slug}-{stamp}"


def create_agent_branch(
    repo: Path,
    request: str,
) -> tuple[str, str, str]:
    """
    Create an isolated branch for an autonomous change.

    Returns:
        original_branch,
        starting_commit,
        new_branch
    """

    if not git_is_clean(repo):
        raise DirtyRepositoryError(
            "Repository is not clean. Commit or discard existing changes first."
        )

    original_branch = git_current_branch(repo)

    if original_branch.startswith("agent/"):
        raise GitTransactionError(
            "Refusing to create an agent branch from another "
            "agent branch. Merge, keep, or switch back to your "
            "normal development branch first."
        )

    starting_commit = git_head(repo)
    branch_name = make_branch_name(request)

    result = run_command(
        [
            "git",
            "switch",
            "-c",
            branch_name,
        ],
        repo,
    )

    if result.returncode != 0:
        raise GitTransactionError(
            "Could not create agent branch:\n" + result.stdout + result.stderr
        )

    return (
        original_branch,
        starting_commit,
        branch_name,
    )


def rollback_agent_changes(
    repo: Path,
    starting_commit: str,
    original_branch: str | None = None,
    agent_branch: str | None = None,
    keep_failed_branch: bool = False,
) -> None:
    """
    Restore the repository to the exact commit where the
    autonomous run started.

    If an isolated agent branch was created, return to the
    original branch and remove the failed temporary branch.
    """

    if keep_failed_branch and agent_branch:
        run_command(["git", "add", "-A"], repo)
        preserved = run_command(
            ["git", "commit", "-m", "agent: preserve failed changes for review"],
            repo,
        )
        if preserved.returncode != 0 and not git_is_clean(repo):
            raise GitTransactionError("Could not preserve failed agent branch: " + preserved.stderr)
    else:
        reset_result = run_command(
            ["git", "reset", "--hard", starting_commit],
            repo,
        )
        if reset_result.returncode != 0:
            raise GitTransactionError(
                "Could not reset failed agent changes: " + reset_result.stderr
            )

        clean_result = run_command(["git", "clean", "-fd"], repo)
        if clean_result.returncode != 0:
            raise GitTransactionError(
                "Could not clean failed agent changes: " + clean_result.stderr
            )

    if original_branch and agent_branch and original_branch != agent_branch:
        switch_result = run_command(
            [
                "git",
                "switch",
                original_branch,
            ],
            repo,
        )

        if switch_result.returncode != 0:
            raise GitTransactionError(
                "Could not return to original branch: " + switch_result.stderr
            )

        if not keep_failed_branch:
            delete_result = run_command(
                [
                    "git",
                    "branch",
                    "-D",
                    agent_branch,
                ],
                repo,
            )
            if delete_result.returncode != 0:
                raise GitTransactionError(
                    "Could not delete failed agent branch: " + delete_result.stderr
                )


def commit_agent_changes(
    repo: Path,
    request: str,
    expected_diff_hash: str | None = None,
) -> str:
    """
    Commit successful autonomous changes.
    """

    run_command(
        ["git", "add", "-A"],
        repo,
    )
    if expected_diff_hash is not None:
        staged = run_command(
            ["git", "diff", "--cached", "HEAD", "--binary", "--find-renames"],
            repo,
        )
        staged_hash = hashlib.sha256(staged.stdout.encode()).hexdigest()
        if staged.returncode != 0 or staged_hash != expected_diff_hash:
            run_command(["git", "restore", "--staged", "."], repo)
            raise GitTransactionError("Staged commit diff differs from reviewed validation diff")

    message = request.strip()

    if len(message) > 65:
        message = message[:62].rstrip() + "..."

    if not message:
        message = "Apply autonomous code change"

    result = run_command(
        [
            "git",
            "-c",
            "core.hooksPath=/dev/null",
            "commit",
            "-m",
            f"agent: {message}",
        ],
        repo,
    )

    if result.returncode != 0:
        raise GitTransactionError("Automatic commit failed:\n" + result.stdout + result.stderr)

    return git_head(repo)


def merge_agent_branch(
    repo: Path,
    original_branch: str,
    agent_branch: str,
) -> str:
    """Fast-forward an approved successful agent branch and remove it."""
    switch_result = run_command(["git", "switch", original_branch], repo)
    if switch_result.returncode != 0:
        raise GitTransactionError("Could not switch to review branch: " + switch_result.stderr)
    merge_result = run_command(["git", "merge", "--ff-only", agent_branch], repo)
    if merge_result.returncode != 0:
        raise GitTransactionError("Approved fast-forward merge failed: " + merge_result.stderr)
    delete_result = run_command(["git", "branch", "-d", agent_branch], repo)
    if delete_result.returncode != 0:
        raise GitTransactionError(
            "Merged agent branch could not be deleted: " + delete_result.stderr
        )
    return git_head(repo)


def validate_python_structure(repo: Path) -> tuple[bool, str]:
    """
    Validate Python files changed by the current agent run.

    Checks:
    - Python syntax
    - duplicate top-level functions
    - duplicate top-level classes

    This intentionally avoids aggressive static analysis that
    could generate false positives.
    """

    import ast

    result = run_command(
        [
            "git",
            "diff",
            "--name-only",
            "--diff-filter=ACMR",
        ],
        repo,
    )

    changed_files = [
        line.strip() for line in result.stdout.splitlines() if line.strip().endswith(".py")
    ]

    if not changed_files:
        return True, "No changed Python files."

    errors = []

    for relative_path in changed_files:
        file_path = repo / relative_path

        if not file_path.is_file():
            continue

        try:
            source = file_path.read_text(
                encoding="utf-8",
            )

            tree = ast.parse(
                source,
                filename=str(file_path),
            )

        except SyntaxError as exc:
            errors.append(f"{relative_path}: syntax error at line {exc.lineno}: {exc.msg}")

            continue

        except Exception as exc:
            errors.append(f"{relative_path}: could not validate: {exc}")

            continue

        functions = {}
        classes = {}

        for node in tree.body:
            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            ):
                functions.setdefault(
                    node.name,
                    [],
                ).append(node.lineno)

            elif isinstance(
                node,
                ast.ClassDef,
            ):
                classes.setdefault(
                    node.name,
                    [],
                ).append(node.lineno)

        for name, lines in functions.items():
            if len(lines) > 1:
                errors.append(
                    f"{relative_path}: duplicate top-level function {name!r} at lines {lines}"
                )

        for name, lines in classes.items():
            if len(lines) > 1:
                errors.append(
                    f"{relative_path}: duplicate top-level class {name!r} at lines {lines}"
                )

    if errors:
        return (
            False,
            "\n".join(errors),
        )

    return (
        True,
        "Python structural validation passed.",
    )


def finalize_agent_run(
    repo: Path,
    request: str,
    tests_passed: bool,
    auto_commit: bool,
    rollback_on_fail: bool,
    starting_commit: str | None,
    original_branch: str | None = None,
    agent_branch: str | None = None,
    keep_failed_branch: bool = False,
    auto_merge: bool = False,
    merge_approved: bool = False,
    expected_diff_hash: str | None = None,
) -> GitTransactionSummary:
    """
    Finalize an autonomous coding-agent transaction.

    Success:
      - optionally commit validated/tested changes.

    Failure:
      - optionally reset to the starting commit,
        switch back to the original branch,
        and delete the failed agent branch.
    """

    if tests_passed and expected_diff_hash is not None:
        actual_diff_hash = hashlib.sha256(worktree_diff(repo).encode()).hexdigest()
        if actual_diff_hash != expected_diff_hash:
            logger.error(
                "reviewed_diff_changed_before_commit",
                extra={
                    "event": "validation.diff_stale",
                    "expected_diff_hash": expected_diff_hash,
                    "actual_diff_hash": actual_diff_hash,
                },
            )
            tests_passed = False

    if tests_passed:
        if not auto_commit:
            return GitTransactionSummary(
                outcome="review_required",
                repository=repo,
                original_branch=original_branch,
                agent_branch=agent_branch,
                starting_commit=starting_commit,
            )

        if git_is_clean(repo):
            print("No repository changes remain; nothing to commit.")
            return GitTransactionSummary(
                outcome="no_changes",
                repository=repo,
                original_branch=original_branch,
                agent_branch=agent_branch,
                starting_commit=starting_commit,
            )

        try:
            commit_hash = commit_agent_changes(
                repo,
                request,
                expected_diff_hash,
            )
        except GitTransactionError:
            if rollback_on_fail and starting_commit:
                rollback_agent_changes(
                    repo,
                    starting_commit,
                    original_branch,
                    agent_branch,
                    keep_failed_branch,
                )
                return GitTransactionSummary(
                    outcome="failed_preserved" if keep_failed_branch else "rolled_back",
                    repository=repo,
                    original_branch=original_branch,
                    agent_branch=agent_branch,
                    starting_commit=starting_commit,
                    rolled_back=not keep_failed_branch,
                    failed_branch_kept=keep_failed_branch,
                )
            raise

        print()
        print("=" * 70)

        print("AUTOMATIC COMMIT")

        print("=" * 70)

        print(f"Committed successful changes: {commit_hash[:12]}")

        outcome = "committed"
        if auto_merge:
            if not merge_approved:
                raise GitTransactionError("Automatic merge requires explicit approval")
            if not original_branch or not agent_branch:
                raise GitTransactionError("Automatic merge requires an isolated agent branch")
            commit_hash = merge_agent_branch(repo, original_branch, agent_branch)
            outcome = "merged"

        if git_head(repo) != commit_hash or not git_is_clean(repo):
            raise GitTransactionError("Final success verification failed")

        summary = GitTransactionSummary(
            outcome=outcome,
            repository=repo,
            original_branch=original_branch,
            agent_branch=agent_branch,
            starting_commit=starting_commit,
            resulting_commit=commit_hash,
        )
        logger.info(
            "git_transaction_completed",
            extra={"event": "git.transaction.completed", "summary": summary},
        )
        print(f"Transaction outcome: {summary.outcome}")

        return summary

    if rollback_on_fail and starting_commit:
        print()
        print("=" * 70)

        print("ROLLBACK")

        print("=" * 70)

        rollback_agent_changes(
            repo,
            starting_commit,
            original_branch,
            agent_branch,
            keep_failed_branch,
        )

        print("Final validation/tests failed. Agent changes were rolled back.")

        summary = GitTransactionSummary(
            outcome="failed_preserved" if keep_failed_branch else "rolled_back",
            repository=repo,
            original_branch=original_branch,
            agent_branch=agent_branch,
            starting_commit=starting_commit,
            rolled_back=not keep_failed_branch,
            failed_branch_kept=keep_failed_branch,
        )
        logger.info(
            "git_transaction_completed",
            extra={"event": "git.transaction.completed", "summary": summary},
        )
        print(f"Transaction outcome: {summary.outcome}")
        return summary

    return GitTransactionSummary(
        outcome="failed_unmodified",
        repository=repo,
        original_branch=original_branch,
        agent_branch=agent_branch,
        starting_commit=starting_commit,
    )


def git_diff(
    repo: Path,
) -> str:

    result = run_command(
        [
            "git",
            "diff",
        ],
        repo,
    )

    return result.stdout


# ============================================================
# PATCH NORMALIZATION
# ============================================================


def extract_diff(
    text: str,
) -> str:

    marker = "diff --git "

    start = text.find(marker)

    if start == -1:
        return ""

    return text[start:].strip() + "\n"


def normalize_patch(
    repo_name: str,
    diff: str,
) -> str:
    """
    Convert:

      a/demo-app/app/api.py

    into:

      a/app/api.py
    """

    prefix_a = f"a/{repo_name}/"

    prefix_b = f"b/{repo_name}/"

    diff = diff.replace(
        prefix_a,
        "a/",
    )

    diff = diff.replace(
        prefix_b,
        "b/",
    )

    return diff


def save_patch(
    repo_name: str,
    diff: str,
    suffix: str = "proposed",
    patch_dir: Path | None = None,
) -> Path:

    safe_name = repo_name.replace(
        "/",
        "_",
    )

    diff = normalize_patch(
        repo_name,
        diff,
    )

    destination = patch_dir or PATCH_DIR
    destination.mkdir(parents=True, exist_ok=True)
    patch_file = destination / f"{safe_name}_{suffix}.patch"

    patch_file.write_text(
        diff,
        encoding="utf-8",
    )

    return patch_file


# ============================================================
# PATCH VALIDATION / APPLICATION
# ============================================================


def check_patch(
    repo: Path,
    patch_file: Path,
) -> bool:

    result = run_command(
        [
            "git",
            "apply",
            "--check",
            "--recount",
            str(patch_file),
        ],
        repo,
    )

    if result.returncode == 0:
        logger.info(
            "patch_validation_passed",
            extra={"event": "agent.patch.validation_passed", "patch": patch_file},
        )

        print("Patch validation: PASS")

        return True

    print("Patch validation: FAIL")
    logger.error(
        "patch_validation_failed",
        extra={"event": "agent.patch.validation_failed", "patch": patch_file},
    )

    if result.stderr:
        print(result.stderr)

    return False


def apply_patch(
    repo: Path,
    patch_file: Path,
) -> bool:

    result = run_command(
        [
            "git",
            "apply",
            "--recount",
            str(patch_file),
        ],
        repo,
    )

    if result.returncode != 0:
        print("Patch application failed.")

        if result.stderr:
            print(result.stderr)

        return False

    print("Patch applied successfully.")
    logger.info(
        "patch_applied",
        extra={"event": "agent.patch.applied", "patch": patch_file},
    )

    return True


# ============================================================
# TEST RUNNER
# ============================================================


def detect_and_run_tests(
    repo: Path,
) -> tuple[
    int | None,
    str,
]:

    logger.info("test_detection_started", extra={"event": "agent.tests.detection_started"})
    print()
    print("Detecting test environment...")

    # --------------------------------------------------------
    # Python
    # --------------------------------------------------------

    if (
        (repo / "tests").exists()
        or (repo / "pytest.ini").exists()
        or (repo / "pyproject.toml").exists()
    ):
        print("Running pytest...")

        result = run_command(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
            ],
            repo,
        )

        output = (result.stdout + "\n" + result.stderr).strip()

        logger.info(
            "tests_completed",
            extra={
                "event": "agent.tests.completed",
                "framework": "pytest",
                "return_code": result.returncode,
            },
        )

        print(output)

        return (
            result.returncode,
            output,
        )

    # --------------------------------------------------------
    # Rust
    # --------------------------------------------------------

    if (repo / "Cargo.toml").exists():
        print("Running cargo test...")

        result = run_command(
            [
                "cargo",
                "test",
            ],
            repo,
        )

        output = (result.stdout + "\n" + result.stderr).strip()

        logger.info(
            "tests_completed",
            extra={
                "event": "agent.tests.completed",
                "framework": "cargo",
                "return_code": result.returncode,
            },
        )

        print(output)

        return (
            result.returncode,
            output,
        )

    # --------------------------------------------------------
    # Node / JS / TS
    # --------------------------------------------------------

    if (repo / "package.json").exists():
        print("Running npm test...")

        result = run_command(
            [
                "npm",
                "test",
                "--",
                "--runInBand",
            ],
            repo,
        )

        output = (result.stdout + "\n" + result.stderr).strip()

        logger.info(
            "tests_completed",
            extra={
                "event": "agent.tests.completed",
                "framework": "npm",
                "return_code": result.returncode,
            },
        )

        print(output)

        return (
            result.returncode,
            output,
        )

    print("No recognized test environment found.")

    return (
        None,
        "No tests detected.",
    )


# ============================================================
# INDEX REFRESH
# ============================================================


def reindex_repository(config: AppConfig | None = None):
    print()
    print("Refreshing repository index...")

    rag = CodeRAG(config=config)

    rag.reindex()

    print("Repository index refreshed.")

    return rag


# ============================================================
# INITIAL PATCH GENERATION
# ============================================================


def propose_patch(
    rag: CodeRAG,
    repo_name: str,
    request: str,
):

    results = rag.retrieve(request)

    context = rag.build_context(results)

    prompt = f"""
You are modifying a software repository.

Repository:
{repo_name}

TASK:

{request}

Relevant repository code:

{context}

Produce the smallest correct patch.

STRICT RULES:

1. Return only a unified Git diff.
2. The output must begin with:

diff --git

3. Use repository-relative paths.
4. Modify only files necessary for the task.
5. Preserve existing style.
6. Do not invent unrelated code.
7. Do not output Markdown fences.
8. Do not add explanations outside the diff.
9. If context is insufficient, return exactly:

INSUFFICIENT_CONTEXT
"""

    answer = rag.llm.chat(
        prompt=prompt,
        system_prompt=(
            "You are a senior software engineer producing minimal Git-compatible patches."
        ),
        temperature=0.0,
        max_tokens=1800,
    )

    return answer, results


# ============================================================
# REPAIR PATCH GENERATION
# ============================================================


def propose_repair_patch(
    rag: CodeRAG,
    repo_name: str,
    original_request: str,
    test_output: str,
):

    query = original_request + "\n\n" + test_output

    results = rag.retrieve(query)

    context = rag.build_context(results)

    current_diff = git_diff(REPO_ROOT / repo_name)

    prompt = f"""
You previously modified a software repository,
but the automated tests failed.

Repository:
{repo_name}

ORIGINAL TASK:

{original_request}

CURRENT UNCOMMITTED DIFF:

{current_diff}

TEST FAILURE:

{test_output}

Relevant repository context:

{context}

Produce a repair patch that fixes the failing tests
while preserving the original task.

STRICT RULES:

1. Return only a unified Git diff.
2. Output must begin with:

diff --git

3. Use repository-relative paths.
4. Do not revert a correct part of the original fix
   unless required.
5. Make the smallest safe change.
6. Do not modify unrelated files.
7. Do not output Markdown fences.
8. Do not include explanations.
9. If there is insufficient information, return exactly:

INSUFFICIENT_CONTEXT
"""

    answer = rag.llm.chat(
        prompt=prompt,
        system_prompt=(
            "You are a senior software engineer "
            "repairing a failing patch using "
            "automated test feedback."
        ),
        temperature=0.0,
        max_tokens=2200,
    )

    return answer, results


# ============================================================
# PRINT RETRIEVED CONTEXT
# ============================================================


def print_sources(
    results,
):

    print()
    print("Retrieved repository context:")

    for result in results:
        print(f"  {result['source']} lines {result['line_start']}-{result['line_end']}")


# ============================================================
# MAIN
# ============================================================


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=("Local Qwen repository coding agent"))

    parser.add_argument(
        "repo",
        help=("Repository directory name inside code-assistant/repos"),
    )

    parser.add_argument(
        "request",
        help="Requested code change",
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help=("Apply the proposed patch after Git validation"),
    )

    parser.add_argument(
        "--test",
        action="store_true",
        help=("Run tests after applying the patch"),
    )

    parser.add_argument(
        "--repair",
        action="store_true",
        help=("Allow one automatic repair attempt if tests fail"),
    )

    parser.add_argument(
        "--branch",
        action="store_true",
        help="Create an isolated agent Git branch before applying changes.",
    )

    parser.add_argument(
        "--auto-commit",
        action="store_true",
        help="Commit agent changes automatically after tests pass.",
    )

    parser.add_argument(
        "--rollback-on-fail",
        action="store_true",
        help="Restore the repository to the starting commit if final tests fail.",
    )

    parser.add_argument(
        "--validate",
        action="store_true",
        help="Run structural validation on changed source files.",
    )

    parser.add_argument(
        "--keep-failed-branch",
        action="store_true",
        help="Preserve failed changes in a review commit on the agent branch.",
    )

    parser.add_argument(
        "--human-review",
        action="store_true",
        help="Apply and verify changes but never commit or merge automatically.",
    )

    parser.add_argument(
        "--auto-merge",
        action="store_true",
        help="Fast-forward an isolated successful branch after explicit approval.",
    )

    parser.add_argument(
        "--approve-merge",
        action="store_true",
        help="Explicit approval required together with --auto-merge.",
    )

    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Generate, validate, persist, and print a plan without generating a patch.",
    )

    parser.add_argument(
        "--plan-output",
        type=Path,
        help="Optional JSON destination for the planning artifact.",
    )

    parser.add_argument(
        "--approve-risk",
        metavar="PLAN_TOKEN",
        help="Approve only the exact validated high/critical-risk plan with this printed token.",
    )
    parser.add_argument(
        "--tool-loop",
        action="store_true",
        help="Use bounded plan-bound tool execution instead of one-shot patch generation.",
    )
    parser.add_argument("--max-steps", type=int, help="Bound tool-loop steps for this run.")
    parser.add_argument("--max-repairs", type=int, help="Bound repair observations for this run.")
    parser.add_argument(
        "--generate-tests",
        action="store_true",
        help="Generate an approved, scope-checked test before tool-driven implementation.",
    )
    parser.add_argument(
        "--tdd",
        action="store_true",
        help="Require the generated test to fail meaningfully before implementation.",
    )
    parser.add_argument("--task-id", help="Reuse an existing Friday task identity.")

    return parser


def validate_cli_options(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """Reject option combinations that bypass the proven Git transaction."""
    if args.human_review:
        args.auto_commit = False
        args.auto_merge = False

    if args.apply:
        required = {
            "--branch": args.branch,
            "--test": args.test,
            "--validate": args.validate,
            "--rollback-on-fail": args.rollback_on_fail,
        }
        missing = [option for option, enabled in required.items() if not enabled]
        if missing:
            parser.error("--apply requires " + ", ".join(missing))
        if not args.tool_loop and not args.human_review:
            parser.error(
                "Stage 8 autonomous --apply requires --tool-loop so mutation and validation use the isolated worktree boundary"
            )
    elif args.auto_commit or args.auto_merge or args.keep_failed_branch:
        parser.error("commit, merge, and failed-branch options require --apply")

    if args.auto_merge and not (args.approve_merge and args.auto_commit):
        parser.error("--auto-merge requires --approve-merge and --auto-commit")
    if args.tool_loop and args.auto_merge:
        parser.error(
            "Stage 8 isolated execution never auto-merges; inspect and promote the task branch explicitly"
        )
    if (args.generate_tests or args.tdd) and not (args.tool_loop and args.apply):
        parser.error("--generate-tests/--tdd require --tool-loop and the complete --apply bundle")
    if args.tdd:
        args.generate_tests = True


def main(argv: list[str] | None = None):
    config = get_config()
    configure_logging(config.runtime)
    parser = build_parser()

    args = parser.parse_args(argv)

    validate_cli_options(parser, args)

    finalize_run = partial(
        finalize_agent_run,
        keep_failed_branch=args.keep_failed_branch,
        auto_merge=args.auto_merge,
        merge_approved=args.approve_merge,
    )

    repo = get_repo(
        args.repo,
        config.paths.code_repo_dir,
    )

    # --------------------------------------------------------
    # Protect existing unrelated changes.
    # --------------------------------------------------------

    existing_changes = git_status(repo)

    if existing_changes:
        print()
        print("Repository currently has uncommitted changes:")

        print()
        print(existing_changes)

        print()

        if args.apply:
            print("Automatic application is blocked when the repository is already dirty.")

            print("Commit or stash existing changes first.")

            sys.exit(1)

    original_branch = None
    starting_commit = None
    agent_branch = None

    # --------------------------------------------------------
    # Load repository index.
    # --------------------------------------------------------

    print("Loading repository index...")

    rag = CodeRAG(config=config)

    print("Refreshing repository index before patch generation...")

    rag.reindex()

    planner = PlannerService(
        repo,
        rag.symbol_index,
        rag.llm,
        config.paths.code_index_dir / "plans" / args.repo,
        getattr(rag, "retrieve", None),
    )
    artifact = planner.generate(args.request)
    if args.task_id:
        artifact = replace(artifact, plan=replace(artifact.plan, task_id=args.task_id))
    plan_path = planner.persist(artifact, args.plan_output)
    current_branch = run_command(["git", "branch", "--show-current"], repo).stdout.strip()
    _record_plan(config, artifact, plan_path, repo, current_branch)
    print()
    print("=" * 70)
    print("IMPLEMENTATION PLAN")
    print("=" * 70)
    print(f"Task:       {artifact.plan.task_id}")
    print(f"Summary:    {artifact.plan.summary}")
    print(f"Risk:       {artifact.plan.risk.level.value}")
    print(f"Confidence: {artifact.plan.confidence.score:.3f}")
    print(f"Approval:   {artifact.plan.approval.status.value}")
    approval_token = plan_approval_token(artifact.plan)
    print(f"Plan token: {approval_token}")
    print(f"Saved:      {plan_path}")
    for step in artifact.plan.steps:
        print(f"{step.order}. {step.description}")
    errors = [
        issue for issue in artifact.validation_issues if issue.severity is IssueSeverity.ERROR
    ]
    if errors:
        print("Plan validation: FAIL")
        for issue in errors:
            print(f"- {issue.code}: {issue.message}")
        sys.exit(1)
    print("Plan validation: PASS")
    if args.plan_only:
        print("Planning-only mode: no patch was generated and nothing was modified.")
        return
    if artifact.plan.approval.status in {ApprovalStatus.REVIEW, ApprovalStatus.BLOCKED}:
        if args.approve_risk != approval_token:
            print(
                "Patch generation is blocked. Review this exact plan, then pass "
                f"--approve-risk {approval_token}."
            )
            sys.exit(1)

    if args.tool_loop:
        limits = config.execution
        if not args.apply or args.human_review:
            context = ToolContext(
                repo,
                artifact,
                scope_guard_from_plan(artifact.plan),
                rag.symbol_index,
                args.approve_risk,
            )
            result = ExecutionLoop(
                rag.llm,
                default_registry(config.execution),
                context,
                LoopLimits(
                    max_steps=args.max_steps or limits.max_steps,
                    max_mutations=limits.max_mutations,
                    max_repairs=(
                        args.max_repairs if args.max_repairs is not None else limits.max_repairs
                    ),
                    max_replans=limits.max_replans,
                    context_characters=limits.context_characters,
                ),
                cancel_check=lambda: _cancel_requested(config, artifact.plan.task_id),
            ).run(dry_run=True)
            print(
                f"Tool-loop {'human review' if args.human_review else 'dry run'}: {result.status}; nothing modified."
            )
            for observation in result.observations:
                print(f"- {observation.kind}: {observation.summary}")
                if observation.data.get("patch_sha256"):
                    print(f"  Patch hash: {observation.data['patch_sha256']}")
            return
        canonical_repo = repo
        starting_commit = artifact.starting_commit
        isolation_manager = WorktreeManager(config.paths.worktree_dir)
        sandbox = select_backend(config.isolation.backend)
        capabilities = sandbox.capabilities()
        network_policy = NetworkPolicy(config.isolation.network_policy)
        if (
            network_policy is not NetworkPolicy.ALLOWED
            and capabilities.network is not CapabilityState.SUPPORTED
        ):
            print(
                "Requested network isolation is unavailable; autonomous mutation is blocked."
            )
            sys.exit(1)
        if config.isolation.require_strong_isolation and (
            capabilities.filesystem is not CapabilityState.SUPPORTED
            or capabilities.network is not CapabilityState.SUPPORTED
        ):
            print(
                "Strong isolation is required but unavailable; autonomous mutation is blocked."
            )
            sys.exit(1)
        isolation_identity = None
        try:
            isolation_identity = isolation_manager.create(
                canonical_repo,
                artifact.plan.task_id,
                starting_commit,
                approval_token,
            )
            repo = Path(isolation_identity.worktree)
            original_branch = None
            agent_branch = isolation_identity.branch
            isolation_identity = isolation_manager.transition(
                isolation_identity, WorktreeState.EXECUTING
            )
            baseline = CheckpointManager(
                config.paths.isolation_dir / "checkpoints"
            ).create(repo, artifact.plan.task_id, approval_token, "baseline")
            _bind_history_worktree(
                config, artifact.plan.task_id, canonical_repo, isolation_identity.branch
            )
            _record_isolation(
                config,
                artifact.plan.task_id,
                "worktree_ready",
                "Task worktree and baseline checkpoint created",
                worktree_id=isolation_identity.repository_id,
                branch=isolation_identity.branch,
                sandbox_backend=capabilities.backend,
                filesystem_capability=capabilities.filesystem.value,
                network_policy=network_policy.value,
                checkpoint_id=baseline.checkpoint_id,
            )
        except IsolationError as exc:
            if isolation_identity is not None:
                try:
                    isolation_manager.cleanup(
                        isolation_identity, delete_branch=True, allow_active=True
                    )
                except IsolationError:
                    pass
            print(f"Isolation setup failed: {exc}")
            sys.exit(1)
        _mark_execution_started(
            config,
            artifact.plan.task_id,
            approval_token,
            args.approve_risk,
        )
        context = ToolContext(
            repo,
            artifact,
            scope_guard_from_plan(artifact.plan),
            rag.symbol_index,
            args.approve_risk,
            sandbox=sandbox,
            sandbox_task_root=(
                config.paths.isolation_dir / "tasks" / artifact.plan.task_id
            ),
            sandbox_resources=ResourcePolicy(
                wall_seconds=config.isolation.wall_seconds,
                cpu_seconds=config.isolation.cpu_seconds,
                max_processes=config.isolation.max_processes,
                max_open_files=config.isolation.max_open_files,
                max_output_bytes=config.isolation.max_output_bytes,
                memory_bytes=config.isolation.memory_bytes,
                max_file_bytes=config.isolation.max_file_bytes,
            ),
            sandbox_network=network_policy,
            cancel_check=lambda: _cancel_requested(config, artifact.plan.task_id),
            canonical_repository=canonical_repo,
        )
        if args.generate_tests:
            generated_ok, generated_output = prepare_generated_test(
                repo,
                artifact,
                rag,
                config,
                context,
                tdd=args.tdd,
            )
            print(generated_output)
            if not generated_ok:
                transaction = finalize_run(
                    repo=repo,
                    request=args.request,
                    tests_passed=False,
                    auto_commit=args.auto_commit,
                    rollback_on_fail=True,
                    starting_commit=starting_commit,
                    original_branch=original_branch,
                    agent_branch=agent_branch,
                )
                _persist_execution(
                    config,
                    ExecutionReport(
                        1,
                        artifact.plan.task_id,
                        approval_token,
                        str(repo),
                        starting_commit,
                        transaction.outcome,
                        (approval_token,),
                        tuple(context.events),
                        final_diff=worktree_diff(repo),
                        final_commit=transaction.resulting_commit,
                    ),
                    config.paths.code_index_dir
                    / "executions"
                    / f"{artifact.plan.task_id}.json",
                )
                if not args.keep_failed_branch:
                    isolation_manager.cleanup(
                        isolation_identity, delete_branch=True, allow_active=True
                    )
                    _record_isolation(
                        config, artifact.plan.task_id, "cleaned", "Failed task worktree cleaned"
                    )
                sys.exit(1)
        try:
            result = ExecutionLoop(
                rag.llm,
                default_registry(config.execution),
                context,
                LoopLimits(
                    max_steps=args.max_steps or limits.max_steps,
                    max_mutations=limits.max_mutations,
                    max_repairs=(
                        args.max_repairs if args.max_repairs is not None else limits.max_repairs
                    ),
                    max_replans=limits.max_replans,
                    context_characters=limits.context_characters,
                ),
                cancel_check=lambda: _cancel_requested(config, artifact.plan.task_id),
            ).run()
        except ToolExecutionError as exc:
            transaction = finalize_run(
                repo=repo,
                request=args.request,
                tests_passed=False,
                auto_commit=args.auto_commit,
                rollback_on_fail=True,
                starting_commit=starting_commit,
                original_branch=original_branch,
                agent_branch=agent_branch,
            )
            _persist_execution(
                config,
                ExecutionReport(
                    1,
                    artifact.plan.task_id,
                    approval_token,
                    str(repo),
                    starting_commit,
                    transaction.outcome,
                    (approval_token,),
                    tuple(context.events),
                    final_diff="",
                    final_commit=transaction.resulting_commit,
                ),
                config.paths.code_index_dir
                / "executions"
                / f"{artifact.plan.task_id}.json",
            )
            print(f"Tool execution failed: {exc}")
            if not args.keep_failed_branch:
                isolation_manager.cleanup(
                    isolation_identity, delete_branch=True, allow_active=True
                )
                _record_isolation(
                    config, artifact.plan.task_id, "cleaned", "Failed task worktree cleaned"
                )
            sys.exit(1)
        report = ExecutionReport(
            1,
            artifact.plan.task_id,
            approval_token,
            str(repo),
            starting_commit,
            result.status,
            (approval_token,),
            tuple(context.events),
            final_diff=worktree_diff(repo),
            repairs=result.repairs,
            replans=result.replans,
        )
        cancelled_before_validation = result.status == "cancelled" or _cancel_requested(
            config, artifact.plan.task_id
        )
        if cancelled_before_validation:
            validation_ok = False
            validation_output = "Execution cancelled before validation; changes were rolled back."
            reviewed_diff_hash = None
        else:
            validation_ok, validation_output, reviewed_diff_hash = run_intelligent_validation(
                repo,
                artifact,
                rag,
                config,
                context=context,
                max_repairs=(
                    args.max_repairs if args.max_repairs is not None else limits.max_repairs
                ),
            )
        cancelled = cancelled_before_validation or _cancel_requested(
            config, artifact.plan.task_id
        )
        if cancelled:
            validation_ok = False
            validation_output = "Execution cancelled; changes were rolled back."
            reviewed_diff_hash = None
        success = result.status == "complete" and validation_ok and not cancelled
        transaction = finalize_run(
            repo=repo,
            request=args.request,
            tests_passed=success,
            auto_commit=args.auto_commit,
            rollback_on_fail=True if cancelled else args.rollback_on_fail,
            starting_commit=starting_commit,
            original_branch=original_branch,
            agent_branch=agent_branch,
            expected_diff_hash=reviewed_diff_hash,
        )
        final_report = ExecutionReport(
            report.schema_version,
            report.task_id,
            report.plan_hash,
            report.repository,
            report.starting_commit,
            (
                "cancelled_rolled_back"
                if cancelled and transaction.outcome == "rolled_back"
                else transaction.outcome
            ),
            report.plan_versions,
            report.events,
            final_diff=report.final_diff,
            final_commit=transaction.resulting_commit,
            repairs=report.repairs,
            replans=report.replans,
        )
        _persist_execution(
            config,
            final_report,
            config.paths.code_index_dir / "executions" / f"{artifact.plan.task_id}.json",
        )
        if not success:
            print(validation_output)
            if not args.keep_failed_branch:
                isolation_manager.cleanup(
                    isolation_identity, delete_branch=True, allow_active=True
                )
                _record_isolation(
                    config, artifact.plan.task_id, "cleaned", "Failed task worktree cleaned"
                )
            sys.exit(1)
        isolation_manager.transition(isolation_identity, WorktreeState.PROMOTION_READY)
        _record_isolation(
            config,
            artifact.plan.task_id,
            "promotion_ready",
            "Validated task branch is ready for explicit review/promotion",
            branch=isolation_identity.branch,
        )
        print(
            "Validated task commit remains on its isolated Friday branch; "
            "canonical checkout was not merged."
        )
        return

    # --------------------------------------------------------
    # Generate patch.
    # --------------------------------------------------------

    print()
    print("Generating proposed patch...")

    answer, results = propose_patch(
        rag,
        args.repo,
        args.request,
    )

    if answer.strip() == "INSUFFICIENT_CONTEXT":
        print("Model reported INSUFFICIENT_CONTEXT.")

        sys.exit(1)

    diff = extract_diff(answer)

    if not diff:
        print("Model did not produce a valid Git diff.")

        print()
        print(answer)

        sys.exit(1)

    patch_file = save_patch(
        args.repo,
        diff,
        "proposed",
        config.paths.patch_dir,
    )

    print()
    print("=" * 70)

    print("PROPOSED PATCH")

    print("=" * 70)

    print()
    print(patch_file.read_text(encoding="utf-8"))
    print(
        "Patch hash: "
        + hashlib.sha256(patch_file.read_bytes()).hexdigest()
    )

    print_sources(results)

    print()

    if not check_patch(
        repo,
        patch_file,
    ):
        sys.exit(1)

    patch_scope = extract_patch_scope(
        patch_file.read_text(encoding="utf-8"),
        tuple(rag.symbol_index.symbols),
        planner.analyzer.index_prefix or "",
    )
    print(render_patch_scope(patch_scope))
    scope_issues = validate_patch_scope(
        scope_guard_from_plan(artifact.plan),
        patch_scope,
    )
    if scope_issues:
        print("Patch scope validation: FAIL")
        for issue in scope_issues:
            print(f"- {issue}")
        print("Nothing has been modified.")
        sys.exit(1)
    print("Patch scope validation: PASS")

    if args.human_review:
        print("Human review stop: plan, patch, scope, risk, confidence, and tests are available.")
        print("Nothing has been modified.")
        return

    # --------------------------------------------------------
    # Proposal-only mode.
    # --------------------------------------------------------

    if not args.apply:
        print()
        print("Nothing has been modified.")

        print("Rerun with --apply to apply this patch.")

        return

    # Create the isolated branch only after proposal validation, but before
    # the first repository mutation. This keeps proposal failures branch-free.
    (
        original_branch,
        starting_commit,
        agent_branch,
    ) = create_agent_branch(
        repo,
        args.request,
    )

    print()
    print("=" * 70)
    print("GIT SAFETY")
    print("=" * 70)
    print(f"Original branch: {original_branch}")
    print(f"Agent branch:    {agent_branch}")
    print(f"Starting commit: {starting_commit}")

    # --------------------------------------------------------
    # Apply patch.
    # --------------------------------------------------------

    if not apply_patch(
        repo,
        patch_file,
    ):
        finalize_run(
            repo=repo,
            request=args.request,
            tests_passed=False,
            auto_commit=args.auto_commit,
            rollback_on_fail=True,
            starting_commit=starting_commit,
            original_branch=original_branch,
            agent_branch=agent_branch,
        )

        sys.exit(1)

    post_apply_scope = extract_patch_scope(
        worktree_diff(repo),
        tuple(rag.symbol_index.symbols),
        planner.analyzer.index_prefix or "",
    )
    post_apply_issues = validate_patch_scope(
        scope_guard_from_plan(artifact.plan),
        post_apply_scope,
    )
    if post_apply_issues:
        print("Post-apply scope validation: FAIL")
        for issue in post_apply_issues:
            print(f"- {issue}")
        finalize_run(
            repo=repo,
            request=args.request,
            tests_passed=False,
            auto_commit=args.auto_commit,
            rollback_on_fail=True,
            starting_commit=starting_commit,
            original_branch=original_branch,
            agent_branch=agent_branch,
        )
        sys.exit(1)
    print("Post-apply scope validation: PASS")

    if args.validate:
        print()
        print("=" * 70)

        print("STRUCTURAL VALIDATION")

        print("=" * 70)

        structure_ok, structure_report = validate_python_structure(repo)

        print(structure_report)

        if not structure_ok:
            print()
            print("Structural validation: FAIL")

            finalize_run(
                repo=repo,
                request=args.request,
                tests_passed=False,
                auto_commit=args.auto_commit,
                rollback_on_fail=args.rollback_on_fail,
                starting_commit=starting_commit,
                original_branch=original_branch,
                agent_branch=agent_branch,
            )

            sys.exit(1)

        print("Structural validation: PASS")

    print()
    print("=" * 70)

    print("CURRENT GIT DIFF")

    print("=" * 70)

    print()
    print(git_diff(repo))

    # --------------------------------------------------------
    # Re-index immediately after edit.
    # --------------------------------------------------------

    rag = reindex_repository(config)

    # --------------------------------------------------------
    # No tests requested.
    # --------------------------------------------------------

    if not args.test:
        print()
        print("Patch applied and repository re-indexed.")

        return

    # --------------------------------------------------------
    # Run tests.
    # --------------------------------------------------------

    return_code, test_output = detect_and_run_tests(repo)

    if return_code is None:
        print()
        print("Patch applied, but no tests were detected.")

        finalize_run(
            repo=repo,
            request=args.request,
            tests_passed=False,
            auto_commit=args.auto_commit,
            rollback_on_fail=True,
            starting_commit=starting_commit,
            original_branch=original_branch,
            agent_branch=agent_branch,
        )
        sys.exit(1)

    if return_code == 0:
        print()
        print("Tests: PASS")

        print("Coding-agent cycle completed successfully.")

        finalize_run(
            repo=repo,
            request=args.request,
            tests_passed=True,
            auto_commit=args.auto_commit,
            rollback_on_fail=args.rollback_on_fail,
            starting_commit=starting_commit,
            original_branch=original_branch,
            agent_branch=agent_branch,
        )

        return

    # --------------------------------------------------------
    # Tests failed.
    # --------------------------------------------------------

    print()
    print("Tests: FAIL")

    if not args.repair:
        print("Automatic repair is disabled.")

        print("Rerun with --repair if you want one repair attempt.")

        finalize_run(
            repo=repo,
            request=args.request,
            tests_passed=False,
            auto_commit=args.auto_commit,
            rollback_on_fail=args.rollback_on_fail,
            starting_commit=starting_commit,
            original_branch=original_branch,
            agent_branch=agent_branch,
        )

        sys.exit(return_code)

    # --------------------------------------------------------
    # One repair attempt.
    # --------------------------------------------------------

    print()
    print("=" * 70)

    print("AUTOMATIC REPAIR ATTEMPT 1/1")

    print("=" * 70)

    repair_answer, repair_results = propose_repair_patch(
        rag,
        args.repo,
        args.request,
        test_output,
    )

    if repair_answer.strip() == "INSUFFICIENT_CONTEXT":
        print("Repair model reported INSUFFICIENT_CONTEXT.")

        finalize_run(
            repo=repo,
            request=args.request,
            tests_passed=False,
            auto_commit=args.auto_commit,
            rollback_on_fail=args.rollback_on_fail,
            starting_commit=starting_commit,
            original_branch=original_branch,
            agent_branch=agent_branch,
        )

        sys.exit(return_code)

    repair_diff = extract_diff(repair_answer)

    if not repair_diff:
        print("Repair model did not produce a Git diff.")

        print()
        print(repair_answer)

        finalize_run(
            repo=repo,
            request=args.request,
            tests_passed=False,
            auto_commit=args.auto_commit,
            rollback_on_fail=args.rollback_on_fail,
            starting_commit=starting_commit,
            original_branch=original_branch,
            agent_branch=agent_branch,
        )

        sys.exit(return_code)

    repair_patch = save_patch(
        args.repo,
        repair_diff,
        "repair",
        config.paths.patch_dir,
    )

    print()
    print(repair_patch.read_text(encoding="utf-8"))

    print_sources(repair_results)

    print()

    if not check_patch(
        repo,
        repair_patch,
    ):
        print("Repair patch rejected.")

        finalize_run(
            repo=repo,
            request=args.request,
            tests_passed=False,
            auto_commit=args.auto_commit,
            rollback_on_fail=args.rollback_on_fail,
            starting_commit=starting_commit,
            original_branch=original_branch,
            agent_branch=agent_branch,
        )

        sys.exit(return_code)

    if not apply_patch(
        repo,
        repair_patch,
    ):
        finalize_run(
            repo=repo,
            request=args.request,
            tests_passed=False,
            auto_commit=args.auto_commit,
            rollback_on_fail=args.rollback_on_fail,
            starting_commit=starting_commit,
            original_branch=original_branch,
            agent_branch=agent_branch,
        )

        sys.exit(return_code)

    if args.validate:
        print()
        print("=" * 70)

        print("STRUCTURAL VALIDATION AFTER REPAIR")

        print("=" * 70)

        structure_ok, structure_report = validate_python_structure(repo)

        print(structure_report)

        if not structure_ok:
            print()
            print("Repair structural validation: FAIL")

            finalize_run(
                repo=repo,
                request=args.request,
                tests_passed=False,
                auto_commit=args.auto_commit,
                rollback_on_fail=args.rollback_on_fail,
                starting_commit=starting_commit,
                original_branch=original_branch,
                agent_branch=agent_branch,
            )

            sys.exit(return_code)

        print("Repair structural validation: PASS")

    # --------------------------------------------------------
    # Refresh index after repair.
    # --------------------------------------------------------

    rag = reindex_repository(config)

    # --------------------------------------------------------
    # Run tests once more.
    # --------------------------------------------------------

    second_code, second_output = detect_and_run_tests(repo)

    if second_code == 0:
        print()
        print("Repair tests: PASS")

        print()
        print("Final Git diff:")

        print(git_diff(repo))

        finalize_run(
            repo=repo,
            request=args.request,
            tests_passed=True,
            auto_commit=args.auto_commit,
            rollback_on_fail=args.rollback_on_fail,
            starting_commit=starting_commit,
            original_branch=original_branch,
            agent_branch=agent_branch,
        )

        return

    print()
    print("Repair tests: FAIL")

    print()
    print(second_output)

    print()
    print("Stopping after one automatic repair attempt.")

    finalize_run(
        repo=repo,
        request=args.request,
        tests_passed=False,
        auto_commit=args.auto_commit,
        rollback_on_fail=args.rollback_on_fail,
        starting_commit=starting_commit,
        original_branch=original_branch,
        agent_branch=agent_branch,
    )

    sys.exit(second_code if second_code is not None else 1)


if __name__ == "__main__":
    main()
