"""Explicit Stage 5 failures."""

from local_ai_assistant.common.errors import LocalAIError


class ValidationIntelligenceError(LocalAIError):
    pass


class ValidationToolUnavailableError(ValidationIntelligenceError):
    pass


class ValidationArtifactError(ValidationIntelligenceError):
    pass


class TestGenerationError(ValidationIntelligenceError):
    pass


class ReviewError(ValidationIntelligenceError):
    pass
