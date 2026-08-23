"""Central typed tool registry and plan-bound invocation boundary."""

from __future__ import annotations

import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from local_ai_assistant.planning.analysis import is_protected_path
from local_ai_assistant.planning.models import (
    PlanningArtifact,
    ScopeGuardPolicy,
    plan_approval_token,
)

from .commands import run_allowed_command
from .errors import ToolArgumentError, ToolNotFoundError, ToolPermissionError
from .models import ToolEvent, ToolObservation, ToolPermission, ToolSpec


@dataclass(slots=True)
class ToolContext:
    repository: Path
    artifact: PlanningArtifact
    policy: ScopeGuardPolicy
    symbol_index: object
    approval_token: str | None = None
    events: list[ToolEvent] = field(default_factory=list)


Handler = Callable[[ToolContext, dict], ToolObservation]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, tuple[ToolSpec, Handler]] = {}

    def register(self, spec: ToolSpec, handler: Handler) -> None:
        if spec.name in self._tools:
            raise ValueError(f"Duplicate tool: {spec.name}")
        self._tools[spec.name] = (spec, handler)

    def specs(self) -> tuple[ToolSpec, ...]:
        return tuple(item[0] for item in self._tools.values())

    def invoke(self, name: str, arguments: dict, context: ToolContext) -> ToolObservation:
        if name not in self._tools:
            raise ToolNotFoundError(f"Unknown tool: {name}")
        spec, handler = self._tools[name]
        missing = set(spec.input_fields) - arguments.keys()
        if missing:
            raise ToolArgumentError("Missing arguments: " + ", ".join(sorted(missing)))
        started = time.monotonic()
        success = False
        affected = tuple(str(item) for item in arguments.get("affected_files", ()))
        try:
            if spec.permission is ToolPermission.BLOCKED:
                raise ToolPermissionError(f"Tool is blocked: {name}")
            if spec.mutates:
                _authorize_mutation(spec, arguments, context)
            observation = handler(context, arguments)
            success = observation.success
            return observation
        finally:
            context.events.append(
                ToolEvent(
                    context.artifact.plan.task_id,
                    plan_approval_token(context.artifact.plan),
                    str(context.repository),
                    context.artifact.starting_commit,
                    name,
                    _safe_arguments(arguments),
                    datetime.now(UTC).isoformat(),
                    round(time.monotonic() - started, 6),
                    success,
                    "completed" if success else "failed/rejected",
                    "mutation requested" if spec.mutates else "read only",
                    affected,
                    context.artifact.plan.risk.level.value,
                    context.artifact.plan.approval.status.value,
                )
            )


def _authorize_mutation(spec: ToolSpec, arguments: dict, context: ToolContext) -> None:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=context.repository, text=True, capture_output=True
    ).stdout.strip()
    if (
        Path(context.artifact.repository).resolve() != context.repository.resolve()
        or head != context.artifact.starting_commit
    ):
        raise ToolPermissionError("Plan repository or starting commit is stale")
    expected = plan_approval_token(context.artifact.plan)
    if spec.approval_required and context.approval_token != expected:
        raise ToolPermissionError("Exact plan approval token is required")
    path = arguments.get("path")
    if path:
        if Path(path).is_absolute() or ".." in Path(path).parts or is_protected_path(path):
            raise ToolPermissionError("Unsafe/protected path")
        allowed = set(context.policy.allowed_files)
        if name := arguments.get("operation"):
            allowed = set(
                context.policy.allowed_new_files
                if name == "create"
                else context.policy.allowed_deletes_or_renames
                if name in {"delete", "rename"}
                else context.policy.allowed_files
            )
        if path not in allowed:
            raise ToolPermissionError(f"Path is outside approved scope: {path}")


def _safe_arguments(arguments: dict) -> dict:
    return {
        key: (
            "[REDACTED]"
            if any(word in key.lower() for word in ("token", "password", "secret", "key"))
            else value
        )
        for key, value in arguments.items()
    }


def default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    for name in (
        "list_tree",
        "read_file",
        "read_symbol",
        "search_code",
        "find_symbol",
        "find_references",
        "find_callers",
        "find_callees",
        "find_imports",
        "find_reverse_imports",
        "repository_map",
        "git_status",
        "git_diff",
        "git_show",
        "git_log",
        "inspect_plan",
        "inspect_scope",
    ):
        registry.register(
            ToolSpec(
                name, f"Controlled {name.replace('_', ' ')}", ToolPermission.READ_ONLY, False, 15
            ),
            _readonly_handler,
        )
    for name in (
        "create_patch",
        "apply_patch",
        "create_file",
        "replace_file",
        "delete_file",
        "rename_file",
        "replace_symbol_body",
        "insert_before_symbol",
        "insert_after_symbol",
        "append_to_file",
        "revert_current_changes",
    ):
        registry.register(
            ToolSpec(
                name,
                f"Plan-bound {name.replace('_', ' ')}",
                ToolPermission.SAFE_MUTATION,
                True,
                30,
                approval_required=True,
            ),
            _mutation_placeholder,
        )
    for name in ("run_tests", "run_build", "run_lint", "run_typecheck", "run_safe_command"):
        registry.register(
            ToolSpec(
                name,
                f"Allowlisted {name.replace('_', ' ')}",
                ToolPermission.VALIDATION,
                False,
                300,
                ("command",),
            ),
            _command_handler,
        )
    return registry


def _readonly_handler(context: ToolContext, arguments: dict) -> ToolObservation:
    return ToolObservation("inspection", True, "Inspection tool accepted", {"arguments": arguments})


def _mutation_placeholder(context: ToolContext, arguments: dict) -> ToolObservation:
    return ToolObservation(
        "mutation", True, "Mutation authorized for structured executor", {"arguments": arguments}
    )


def _command_handler(context: ToolContext, arguments: dict) -> ToolObservation:
    result = run_allowed_command(
        arguments["command"], context.repository, int(arguments.get("timeout", 300))
    )
    return ToolObservation(
        "command",
        result.return_code == 0 and not result.timed_out,
        "Command completed" if result.return_code == 0 else "Command failed",
        {"return_code": result.return_code},
        result.stdout,
        result.stderr,
        result.timed_out,
    )
