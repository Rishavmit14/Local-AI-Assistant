"""Typed Linux-local sandbox backends with fail-closed capability policy."""

from __future__ import annotations

import os
import resource
import shutil
import signal
import subprocess
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from .errors import IsolationError, SandboxUnavailableError
from .models import (
    CapabilityState,
    NetworkPolicy,
    ResourcePolicy,
    SandboxCapabilities,
    SandboxResult,
)

SAFE_ENVIRONMENT = {
    "LANG",
    "LANGUAGE",
    "LC_ALL",
    "LC_CTYPE",
    "TERM",
    "TZ",
}
TRUSTED_PATH = "/usr/local/bin:/usr/bin:/bin"


def isolated_environment(
    home: Path,
    temporary: Path,
    parent: Mapping[str, str] | None = None,
    approved: Mapping[str, str] | None = None,
) -> dict[str, str]:
    source = os.environ if parent is None else parent
    environment = {
        key: value for key, value in source.items() if key in SAFE_ENVIRONMENT
    }
    environment.update(
        {
            "PATH": TRUSTED_PATH,
            "HOME": str(home),
            "TMPDIR": str(temporary),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_DATA_HOME": str(home / ".local" / "share"),
            "XDG_STATE_HOME": str(home / ".local" / "state"),
            "XDG_CACHE_HOME": str(home / ".cache"),
            "PIP_CACHE_DIR": str(home / ".cache" / "pip"),
            "PIP_CONFIG_FILE": "/dev/null",
            "npm_config_cache": str(home / ".cache" / "npm"),
            "NPM_CONFIG_USERCONFIG": str(home / ".npmrc"),
            "CARGO_HOME": str(home / ".cargo"),
            "RUSTUP_HOME": str(home / ".rustup"),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
        }
    )
    if approved:
        for key, value in approved.items():
            if not key or not key.replace("_", "").isalnum() or not key[0].isalpha():
                raise IsolationError(f"Invalid approved environment name: {key!r}")
            environment[key] = value
    return environment


