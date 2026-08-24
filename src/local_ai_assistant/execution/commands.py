"""Parsed allowlist command execution without shell interpretation."""

from __future__ import annotations

import os
import shlex
import shutil
import signal
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

from .errors import CommandPolicyError

SHELL_TOKENS = {"|", "||", "&&", ";", ">", ">>", "<", "<<", "$(", "`"}
ALLOWED_PREFIXES = (
    ("python", "-m", "pytest"),
    ("python3", "-m", "pytest"),
    ("pytest",),
    ("ruff", "check"),
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
BLOCKED_OPTIONS = {
    "--config",
    "--exec",
    "--ext-diff",
    "--ffi",
    "--fork-url",
    "--fix",
    "--fix-only",
    "--follow",
    "--install-types",
    "--junitxml",
    "--output",
    "--output-file",
    "--pyargs",
    "--python-executable",
    "--script-shell",
    "--basetemp",
    "--createstub",
    "--textconv",
    "--use-program-main",
    "--write",
    "-L",
    "-o",
    "-p",
}
NODE_TEST_ARGUMENTS = {"--runInBand", "--watch=false", "--watchAll=false", "--coverage"}


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
        part in BLOCKED_OPTIONS
        or any(part.startswith(option + "=") for option in BLOCKED_OPTIONS if option.startswith("--"))
        for part in parts[1:]
    ):
        raise CommandPolicyError("Command option can execute code, access external state, or write output")
    if parts[0] == "git" and any(
        part in {"--no-index", "--src-prefix", "--dst-prefix"}
        or part.startswith(("--output=", "--src-prefix=", "--dst-prefix="))
        for part in parts[2:]
    ):
        raise CommandPolicyError("Dangerous Git inspection arguments are blocked")
    if parts[0] in {"npm", "pnpm", "yarn"}:
        extra = parts[2:]
        if extra[:1] == ("--",):
            extra = extra[1:]
        if any(part not in NODE_TEST_ARGUMENTS for part in extra):
            raise CommandPolicyError("Node test arguments are restricted")
    if any(
        Path(part).is_absolute() or ".." in Path(part).parts
        for part in parts[1:]
        if not part.startswith("-")
    ):
        raise CommandPolicyError("Command arguments must remain repository-relative")
    if parts[0] == "find" and any(
        part in {"-exec", "-execdir", "-delete", "-ok", "-okdir", "-follow", "-H", "-L"}
        for part in parts
    ):
        raise CommandPolicyError("Mutating/executing find actions are blocked")
    if parts[0] == "rg" and any(part.startswith("--pre") for part in parts):
        raise CommandPolicyError("rg preprocessors are blocked")
    if parts[0] in {"rg", "grep"} and any(
        part == "-f" or part.startswith("-f") and len(part) > 2 for part in parts[1:]
    ):
        raise CommandPolicyError("External pattern files are blocked")
    if parts[0] == "grep" and any(
        part == "-R"
        or part == "--dereference-recursive"
        or part.startswith("-") and "R" in part[1:]
        for part in parts[1:]
    ):
        raise CommandPolicyError("Recursive symlink following is blocked")
    if parts[0] == "tsc" and any(
        part in {"--emitDeclarationOnly", "--out", "--outDir"}
        or part.startswith(("--out=", "--outDir="))
        for part in parts[2:]
    ):
        raise CommandPolicyError("TypeScript output options are blocked")
    return parts


def run_allowed_command(
    command: str | list[str], repository: Path, timeout: int, output_limit: int = 20_000
) -> CommandResult:
    parts = parse_allowed_command(command)
    repository = repository.resolve()
    executable = shutil.which(parts[0])
    if executable is None:
        raise CommandPolicyError(f"Allowlisted executable was not found: {parts[0]}")
    executable_path = Path(executable).resolve()
    if executable_path == repository or repository in executable_path.parents:
        raise CommandPolicyError("Repository-local executable wrappers are blocked")
    for argument in parts[1:]:
        candidate_value = argument.split("=", 1)[1] if "=" in argument else argument
        if candidate_value.startswith("-"):
            continue
        candidate = repository / candidate_value
        if candidate.exists() or candidate.is_symlink():
            resolved = candidate.resolve()
            if resolved != repository and repository not in resolved.parents:
                raise CommandPolicyError(
                    f"Command argument resolves outside repository: {candidate_value}"
                )
    process = subprocess.Popen(
        (str(executable_path), *parts[1:]),
        cwd=repository,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
        env={"PATH": os.environ.get("PATH", ""), "PYTHONPATH": os.environ.get("PYTHONPATH", "")},
    )
    stdout_buffer = bytearray()
    stderr_buffer = bytearray()
    readers = (
        threading.Thread(
            target=_read_bounded,
            args=(process.stdout, stdout_buffer, output_limit),
            daemon=True,
        ),
        threading.Thread(
            target=_read_bounded,
            args=(process.stderr, stderr_buffer, output_limit),
            daemon=True,
        ),
    )
    for reader in readers:
        reader.start()
    try:
        process.wait(timeout=timeout)
        timed_out = False
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        timed_out = True
    for reader in readers:
        reader.join(timeout=2)
    return CommandResult(
        parts,
        process.returncode if process.returncode is not None else -1,
        stdout_buffer.decode(errors="replace"),
        stderr_buffer.decode(errors="replace"),
        timed_out,
    )


def _read_bounded(stream, output: bytearray, limit: int) -> None:
    if stream is None:
        return
    try:
        while chunk := stream.read(4096):
            output.extend(chunk)
            if len(output) > limit:
                del output[: len(output) - limit]
    finally:
        stream.close()
