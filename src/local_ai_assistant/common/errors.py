"""Application-specific exception hierarchy."""


class LocalAIError(Exception):
    """Base class for expected Local-AI-Assistant failures."""


class ConfigurationError(LocalAIError):
    """Raised when environment or runtime configuration is invalid."""


class LLMError(LocalAIError):
    """Raised when the local model API cannot complete a request."""


class IndexingError(LocalAIError):
    """Raised when a document or repository index cannot be built or loaded."""


class ParserUnavailableError(IndexingError):
    """Raised when a requested deterministic language parser is unavailable."""


class CorruptIndexError(IndexingError):
    """Raised when persisted index state is malformed or internally inconsistent."""


class RepositoryError(LocalAIError):
    """Raised when a configured coding repository is unavailable or invalid."""


class DirtyRepositoryError(RepositoryError):
    """Raised when an automated mutation targets a dirty repository."""


class GitTransactionError(RepositoryError):
    """Raised when a Git transaction cannot be completed safely."""


class PatchValidationError(GitTransactionError):
    """Raised when a generated patch fails deterministic validation."""
