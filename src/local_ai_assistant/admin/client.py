"""AF_UNIX client for the root-owned Friday administrator broker.

This API never retrieves or returns the administrator credential. The trusted
Friday service is authenticated by the broker using peer PID and systemd unit
identity; caller-side checks are defense in depth only.
"""

from __future__ import annotations

import base64
import json
import os
import socket
import struct
import time
from pathlib import Path
from uuid import uuid4

from .models import AdminCredentialStatus, PrivilegedResult

_MAX_REQUEST_BYTES = 128 * 1024
_MAX_RESPONSE_BYTES = 128 * 1024
_MAX_STDIN_BYTES = 32 * 1024
_MAX_TIMEOUT_SECONDS = 300


class AdministratorCredentialService:
    """Read-only, non-secret credential status from the trusted broker."""

    def __init__(self, socket_path: Path | str = "/run/friday-admin/broker.sock") -> None:
        self.socket_path = Path(socket_path)

    def status(self) -> AdminCredentialStatus:
        response = _request(self.socket_path, {"op": "status"})
        try:
            return AdminCredentialStatus(response["status"])
        except (KeyError, ValueError, TypeError) as exc:
            raise RuntimeError("administrator broker returned invalid status") from exc


class PrivilegedExecutor:
    """Submit a task-bound operation; the password remains inside the broker."""

    def __init__(self, socket_path: Path | str = "/run/friday-admin/broker.sock") -> None:
        self.socket_path = Path(socket_path)

    def execute(
        self,
        executable: str,
        argv: tuple[str, ...] | list[str],
        *,
        task_id: str,
        action_id: str,
        working_directory: Path | str = "/",
        environment: dict[str, str] | None = None,
        stdin: bytes = b"",
        timeout_seconds: int = 60,
    ) -> PrivilegedResult:
        if not isinstance(executable, str) or not os.path.isabs(executable) or "\x00" in executable:
            raise ValueError("privileged executable must be an absolute path")
        if (
            not isinstance(task_id, str)
            or not isinstance(action_id, str)
            or not task_id.strip()
            or not action_id.strip()
            or len(task_id) > 128
            or len(action_id) > 128
            or "\x00" in task_id
            or "\x00" in action_id
        ):
            raise ValueError("task and action identity are required")
        if not isinstance(argv, (tuple, list)):
            raise ValueError("privileged argv must be a list or tuple")
        if not isinstance(stdin, bytes):
            raise ValueError("privileged stdin must be bytes")
        if len(stdin) > _MAX_STDIN_BYTES:
            raise ValueError("privileged stdin exceeds the configured limit")
        if isinstance(timeout_seconds, bool) or not 1 <= timeout_seconds <= _MAX_TIMEOUT_SECONDS:
            raise ValueError("privileged timeout is outside the supported range")
        values = [executable, *argv]
        if any(not isinstance(item, str) or "\x00" in item for item in values):
            raise ValueError("privileged argv must contain NUL-free strings")
        directory = str(working_directory)
        if not os.path.isabs(directory) or "\x00" in directory:
            raise ValueError("privileged working directory must be absolute")
        env = {} if environment is None else environment
        if not isinstance(env, dict) or len(env) > 32 or any(
            not isinstance(key, str)
            or not isinstance(value, str)
            or "\x00" in value
            or len(value) > 4096
            for key, value in env.items()
        ):
            raise ValueError("privileged environment is invalid")
        if any(
            not key or not key.replace("_", "").isalnum() or not key[0].isalpha()
            or key == "PATH"
            or key.startswith(("LD_", "SUDO_", "PYTHON"))
            for key in env
        ):
            raise ValueError("privileged environment contains a forbidden name")
        payload = {
            "op": "execute",
            "operation_id": uuid4().hex,
            "task_id": task_id[:128],
            "action_id": action_id[:128],
            "executable": executable,
            "argv": list(argv),
            "cwd": directory,
            "environment": env,
            "stdin_b64": base64.b64encode(stdin).decode("ascii"),
            "timeout_seconds": timeout_seconds,
        }
        response = _request(self.socket_path, payload)
        try:
            return PrivilegedResult(
                operation_id=str(response["operation_id"]),
                return_code=int(response["return_code"]),
                stdout=str(response.get("stdout", "")),
                stderr=str(response.get("stderr", "")),
                timed_out=bool(response["timed_out"]),
                duration_seconds=float(response["duration_seconds"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("administrator broker returned an invalid result") from exc

    def execute_shell(
        self,
        script: str,
        *,
        task_id: str,
        action_id: str,
        working_directory: Path | str = "/",
        environment: dict[str, str] | None = None,
        stdin: bytes = b"",
        timeout_seconds: int = 60,
    ) -> PrivilegedResult:
        """Run explicitly requested shell syntax; the credential stays separate."""
        if not script or "\x00" in script or len(script) > 32_000:
            raise ValueError("privileged shell source is invalid or too large")
        return self.execute(
            "/bin/bash", ("--noprofile", "--norc", "-c", script),
            task_id=task_id, action_id=action_id,
            working_directory=working_directory, environment=environment,
            stdin=stdin, timeout_seconds=timeout_seconds,
        )


def _request(socket_path: Path, payload: dict[str, object]) -> dict[str, object]:
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    if len(body) > _MAX_REQUEST_BYTES:
        raise ValueError("administrator request exceeds the configured limit")
    deadline = time.monotonic() + 10
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        client.settimeout(max(0.1, deadline - time.monotonic()))
        client.connect(str(socket_path))
        client.sendall(struct.pack("!I", len(body)) + body)
        header = _recv_exact(client, 4)
        size = struct.unpack("!I", header)[0]
        if not 0 < size <= _MAX_RESPONSE_BYTES:
            raise RuntimeError("administrator broker response size is invalid")
        response = json.loads(_recv_exact(client, size))
        if not isinstance(response, dict):
            raise RuntimeError("administrator broker response is not an object")
        if response.get("ok") is not True:
            message = response.get("error")
            raise RuntimeError(str(message)[:200] if isinstance(message, str) else "administrator request failed")
        return response
    finally:
        client.close()


def _recv_exact(client: socket.socket, count: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < count:
        block = client.recv(count - len(chunks))
        if not block:
            raise RuntimeError("administrator broker closed an incomplete response")
        chunks.extend(block)
    return bytes(chunks)
