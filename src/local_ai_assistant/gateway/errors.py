"""Typed external integration failures."""
from __future__ import annotations

class GitHubError(RuntimeError):
    retryable = False
    category = "remote_error"

class GitHubAuthenticationError(GitHubError):
    category = "auth"

class GitHubPermissionError(GitHubError):
    category = "permission"

class GitHubNotFoundError(GitHubError):
    category = "not_found"

class GitHubRateLimitError(GitHubError):
    retryable = True
    category = "rate_limit"

class GitHubConflictError(GitHubError):
    category = "conflict"

class GitHubValidationError(GitHubError):
    category = "validation"

class GitHubTransientError(GitHubError):
    retryable = True
    category = "transient"

class GitHubMalformedResponseError(GitHubError):
    category = "malformed_response"

class GitHubOversizedResponseError(GitHubError):
    category = "oversized_response"