class SandboxBackend(ABC):
    @abstractmethod
    def capabilities(self) -> SandboxCapabilities: ...

    @abstractmethod
    def run(
        self,
        command: Sequence[str],
        worktree: Path,
        task_root: Path,
        *,
        resources: ResourcePolicy,
        network: NetworkPolicy,
        approved_environment: Mapping[str, str] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> SandboxResult: ...


class NativeProcessSandbox(SandboxBackend):
    """Process/resource isolation; intentionally no filesystem/network claims."""

    def capabilities(self) -> SandboxCapabilities:
        return SandboxCapabilities(
            "native",
            CapabilityState.SUPPORTED,
            CapabilityState.PARTIAL,
            CapabilityState.UNAVAILABLE,
            CapabilityState.SUPPORTED,
            CapabilityState.UNAVAILABLE,
            _cgroup_capability(),
            ("rlimits and process groups available", "no mount or network namespace"),
        )

    def run(
        self,
        command: Sequence[str],
        worktree: Path,
        task_root: Path,
        *,
        resources: ResourcePolicy,
        network: NetworkPolicy,
        approved_environment: Mapping[str, str] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> SandboxResult:
        if network is not NetworkPolicy.ALLOWED:
            raise SandboxUnavailableError(
                "Native backend cannot enforce requested network isolation"
            )
        return _run_process(
            tuple(command),
            worktree,
            task_root,
            resources,
            "native",
            approved_environment,
            cancel_check,
        )


class BubblewrapSandbox(SandboxBackend):
    def __init__(self) -> None:
        self.executable = shutil.which("bwrap")
        self._usable = _bubblewrap_usable(self.executable)

    def capabilities(self) -> SandboxCapabilities:
        state = CapabilityState.SUPPORTED if self._usable else CapabilityState.UNAVAILABLE
        return SandboxCapabilities(
            "bubblewrap",
            state,
            state,
            state,
            CapabilityState.SUPPORTED,
            state,
            _cgroup_capability(),
            (() if self._usable else ("bubblewrap/user namespace probe failed",)),
        )

    def run(
        self,
        command: Sequence[str],
        worktree: Path,
        task_root: Path,
        *,
        resources: ResourcePolicy,
        network: NetworkPolicy,
        approved_environment: Mapping[str, str] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> SandboxResult:
        if not self._usable or not self.executable:
            raise SandboxUnavailableError("Bubblewrap is unavailable on this host")
        worktree = worktree.resolve(strict=True)
        task_root = task_root.resolve()
        (task_root / "home").mkdir(parents=True, exist_ok=True, mode=0o700)
        (task_root / "tmp").mkdir(parents=True, exist_ok=True, mode=0o700)
        prefix = [
            self.executable,
            "--die-with-parent",
            "--new-session",
            "--unshare-pid",
            "--unshare-ipc",
            "--unshare-uts",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--ro-bind",
            "/usr",
            "/usr",
            "--ro-bind",
            "/bin",
            "/bin",
        ]
        for system_path in ("/lib", "/lib64", "/etc/ld.so.cache"):
            if Path(system_path).exists():
                prefix.extend(("--ro-bind", system_path, system_path))
        prefix.extend(
            (
                "--bind", str(worktree), str(worktree),
                "--bind", str(task_root), str(task_root),
                "--chdir", str(worktree),
            )
        )
        if network is NetworkPolicy.DENY:
            prefix.append("--unshare-net")
        elif network is NetworkPolicy.LOOPBACK_ONLY:
            raise SandboxUnavailableError(
                "Loopback-only setup is not supported without a trusted namespace helper"
            )
        return _run_process(
            tuple(prefix) + tuple(command),
            worktree,
            task_root,
            resources,
            "bubblewrap",
            approved_environment,
            cancel_check,
        )


def select_backend(name: str = "auto") -> SandboxBackend:
    normalized = name.strip().lower()
    if normalized not in {"auto", "bubblewrap", "native"}:
        raise SandboxUnavailableError(f"Unknown sandbox backend: {name}")
    bubblewrap = BubblewrapSandbox()
    if normalized == "bubblewrap" or (
        normalized == "auto"
        and bubblewrap.capabilities().process is CapabilityState.SUPPORTED
    ):
        if bubblewrap.capabilities().process is CapabilityState.UNAVAILABLE:
            raise SandboxUnavailableError("Required bubblewrap backend is unavailable")
        return bubblewrap
    return NativeProcessSandbox()


def _run_process(
    command: tuple[str, ...],
    worktree: Path,
    task_root: Path,
    resources: ResourcePolicy,
    backend: str,
    approved_environment: Mapping[str, str] | None,
    cancel_check: Callable[[], bool] | None,
) -> SandboxResult:
    worktree = worktree.resolve(strict=True)
    task_root.mkdir(parents=True, exist_ok=True)
    home = task_root / "home"
    temporary = task_root / "tmp"
    home.mkdir(mode=0o700, exist_ok=True)
    temporary.mkdir(mode=0o700, exist_ok=True)
    environment = isolated_environment(home, temporary, approved=approved_environment)
    started = time.monotonic()
    process = subprocess.Popen(
        command,
        cwd=worktree,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
        env=environment,
        preexec_fn=lambda: _set_limits(resources),
        close_fds=True,
    )
    stdout = bytearray()
    stderr = bytearray()
    truncated = [False, False]
    readers = (
        threading.Thread(
            target=_read_bounded,
            args=(process.stdout, stdout, resources.max_output_bytes, truncated, 0),
            daemon=True,
        ),
        threading.Thread(
            target=_read_bounded,
            args=(process.stderr, stderr, resources.max_output_bytes, truncated, 1),
            daemon=True,
        ),
    )
    for reader in readers:
        reader.start()
    timed_out = cancelled = False
    deadline = started + resources.wall_seconds
    while process.poll() is None:
        if cancel_check and cancel_check():
            cancelled = True
            _terminate_group(process)
            break
        if time.monotonic() >= deadline:
            timed_out = True
            _terminate_group(process)
            break
        time.sleep(0.02)
    for reader in readers:
        reader.join(timeout=2)
    marker = b"\n[OUTPUT TRUNCATED]\n"
    if truncated[0]:
        stdout.extend(marker)
    if truncated[1]:
        stderr.extend(marker)
    return SandboxResult(
        command,
        process.returncode if process.returncode is not None else -1,
        stdout.decode(errors="replace"),
        stderr.decode(errors="replace"),
        timed_out,
        cancelled,
        any(truncated),
        round(time.monotonic() - started, 6),
        backend,
    )


def _set_limits(policy: ResourcePolicy) -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (policy.cpu_seconds, policy.cpu_seconds))
    resource.setrlimit(resource.RLIMIT_NPROC, (policy.max_processes, policy.max_processes))
    resource.setrlimit(resource.RLIMIT_NOFILE, (policy.max_open_files, policy.max_open_files))
    resource.setrlimit(resource.RLIMIT_FSIZE, (policy.max_file_bytes, policy.max_file_bytes))
    if hasattr(resource, "RLIMIT_AS"):
        resource.setrlimit(resource.RLIMIT_AS, (policy.memory_bytes, policy.memory_bytes))


def _terminate_group(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=2)


def _read_bounded(stream, output: bytearray, limit: int, flags: list[bool], index: int) -> None:
    if stream is None:
        return
    try:
        while chunk := stream.read(4096):
            output.extend(chunk)
            if len(output) > limit:
                flags[index] = True
                del output[: len(output) - limit]
    finally:
        stream.close()


def _bubblewrap_usable(executable: str | None) -> bool:
    if not executable:
        return False
    try:
        result = subprocess.run(
            [executable, "--ro-bind", "/usr", "/usr", "--proc", "/proc", "/bin/true"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _cgroup_capability() -> CapabilityState:
    path = Path("/sys/fs/cgroup/cgroup.controllers")
    return CapabilityState.PARTIAL if path.is_file() else CapabilityState.UNAVAILABLE
