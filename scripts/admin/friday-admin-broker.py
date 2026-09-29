#!/usr/bin/python3
"""Root-owned Owner Sovereign Mode broker; stdlib-only by design."""

from __future__ import annotations

import base64
import json
import os
import re
import signal
import socket
import stat
import struct
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

MAX_FRAME = 128 * 1024
MAX_STDIN = 32 * 1024
MAX_OUTPUT = 8 * 1024
MAX_TIMEOUT = 300
MAX_SECRET = 4096
STDIN_READY_MARKER = b"\x1eFRIDAY_SUDO_INPUT_READY\x1f"
SUDO = "/usr/bin/sudo"
SETPRIV = "/usr/bin/setpriv"
ENVCMD = "/usr/bin/env"
SYSTEMCTL = "/usr/bin/systemctl"
SYSTEMD_CREDS = "/usr/bin/systemd-creds"
STORE = Path("/etc/credstore.encrypted/friday-admin-password")
AUDIT = Path("/var/lib/friday-admin/audit.jsonl")
INVALID_MARKER = Path("/var/lib/friday-admin/credential-invalid")
CONFIG = Path("/etc/friday-admin/clients.json")
REDACT_PATTERNS = (
    re.compile(rb"(?i)(password|passwd|token|secret|credential)\s*([=:])\s*[^\s,;]+"),
    re.compile(rb"(?i)authorization\s*:\s*bearer\s+[^\s]+"),
)


@dataclass(frozen=True)
class Peer:
    pid: int
    uid: int
    gid: int


@dataclass(frozen=True)
class BrokerConfig:
    owner_uid: int
    owner_gid: int
    system_units: tuple[str, ...]
    user_units: tuple[str, ...]

    @classmethod
    def load(cls, path: Path = CONFIG) -> BrokerConfig:
        st = path.lstat()
        if (
            not stat.S_ISREG(st.st_mode)
            or st.st_uid != 0
            or st.st_mode & 0o022
        ):
            raise RuntimeError("broker client policy must be a root-owned regular file")
        raw = json.loads(path.read_text(encoding="utf-8"))
        uid = raw.get("owner_uid")
        gid = raw.get("owner_gid")
        system_units = tuple(raw.get("system_units", ()))
        user_units = tuple(raw.get("user_units", ()))
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 1 for value in (uid, gid)):
            raise RuntimeError("broker client policy has an invalid owner identity")
        units = system_units + user_units
        if not units or any(
            not isinstance(unit, str) or not re.fullmatch(r"[A-Za-z0-9_.@:-]+\.service", unit)
            for unit in units
        ):
            raise RuntimeError("broker client policy has invalid Friday service names")
        return cls(uid, gid, system_units, user_units)


class MainProcessVerifier:
    """Accept only the MainPID of an explicitly configured Friday systemd unit."""

    def __init__(self, config: BrokerConfig, *, command_runner=subprocess.run,
                 proc_root: Path = Path("/proc")) -> None:
        self.config = config
        self.command_runner = command_runner
        self.proc_root = proc_root

    def allows(self, peer: Peer) -> bool:
        if peer.uid != self.config.owner_uid:
            return False
        for scope, units in (("system", self.config.system_units), ("user", self.config.user_units)):
            for unit in units:
                command = [SYSTEMCTL]
                environment = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C"}
                if scope == "user":
                    runtime = f"/run/user/{self.config.owner_uid}"
                    command = [
                        SETPRIV, f"--reuid={self.config.owner_uid}",
                        f"--regid={self.config.owner_gid}", "--init-groups", "--",
                        ENVCMD, f"XDG_RUNTIME_DIR={runtime}",
                        f"DBUS_SESSION_BUS_ADDRESS=unix:path={runtime}/bus",
                        "PATH=/usr/sbin:/usr/bin:/sbin:/bin", "LANG=C",
                        SYSTEMCTL, "--user",
                    ]
                command.extend(("show", unit, "--property=MainPID", "--value", "--no-pager"))
                try:
                    result = self.command_runner(
                        command, capture_output=True, text=True, timeout=2,
                        check=False, env=environment if scope == "system" else None,
                    )
                    main_pid = int(result.stdout.strip()) if result.returncode == 0 else 0
                except (OSError, subprocess.SubprocessError, ValueError):
                    continue
                if main_pid == peer.pid and self._peer_still_matches(peer, unit):
                    return True
        return False

    def _peer_still_matches(self, peer: Peer, unit: str) -> bool:
        try:
            process = self.proc_root / str(peer.pid)
            if process.stat().st_uid != peer.uid:
                return False
            cgroup = (process / "cgroup").read_text(encoding="ascii")
            components = {
                component
                for line in cgroup.splitlines()
                for component in line.rsplit(":", 1)[-1].split("/")
            }
            return unit in components
        except OSError:
            return False


