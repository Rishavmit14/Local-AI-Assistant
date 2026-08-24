from local_ai_assistant.common.errors import LocalAIError


class HistoryError(LocalAIError):
    """Base class for task-history failures."""


class HistoryDatabaseError(HistoryError):
    """The local history database is unavailable or corrupt."""


class InvalidStatusTransition(HistoryError):
    """A task status transition violates the lifecycle."""


class ArtifactImportError(HistoryError):
    """An existing Stage 3-5 artifact is invalid or mismatched."""
