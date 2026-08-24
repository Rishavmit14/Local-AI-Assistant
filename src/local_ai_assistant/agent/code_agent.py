from __future__ import annotations

import argparse
import subprocess
import sys
import time
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

_DEFAULT_CONFIG = get_config()
REPO_ROOT = _DEFAULT_CONFIG.paths.code_repo_dir
PATCH_DIR = _DEFAULT_CONFIG.paths.patch_dir
logger = get_logger(__name__)

PATCH_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


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
) -> str:
    """
    Commit successful autonomous changes.
    """

    run_command(
        ["git", "add", "-A"],
        repo,
    )

    message = request.strip()

    if len(message) > 65:
        message = message[:62].rstrip() + "..."

    if not message:
        message = "Apply autonomous code change"

    result = run_command(
        [
            "git",
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

        commit_hash = commit_agent_changes(
            repo,
            request,
        )

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
    elif args.auto_commit or args.auto_merge or args.keep_failed_branch:
        parser.error("commit, merge, and failed-branch options require --apply")

    if args.auto_merge and not (args.approve_merge and args.auto_commit):
        parser.error("--auto-merge requires --approve-merge and --auto-commit")


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
    plan_path = planner.persist(artifact, args.plan_output)
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
            ).run(dry_run=True)
            print(
                f"Tool-loop {'human review' if args.human_review else 'dry run'}: {result.status}; nothing modified."
            )
            return
        original_branch, starting_commit, agent_branch = create_agent_branch(repo, args.request)
        context = ToolContext(
            repo,
            artifact,
            scope_guard_from_plan(artifact.plan),
            rag.symbol_index,
            args.approve_risk,
        )
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
            persist_report(
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
        structure_ok, structure_output = validate_python_structure(repo)
        test_code, _ = detect_and_run_tests(repo) if args.test else (0, "Tests skipped")
        success = result.status == "complete" and structure_ok and test_code in {0, None}
        transaction = finalize_run(
            repo=repo,
            request=args.request,
            tests_passed=success,
            auto_commit=args.auto_commit,
            rollback_on_fail=args.rollback_on_fail,
            starting_commit=starting_commit,
            original_branch=original_branch,
            agent_branch=agent_branch,
        )
        final_report = ExecutionReport(
            report.schema_version,
            report.task_id,
            report.plan_hash,
            report.repository,
            report.starting_commit,
            transaction.outcome,
            report.plan_versions,
            report.events,
            final_diff=report.final_diff,
            final_commit=transaction.resulting_commit,
            repairs=report.repairs,
            replans=report.replans,
        )
        persist_report(
            final_report,
            config.paths.code_index_dir / "executions" / f"{artifact.plan.task_id}.json",
        )
        if not success:
            print(structure_output)
            sys.exit(1)
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
