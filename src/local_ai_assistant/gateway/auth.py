"""Authentication and authorization with no plaintext token persistence."""
from __future__ import annotations

import hashlib
import hmac
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from .models import GatewayScope


class GatewayAuthenticationError(PermissionError):
    pass


class GatewayAuthorizationError(PermissionError):
    pass


class GatewayRateLimitError(PermissionError):
    pass


@dataclass(frozen=True, slots=True)
class Principal:
    name: str
    scopes: frozenset[GatewayScope]


class GatewayAuth:
    def __init__(self, token_hash: str, scopes: frozenset[GatewayScope] | None = None):
        normalized = token_hash.strip().lower()
        if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
            raise ValueError("LOCAL_AI_GATEWAY_TOKEN_HASH must be a SHA-256 hex digest")
        self._token_hash = normalized
        self._scopes = scopes if scopes is not None else frozenset({GatewayScope.READ_STATUS, GatewayScope.READ_HISTORY})

    def authenticate(self, token: str | None) -> Principal | None:
        if not token or not self._token_hash:
            return None
        digest = hashlib.sha256(token.encode()).hexdigest()
        if not hmac.compare_digest(digest, self._token_hash):
            return None
        return Principal("local-token", self._scopes)

    def require(self, token: str | None, scope: GatewayScope) -> Principal:
        principal = self.authenticate(token)
        if principal is None:
            raise GatewayAuthenticationError("authentication required")
        if scope not in principal.scopes:
            raise GatewayAuthorizationError("insufficient gateway scope")
        return principal


class GatewayRateLimiter:
    def __init__(self, requests_per_minute: int):
        if requests_per_minute < 1:
            raise ValueError("requests_per_minute must be positive")
        self.limit = requests_per_minute
        self._calls: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, principal: str) -> bool:
        now = time.monotonic()
        calls = self._calls[principal]
        while calls and now - calls[0] >= 60:
            calls.popleft()
        if len(calls) >= self.limit:
            return False
        calls.append(now)
        return True
