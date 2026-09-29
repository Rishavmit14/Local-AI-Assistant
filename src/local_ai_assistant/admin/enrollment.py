"""Local hidden-input lifecycle for the systemd host-key credential vault.

This module is for an interactive owner terminal only. It never returns a
credential to the caller or writes plaintext to a file, argv, environment, or
logs. Python and subprocess buffers are cleared on a best-effort basis.
"""

from __future__ import annotations

import getpass
import hmac
import json
import os
import secrets
import subprocess
import sys
import threading
import warnings
from collections.abc import Callable
from pathlib import Path

SUDO = "/usr/bin/sudo"
CREDS = "/usr/bin/systemd-creds"
INSTALL = "/usr/bin/install"
MV = "/usr/bin/mv"
RM = "/usr/bin/rm"
SYSTEMCTL = "/usr/bin/systemctl"
STORE = "/etc/credstore.encrypted/friday-admin-password"
STORE_DIR = "/etc/credstore.encrypted"
POLICY = "/etc/friday-admin/clients.json"
INVALID_MARKER = "/var/lib/friday-admin/credential-invalid"
RUNTIME_DIR = "/run/friday-admin"
UNIT_DIR = "/run/systemd/system"
MAX_SECRET_BYTES = 4096
_ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C"}
_READY = b"\x1eFRIDAY_SUDO_INPUT_READY\x1f"


class EnrollmentError(RuntimeError):
    """A safe, non-secret lifecycle failure."""


