"""Non-interactive Git execution safeguards for isolation-owned operations."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .errors import IsolationError

_FILTER_ATTRIBUTE = re.compile(r"(?:^|\s)(?:-?filter(?:=\S+)?)(?:\s|$)")


def safe_git_environment(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Return a minimal Git environment without inherited config or prompt hooks."""
    environment = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": "/nonexistent",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ASKPASS": "/bin/false",
        "GIT_PAGER": "cat",
        "PAGER": "cat",
        "GIT_EDITOR": "/bin/true",
        "GIT_SEQUENCE_EDITOR": "/bin/true",
    }
    if extra:
        environment.update(extra)
    return environment


def git_argv(*arguments: str) -> list[str]:
    return [
        "git",
        "-c", "core.hooksPath=/dev/null",
        "-c", "core.attributesFile=/dev/null",
        "-c", "commit.gpgSign=false",
        *arguments,
    ]


def ensure_no_git_filters(repository: Path, revision: str | None = None) -> None:
    """Reject clean/smudge/LFS attributes before Git may execute their drivers.

    Git worktrees share administration data.  Friday deliberately does not execute
    repository-defined filters during its isolation-owned checkout/stage/commit path.
    """
    repository = repository.resolve(strict=True)
    revision = revision or "HEAD"
    listed = subprocess.run(
        git_argv("ls-tree", "-r", "--name-only", revision),
        cwd=repository,
        env=safe_git_environment(),
        text=True,
        capture_output=True,
    )
    if listed.returncode:
        raise IsolationError("Could not inspect Git attributes safely")
    attribute_paths = [
        line for line in listed.stdout.splitlines()
        if Path(line).name == ".gitattributes"
    ]
    for relative in attribute_paths:
        shown = subprocess.run(
            git_argv("show", f"{revision}:{relative}"),
            cwd=repository,
            env=safe_git_environment(),
            text=True,
            capture_output=True,
        )
        if shown.returncode:
            raise IsolationError("Could not inspect Git attributes safely")
        if any(
            _FILTER_ATTRIBUTE.search(line.split("#", 1)[0])
            for line in shown.stdout.splitlines()
        ):
            raise IsolationError(
                "Repository-defined Git filters/LFS are unsupported for isolated automation"
            )
    # Recheck the live worktree immediately before staging.  A candidate patch may
    # add or modify attributes after the approved starting revision.
    for attributes in repository.rglob(".gitattributes"):
        resolved = attributes.resolve(strict=True)
        if resolved != repository and repository not in resolved.parents:
            raise IsolationError("Git attributes path escapes repository")
        if any(
            _FILTER_ATTRIBUTE.search(line.split("#", 1)[0])
            for line in resolved.read_text(errors="replace").splitlines()
        ):
            raise IsolationError(
                "Worktree Git filters/LFS are unsupported for isolated automation"
            )
    common = subprocess.run(
        git_argv("rev-parse", "--path-format=absolute", "--git-common-dir"),
        cwd=repository,
        env=safe_git_environment(),
        text=True,
        capture_output=True,
    )
    if common.returncode:
        raise IsolationError("Could not inspect shared Git metadata safely")
    info_attributes = Path(common.stdout.strip()).resolve() / "info" / "attributes"
    if info_attributes.is_file() and any(
        _FILTER_ATTRIBUTE.search(line.split("#", 1)[0])
        for line in info_attributes.read_text(errors="replace").splitlines()
    ):
        raise IsolationError("Shared Git filter attributes are unsupported")
