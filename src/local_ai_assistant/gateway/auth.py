"""Authentication and authorization with no plaintext token persistence."""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

from .models import GatewayScope


@dataclass(frozen=True, slots=True)
class Principal:
    name: str
    scopes: frozenset[GatewayScope]


class GatewayAuth:
    def __init__(self, token_hash: str, scopes: frozenset[GatewayScope] | None = None):
        self._token_hash = token_hash.strip().lower()
        self._scopes = scopes or frozenset(GatewayScope)

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
            raise PermissionError("authentication required")
        if scope not in principal.scopes:
            raise PermissionError("insufficient gateway scope")
        return principal