class CredentialLifecycle:
    """Owner-terminal enrollment, update, revoke, and safe status operations."""

    def __init__(
        self,
        *,
        sudo_executor: Callable[..., subprocess.CompletedProcess[bytes]] | None = None,
        store: str = STORE,
        store_dir: str = STORE_DIR,
        sudo: str = SUDO,
        creds: str = CREDS,
    ) -> None:
        self.sudo_executor = sudo_executor or _run_sudo_command
        self.store = store
        self.store_dir = store_dir
        self.sudo = sudo
        self.creds = creds

    def enroll_from_terminal(self, *, update: bool = False) -> None:
        label = "new administrator password" if update else "administrator password"
        entered = _hidden_input(f"Friday {label} (hidden): ")
        secret = bytearray(entered.encode("utf-8"))
        entered = ""
        try:
            if not secret or len(secret) > MAX_SECRET_BYTES or any(
                value in secret for value in (0, 10, 13)
            ):
                raise EnrollmentError("credential format is unsupported")
            self._enroll(secret, update=update)
        finally:
            secret[:] = b"\x00" * len(secret)

    def revoke_from_terminal(self) -> None:
        entered = _hidden_input("Friday administrator password to authorize revoke (hidden): ")
        secret = bytearray(entered.encode("utf-8"))
        entered = ""
        try:
            result = self._root([RM, "-f", "--", self.store], secret=secret, operation="remove encrypted credential")
            if result.returncode:
                raise EnrollmentError("credential revoke failed")
            self._remove_candidate_runtime(secret)
        finally:
            secret[:] = b"\x00" * len(secret)

    def _enroll(self, secret: bytearray, *, update: bool = False) -> None:
        exists = self._root(
            ["/usr/bin/test", "-e", self.store], secret=secret, check=False,
            operation="check encrypted credential state",
        )
        if exists.returncode not in (0, 1):
            raise EnrollmentError("credential store state could not be checked")
        if exists.returncode == 0 and not update:
            raise EnrollmentError("a credential is already enrolled; use update-credential")
        suffix = secrets.token_hex(12)
        temporary = f"{self.store}.new-{suffix}"
        try:
            encrypted = self._root(
                [
                    self.creds,
                    "--with-key=host",
                    "--name=friday-admin-password",
                    "encrypt",
                    "-",
                    "-",
                ],
                input=bytes(secret), secret=secret,
                operation="encrypt credential with host key",
            )
            if encrypted.returncode or not encrypted.stdout or len(encrypted.stdout) > 16 * 1024:
                raise EnrollmentError("credential encryption failed")

            directory = self._root(
                [INSTALL, "-d", "-o", "root", "-g", "root", "-m", "0700", "--", self.store_dir],
                secret=secret,
                operation="prepare encrypted credential directory",
            )
            if directory.returncode:
                raise EnrollmentError("credential storage is unavailable")

            installed = self._root(
                [INSTALL, "-o", "root", "-g", "root", "-m", "0600", "/dev/stdin", temporary],
                input=encrypted.stdout,
                secret=secret,
                operation="write encrypted credential atomically",
            )
            if installed.returncode:
                raise EnrollmentError("encrypted credential could not be stored")

            decrypted = self._root(
                [
                    self.creds,
                    "--with-key=host",
                    "--name=friday-admin-password",
                    "decrypt",
                    temporary,
                    "-",
                ],
                secret=secret,
                operation="verify encrypted credential retrieval",
            )
            if decrypted.returncode or not hmac.compare_digest(decrypted.stdout, secret):
                raise EnrollmentError("stored credential retrieval validation failed")

            moved = self._root(
                [MV, "-f", "--", temporary, self.store],
                secret=secret,
                operation="publish encrypted credential",
            )
            if moved.returncode:
                raise EnrollmentError("credential replacement failed")
            self._install_candidate_runtime(secret)
        finally:
            self._root([RM, "-f", "--", temporary], secret=secret, check=False)

    def _install_candidate_runtime(self, secret: bytearray) -> None:
        repository = Path(__file__).resolve().parents[3]
        broker = (repository / "scripts/admin/friday-admin-broker.py").read_bytes()
        service = (repository / "config/services/friday-admin-broker.service").read_bytes()
        socket_unit = (repository / "config/services/friday-admin-broker.socket").read_text()
        socket_unit = socket_unit.replace("@OWNER_GID@", str(os.getgid())).encode()
        policy = json.loads(
            (repository / "config/services/friday-admin-clients.example.json").read_text()
        )
        policy["owner_uid"] = os.getuid()
        policy["owner_gid"] = os.getgid()
        policy_bytes = (json.dumps(policy, indent=2) + "\n").encode()

        for directory, group, mode in (
            ("/etc/friday-admin", "root", "0700"),
            (RUNTIME_DIR, str(os.getgid()), "0750"),
        ):
            result = self._root(
                [INSTALL, "-d", "-o", "root", "-g", group, "-m", mode, directory],
                secret=secret,
                operation="prepare candidate administrator runtime",
            )
            if result.returncode:
                raise EnrollmentError("candidate administrator runtime setup failed")
        files = (
            (broker, f"{RUNTIME_DIR}/broker.py", "0755"),
            (policy_bytes, POLICY, "0600"),
            (service, f"{UNIT_DIR}/friday-admin-broker.service", "0644"),
            (socket_unit, f"{UNIT_DIR}/friday-admin-broker.socket", "0644"),
        )
        for contents, destination, mode in files:
            result = self._root(
                [INSTALL, "-o", "root", "-g", "root", "-m", mode, "/dev/stdin", destination],
                input=contents,
                secret=secret,
                operation="install candidate administrator runtime file",
            )
            if result.returncode:
                raise EnrollmentError("candidate administrator runtime install failed")
        for command in (
            [RM, "-f", "--", INVALID_MARKER],
            [SYSTEMCTL, "daemon-reload"],
            [SYSTEMCTL, "start", "friday-admin-broker.socket"],
            [SYSTEMCTL, "try-restart", "friday-admin-broker.service"],
        ):
            result = self._root(command, secret=secret, operation="activate candidate administrator socket")
            if result.returncode:
                raise EnrollmentError("candidate administrator socket activation failed")

    def _remove_candidate_runtime(self, secret: bytearray) -> None:
        for command in (
            [SYSTEMCTL, "stop", "friday-admin-broker.socket"],
            [SYSTEMCTL, "stop", "friday-admin-broker.service"],
        ):
            self._root(command, secret=secret, check=False)
        paths = [
            POLICY,
            f"{RUNTIME_DIR}/broker.py",
            f"{UNIT_DIR}/friday-admin-broker.service",
            f"{UNIT_DIR}/friday-admin-broker.socket",
            INVALID_MARKER,
        ]
        self._root([RM, "-f", "--", *paths], secret=secret, check=False)
        self._root([SYSTEMCTL, "daemon-reload"], secret=secret, check=False)

    def _root(
        self, command: list[str], *, secret: bytearray, input: bytes | None = None,
        check: bool = True, operation: str = "perform privileged operation",
    ):
        try:
            result = self.sudo_executor(
                [self.sudo, *command], secret=secret, input=input, timeout=15,
                env=dict(_ENV),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            if check:
                raise EnrollmentError(f"credential vault could not {operation}") from exc
            return subprocess.CompletedProcess(command, 1, b"", b"")
        detail = _safe_failure_category(result.stderr) if result.returncode else ""
        if result.returncode and detail == "sudo authorization was unavailable to the privileged command":
            raise EnrollmentError("sudo credential validation failed")
        if check and result.returncode:
            suffix = f"; {detail}" if detail else ""
            raise EnrollmentError(
                f"credential vault could not {operation} (exit {result.returncode}{suffix})"
            )
        return result


def _run_sudo_command(
    command: list[str], *, secret: bytearray, input: bytes | None,
    timeout: int, env: dict[str, str],
) -> subprocess.CompletedProcess[bytes]:
    """Authenticate each sudo call and separate auth bytes from command stdin."""
    wrapped = [
        command[0], "-S", "-p", "", "-k", "--",
        "/bin/sh", "-c", "printf '\\036FRIDAY_SUDO_INPUT_READY\\037'; exec \"$@\"",
        "friday-root-operation", *command[1:],
    ]
    process = subprocess.Popen(
        wrapped, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        close_fds=True, start_new_session=True, env=env,
    )
    assert process.stdin is not None and process.stdout is not None and process.stderr is not None
    ready = threading.Event()
    marker_seen = [False]
    stdout = bytearray()
    stderr = bytearray()

    def read_output() -> None:
        marker = bytearray()
        while len(marker) < len(_READY):
            part = process.stdout.read(1)
            if not part:
                break
            marker.extend(part)
        if bytes(marker) == _READY:
            marker_seen[0] = True
            ready.set()
        else:
            stdout.extend(marker)
            ready.set()
        while True:
            chunk = process.stdout.read(4096)
            if not chunk:
                return
            if len(stdout) < 64 * 1024:
                stdout.extend(chunk[: 64 * 1024 - len(stdout)])

    def read_errors() -> None:
        while True:
            chunk = process.stderr.read(4096)
            if not chunk:
                return
            if len(stderr) < 8 * 1024:
                stderr.extend(chunk[: 8 * 1024 - len(stderr)])

    readers = [threading.Thread(target=read_output, daemon=True), threading.Thread(target=read_errors, daemon=True)]
    for reader in readers:
        reader.start()
    auth_input = bytearray(secret)
    auth_input.append(10)
    try:
        process.stdin.write(auth_input)
        process.stdin.flush()
        if input is not None and ready.wait(timeout) and marker_seen[0]:
            process.stdin.write(input)
            process.stdin.flush()
        process.stdin.close()
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, 15)
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, 9)
                process.wait()
            return subprocess.CompletedProcess(wrapped, 124, bytes(stdout), b"privileged operation timed out")
    finally:
        auth_input[:] = b"\x00" * len(auth_input)
        try:
            if not process.stdin.closed:
                process.stdin.close()
        except OSError:
            pass
        for reader in readers:
            reader.join(timeout=2)
    return subprocess.CompletedProcess(wrapped, process.returncode, bytes(stdout), bytes(stderr))


