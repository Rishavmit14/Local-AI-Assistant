"""Parsed allowlist command execution without shell interpretation."""

from __future__ import annotations

import os
import shlex
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .errors import CommandPolicyError

SHELL_TOKENS = {"|", "||", "&&", ";", ">", ">>", "<", "<<", "$(", "`"}
ALLOWED_PREFIXES = (
    ("python", "-m", "pytest"),
    ("python3", "-m", "pytest"),
    ("pytest",),
    ("ruff",),
    ("mypy",),
    ("pyright",),
    ("cargo", "check"),
    ("cargo", "test"),
    ("cargo", "clippy"),
    ("forge", "build"),
    ("forge", "test"),
    ("npm", "test"),
    ("pnpm", "test"),
    ("yarn", "test"),
    ("tsc", "--noEmit"),
    ("eslint",),
    ("git", "status"),
    ("git", "diff"),
    ("git", "show"),
    ("git", "log"),
    ("git", "branch", "--show-current"),
    ("rg",),
    ("grep",),
    ("find",),
)
BLOCKED_EXECUTABLES = {
    "sudo",
    "rm",
    "chmod",
    "chown",
    "curl",
    "wget",
    "apt",
    "apt-get",
    "dnf",
    "yum",
    "pip",
    "systemctl",
}


@dataclass(frozen=True, slots=True)
class CommandResult:
    command: tuple[str, ...]
    return_code: int
    stdout: str
    stderr: str
    timed_out: bool


def parse_allowed_command(command: str | list[str]) -> tuple[str, ...]:
    if isinstance(command, str):
        if any(token in command for token in ("$(", "`", "${", "\n", "\r")):
            raise CommandPolicyError("Command substitution/environment injection is blocked")
        try:
            parts = tuple(shlex.split(command, posix=True))
        except ValueError as exc:
            raise CommandPolicyError(f"Invalid command syntax: {exc}") from exc
    else:
        parts = tuple(str(item) for item in command)
    if not parts:
        raise CommandPolicyError("Empty command")
    if parts[0] in BLOCKED_EXECUTABLES or "/" in parts[0]:
        raise CommandPolicyError(f"Executable is blocked: {parts[0]}")
    if any(
        part in SHELL_TOKENS or any(token in part for token in ("$(", "`", "${", ">", "<"))
        for part in parts
    ):
        raise CommandPolicyError("Shell composition, redirection, and substitution are blocked")
    if parts[:2] == ("git", "push") or "--force" in parts or "-f" in parts and parts[0] == "git":
        raise CommandPolicyError("Git mutation/force operation is blocked")
    if not any(parts[: len(prefix)] == prefix for prefix in ALLOWED_PREFIXES):
        raise CommandPolicyError("Command family is not allowlisted")
    if any(
        Path(part).is_absolute() or ".." in Path(part).parts
        for part in parts[1:]
        if not part.startswith("-")
    ):
        raise CommandPolicyError("Command arguments must remain repository-relative")
    if parts[0] == "find" and any(
        part in {"-exec", "-execdir", "-delete", "-ok", "-okdir"} for part in parts
    ):
        raise CommandPolicyError("Mutating/executing find actions are blocked")
    if parts[0] == "rg" and any(part.startswith("--pre") for part in parts):
        raise CommandPolicyError("rg preprocessors are blocked")
    return parts


def run_allowed_command(
    command: str | list[str], repository: Path, timeout: int, output_limit: int = 20_000
) -> CommandResult:
    parts = parse_allowed_command(command)
    process = subprocess.Popen(
        parts,
        cwd=repository,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
        env={"PATH": os.environ.get("PATH", ""), "PYTHONPATH": os.environ.get("PYTHONPATH", "")},
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        timed_out = False
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            stdout, stderr = process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
        timed_out = True
    return CommandResult(
        parts,
        process.returncode if process.returncode is not None else -1,
        stdout[-output_limit:],
        stderr[-output_limit:],
        timed_out,
    )
