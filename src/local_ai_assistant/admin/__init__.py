"""Owner Sovereign Mode administrator-execution boundary."""

from .client import AdministratorCredentialService, PrivilegedExecutor
from .models import AdminCredentialStatus, PrivilegedResult

__all__ = [
    "AdminCredentialStatus",
    "AdministratorCredentialService",
    "PrivilegedExecutor",
    "PrivilegedResult",
]
