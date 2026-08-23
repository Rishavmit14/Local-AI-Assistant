from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

from local_ai_assistant.code_index import CodeRAG
from local_ai_assistant.common.paths import CODE_REPO_DIR as REPO_ROOT
from local_ai_assistant.common.paths import PATCH_DIR

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
) -> subprocess.CompletedProcess:

    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
    )


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
        raise RuntimeError(
            f"{repo} is not a Git repository."
        )


def get_repo(
    name: str,
) -> Path:

    repo = REPO_ROOT / name

    if not repo.exists():
        raise RuntimeError(
            f"Repository not found: {repo}"
        )

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
        raise RuntimeError(
            "Repository is not clean. "
            "Commit or discard existing changes first."
        )

    original_branch = git_current_branch(repo)

    if original_branch.startswith("agent/"):
        raise RuntimeError(
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
        raise RuntimeError(
            "Could not create agent branch:\n"
            + result.stdout
            + result.stderr
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
) -> None:
    """
    Restore the repository to the exact commit where the
    autonomous run started.

    If an isolated agent branch was created, return to the
    original branch and remove the failed temporary branch.
    """

    run_command(
        [
            "git",
            "reset",
            "--hard",
            starting_commit,
        ],
        repo,
    )

    run_command(
        [
            "git",
            "clean",
            "-fd",
        ],
        repo,
    )

    if (
        original_branch
        and agent_branch
        and original_branch != agent_branch
    ):

        switch_result = run_command(
            [
                "git",
                "switch",
                original_branch,
            ],
            repo,
        )

        if switch_result.returncode == 0:

            run_command(
                [
                    "git",
                    "branch",
                    "-D",
                    agent_branch,
                ],
                repo,
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
        raise RuntimeError(
            "Automatic commit failed:\n"
            + result.stdout
            + result.stderr
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
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip().endswith(".py")
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

            errors.append(
                f"{relative_path}: "
                f"syntax error at line "
                f"{exc.lineno}: {exc.msg}"
            )

            continue

        except Exception as exc:

            errors.append(
                f"{relative_path}: "
                f"could not validate: {exc}"
            )

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
                ).append(
                    node.lineno
                )

            elif isinstance(
                node,
                ast.ClassDef,
            ):
                classes.setdefault(
                    node.name,
                    [],
                ).append(
                    node.lineno
                )

        for name, lines in functions.items():

            if len(lines) > 1:
                errors.append(
                    f"{relative_path}: duplicate "
                    f"top-level function "
                    f"{name!r} at lines {lines}"
                )

        for name, lines in classes.items():

            if len(lines) > 1:
                errors.append(
                    f"{relative_path}: duplicate "
                    f"top-level class "
                    f"{name!r} at lines {lines}"
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
) -> None:
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
            return

        if git_is_clean(repo):
            print(
                "No repository changes remain; "
                "nothing to commit."
            )
            return

        commit_hash = commit_agent_changes(
            repo,
            request,
        )

        print()
        print(
            "=" * 70
        )

        print(
            "AUTOMATIC COMMIT"
        )

        print(
            "=" * 70
        )

        print(
            f"Committed successful changes: "
            f"{commit_hash[:12]}"
        )

        return

    if (
        rollback_on_fail
        and starting_commit
    ):

        print()
        print(
            "=" * 70
        )

        print(
            "ROLLBACK"
        )

        print(
            "=" * 70
        )

        rollback_agent_changes(
            repo,
            starting_commit,
            original_branch,
            agent_branch,
        )

        print(
            "Final validation/tests failed. "
            "Agent changes were rolled back."
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

    prefix_a = (
        f"a/{repo_name}/"
    )

    prefix_b = (
        f"b/{repo_name}/"
    )

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
) -> Path:

    safe_name = repo_name.replace(
        "/",
        "_",
    )

    diff = normalize_patch(
        repo_name,
        diff,
    )

    patch_file = (
        PATCH_DIR
        / f"{safe_name}_{suffix}.patch"
    )

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

        print(
            "Patch validation: PASS"
        )

        return True

    print(
        "Patch validation: FAIL"
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

        print(
            "Patch application failed."
        )

        if result.stderr:
            print(result.stderr)

        return False

    print(
        "Patch applied successfully."
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

    print()
    print(
        "Detecting test environment..."
    )

    # --------------------------------------------------------
    # Python
    # --------------------------------------------------------

    if (
        (repo / "tests").exists()
        or (repo / "pytest.ini").exists()
        or (repo / "pyproject.toml").exists()
    ):

        print(
            "Running pytest..."
        )

        result = run_command(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
            ],
            repo,
        )

        output = (
            result.stdout
            + "\n"
            + result.stderr
        ).strip()

        print(output)

        return (
            result.returncode,
            output,
        )

    # --------------------------------------------------------
    # Rust
    # --------------------------------------------------------

    if (
        repo
        / "Cargo.toml"
    ).exists():

        print(
            "Running cargo test..."
        )

        result = run_command(
            [
                "cargo",
                "test",
            ],
            repo,
        )

        output = (
            result.stdout
            + "\n"
            + result.stderr
        ).strip()

        print(output)

        return (
            result.returncode,
            output,
        )

    # --------------------------------------------------------
    # Node / JS / TS
    # --------------------------------------------------------

    if (
        repo
        / "package.json"
    ).exists():

        print(
            "Running npm test..."
        )

        result = run_command(
            [
                "npm",
                "test",
                "--",
                "--runInBand",
            ],
            repo,
        )

        output = (
            result.stdout
            + "\n"
            + result.stderr
        ).strip()

        print(output)

        return (
            result.returncode,
            output,
        )

    print(
        "No recognized test environment found."
    )

    return (
        None,
        "No tests detected.",
    )


# ============================================================
# INDEX REFRESH
# ============================================================

def reindex_repository():
    print()
    print(
        "Refreshing repository index..."
    )

    rag = CodeRAG()

    rag.reindex()

    print(
        "Repository index refreshed."
    )

    return rag


# ============================================================
# INITIAL PATCH GENERATION
# ============================================================

def propose_patch(
    rag: CodeRAG,
    repo_name: str,
    request: str,
):

    results = rag.retrieve(
        request
    )

    context = rag.build_context(
        results
    )

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
            "You are a senior software "
            "engineer producing minimal "
            "Git-compatible patches."
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

    query = (
        original_request
        + "\n\n"
        + test_output
    )

    results = rag.retrieve(
        query
    )

    context = rag.build_context(
        results
    )

    current_diff = git_diff(
        REPO_ROOT / repo_name
    )

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
    print(
        "Retrieved repository context:"
    )

    for result in results:

        print(
            f"  {result['source']} "
            f"lines "
            f"{result['line_start']}-"
            f"{result['line_end']}"
        )


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Local Qwen repository coding agent"
        )
    )

    parser.add_argument(
        "repo",
        help=(
            "Repository directory name "
            "inside code-assistant/repos"
        ),
    )

    parser.add_argument(
        "request",
        help="Requested code change",
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Apply the proposed patch "
            "after Git validation"
        ),
    )

    parser.add_argument(
        "--test",
        action="store_true",
        help=(
            "Run tests after applying "
            "the patch"
        ),
    )

    parser.add_argument(
        "--repair",
        action="store_true",
        help=(
            "Allow one automatic repair "
            "attempt if tests fail"
        ),
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


    args = parser.parse_args()

    repo = get_repo(
        args.repo
    )

    # --------------------------------------------------------
    # Protect existing unrelated changes.
    # --------------------------------------------------------

    existing_changes = (
        git_status(repo)
    )

    if existing_changes:

        print()
        print(
            "Repository currently has "
            "uncommitted changes:"
        )

        print()
        print(
            existing_changes
        )

        print()

        if args.apply:

            print(
                "Automatic application is blocked "
                "when the repository is already dirty."
            )

            print(
                "Commit or stash existing changes first."
            )

            sys.exit(1)

    # --------------------------------------------------------
    # Optional isolated Git branch for autonomous edits.
    # --------------------------------------------------------

    original_branch = None
    starting_commit = None
    agent_branch = None

    if args.apply and args.branch:

        (
            original_branch,
            starting_commit,
            agent_branch,
        ) = create_agent_branch(
            repo,
            args.request,
        )

        print()
        print(
            "=" * 70
        )

        print(
            "GIT SAFETY"
        )

        print(
            "=" * 70
        )

        print(
            f"Original branch: {original_branch}"
        )

        print(
            f"Agent branch:    {agent_branch}"
        )

        print(
            f"Starting commit: {starting_commit}"
        )

    # --------------------------------------------------------
    # Load repository index.
    # --------------------------------------------------------

    print(
        "Loading repository index..."
    )

    rag = CodeRAG()

    print(
        "Refreshing repository index before patch generation..."
    )

    rag.reindex()

    # --------------------------------------------------------
    # Generate patch.
    # --------------------------------------------------------

    print()
    print(
        "Generating proposed patch..."
    )

    answer, results = propose_patch(
        rag,
        args.repo,
        args.request,
    )

    if (
        answer.strip()
        == "INSUFFICIENT_CONTEXT"
    ):

        print(
            "Model reported "
            "INSUFFICIENT_CONTEXT."
        )

        sys.exit(1)

    diff = extract_diff(
        answer
    )

    if not diff:

        print(
            "Model did not produce "
            "a valid Git diff."
        )

        print()
        print(
            answer
        )

        sys.exit(1)

    patch_file = save_patch(
        args.repo,
        diff,
        "proposed",
    )

    print()
    print(
        "=" * 70
    )

    print(
        "PROPOSED PATCH"
    )

    print(
        "=" * 70
    )

    print()
    print(
        patch_file.read_text(
            encoding="utf-8"
        )
    )

    print_sources(
        results
    )

    print()

    if not check_patch(
        repo,
        patch_file,
    ):

        sys.exit(1)

    # --------------------------------------------------------
    # Proposal-only mode.
    # --------------------------------------------------------

    if not args.apply:

        print()
        print(
            "Nothing has been modified."
        )

        print(
            "Rerun with --apply "
            "to apply this patch."
        )

        return

    # --------------------------------------------------------
    # Apply patch.
    # --------------------------------------------------------

    if not apply_patch(
        repo,
        patch_file,
    ):

        sys.exit(1)

    if args.validate:

        print()
        print(
            "=" * 70
        )

        print(
            "STRUCTURAL VALIDATION"
        )

        print(
            "=" * 70
        )

        structure_ok, structure_report = (
            validate_python_structure(
                repo
            )
        )

        print(
            structure_report
        )

        if not structure_ok:

            print()
            print(
                "Structural validation: FAIL"
            )

            if (
                args.rollback_on_fail
                and starting_commit
            ):

                rollback_agent_changes(
                    repo,
                    starting_commit,
                    original_branch,
                    agent_branch,
                )

                print(
                    "Agent changes rolled back."
                )

            sys.exit(1)

        print(
            "Structural validation: PASS"
        )

    print()
    print(
        "=" * 70
    )

    print(
        "CURRENT GIT DIFF"
    )

    print(
        "=" * 70
    )

    print()
    print(
        git_diff(repo)
    )

    # --------------------------------------------------------
    # Re-index immediately after edit.
    # --------------------------------------------------------

    rag = reindex_repository()

    # --------------------------------------------------------
    # No tests requested.
    # --------------------------------------------------------

    if not args.test:

        print()
        print(
            "Patch applied and "
            "repository re-indexed."
        )

        return

    # --------------------------------------------------------
    # Run tests.
    # --------------------------------------------------------

    return_code, test_output = (
        detect_and_run_tests(
            repo
        )
    )

    if return_code is None:

        print()
        print(
            "Patch applied, but no "
            "tests were detected."
        )

        return

    if return_code == 0:

        print()
        print(
            "Tests: PASS"
        )

        print(
            "Coding-agent cycle completed successfully."
        )

        finalize_agent_run(
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
    print(
        "Tests: FAIL"
    )

    if not args.repair:

        print(
            "Automatic repair is disabled."
        )

        print(
            "Rerun with --repair if you want "
            "one repair attempt."
        )

        finalize_agent_run(
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
    print(
        "=" * 70
    )

    print(
        "AUTOMATIC REPAIR ATTEMPT 1/1"
    )

    print(
        "=" * 70
    )

    repair_answer, repair_results = (
        propose_repair_patch(
            rag,
            args.repo,
            args.request,
            test_output,
        )
    )

    if (
        repair_answer.strip()
        == "INSUFFICIENT_CONTEXT"
    ):

        print(
            "Repair model reported "
            "INSUFFICIENT_CONTEXT."
        )

        finalize_agent_run(
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

    repair_diff = extract_diff(
        repair_answer
    )

    if not repair_diff:

        print(
            "Repair model did not "
            "produce a Git diff."
        )

        print()
        print(
            repair_answer
        )

        finalize_agent_run(
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
    )

    print()
    print(
        repair_patch.read_text(
            encoding="utf-8"
        )
    )

    print_sources(
        repair_results
    )

    print()

    if not check_patch(
        repo,
        repair_patch,
    ):

        print(
            "Repair patch rejected."
        )

        finalize_agent_run(
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

        finalize_agent_run(
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
        print(
            "=" * 70
        )

        print(
            "STRUCTURAL VALIDATION AFTER REPAIR"
        )

        print(
            "=" * 70
        )

        structure_ok, structure_report = (
            validate_python_structure(
                repo
            )
        )

        print(
            structure_report
        )

        if not structure_ok:

            print()
            print(
                "Repair structural validation: FAIL"
            )

            if (
                args.rollback_on_fail
                and starting_commit
            ):

                rollback_agent_changes(
                    repo,
                    starting_commit,
                    original_branch,
                    agent_branch,
                )

                print(
                    "Agent changes rolled back."
                )

            sys.exit(return_code)

        print(
            "Repair structural validation: PASS"
        )

    # --------------------------------------------------------
    # Refresh index after repair.
    # --------------------------------------------------------

    rag = reindex_repository()

    # --------------------------------------------------------
    # Run tests once more.
    # --------------------------------------------------------

    second_code, second_output = (
        detect_and_run_tests(
            repo
        )
    )

    if second_code == 0:

        print()
        print(
            "Repair tests: PASS"
        )

        print()
        print(
            "Final Git diff:"
        )

        print(
            git_diff(repo)
        )

        finalize_agent_run(
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
    print(
        "Repair tests: FAIL"
    )

    print()
    print(
        second_output
    )

    print()
    print(
        "Stopping after one "
        "automatic repair attempt."
    )

    finalize_agent_run(
        repo=repo,
        request=args.request,
        tests_passed=False,
        auto_commit=args.auto_commit,
        rollback_on_fail=args.rollback_on_fail,
        starting_commit=starting_commit,
        original_branch=original_branch,
        agent_branch=agent_branch,
    )

    sys.exit(
        second_code
        if second_code is not None
        else 1
    )


if __name__ == "__main__":
    main()