class SystemdCredentialStore:
    """Systemd host-key encrypted storage; plaintext is never written to disk."""

    def __init__(self, path: Path = STORE, *, runner=subprocess.run) -> None:
        self.path = path
        self.runner = runner

    def exists(self) -> bool:
        try:
            file_stat = self.path.lstat()
        except FileNotFoundError:
            return False
        if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_uid != 0 or file_stat.st_mode & 0o077:
            raise RuntimeError("encrypted credential file permissions are unsafe")
        return True

    def retrieve(self) -> bytearray:
        if not self.exists():
            raise LookupError("administrator credential is not enrolled")
        encrypted = self.path.read_bytes()
        if not encrypted or len(encrypted) > 16 * 1024:
            raise RuntimeError("encrypted credential size is invalid")
        result = self.runner(
            [SYSTEMD_CREDS, "--with-key=host", "--name=friday-admin-password", "decrypt", "-", "-"],
            input=encrypted, capture_output=True, timeout=5, check=False,
            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C"},
        )
        if result.returncode != 0 or not result.stdout or len(result.stdout) > MAX_SECRET:
            raise RuntimeError("administrator credential decryption failed")
        value = bytearray(result.stdout)
        while value and value[-1] in (10, 13):
            value.pop()
        if not value or b"\x00" in value or b"\n" in value or b"\r" in value:
            value[:] = b"\x00" * len(value)
            raise RuntimeError("stored administrator credential format is invalid")
        return value

    def replace(self, password: bytearray) -> None:
        if not password or len(password) > MAX_SECRET or any(char in password for char in (0, 10, 13)):
            raise ValueError("administrator credential format is invalid")
        result = self.runner(
            [SYSTEMD_CREDS, "--with-key=host", "--name=friday-admin-password", "encrypt", "-", "-"],
            input=bytes(password), capture_output=True, timeout=5, check=False,
            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C"},
        )
        if result.returncode != 0 or not result.stdout or len(result.stdout) > 16 * 1024:
            raise RuntimeError("systemd credential encryption failed")
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.{uuid4().hex}.tmp")
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC, 0o600)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(result.stdout)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            os.chmod(self.path, 0o600)
            dir_fd = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

    def revoke(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            return


class SudoRunner:
    """Runs sudo as the owner; the password is written only to sudo stdin."""

    def __init__(self, config: BrokerConfig, *, popen=subprocess.Popen) -> None:
        self.config = config
        self.popen = popen

    def execute(
        self, executable: str, argv: list[str], password: bytearray, *, cwd: str,
        environment: dict[str, str], stdin: bytes, timeout: int,
    ) -> dict[str, Any]:
        env_items = [f"{key}={value}" for key, value in sorted(environment.items())]
        command_stdin = [
            "/bin/sh", "-c",
            "printf '\\036FRIDAY_SUDO_INPUT_READY\\037'; exec \"$@\"",
            "friday-privileged-stdin", executable, *argv,
        ]
        target = [
            ENVCMD, "-i", f"PATH={environment.get('PATH', '/usr/sbin:/usr/bin:/sbin:/bin')}",
            *env_items, *command_stdin,
        ]
        command = [
            SETPRIV, f"--reuid={self.config.owner_uid}",
            f"--regid={self.config.owner_gid}", "--init-groups", "--",
            SUDO, "-S", "-p", "", "-k", "--", *target,
        ]
        started = time.monotonic()
        process = self.popen(
            command, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, start_new_session=True, close_fds=True,
            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C"},
        )
        assert process.stdin is not None and process.stdout is not None and process.stderr is not None
        out = bytearray()
        err = bytearray()
        command_ready = threading.Event()
        readers = [
            threading.Thread(
                target=_read_ready_limited,
                args=(process.stdout, out, command_ready),
                daemon=True,
            ),
            threading.Thread(target=_read_limited, args=(process.stderr, err), daemon=True),
        ]
        for reader in readers:
            reader.start()
        timed_out = False
        secret_input = bytearray(password)
        secret_input.extend(b"\n")

        def write_input() -> None:
            try:
                process.stdin.write(secret_input)
                process.stdin.flush()
                if stdin and command_ready.wait(timeout + 1):
                    process.stdin.write(stdin)
                    process.stdin.flush()
            except (BrokenPipeError, OSError):
                pass
            finally:
                try:
                    process.stdin.close()
                except OSError:
                    pass
                secret_input[:] = b"\x00" * len(secret_input)

        writer = threading.Thread(target=write_input, daemon=True)
        writer.start()
        try:
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=2)
                except (ProcessLookupError, subprocess.TimeoutExpired):
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait()
        finally:
            command_ready.set()
            writer.join(timeout=2)
            for reader in readers:
                reader.join(timeout=2)
        password_bytes = bytes(password)
        stdout = _redact(bytes(out), password_bytes)
        stderr = _redact(bytes(err), password_bytes)
        return {
            "return_code": process.returncode if process.returncode is not None else -1,
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
            "timed_out": timed_out,
            "duration_seconds": round(time.monotonic() - started, 3),
            "authentication_failed": _sudo_auth_failed(stderr),
        }


