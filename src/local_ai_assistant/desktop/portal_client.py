"""Trusted controller transport for the private, system-Python portal worker."""

from __future__ import annotations

import json
import os
import select
import subprocess
import threading
import time
from pathlib import Path

from .portal_worker import RestoreCapabilityStore


class PortalDesktopClient:
    """Own one worker and fail closed when a response is missing or malformed."""

    def __init__(self, token_file: Path, *, worker: Path | None = None,
                 popen=subprocess.Popen) -> None:
        self._lock = threading.RLock()
        self._process = None
        self._popen = popen
        self._token_file = token_file.expanduser().absolute()
        self._worker = worker or Path(__file__).with_name("portal_worker.py")
        self._status = "unavailable"
        self._last_attempt = 0.0

    @property
    def status(self) -> str:
        return self._status

    def start(self) -> str:
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                if self._status != "unavailable" or time.monotonic() - self._last_attempt < 10:
                    return self._status
                self.close()
            if self._process is not None:
                self.close()
            self._last_attempt = time.monotonic()
            environment = os.environ.copy()
            environment["LOCAL_AI_DESKTOP_RESTORE_TOKEN_FILE"] = str(self._token_file)
            self._process = self._popen(
                ["/usr/bin/python3", "-I", "-u", str(self._worker)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, bufsize=1, close_fds=True, env=environment,
            )
            try:
                self._status = self._read_status(timeout=15)
            except Exception:
                self.close()
                raise
            return self._status

    def enroll(self) -> str:
        """Only a dedicated owner setup path may call this and show a GNOME dialog."""
        if self.start() == "active":
            return "active"
        return self.command({"command": "enroll"}, timeout=250)

    def command(self, command: dict, *, timeout: int = 10) -> str:
        with self._lock:
            if self.start() != "active" and command.get("command") != "enroll":
                raise RuntimeError("desktop permission requires owner recovery")
            process = self._process
            if process is None or process.poll() is not None or process.stdin is None:
                self._status = "unavailable"
                raise RuntimeError("desktop worker is unavailable")
            encoded = json.dumps(command, separators=(",", ":"))
            if len(encoded) > 4095:
                raise ValueError("desktop command is too large")
            try:
                process.stdin.write(encoded + "\n")
                process.stdin.flush()
                status = self._read_status(timeout=timeout)
            except (BrokenPipeError, OSError, RuntimeError):
                self.close()
                raise RuntimeError("desktop worker result is uncertain") from None
            if status == "active":
                self._status = "active"
            expected = {
                "enroll": "active", "status": "active", "stop": "stopped", "close": "closed",
                "move_relative": "executed", "key": "executed", "button": "executed",
                "scroll": "executed", "type_text": "executed",
            }.get(command.get("command"))
            if status != expected:
                raise RuntimeError("desktop action was not executed")
            return status

    def _read_status(self, *, timeout: int) -> str:
        process = self._process
        if process is None or process.stdout is None:
            raise RuntimeError("desktop worker is unavailable")
        ready, _, _ = select.select([process.stdout], [], [], timeout)
        if not ready:
            raise RuntimeError("desktop worker timed out")
        line = process.stdout.readline(4097)
        if len(line) > 4096 or not line.endswith("\n"):
            raise RuntimeError("desktop worker response is invalid")
        try:
            response = json.loads(line)
        except ValueError as exc:
            raise RuntimeError("desktop worker response is invalid") from exc
        status = response.get("status") if isinstance(response, dict) else None
        if status not in {"active", "permission_required", "not_granted", "unavailable",
                          "executed", "stopped", "closed", "invalid"}:
            raise RuntimeError("desktop worker response is invalid")
        return status

    def close(self) -> None:
        with self._lock:
            process = self._process
            self._process = None
            self._status = "unavailable"
            if process is None:
                return
            if process.poll() is None:
                try:
                    if process.stdin:
                        process.stdin.write('{"command":"close"}\n')
                        process.stdin.flush()
                    process.wait(timeout=3)
                except (BrokenPipeError, OSError, subprocess.TimeoutExpired):
                    process.kill()
                    process.wait(timeout=3)
            if process.stdin:
                process.stdin.close()
            if process.stdout:
                process.stdout.close()

    def revoke_local(self) -> None:
        """Disable Friday's saved grant; GNOME may retain its own grant record."""
        with self._lock:
            self.close()
            store = RestoreCapabilityStore(self._token_file)
            if store.load() is None:
                return
            store.path.unlink()
            directory = os.open(store.path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