def _hidden_input(prompt: str) -> str:
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        try:
            return getpass.getpass(prompt)
        except getpass.GetPassWarning as exc:
            raise EnrollmentError("a hidden local terminal prompt is unavailable") from exc


def _safe_failure_category(stderr: bytes) -> str:
    """Map privileged-command diagnostics to fixed, non-secret categories."""
    message = stderr.decode("utf-8", "replace").lower()
    if "interactive authentication is required" in message or "a password is required" in message:
        return "sudo authorization was unavailable to the privileged command"
    if "not allowed" in message or "not permitted" in message:
        return "sudo policy denied the privileged command"
    if "host key" in message or "credential key" in message:
        return "systemd host credential key operation failed"
    if "permission denied" in message:
        return "the privileged command reported a permission failure"
    return "privileged command reported an unclassified error"


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["enroll"]:
        action_name = "enroll"
    elif args == ["update-credential"]:
        action_name = "update"
    elif args == ["revoke"]:
        action_name = "revoke"
    elif args == ["status"]:
        from local_ai_assistant.admin.client import AdministratorCredentialService

        try:
            print(f"Owner Sovereign Mode: {AdministratorCredentialService().status().value}")
            return 0
        except (OSError, RuntimeError):
            print("Owner Sovereign Mode: unavailable", file=sys.stderr)
            return 1
    else:
        print("usage: friday-admin {status|enroll|update-credential|revoke}", file=sys.stderr)
        return 2
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        print("credential lifecycle requires a local interactive terminal", file=sys.stderr)
        return 2
    try:
        lifecycle = CredentialLifecycle()
        if action_name == "enroll":
            lifecycle.enroll_from_terminal()
        elif action_name == "update":
            lifecycle.enroll_from_terminal(update=True)
        else:
            lifecycle.revoke_from_terminal()
    except EnrollmentError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("Owner Sovereign Mode credential operation completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