class AdminBroker:
    def __init__(self, store: SystemdCredentialStore, verifier: MainProcessVerifier,
                 runner: SudoRunner, *, audit_path: Path = AUDIT,
                 invalid_marker: Path = INVALID_MARKER) -> None:
        self.store = store
        self.verifier = verifier
        self.runner = runner
        self.audit_path = audit_path
        self.invalid_marker = invalid_marker
        self.invalid_credential = self._invalid_marker_present()

    def handle(self, peer: Peer, request: dict[str, Any]) -> dict[str, Any]:
        operation = request.get("op")
        if operation == "status" and peer.uid == self.verifier.config.owner_uid:
            return self._status()
        if not self.verifier.allows(peer):
            return {"ok": False, "error": "untrusted administrator client"}
        if operation == "status":
            return self._status()
        if operation != "execute":
            return {"ok": False, "error": "unsupported administrator operation"}
        return self._execute(request)

    def _status(self) -> dict[str, Any]:
        if self._invalid_marker_present():
            self.invalid_credential = True
        if self.invalid_credential:
            return {"ok": True, "status": "invalid"}
        try:
            if not self.store.exists():
                state = "not_enrolled"
            else:
                credential = self.store.retrieve()
                credential[:] = b"\x00" * len(credential)
                state = "available"
        except (OSError, RuntimeError):
            state = "degraded"
        except LookupError:
            state = "not_enrolled"
        return {"ok": True, "status": state}

    def _execute(self, request: dict[str, Any]) -> dict[str, Any]:
        operation_id = _short_text(request.get("operation_id"), 64) or uuid4().hex
        task_id = _short_text(request.get("task_id"), 128)
        action_id = _short_text(request.get("action_id"), 128)
        executable = request.get("executable")
        argv = request.get("argv")
        cwd = request.get("cwd")
        env = request.get("environment", {})
        timeout = request.get("timeout_seconds")
        try:
            stdin = base64.b64decode(request.get("stdin_b64", ""), validate=True)
        except (ValueError, TypeError):
            return {"ok": False, "error": "invalid operation input"}
        if (
            not task_id or not action_id or not isinstance(executable, str)
            or not os.path.isabs(executable) or "\x00" in executable
            or not isinstance(argv, list) or len(argv) > 256
            or any(not isinstance(item, str) or "\x00" in item or len(item) > 8192 for item in argv)
            or not isinstance(cwd, str) or not os.path.isabs(cwd)
            or not isinstance(env, dict) or len(env) > 32
            or any(not _safe_env(key, value) for key, value in env.items())
            or not isinstance(timeout, int) or isinstance(timeout, bool) or not 1 <= timeout <= MAX_TIMEOUT
            or len(stdin) > MAX_STDIN
        ):
            return {"ok": False, "error": "invalid privileged operation"}
        password: bytearray | None = None
        try:
            if self.invalid_credential or self._invalid_marker_present():
                self.invalid_credential = True
                return {"ok": False, "error": "administrator_credential_invalid"}
            password = self.store.retrieve()
            if _request_contains_secret(request, password, stdin):
                password[:] = b"\x00" * len(password)
                return {"ok": False, "error": "credential material is not valid operation input"}
            result = self.runner.execute(
                executable, argv, password, cwd=cwd, environment=env,
                stdin=stdin, timeout=timeout,
            )
        except LookupError:
            if password is not None:
                password[:] = b"\x00" * len(password)
            return {"ok": False, "error": "administrator_credential_unavailable"}
        except (OSError, RuntimeError, subprocess.SubprocessError):
            if password is not None:
                password[:] = b"\x00" * len(password)
            return {"ok": False, "error": "administrator_credential_or_executor_unavailable"}
        assert password is not None
        if result.get("authentication_failed"):
            self.invalid_credential = True
            _mark_credential_invalid(self.invalid_marker)
            try:
                _audit(self.audit_path, {
                    "timestamp": _timestamp(),
                    "operation_id": _redact_text(operation_id, password),
                    "task_id": _redact_text(task_id, password),
                    "action_id": _redact_text(action_id, password),
                    "executable": _redact_text(executable, password),
                    "outcome": "administrator_credential_invalid",
                })
            finally:
                password[:] = b"\x00" * len(password)
            return {"ok": False, "error": "administrator_credential_invalid"}
        try:
            _audit(self.audit_path, {
                "timestamp": _timestamp(),
                "operation_id": _redact_text(operation_id, password),
                "task_id": _redact_text(task_id, password),
                "action_id": _redact_text(action_id, password),
                "executable": _redact_text(executable, password),
                "argv": [_redact_text(item, password)[:512] for item in argv],
                "return_code": result["return_code"],
                "timed_out": result["timed_out"],
                "duration_seconds": result["duration_seconds"],
            })
        finally:
            password[:] = b"\x00" * len(password)
        result.pop("authentication_failed", None)
        return {"ok": True, "operation_id": operation_id, **result}

    def _invalid_marker_present(self) -> bool:
        try:
            marker = self.invalid_marker.lstat()
        except FileNotFoundError:
            return False
        if (
            not stat.S_ISREG(marker.st_mode)
            or marker.st_uid != 0
            or marker.st_mode & 0o077
        ):
            return True
        return True


