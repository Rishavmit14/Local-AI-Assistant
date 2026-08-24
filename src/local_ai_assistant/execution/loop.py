"""Bounded model-directed tool loop over an already validated plan."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass

from local_ai_assistant.planning.models import ApprovalStatus, IssueSeverity

from .errors import ToolExecutionError
from .models import ToolObservation, ToolPermission, ToolRequest
from .registry import ToolContext, ToolRegistry


@dataclass(frozen=True, slots=True)
class LoopLimits:
    max_steps: int = 12
    max_mutations: int = 4
    max_repairs: int = 1
    max_replans: int = 1
    context_characters: int = 32_000


@dataclass(frozen=True, slots=True)
class LoopResult:
    status: str
    observations: tuple[ToolObservation, ...]
    steps: int
    mutations: int
    repairs: int
    replans: int


class ExecutionLoop:
    def __init__(
        self,
        model,
        registry: ToolRegistry,
        context: ToolContext,
        limits: LoopLimits = LoopLimits(),
        cancel_check: Callable[[], bool] | None = None,
    ) -> None:
        self.model, self.registry, self.context, self.limits = model, registry, context, limits
        self.cancel_check = cancel_check

    def run(self, *, dry_run: bool = False) -> LoopResult:
        if any(
            issue.severity is IssueSeverity.ERROR
            for issue in self.context.artifact.validation_issues
        ):
            raise ToolExecutionError("Cannot execute an invalid plan")
        if self.context.artifact.plan.approval.status is ApprovalStatus.REJECTED:
            raise ToolExecutionError("Cannot execute a policy-rejected plan")
        observations: list[ToolObservation] = []
        mutations = repairs = replans = 0
        for step in range(1, self.limits.max_steps + 1):
            if self.cancel_check and self.cancel_check():
                observations.append(
                    ToolObservation("cancelled", False, "Cooperative cancellation requested")
                )
                return LoopResult(
                    "cancelled", tuple(observations), step - 1, mutations, repairs, replans
                )
            request = self._next_request(observations)
            if request.tool == "finish":
                if dry_run:
                    return LoopResult(
                        (
                            "dry_run_complete"
                            if all(item.success for item in observations)
                            else "dry_run_failed"
                        ),
                        tuple(observations),
                        step,
                        mutations,
                        repairs,
                        replans,
                    )
                missing_commands = self._missing_validation_commands()
                if missing_commands:
                    observations.append(
                        ToolObservation(
                            "validation_required",
                            False,
                            "Plan-required validation has not run successfully: "
                            + ", ".join(missing_commands),
                        )
                    )
                    continue
                return LoopResult(
                    "complete", tuple(observations), step, mutations, repairs, replans
                )
            spec = next((item for item in self.registry.specs() if item.name == request.tool), None)
            if spec and spec.mutates != request.mutation_intended:
                observations.append(
                    ToolObservation(
                        "tool_error",
                        False,
                        "Tool mutation intent does not match registered tool metadata.",
                    )
                )
                repairs += 1
                if repairs > self.limits.max_repairs:
                    return LoopResult(
                        "max_repairs", tuple(observations), step, mutations, repairs, replans
                    )
                continue
            if spec and spec.mutates:
                mutations += 1
                if dry_run:
                    if request.tool in {"create_patch", "apply_patch"}:
                        try:
                            observations.append(
                                self.registry.invoke(
                                    "create_patch", request.arguments, self.context
                                )
                            )
                        except ToolExecutionError as exc:
                            observations.append(ToolObservation("tool_error", False, str(exc)))
                    else:
                        observations.append(
                            ToolObservation("dry_run", True, f"Would invoke {request.tool}")
                        )
                    continue
                if mutations > self.limits.max_mutations:
                    return LoopResult(
                        "max_mutations", tuple(observations), step, mutations, repairs, replans
                    )
            if dry_run and spec and spec.permission is ToolPermission.VALIDATION:
                observations.append(
                    ToolObservation("dry_run", True, f"Would invoke {request.tool}")
                )
                continue
            try:
                audit_arguments = {
                    **request.arguments,
                    "_rationale": request.rationale,
                    "_expected_outcome": request.expected_outcome,
                    "_plan_step": request.plan_step,
                    "_mutation_intended": request.mutation_intended,
                }
                observation = self.registry.invoke(request.tool, audit_arguments, self.context)
            except ToolExecutionError as exc:
                observation = ToolObservation("tool_error", False, str(exc))
            observations.append(observation)
            if not observation.success:
                if (
                    observation.kind in {"scope_rejection", "tool_error"}
                    and "scope" in observation.summary.lower()
                ):
                    replans += 1
                    if replans > self.limits.max_replans:
                        return LoopResult(
                            "max_replans", tuple(observations), step, mutations, repairs, replans
                        )
                    return LoopResult(
                        "reapproval_required",
                        tuple(observations),
                        step,
                        mutations,
                        repairs,
                        replans,
                    )
                repairs += 1
                if repairs > self.limits.max_repairs:
                    return LoopResult(
                        "max_repairs", tuple(observations), step, mutations, repairs, replans
                    )
        return LoopResult(
            "max_steps", tuple(observations), self.limits.max_steps, mutations, repairs, replans
        )

    def _missing_validation_commands(self) -> tuple[str, ...]:
        successful = {
            str(event.arguments.get("command"))
            for event in self.context.events
            if event.success and event.tool_name in {
                "run_tests",
                "run_build",
                "run_lint",
                "run_typecheck",
                "run_safe_command",
            }
        }
        return tuple(
            command
            for command in self.context.artifact.plan.validation_commands
            if command not in successful
        )

    def _next_request(self, observations: list[ToolObservation]) -> ToolRequest:
        history = [
            {"kind": item.kind, "success": item.success, "summary": item.summary}
            for item in observations[-8:]
        ]
        prompt = json.dumps(
            {
                "plan": self.context.artifact.plan.to_dict(),
                "tools": [item.name for item in self.registry.specs()],
                "observations": history,
            }
        )[: self.limits.context_characters]
        raw = self.model.chat(
            prompt=prompt,
            system_prompt="Choose one tool action. Return strict JSON with tool, arguments, rationale, expected_outcome, plan_step, mutation_intended. Use tool=finish when verified.",
            temperature=0.0,
            max_tokens=800,
        )
        try:
            return ToolRequest.from_dict(json.loads(raw))
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            raise ToolExecutionError(f"Malformed tool choice: {exc}") from exc
