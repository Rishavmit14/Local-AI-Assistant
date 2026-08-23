"""Explicit execution and tool failures."""

from local_ai_assistant.common.errors import LocalAIError


class ToolExecutionError(LocalAIError):
    pass


class ToolNotFoundError(ToolExecutionError):
    pass


class ToolArgumentError(ToolExecutionError):
    pass


class ToolPermissionError(ToolExecutionError):
    pass


class ScopeViolationError(ToolExecutionError):
    pass


class CommandPolicyError(ToolExecutionError):
    pass


class ExecutionHistoryError(ToolExecutionError):
    pass