def serve_connection(connection: socket.socket, broker: AdminBroker) -> None:
    raw = connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    peer = Peer(*struct.unpack("3i", raw))
    request = _read_frame(connection)
    try:
        if not isinstance(request, dict):
            raise ValueError
        response = broker.handle(peer, request)
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        response = {"ok": False, "error": "invalid administrator request"}
    body = json.dumps(response, separators=(",", ":"), ensure_ascii=True).encode("utf-8")[:MAX_FRAME]
    connection.sendall(struct.pack("!I", len(body)) + body)


def _read_frame(connection: socket.socket) -> Any:
    header = _read_exact(connection, 4)
    size = struct.unpack("!I", header)[0]
    if not 0 < size <= MAX_FRAME:
        raise ValueError("invalid frame size")
    return json.loads(_read_exact(connection, size))


def _read_exact(connection: socket.socket, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = connection.recv(size - len(data))
        if not chunk:
            raise ValueError("incomplete frame")
        data.extend(chunk)
    return bytes(data)


def _read_limited(stream: Any, buffer: bytearray) -> None:
    while chunk := stream.read(8192):
        remaining = MAX_OUTPUT - len(buffer)
        if remaining > 0:
            buffer.extend(chunk[:remaining])


def _read_ready_limited(stream: Any, buffer: bytearray, ready: threading.Event) -> None:
    marker = STDIN_READY_MARKER
    prefix = bytearray()
    while len(prefix) < len(marker):
        chunk = stream.read(len(marker) - len(prefix))
        if not chunk:
            buffer.extend(prefix)
            return
        prefix.extend(chunk)
    if prefix == marker:
        ready.set()
    else:
        buffer.extend(prefix)
    _read_limited(stream, buffer)


def _redact(value: bytes, secret: bytes) -> bytes:
    if secret:
        value = value.replace(secret, b"[REDACTED]")
    for pattern in REDACT_PATTERNS:
        value = pattern.sub(lambda match: match.group(1) + match.group(2) + b"[REDACTED]", value)
    return value


def _redact_text(value: str, secret: bytes | bytearray = b"") -> str:
    encoded = _redact(value.encode("utf-8", errors="replace"), bytes(secret))
    return encoded.decode("utf-8", errors="replace")[:2048]


def _request_contains_secret(request: dict[str, Any], secret: bytearray, stdin: bytes) -> bool:
    credential = bytes(secret)
    if not credential:
        return False
    candidates: list[str | bytes] = [
        request.get("operation_id", ""),
        request.get("task_id", ""),
        request.get("action_id", ""),
        request.get("executable", ""),
        request.get("cwd", ""),
        stdin,
    ]
    argv = request.get("argv", [])
    environment = request.get("environment", {})
    if isinstance(argv, list):
        candidates.extend(item for item in argv if isinstance(item, str))
    if isinstance(environment, dict):
        candidates.extend(
            item for pair in environment.items() for item in pair if isinstance(item, str)
        )
    return any(
        credential in value if isinstance(value, bytes)
        else credential.decode("utf-8", errors="ignore") in value
        for value in candidates
    )


def _sudo_auth_failed(stderr: bytes) -> bool:
    diagnostic = stderr.lower()
    return any(marker in diagnostic for marker in (
        b"authentication failure", b"authentication failed", b"incorrect password",
        b"sorry, try again", b"a password is required", b"no password was provided",
    ))


def _safe_env(key: Any, value: Any) -> bool:
    return (
        isinstance(key, str) and isinstance(value, str) and 0 < len(key) <= 64
        and key[0].isalpha() and key.replace("_", "").isalnum()
        and key != "PATH"
        and not key.startswith(("LD_", "SUDO_", "PYTHON", "DBUS_", "XDG_RUNTIME_DIR"))
        and "\x00" not in value and len(value) <= 4096
    )


def _short_text(value: Any, size: int) -> str:
    if not isinstance(value, str):
        return ""
    result = value.strip()[:size]
    return "" if "\x00" in result else result


def _audit(path: Path, record: dict[str, Any]) -> None:
    owner_uid = os.geteuid()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    parent_stat = path.parent.lstat()
    if (
        not stat.S_ISDIR(parent_stat.st_mode)
        or parent_stat.st_uid != owner_uid
        or parent_stat.st_mode & 0o077
    ):
        raise RuntimeError("administrator audit directory permissions are unsafe")
    fd = os.open(
        path,
        os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW,
        0o600,
    )
    try:
        file_stat = os.fstat(fd)
        if (
            not stat.S_ISREG(file_stat.st_mode)
            or file_stat.st_uid != owner_uid
            or file_stat.st_mode & 0o077
        ):
            raise RuntimeError("administrator audit file permissions are unsafe")
        payload = (json.dumps(record, separators=(",", ":"), ensure_ascii=True) + "\n").encode()
        remaining = memoryview(payload)
        while remaining:
            written = os.write(fd, remaining)
            remaining = remaining[written:]
        os.fsync(fd)
    finally:
        os.close(fd)


def _mark_credential_invalid(path: Path) -> None:
    owner_uid = os.geteuid()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    parent = path.parent.lstat()
    if not stat.S_ISDIR(parent.st_mode) or parent.st_uid != owner_uid or parent.st_mode & 0o077:
        raise RuntimeError("credential state directory permissions are unsafe")
    try:
        fd = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
        )
    except FileExistsError:
        return
    try:
        os.write(fd, (_timestamp() + "\n").encode())
        os.fsync(fd)
    finally:
        os.close(fd)


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def main() -> int:
    if os.geteuid() != 0:
        print("administrator broker must run as root", file=sys.stderr)
        return 2
    try:
        config = BrokerConfig.load()
        broker = AdminBroker(SystemdCredentialStore(), MainProcessVerifier(config), SudoRunner(config))
    except Exception:
        print("administrator broker configuration is unavailable", file=sys.stderr)
        return 2
    if (
        int(os.environ.get("LISTEN_FDS", "0")) != 1
        or int(os.environ.get("LISTEN_PID", "0")) != os.getpid()
    ):
        print("administrator broker requires systemd socket activation", file=sys.stderr)
        return 2
    listener = socket.socket(fileno=os.dup(3))
    while True:
        connection, _ = listener.accept()
        with connection:
            connection.settimeout(10)
            try:
                serve_connection(connection, broker)
            except (OSError, ValueError):
                continue


if __name__ == "__main__":
    raise SystemExit(main())
