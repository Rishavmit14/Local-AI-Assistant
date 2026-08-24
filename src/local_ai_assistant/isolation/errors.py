"""Explicit Stage 8 isolation failures."""

from local_ai_assistant.common.errors import LocalAIError


class IsolationError(LocalAIError):
    """Base error for task isolation."""


class WorktreeIdentityError(IsolationError):
    """Persisted worktree identity does not match the requested task."""


class SandboxUnavailableError(IsolationError):
    """The required sandbox capability is unavailable."""


class CheckpointError(IsolationError):
    """A checkpoint cannot be created or restored safely."""


class PromotionError(IsolationError):
    """A worktree is not eligible for promotion."""
