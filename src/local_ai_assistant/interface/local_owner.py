"""Explicit single-Unix-user trust for a private, server-side UI bridge.

The capability never travels to the browser. It authenticates the trusted UI
server to the loopback API, which still enforces Origin, CSRF and plan authority.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import stat
import threading
from pathlib import Path

from local_ai_assistant.isolation.owner_rollback import OwnerBrowserSessions


class LocalOwnerTrust:
    def __init__(self, path: Path, installation: Path):
        self.path = path.absolute()
        self.installation = installation.resolve(strict=True)
        if self.installation.stat().st_uid != os.getuid():
            raise ValueError("local owner installation must belong to the current Unix user")
        if any((parent / ".git").exists() for parent in (self.path.parent, *self.path.parents)):
            raise ValueError("local owner capability must be outside Git")
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._private_parent()
        try:
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, "w") as stream:
                json.dump({"version": 1, "uid": os.getuid(),
                           "installation": str(self.installation),
                           "capability": secrets.token_hex(32)}, stream)
                stream.flush()
                os.fsync(stream.fileno())
        value = self._read()
        self._digest = hashlib.sha256(value.encode()).hexdigest()
        self.sessions = OwnerBrowserSessions(self._digest)
        self._restore_lock = threading.Lock()
        self._restored_session: tuple[str, str] | None = None

    def _private_parent(self) -> None:
        parent = self.path.parent
        if parent.resolve() != parent or self.path.is_symlink():
            raise ValueError("local owner capability cannot use symlinks")
        info = parent.stat()
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise ValueError("local owner capability directory must be owner-only")

    def _read(self) -> str:
        self._private_parent()
        fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd) as stream:
            info = os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
                raise ValueError("local owner capability must be a private regular file")
            value = json.loads(stream.read(4097))
        capability = value.get("capability", "")
        if (value.get("version") != 1 or value.get("uid") != os.getuid()
                or value.get("installation") != str(self.installation)
                or not isinstance(capability, str) or len(capability) != 64
                or any(char not in "0123456789abcdef" for char in capability)):
            raise ValueError("invalid local owner installation capability")
        return capability

    def restore(self, supplied: str, peer: str, host: str) -> tuple[str, str] | None:
        if peer not in {"127.0.0.1", "::1"} or host not in {"127.0.0.1", "localhost", "::1"}:
            return None
        try:
            current = self._read()
        except (OSError, ValueError, TypeError):
            return None
        # Deletion, rotation or changed ownership revokes restoration immediately.
        if not hmac.compare_digest(hashlib.sha256(current.encode()).hexdigest(), self._digest):
            return None
        with self._restore_lock:
            if (self._restored_session is not None
                    and self.sessions.principal(*self._restored_session) == "local-owner"):
                return self._restored_session
            self._restored_session = self.sessions.unlock(supplied, peer)
            return self._restored_session

    def local_voice_principal(self) -> str:
        """Return the same local Owner principal only while its private grant is valid."""
        try:
            current = self._read()
        except (OSError, ValueError, TypeError) as exc:
            raise RuntimeError("local Owner trust is unavailable") from exc
        if not hmac.compare_digest(hashlib.sha256(current.encode()).hexdigest(), self._digest):
            raise RuntimeError("local Owner trust has been revoked")
        return "local-owner"
