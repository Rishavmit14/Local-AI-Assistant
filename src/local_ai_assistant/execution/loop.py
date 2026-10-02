"""Bounded model-directed tool loop over an already validated plan."""

from __future__ import annotations

import json
import os
import secrets
import stat
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from local_ai_assistant.planning.models import ApprovalStatus, IssueSeverity, plan_approval_token

from .errors import ToolExecutionError
from .models import ToolEvent, ToolObservation, ToolPermission, ToolRequest
from .registry import ToolContext, ToolRegistry, _file_level_approved_symbol


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
        diagnostics_dir: Path | None = None,
    ) -> None:
        self.model, self.registry, self.context, self.limits = model, registry, context, limits
        self.cancel_check = cancel_check
        self.diagnostics_dir = diagnostics_dir

    def run(
        self,
        *,
        dry_run: bool = False,
        initial_observations: tuple[ToolObservation, ...] = (),
    ) -> LoopResult:
        if any(
            issue.severity is IssueSeverity.ERROR
            for issue in self.context.artifact.validation_issues
        ):
            raise ToolExecutionError("Cannot execute an invalid plan")
        if self.context.artifact.plan.approval.status is ApprovalStatus.REJECTED:
            raise ToolExecutionError("Cannot execute a policy-rejected plan")
        observations: list[ToolObservation] = list(initial_observations)
        mutations = repairs = replans = 0
        read_paths: set[str] = set()
        failed_validation_commands: set[str] = set()
        # A no-change plan has no patch decision for the model to make.  Execute
        # its exact approved inspection/validation contract deterministically;
        # this avoids spending every bounded loop step on a model repeatedly
        # choosing `finish` before its required read-only check has run.
        if self._report_only():
            return self._run_report_only(observations, dry_run)
        for step in range(1, self.limits.max_steps + 1):
            cancelled = self._cancelled(observations, step - 1, mutations, repairs, replans)
            if cancelled:
                return cancelled
            request = self._next_request(observations)
            cancelled = self._cancelled(observations, step, mutations, repairs, replans)
            if cancelled:
                return cancelled
            if self._test_symbol_requires_file_patch(request):
                observations.append(ToolObservation(
                    "test_symbol_requires_file_patch",
                    True,
                    "The approved test file is file-scoped and this test class/method is not an approved symbol. Use apply_patch for a focused edit to the approved test file; preserve all existing tests and change only contract-contradictory expected literals.",
                ))
                continue
            if request.tool == "read_file":
                path = str(request.arguments.get("path", ""))
                if path in read_paths:
                    observations.append(ToolObservation(
                        "duplicate_read", True,
                        "This exact file was already read without an intervening mutation; use the existing file observation.",
                    ))
                    continue
                read_paths.add(path)
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
                missing_owner_test_files = self._missing_owner_test_mutations()
                if missing_owner_test_files:
                    observations.append(ToolObservation(
                        "owner_requirement_required", True,
                        "The owner explicitly requested test changes in approved files; mutate these before finishing: "
                        + ", ".join(missing_owner_test_files),
                    ))
                    continue
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
                required = set(self._required_inspections())
                inspected = {
                    item.summary for item in observations
                    if item.kind == "file" and item.success
                }
                missing_inspections = sorted(required - inspected)
                if missing_inspections:
                    observations.append(ToolObservation(
                        "inspection_required", True,
                        "Read all approved acceptance files before mutation: "
                        + ", ".join(missing_inspections),
                    ))
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
            if spec and spec.permission is ToolPermission.VALIDATION:
                missing_owner_test_files = self._missing_owner_test_mutations()
                if missing_owner_test_files:
                    observations.append(ToolObservation(
                        "owner_requirement_required", True,
                        "The owner explicitly requested test additions or expansion; do not validate "
                        "until an approved mutation updates: " + ", ".join(missing_owner_test_files),
                    ))
                    continue
            command = request.arguments.get("command")
            try:
                if (
                    spec and spec.permission is ToolPermission.VALIDATION
                    and isinstance(command, str) and command in failed_validation_commands
                ):
                    observation = ToolObservation(
                        "tool_error", False,
                        "This exact validator already failed without an intervening successful mutation. "
                        "Inspect its failure output and make an approved correction before rerunning it.",
                    )
                else:
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
            if spec and spec.permission is ToolPermission.VALIDATION and isinstance(command, str):
                if observation.success:
                    failed_validation_commands.discard(command)
                else:
                    failed_validation_commands.add(command)
            if spec and spec.mutates and observation.success:
                failed_validation_commands.clear()
            observations.append(observation)
            if (
                observation.success
                and spec
                and spec.permission is ToolPermission.VALIDATION
                and not self._missing_validation_commands()
                and not self.context.artifact.plan.files_to_delete_or_rename
                and all(
                    (self.context.repository / path).is_file()
                    for path in self.context.artifact.plan.files_to_create
                )
                and self._repeated_validation_without_edit(request)
            ):
                return LoopResult(
                    "complete", tuple(observations), step, mutations, repairs, replans
                )
            cancelled = self._cancelled(observations, step, mutations, repairs, replans)
            if cancelled:
                return cancelled
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

    def _report_only(self) -> bool:
        plan = self.context.artifact.plan
        return not any(
            (plan.files_to_modify, plan.files_to_create, plan.files_to_delete_or_rename)
        )

    def _run_report_only(self, observations: list[ToolObservation], dry_run: bool) -> LoopResult:
        plan = self.context.artifact.plan
        requests = [
            ToolRequest(
                "read_file",
                {"path": path},
                "Approved report-only inspection",
                "Read approved file",
                index,
                False,
            )
            for index, path in enumerate(plan.files_to_inspect, start=1)
        ]
        requests.extend(
            ToolRequest(
                "run_safe_command",
                {"command": command},
                "Approved report-only validation",
                "Run exact approved check",
                len(requests) + index,
                False,
            )
            for index, command in enumerate(plan.validation_commands, start=1)
        )
        for step, request in enumerate(requests, start=1):
            cancelled = self._cancelled(observations, step - 1, 0, 0, 0)
            if cancelled:
                return cancelled
            if dry_run and request.tool == "run_safe_command":
                observations.append(ToolObservation("dry_run", True, f"Would invoke {request.tool}"))
            else:
                try:
                    observations.append(
                        self.registry.invoke(
                            request.tool,
                            {
                                **request.arguments,
                                "_rationale": request.rationale,
                                "_expected_outcome": request.expected_outcome,
                                "_plan_step": request.plan_step,
                                "_mutation_intended": False,
                            },
                            self.context,
                        )
                    )
                except ToolExecutionError as exc:
                    observations.append(ToolObservation("tool_error", False, str(exc)))
            if not observations[-1].success:
                return LoopResult("max_repairs", tuple(observations), step, 0, 1, 0)
        return LoopResult(
            "dry_run_complete" if dry_run else "complete",
            tuple(observations),
            len(requests),
            0,
            0,
            0,
        )

    def _cancelled(
        self,
        observations: list[ToolObservation],
        steps: int,
        mutations: int,
        repairs: int,
        replans: int,
    ) -> LoopResult | None:
        if not self.cancel_check or not self.cancel_check():
            return None
        observations.append(
            ToolObservation("cancelled", False, "Cooperative cancellation requested")
        )
        return LoopResult(
            "cancelled", tuple(observations), steps, mutations, repairs, replans
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

    def _repeated_validation_without_edit(self, request: ToolRequest) -> bool:
        successful = [
            (index, event)
            for index, event in enumerate(self.context.events)
            if event.success
            and event.tool_name in {
                "run_tests",
                "run_build",
                "run_lint",
                "run_typecheck",
                "run_safe_command",
            }
        ]
        if len(successful) < 2:
            return False
        previous_index, previous = successful[-2]
        current = successful[-1][1]
        if (
            previous.tool_name != request.tool
            or current.tool_name != request.tool
            or previous.arguments.get("command") != request.arguments.get("command")
            or current.arguments.get("command") != request.arguments.get("command")
        ):
            return False
        return not any(
            event.success and event.mutation_summary == "mutation requested"
            for event in self.context.events[previous_index + 1 : -1]
        )

    def _next_request(self, observations: list[ToolObservation]) -> ToolRequest:
        recent = observations[-8:]
        data_start = max(0, len(recent) - 2)
        binding_files = set(self._required_inspections())
        owner_contracts = [
            {"path": item.summary, "content": item.data["content"][:6_000]}
            for item in observations
            if item.kind == "file"
            and item.success
            and item.summary in binding_files
            and isinstance(item.data.get("content"), str)
        ]
        history = []
        for index, item in enumerate(recent):
            entry = {"kind": item.kind, "success": item.success, "summary": item.summary}
            if item.data and index >= data_start:
                encoded = json.dumps(item.data, ensure_ascii=False, sort_keys=True)
                entry["data"] = item.data if len(encoded) <= 8_000 else {
                    "truncated_json": encoded[:8_000] + "...[truncated]"
                }
            history.append(entry)
        prompt = json.dumps(
            {
                "plan": self.context.artifact.plan.to_dict(),
                "tools": [
                    {
                        "name": item.name,
                        "description": item.description,
                        "input_fields": list(item.input_fields),
                        "permission": item.permission.value,
                        "mutates": item.mutates,
                    }
                    for item in self.registry.specs()
                ],
                "symbol_scoped_files": list(self.context.policy.symbol_scoped_files),
                "owner_binding_files": owner_contracts,
                "observations": history,
            }
        )[: self.limits.context_characters]
        system_prompt = (
            "Choose one tool action from the supplied tool schemas. The arguments object "
            "must contain exactly that tool's listed input_fields; do not add reason, "
            "description, or other parameters. Return strict JSON with tool, arguments, "
            "rationale, expected_outcome, plan_step, mutation_intended. "
            "For replace_symbol_body, content should contain only body statements without "
            "a def/class header or signature. Keep the existing signature unchanged. "
            "Never put a nested def/class with the target name inside a replacement body. "
            "For tests, use replace_symbol_body only for an exact test symbol listed in "
            "symbols_to_modify. If a test file is approved but its class/method is not "
            "listed, use apply_patch for a focused edit within that exact file. Never "
            "replace an unlisted test class or a whole test module. Preserve every "
            "existing test and change only contract-contradictory expected literals. "
            "After a scope_rejection, the rejected mutation was rolled back and earlier "
            "approved edits were preserved; do not repeat the rejected content, inspect "
            "the current file if needed, and choose a corrected in-scope action. If the "
            "rejection names the target symbol as an unplanned new symbol, remove any "
            "duplicate or nested definition and submit only that symbol's body statements. "
            "After a mutation_rejected observation, no write occurred; correct the syntax "
            "or signature issue before choosing another action. "
            "To create a symbol listed in symbols_to_create inside a symbol-scoped file, "
            "use insert_before_symbol or insert_after_symbol anchored to an existing "
            "approved symbol in that file, with the complete new definition as content. "
            "Do not use replace_symbol_body or a module symbol to create a new symbol. "
            "Set mutation_intended "
            "to match the registered mutates value. Use returned observation data when deciding "
            "the next action. Do not repeat an unchanged read_file request; use its returned "
            "content to continue the approved plan. Use tool=finish only after all required "
            "mutations and validation commands are complete. Keep rationale and expected_outcome "
            "under 120 characters each. The owner's original_request and explicitly referenced "
            "acceptance documents are binding; generated plan steps are sequence guidance and "
            "must not narrow or contradict them. Resolve conflicts within the exact approved "
            "scope, or stop safely if that is impossible. Return one compact JSON object with "
            "no surrounding prose."
        )
        original_request = self.context.artifact.plan.original_request.lower()
        approved_modifications = set(self.context.artifact.plan.files_to_modify)
        requested_test_paths = sorted(
            path for path in approved_modifications
            if "test" in path.lower() and path.lower() in original_request
        )
        if requested_test_paths and any(
            token in original_request for token in ("expand", "add", "update", "extend")
        ):
            system_prompt += (
                " The owner's request explicitly requires test additions or expansion in "
                + json.dumps(requested_test_paths)
                + ". Make those approved test changes even if a generated plan step says to "
                "preserve existing assertions. If an assertion conflicts with the referenced "
                "acceptance contract, correct it to match that contract and retain or add meaningful "
                "coverage; never delete or weaken coverage. Create each planned file and run the "
                "exact owner-requested full-suite command."
            )
        last_mutation = max(
            (i for i, item in enumerate(observations) if item.kind == "mutation" and item.success),
            default=-1,
        )
        if any(
            i > last_mutation and item.kind == "tool_error"
            and "command failed" in item.summary.lower()
            for i, item in enumerate(observations)
        ):
            system_prompt += (
                " The last required validator failed. Do not repeat it without an intervening "
                "successful approved mutation. Use its failure output to make one minimal scoped "
                "correction, then rerun the exact required command."
            )
        if any(item.kind == "mutation" and item.success for item in observations):
            system_prompt += (
                " A scoped edit has already succeeded. Review its current_source observation, "
                "then run the plan-required validation command before making another edit. "
                "Only edit again if validation provides a concrete defect to fix."
            )
        if (
            not self._missing_validation_commands()
            and all(
                (self.context.repository / path).is_file()
                for path in self.context.artifact.plan.files_to_create
            )
        ):
            system_prompt += (
                " Every plan-required validation command has succeeded and every planned "
                "creation exists. Select finish now; do not repeat successful validation."
            )
        if self.context.artifact.plan.symbols_to_create and any(
            item.kind == "tool_error"
            and "exactly one function" in item.summary.lower()
            for item in observations
        ):
            system_prompt += (
                " The prior replace_symbol_body request contained more than one function and "
                "was rejected. Do not repeat it. Create the planned symbol using "
                "insert_before_symbol or insert_after_symbol with exactly one complete new "
                "definition anchored to an approved existing symbol; then edit the existing "
                "function body separately."
            )
        inspected_files = {
            item.summary for item in observations
            if item.kind == "file" and item.success
        }
        if inspected_files:
            system_prompt += (
                " Already-read files: " + json.dumps(sorted(inspected_files))
                + ". Do not call read_file for these paths; use their supplied content."
            )
        required_inspections = set(self._required_inspections())
        missing_inspections = sorted(required_inspections - inspected_files)
        if missing_inspections:
            system_prompt += (
                " Before any mutation, read every remaining required contract with read_file: "
                + json.dumps(missing_inspections)
                + ". Do not mutate until those file contents are supplied."
            )
        if required_inspections and required_inspections.issubset(inspected_files):
            system_prompt += (
                " Every approved files_to_inspect target is already supplied. Choose a "
                "bounded approved edit now; do not request more file reads."
            )
        response_format = self._tool_choice_schema()
        raw = self.model.chat(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.0,
            max_tokens=4096,
            response_format=response_format,
        )
        response_metadata = [dict(self._last_response_metadata())]
        corrective = False
        try:
            if self._last_response_metadata().get("finish_reason") == "length":
                raise ValueError("tool-choice response was truncated at the configured token limit")
            request = self._decode_tool_request(raw)
        except (json.JSONDecodeError, ValueError, TypeError, AttributeError) as exc:
            # Local model output is untrusted at this boundary.  A single,
            # deterministic corrective retry is enough to repair harmless
            # serialization drift without relaxing the tool request schema.
            correction = (
                "Your immediately preceding response was rejected: "
                f"{str(exc)[:240]}. Return only one corrected JSON object matching "
                "the required schema. plan_step must be a JSON integer (for example, "
                "1), not a string, decimal, list, or object. Keep rationale and expected_outcome "
                "under 120 characters each and return one compact JSON object."
            )
            retry_raw = self.model.chat(
                prompt=f"{prompt}\n{correction}",
                system_prompt=system_prompt,
                temperature=0.0,
                max_tokens=4096,
                response_format=response_format,
            )
            response_metadata.append(dict(self._last_response_metadata()))
            try:
                if self._last_response_metadata().get("finish_reason") == "length":
                    raise ValueError("corrective tool-choice response was truncated at the configured token limit")
                request = self._decode_tool_request(retry_raw)
                raw = retry_raw
                corrective = True
            except (json.JSONDecodeError, ValueError, TypeError, AttributeError) as retry_exc:
                self._capture_invalid_tool_choice(prompt, system_prompt, response_format, raw, retry_raw, response_metadata)
                raise ToolExecutionError(
                    "Malformed tool choice after bounded corrective retry: "
                    f"{retry_exc}"
                ) from retry_exc
        metadata = self._last_response_metadata()
        response_format = metadata.get("response_format")
        response_format_type = response_format.get("type") if isinstance(response_format, dict) else None
        schema = response_format.get("json_schema") if isinstance(response_format, dict) else None
        scope_mapping = {}
        path = request.arguments.get("path")
        symbol = request.arguments.get("symbol") or request.arguments.get("symbol_name")
        if isinstance(path, str) and path in self.context.policy.symbol_scoped_files:
            scope_mapping = {"path": path, "symbol": symbol if isinstance(symbol, str) else None,
                             "scope": "approved_symbol"}
        elif isinstance(symbol, str):
            indexed_symbols = getattr(self.context.symbol_index, "symbols", ())
            indexed = next((item for item in indexed_symbols
                            if symbol in {getattr(item, "identifier", None), getattr(item, "qualified_name", None)}), None)
            scope_mapping = {
                "path": getattr(indexed, "path", None),
                "symbol": symbol,
                "scope": "approved_symbol" if symbol in self.context.policy.allowed_symbols else "unapproved_symbol",
            }
        self.context.tool_choice_metadata = {
            "finish_reason": metadata.get("finish_reason"),
            "response_characters": len(raw),
            "response_format_type": response_format_type,
            "schema_name": schema.get("name") if isinstance(schema, dict) else None,
            "corrective_retry": corrective,
            "parsed_tool": request.tool,
            "plan_step": request.plan_step,
            "argument_names": sorted(request.arguments),
            "scope_mapping": scope_mapping,
        }
        if request.tool == "finish":
            plan = self.context.artifact.plan
            self.context.events.append(ToolEvent(
                task_id=plan.task_id,
                plan_hash=plan_approval_token(plan),
                repository=str(self.context.repository),
                starting_commit=self.context.artifact.starting_commit,
                tool_name="model_tool_choice",
                arguments={"tool": request.tool, "plan_step": request.plan_step},
                timestamp=datetime.now(UTC).isoformat(),
                duration_seconds=0,
                success=True,
                output_summary="Validated structured tool choice",
                mutation_summary="no mutation",
                affected_files=(),
                risk=plan.risk.level.value,
                approval=plan.approval.status.value,
                decision_metadata=dict(self.context.tool_choice_metadata),
            ))
        return request

    def _required_inspections(self) -> tuple[str, ...]:
        paths = set(self.context.artifact.plan.files_to_inspect)
        # A named repository acceptance contract is an owner-authored input,
        # even if the generated plan omitted it from its suggested inspections.
        original_request = self.context.artifact.plan.original_request.lower()
        if "acceptance.md" in original_request and (self.context.repository / "ACCEPTANCE.md").is_file():
            paths.add("ACCEPTANCE.md")
        return tuple(sorted(paths))

    def _test_symbol_requires_file_patch(self, request: ToolRequest) -> bool:
        if request.tool != "replace_symbol_body":
            return False
        value = request.arguments.get("symbol")
        if not isinstance(value, str):
            return False
        plan = self.context.artifact.plan
        original_request = plan.original_request.lower()
        requested_test_files = {
            Path(path).name.lower()
            for path in plan.files_to_modify
            if Path(path).name.lower().startswith("test_")
            and Path(path).name.lower() in original_request
        }
        if not requested_test_files or not any(
            word in original_request for word in ("expand", "add", "extend", "update")
        ):
            return False
        return not any(
            value == approved
            or value.endswith("." + approved)
            or approved.endswith("." + value)
            for approved in plan.symbols_to_modify
        )

    def _missing_owner_test_mutations(self) -> tuple[str, ...]:
        request = self.context.artifact.plan.original_request.lower()
        if not any(term in request for term in ("expand", "add", "update", "extend")):
            return ()
        requested = {
            path for path in self.context.artifact.plan.files_to_modify
            if "test" in path.lower() and Path(path).name.lower() in request
        }
        changed = {
            path for event in self.context.events
            if event.success and event.mutation_summary == "mutation requested"
            for path in event.affected_files
        }
        return tuple(sorted(requested - changed))

    def _decode_tool_request(self, raw: str) -> ToolRequest:
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("tool choice must be a JSON object")
        request = ToolRequest.from_dict(value)
        if request.tool == "finish":
            if request.arguments:
                raise ValueError("finish arguments must be an empty object")
            if request.mutation_intended:
                raise ValueError("finish mutation_intended must be false")
            return request
        spec = next((item for item in self.registry.specs() if item.name == request.tool), None)
        if spec is None:
            raise ValueError("tool must name a registered action")
        required = set(spec.input_fields)
        allowed = required | ({"timeout"} if spec.permission is ToolPermission.VALIDATION else set())
        missing = required - request.arguments.keys()
        unexpected = request.arguments.keys() - allowed
        if missing or unexpected:
            issues = []
            if missing:
                issues.append("missing arguments: " + ", ".join(sorted(missing)))
            if unexpected:
                issues.append("unexpected arguments: " + ", ".join(sorted(unexpected)))
            raise ValueError(f"{request.tool} " + "; ".join(issues))
        for name in spec.input_fields:
            if not isinstance(request.arguments[name], str):
                raise ValueError(f"{request.tool} argument {name!r} must be a string")
        timeout = request.arguments.get("timeout")
        if timeout is not None and (
            isinstance(timeout, bool) or not isinstance(timeout, int) or timeout < 1
        ):
            raise ValueError("validation timeout must be a positive integer")
        if request.mutation_intended is not spec.mutates:
            raise ValueError("mutation_intended must match registered tool metadata")
        path = request.arguments.get("path")
        if (
            request.tool in {"replace_file", "append_to_file"}
            and path in self.context.policy.symbol_scoped_files
        ):
            raise ValueError(
                f"{request.tool} cannot edit symbol-scoped path {path}; use "
                "replace_symbol_body or apply_patch within the approved symbol"
            )
        symbol = request.arguments.get("symbol")
        approved_aliases = {
            alias
            for candidate in (*self.context.artifact.plan.direct_scope,
                              *self.context.artifact.plan.dependent_scope)
            if candidate.path in self.context.policy.symbol_scoped_files
            and (candidate.symbol_id in self.context.artifact.plan.symbols_to_modify
                 or candidate.qualified_name in self.context.artifact.plan.symbols_to_modify)
            for alias in (candidate.symbol_id, candidate.qualified_name)
            if alias
        }
        approved_qualified_suffix = bool(symbol and any(
            alias.endswith("." + symbol) for alias in approved_aliases
        ))
        if (symbol and symbol not in self.context.policy.allowed_symbols
                and symbol not in approved_aliases and not approved_qualified_suffix
                and not _file_level_approved_symbol(self.context, symbol)):
            raise ValueError(
                f"symbol {symbol} is outside approved scope; for an approved new symbol, "
                "use insert_before_symbol or insert_after_symbol anchored to an existing "
                "approved symbol in the same file"
            )
        return request

    def _tool_choice_schema(self) -> dict[str, object]:
        fields = {
            "tool": {"type": "string", "enum": ["finish", *(item.name for item in self.registry.specs())]},
            "arguments": {"type": "object"},
            "rationale": {"type": "string", "maxLength": 120},
            "expected_outcome": {"type": "string", "maxLength": 120},
            "plan_step": {"type": "integer"},
            "mutation_intended": {"type": "boolean"},
        }
        return {"type": "json_schema", "json_schema": {
            "name": "friday_tool_choice", "strict": True,
            "schema": {"type": "object", "properties": fields,
                       "required": list(fields), "additionalProperties": False},
        }}

    def _last_response_metadata(self) -> dict[str, object]:
        orchestrator = getattr(self.model, "_orchestrator", None)
        # RoleClient keeps the actual model on RoleOrchestrator.model. Read
        # metadata from that same model so truncation and schema evidence are
        # enforced in the production role-routed execution path.
        model = getattr(orchestrator, "model", getattr(orchestrator, "llm", self.model))
        metadata = getattr(model, "last_response_metadata", {})
        return metadata if isinstance(metadata, dict) else {}

    def _capture_invalid_tool_choice(self, prompt, system_prompt, response_format, raw, retry_raw, response_metadata) -> None:
        """Keep malformed model data private and mode-restricted for diagnosis."""
        if self.diagnostics_dir is None:
            return
        directory = self.diagnostics_dir
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.chmod(0o700)
        payload = {
            "prompt": prompt, "system_prompt": system_prompt,
            "response_format": response_format,
            "responses": [{"raw": raw, "characters": len(raw)},
                          {"raw": retry_raw, "characters": len(retry_raw)}],
            "response_metadata": response_metadata,
            "max_tokens": 4096,
            "stop_sequences": [],
            "parser": "json.loads then ToolRequest.from_dict; fail closed",
        }
        destination = directory / f"tool-choice-invalid-{secrets.token_hex(8)}.json"
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, stat.S_IRUSR | stat.S_IWUSR)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False)
