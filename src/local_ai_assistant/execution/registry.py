"""Central typed tool registry and plan-bound invocation boundary."""

from __future__ import annotations

import ast
import hashlib
import subprocess
import tempfile
import textwrap
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path

from local_ai_assistant.common.errors import PatchValidationError
from local_ai_assistant.planning.analysis import is_protected_path
from local_ai_assistant.planning.models import (
    ApprovalStatus,
    PlanningArtifact,
    ScopeGuardPolicy,
    plan_approval_token,
)
from local_ai_assistant.planning.patch_scope import (
    extract_patch_scope,
    validate_patch_scope,
    worktree_diff,
)

from .commands import run_allowed_command
from .errors import ToolArgumentError, ToolExecutionError, ToolNotFoundError, ToolPermissionError
from .models import ToolEvent, ToolObservation, ToolPermission, ToolSpec


@dataclass(slots=True)
class ToolContext:
    repository: Path
    artifact: PlanningArtifact
    policy: ScopeGuardPolicy
    symbol_index: object
    approval_token: str | None = None
    events: list[ToolEvent] = field(default_factory=list)
    sandbox: object | None = None
    sandbox_task_root: Path | None = None
    sandbox_resources: object | None = None
    sandbox_network: object | None = None
    cancel_check: Callable[[], bool] | None = None
    canonical_repository: Path | None = None
    attempt_id: str | None = None
    tool_choice_metadata: dict = field(default_factory=dict)


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
            if context is not None:
                context.events.append(
                    _event(context, name, arguments, 0.0, False, "unknown tool rejected", False)
                )
            raise ToolNotFoundError(f"Unknown tool: {name}")
        spec, handler = self._tools[name]
        started = time.monotonic()
        success = False
        observation = None
        failure_summary = None
        if not isinstance(arguments, dict):
            context.events.append(
                _event(context, name, {}, 0.0, False, "invalid arguments rejected", spec.mutates)
            )
            raise ToolArgumentError("Tool arguments must be an object")
        affected = tuple(
            dict.fromkeys(
                str(item)
                for item in (
                    *arguments.get("affected_files", ()),
                    arguments.get("path"),
                    arguments.get("destination"),
                )
                if item
            )
        )
        try:
            missing = set(spec.input_fields) - arguments.keys()
            if missing:
                raise ToolArgumentError("Missing arguments: " + ", ".join(sorted(missing)))
            allowed_arguments = set(spec.input_fields) | {
                "_rationale",
                "_expected_outcome",
                "_plan_step",
                "_mutation_intended",
            }
            if spec.permission is ToolPermission.VALIDATION:
                allowed_arguments.add("timeout")
            unexpected = arguments.keys() - allowed_arguments
            if unexpected:
                raise ToolArgumentError(
                    "Unexpected arguments: " + ", ".join(sorted(unexpected))
                )
            for field_name in spec.input_fields:
                if not isinstance(arguments[field_name], str):
                    raise ToolArgumentError(f"Argument {field_name!r} must be a string")
            if "timeout" in arguments and (
                isinstance(arguments["timeout"], bool)
                or not isinstance(arguments["timeout"], int)
                or arguments["timeout"] < 1
            ):
                raise ToolArgumentError("Argument 'timeout' must be a positive integer")
            if spec.permission is ToolPermission.BLOCKED:
                raise ToolPermissionError(f"Tool is blocked: {name}")
            if spec.mutates:
                _authorize_mutation(spec, arguments, context)
            observation = handler(context, arguments)
            success = observation.success
            affected = tuple(
                dict.fromkeys(
                    item
                    for item in (
                        *affected,
                        *observation.data.get("files", ()),
                        observation.data.get("path"),
                    )
                    if item
                )
            )
            return observation
        except ToolExecutionError as exc:
            if spec.mutates:
                _rollback_worktree(context.repository)
            failure_summary = f"{type(exc).__name__}: {exc}"[:500]
            raise
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            if spec.mutates:
                _rollback_worktree(context.repository)
            wrapped = ToolExecutionError(f"Tool {name} failed safely: {exc}")
            failure_summary = f"{type(wrapped).__name__}: {wrapped}"[:500]
            raise wrapped from exc
        except Exception as exc:
            # Execution reports deliberately redact tool input content. Preserve
            # the bounded failure class/message separately so rejected mutations
            # can be diagnosed without retaining their source payload.
            failure_summary = f"{type(exc).__name__}: {exc}"[:500]
            raise
        finally:
            if not success and observation is None and failure_summary is None:
                # ToolExecutionError and wrapped operational errors are also
                # useful audit evidence; avoid logging arguments or content.
                failure_summary = "tool invocation rejected"
            context.events.append(
                _event(
                    context,
                    name,
                    arguments,
                    round(time.monotonic() - started, 6),
                    success,
                    (
                        failure_summary
                        if failure_summary
                        else
                        (observation.summary + " " + observation.stderr[:500]).strip()
                        if observation
                        else "failed/rejected"
                    ),
                    spec.mutates,
                    affected,
                )
            )


def _event(
    context: ToolContext,
    name: str,
    arguments: dict,
    duration: float,
    success: bool,
    summary: str,
    mutates: bool,
    affected: tuple[str, ...] = (),
) -> ToolEvent:
    return ToolEvent(
        context.artifact.plan.task_id,
        plan_approval_token(context.artifact.plan),
        str(context.repository),
        context.artifact.starting_commit,
        name,
        _safe_arguments(arguments),
        datetime.now(UTC).isoformat(),
        duration,
        success,
        summary,
        "mutation requested" if mutates else "read only/rejected",
        affected,
        context.artifact.plan.risk.level.value,
        context.artifact.plan.approval.status.value,
        dict(context.tool_choice_metadata),
    )


def _authorize_mutation(spec: ToolSpec, arguments: dict, context: ToolContext) -> None:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=context.repository, text=True, capture_output=True
    ).stdout.strip()
    if (
        Path(context.artifact.repository).resolve()
        != (context.canonical_repository or context.repository).resolve()
        or head != context.artifact.starting_commit
    ):
        raise ToolPermissionError("Plan repository or starting commit is stale")
    expected = plan_approval_token(context.artifact.plan)
    if context.artifact.plan.approval.status is ApprovalStatus.REJECTED:
        raise ToolPermissionError("Policy-rejected plans cannot authorize mutations")
    if (
        spec.approval_required
        and (
            context.artifact.plan.approval.status is not ApprovalStatus.AUTOMATIC
            or spec.permission is ToolPermission.HIGH_RISK
        )
        and context.approval_token != expected
    ):
        raise ToolPermissionError("Exact plan approval token is required")
    path = arguments.get("path")
    if path:
        if Path(path).is_absolute() or ".." in Path(path).parts or is_protected_path(path):
            raise ToolPermissionError("Unsafe/protected path")
        allowed = set(context.policy.allowed_files)
        name = spec.name
        if name:
            allowed = set(
                context.policy.allowed_new_files
                if name == "create_file"
                else context.policy.allowed_deletes_or_renames
                if name in {"delete_file", "rename_file"}
                else context.policy.allowed_files
            )
        if path not in allowed:
            raise ToolPermissionError(f"Path is outside approved scope: {path}")
    if spec.name == "rename_file" and arguments.get("destination") not in set(
        context.policy.allowed_deletes_or_renames
    ):
        raise ToolPermissionError("Rename destination is outside approved scope")
    symbol = arguments.get("symbol")
    if (symbol and symbol not in set(context.policy.allowed_symbols)
            and not _file_level_approved_symbol(context, symbol)):
        raise ToolPermissionError(f"Symbol is outside approved scope: {symbol}")


def _safe_arguments(arguments: dict) -> dict:
    safe = {}
    for key, value in arguments.items():
        lowered = key.lower()
        if any(word in lowered for word in ("token", "password", "secret", "key")):
            safe[key] = "[REDACTED]"
        elif key in {"patch", "content"} and isinstance(value, str):
            safe[key] = {
                "sha256": hashlib.sha256(value.encode()).hexdigest(),
                "characters": len(value),
            }
        else:
            safe[key] = value
    return safe


def default_registry(execution_config=None) -> ToolRegistry:
    registry = ToolRegistry()
    read_tools = {
        "list_tree": (),
        "read_file": ("path",),
        "read_symbol": ("symbol",),
        "search_code": ("query",),
        "find_symbol": ("symbol",),
        "find_references": ("symbol",),
        "find_callers": ("symbol",),
        "find_callees": ("symbol",),
        "find_imports": ("module",),
        "find_reverse_imports": ("module",),
        "repository_map": (),
        "git_status": (),
        "git_diff": (),
        "git_show": (),
        "git_log": (),
        "inspect_plan": (),
        "inspect_scope": (),
    }
    for name, fields in read_tools.items():
        registry.register(
            ToolSpec(
                name,
                f"Controlled {name.replace('_', ' ')}",
                ToolPermission.READ_ONLY,
                False,
                15,
                fields,
            ),
            _handler_for_read(name),
        )
    mutations = {
        "create_patch": ("patch",),
        "apply_patch": ("patch",),
        "create_file": ("path", "content"),
        "replace_file": ("path", "content"),
        "delete_file": ("path",),
        "rename_file": ("path", "destination"),
        "replace_symbol_body": ("symbol", "content"),
        "insert_before_symbol": ("symbol", "content"),
        "insert_after_symbol": ("symbol", "content"),
        "append_to_file": ("path", "content"),
        "revert_current_changes": (),
    }
    for name, fields in mutations.items():
        registry.register(
            ToolSpec(
                name,
                f"Plan-bound {name.replace('_', ' ')}",
                (
                    ToolPermission.HIGH_RISK
                    if name in {"delete_file", "rename_file", "revert_current_changes"}
                    else ToolPermission.SAFE_MUTATION
                ),
                True,
                30,
                fields,
                approval_required=True,
                risk_level=(
                    "high"
                    if name in {"delete_file", "rename_file", "revert_current_changes"}
                    else "medium"
                ),
            ),
            _handler_for_mutation(name),
        )
    for name in ("run_tests", "run_build", "run_lint", "run_typecheck", "run_safe_command"):
        timeout = (
            getattr(execution_config, "test_timeout_seconds", 900)
            if name == "run_tests"
            else getattr(execution_config, "build_timeout_seconds", 900)
            if name == "run_build"
            else getattr(execution_config, "lint_timeout_seconds", 180)
            if name in {"run_lint", "run_typecheck"}
            else getattr(execution_config, "inspection_timeout_seconds", 15)
        )
        registry.register(
            ToolSpec(
                name,
                f"Allowlisted {name.replace('_', ' ')}",
                ToolPermission.VALIDATION,
                False,
                timeout,
                ("command",),
                risk_level="medium",
            ),
            _handler_for_command(timeout),
        )
    return registry


def _handler_for_read(name: str) -> Handler:
    def handler(context: ToolContext, arguments: dict) -> ToolObservation:
        repo, index = context.repository, context.symbol_index
        if name == "list_tree":
            paths = sorted(
                p.relative_to(repo).as_posix() for p in repo.rglob("*") if ".git" not in p.parts
            )[:500]
            return ToolObservation("tree", True, f"{len(paths)} paths", {"paths": paths})
        if name == "read_file":
            path = _safe_path(repo, arguments["path"])
            return ToolObservation(
                "file",
                True,
                arguments["path"],
                {"content": path.read_text(encoding="utf-8", errors="replace")[:50_000]},
            )
        if name in {"read_symbol", "find_symbol"}:
            found = _local_symbols(context, index.find_exact(arguments["symbol"]))
            data = [
                {
                    "identifier": item.identifier,
                    "path": item.path,
                    "name": item.qualified_name,
                    "source": item.source[:20_000],
                }
                for item in found
            ]
            return ToolObservation("symbols", True, f"{len(data)} symbols", {"symbols": data})
        if name == "repository_map":
            prefix = _index_prefix(context)
            repository_map = index.repository_map()
            if prefix:
                repository_map = {
                    path[len(prefix) :]: value
                    for path, value in repository_map.items()
                    if path.startswith(prefix)
                }
            return ToolObservation(
                "repository_map", True, "Repository map", {"map": repository_map}
            )
        if name == "search_code":
            found = index.hybrid_search(arguments["query"], 10)
            return ToolObservation(
                "search",
                True,
                f"{len(found)} results",
                {
                    "results": [
                        {
                            "identifier": item["symbol"].identifier,
                            "path": item["symbol"].path,
                            "score": item["hybrid_score"],
                        }
                        for item in found
                        if item["symbol"] in _local_symbols(context, (item["symbol"],))
                    ]
                },
            )
        if name in {"find_references", "find_callers", "find_callees"}:
            symbol = _resolve_symbol(context, arguments["symbol"])
            values = (
                index.references_to(symbol.identifier)
                if name == "find_references"
                else index.callers(symbol.identifier)
                if name == "find_callers"
                else index.callees(symbol.identifier)
            )
            prefix = _index_prefix(context)
            values = [
                item
                for item in values
                if not prefix or getattr(item, "path", "").startswith(prefix)
            ]
            return ToolObservation(
                "graph", True, f"{len(values)} results", {"results": [str(item) for item in values]}
            )
        if name in {"find_imports", "find_reverse_imports"}:
            local_modules = {
                item.qualified_name
                for item in _local_symbols(context, index.symbols)
                if item.kind.value == "module"
            }
            if arguments["module"] not in local_modules:
                raise ToolArgumentError("Module is outside the active repository")
            values = (
                index.imports_of(arguments["module"])
                if name == "find_imports"
                else index.imported_by(arguments["module"])
            )
            if name == "find_reverse_imports":
                values = [item for item in values if item in local_modules]
            return ToolObservation("imports", True, f"{len(values)} results", {"results": values})
        if name == "inspect_plan":
            return ToolObservation(
                "plan",
                True,
                context.artifact.plan.summary,
                {"plan": context.artifact.plan.to_dict()},
            )
        if name == "inspect_scope":
            return ToolObservation("scope", True, "Approved scope", {"policy": str(context.policy)})
        git_commands = {
            "git_status": ["git", "status", "--short"],
            "git_diff": ["git", "diff"],
            "git_show": ["git", "show", "--stat", "HEAD"],
            "git_log": ["git", "log", "-10", "--oneline"],
        }
        if name in git_commands:
            result = subprocess.run(git_commands[name], cwd=repo, text=True, capture_output=True)
            return ToolObservation(
                "git",
                result.returncode == 0,
                name,
                stdout=result.stdout[:50_000],
                stderr=result.stderr[:10_000],
            )
        return ToolObservation("inspection", True, name, {"arguments": arguments})

    return handler


def _handler_for_mutation(name: str) -> Handler:
    def handler(context: ToolContext, arguments: dict) -> ToolObservation:
        if name in {"create_patch", "apply_patch"}:
            before_diff = worktree_diff(context.repository)
            try:
                scope = extract_patch_scope(
                    arguments["patch"], tuple(context.symbol_index.symbols), _index_prefix(context)
                )
            except PatchValidationError as exc:
                # A malformed model patch is a bounded tool rejection, not a
                # worker-fatal error. No file has been changed at this point.
                return ToolObservation("patch_rejection", False, "Patch could not be parsed", stderr=str(exc))
            for candidate in (
                *scope.changed_files,
                *(old for old, _ in scope.renamed_files),
            ):
                _safe_path(context.repository, candidate)
            issues = validate_patch_scope(context.policy, scope)
            if issues:
                raise ToolPermissionError("; ".join(issues))
            if name == "create_patch":
                return ToolObservation(
                    "patch",
                    True,
                    "Patch scope accepted",
                    {
                        "files": scope.changed_files,
                        "symbols": scope.changed_symbols,
                        "patch_sha256": hashlib.sha256(arguments["patch"].encode()).hexdigest(),
                    },
                )
            with tempfile.NamedTemporaryFile("w", suffix=".patch", delete=False) as stream:
                stream.write(arguments["patch"])
                patch_path = stream.name
            try:
                check = subprocess.run(
                    ["git", "apply", "--check", "--recount", patch_path],
                    cwd=context.repository,
                    text=True,
                    capture_output=True,
                )
                if check.returncode:
                    return ToolObservation(
                        "patch_rejection", False, "Patch preflight failed", stderr=check.stderr
                    )
                applied = subprocess.run(
                    ["git", "apply", "--recount", patch_path],
                    cwd=context.repository,
                    text=True,
                    capture_output=True,
                )
            finally:
                Path(patch_path).unlink(missing_ok=True)
            if applied.returncode:
                _rollback_worktree(context.repository)
                return ToolObservation(
                    "patch_failure", False, "Patch application failed", stderr=applied.stderr
                )
            post = extract_patch_scope(
                worktree_diff(context.repository),
                tuple(context.symbol_index.symbols),
                _index_prefix(context),
            )
            post_issues = validate_patch_scope(context.policy, post)
            if post_issues:
                restored = _restore_worktree_diff(context.repository, before_diff)
                detail = "; ".join(post_issues)
                if not restored:
                    detail += "; earlier task edits could not be restored and were discarded"
                return ToolObservation("scope_rejection", False, detail)
            return ToolObservation(
                "mutation", True, "Patch applied within scope", {"files": post.changed_files}
            )
        if name == "revert_current_changes":
            _rollback_worktree(context.repository)
            return ToolObservation("mutation", True, "Current changes reverted")
        if name in {"replace_symbol_body", "insert_before_symbol", "insert_after_symbol"}:
            before_diff = worktree_diff(context.repository)
            symbol = _resolve_symbol(context, arguments["symbol"])
            prefix = _index_prefix(context)
            relative = symbol.path[len(prefix) :] if prefix else symbol.path
            path = _safe_path(context.repository, relative)
            lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
            current_source = "".join(lines[symbol.start_line - 1 : symbol.end_line]).rstrip("\r\n")
            if symbol.language == "python":
                # ast.get_source_segment, used by SymbolIndex, starts at the
                # nested node's column but keeps indentation on later lines.
                first, separator, rest = current_source.partition("\n")
                current_source = first.lstrip(" \t") + separator + rest
            if hashlib.sha256(current_source.encode()).hexdigest() != symbol.source_hash:
                prior_mutation = any(
                    event.success
                    and event.tool_name in {"replace_symbol_body", "insert_before_symbol", "insert_after_symbol"}
                    and relative in event.affected_files
                    for event in context.events
                )
                if not prior_mutation:
                    raise ToolPermissionError(
                        "Symbol source/range is stale; refresh the index and revalidate the plan"
                    )
                symbol = _refresh_task_symbol(path, symbol)
                lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
                current_source = "".join(lines[symbol.start_line - 1 : symbol.end_line]).rstrip("\r\n")
                if symbol.language == "python":
                    first, separator, rest = current_source.partition("\n")
                    current_source = first.lstrip(" \t") + separator + rest
                if hashlib.sha256(current_source.encode()).hexdigest() != symbol.source_hash:
                    raise ToolPermissionError("Task symbol source could not be revalidated")
            content = arguments["content"]
            try:
                if name == "replace_symbol_body":
                    content = _normalize_symbol_body(content, path, symbol)
                if content and not content.endswith("\n"):
                    content += "\n"
                if name == "replace_symbol_body":
                    body_start, body_end, indentation = _python_body_range(path, symbol)
                    replacement = textwrap.indent(
                        _dedent_python_body(content), " " * indentation
                    ) + "\n"
                    candidate_lines = list(lines)
                    candidate_lines[body_start - 1 : body_end] = [replacement]
                    candidate = "".join(candidate_lines)
                    _validate_python_candidate(path, candidate)
                    lines = candidate_lines
                elif name == "insert_before_symbol":
                    candidate_lines = list(lines)
                    candidate_lines[symbol.start_line - 1 : symbol.start_line - 1] = [content]
                    candidate = "".join(candidate_lines)
                    _validate_python_candidate(path, candidate)
                    lines = candidate_lines
                else:
                    candidate_lines = list(lines)
                    candidate_lines[symbol.end_line : symbol.end_line] = [content]
                    candidate = "".join(candidate_lines)
                    _validate_python_candidate(path, candidate)
                    lines = candidate_lines
            except ToolArgumentError as exc:
                return ToolObservation(
                    "mutation_rejected", False,
                    f"Candidate rejected before writing; current file is unchanged: {exc}",
                )
            path.write_text(candidate, encoding="utf-8")
            issues = _enforce_worktree_scope(context, before_diff)
            if issues:
                return ToolObservation(
                    "scope_rejection",
                    False,
                    "Rejected mutation rolled back; earlier approved edits were preserved. "
                    + "; ".join(issues),
                )
            refreshed = _refresh_task_symbol(path, symbol)
            updated_lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
            updated_source = "".join(
                updated_lines[refreshed.start_line - 1 : refreshed.end_line]
            )
            return ToolObservation(
                "mutation",
                True,
                f"{name} completed; current candidate symbol is available for validation",
                {
                    "path": relative,
                    "symbol": symbol.identifier,
                    "current_source": updated_source[:12_000],
                },
            )
        if "path" not in arguments:
            return ToolObservation("mutation", False, f"{name} requires structured editor context")
        before_diff = worktree_diff(context.repository)
        path = _safe_path(context.repository, arguments["path"])
        if name in {"create_file", "replace_file"}:
            if name == "create_file" and path.exists():
                raise ToolArgumentError("create_file target already exists")
            if name == "replace_file" and not path.is_file():
                raise ToolArgumentError("replace_file target does not exist")
            try:
                _validate_python_candidate(path, arguments["content"])
            except ToolArgumentError as exc:
                return ToolObservation(
                    "mutation_rejected", False,
                    f"Candidate rejected before writing; current file is unchanged: {exc}",
                )
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(arguments["content"], encoding="utf-8")
        elif name == "append_to_file":
            with path.open("a", encoding="utf-8") as stream:
                stream.write(arguments["content"])
        elif name == "delete_file":
            path.unlink()
        elif name == "rename_file":
            path.rename(_safe_path(context.repository, arguments["destination"]))
        else:
            return ToolObservation("mutation", False, f"{name} delegated to patch editor")
        issues = _enforce_worktree_scope(context, before_diff)
        if issues:
            return ToolObservation(
                "scope_rejection",
                False,
                "Rejected mutation rolled back; earlier approved edits were preserved. "
                + "; ".join(issues),
            )
        return ToolObservation("mutation", True, f"{name} completed", {"path": arguments["path"]})

    return handler


def _safe_path(repository: Path, value: str) -> Path:
    path = (repository / value).resolve()
    name = path.name.lower()
    sensitive = (
        name == ".env"
        or name.startswith(".env.")
        or name in {"id_rsa", "id_ed25519"}
        or name.endswith((".pem", ".key"))
    )
    if repository.resolve() not in path.parents or is_protected_path(value) or sensitive:
        raise ToolPermissionError("Path escapes repository or is protected")
    return path


def _index_prefix(context: ToolContext) -> str:
    try:
        indexed_repository = context.canonical_repository or context.repository
        relative = (
            indexed_repository.resolve()
            .relative_to(context.symbol_index.repository.resolve())
            .as_posix()
        )
        return "" if relative == "." else relative + "/"
    except ValueError:
        return ""


def _local_symbols(context: ToolContext, symbols):
    prefix = _index_prefix(context)
    return [item for item in symbols if not prefix or item.path.startswith(prefix)]


def _file_level_approved_symbol(context: ToolContext, value: str) -> bool:
    """Resolve an existing symbol only within an approved path-level scope."""
    prefix = _index_prefix(context)
    candidates = {
        (item.path, item.symbol_id, item.qualified_name)
        for item in (*context.artifact.plan.direct_scope, *context.artifact.plan.dependent_scope)
        if value in {item.symbol_id, item.qualified_name}
        and item.path in context.policy.allowed_files
        and item.path not in context.policy.symbol_scoped_files
    }
    if len(candidates) != 1:
        return False
    path, symbol_id, qualified = next(iter(candidates))
    matching = []
    for item in _local_symbols(context, context.symbol_index.symbols):
        relative_path = item.path[len(prefix):] if prefix else item.path
        if relative_path != path:
            continue
        if (item.identifier == symbol_id or _same_path_qualified_name(
            qualified, item.qualified_name, path
        )):
            matching.append(item)
    return len({item.identifier for item in matching}) == 1


def _same_path_qualified_name(approved: str | None, indexed: str | None, path: str) -> bool:
    """Compare names after dropping repository-specific package prefixes.

    Names are anchored at the path's module stem so an approved class cannot
    accidentally resolve to all of its child methods through a suffix match.
    """
    if not approved or not indexed:
        return False
    module = Path(path).stem

    def suffix(value: str) -> tuple[str, ...] | None:
        parts = tuple(value.split("."))
        positions = [index for index, part in enumerate(parts) if part == module]
        if len(positions) != 1:
            return parts if positions == [] else None
        return parts[positions[0] :]

    return suffix(approved) is not None and suffix(approved) == suffix(indexed)


def _resolve_symbol(context: ToolContext, value: str):
    found = _local_symbols(context, context.symbol_index.find_exact(value))
    if value in set(context.policy.allowed_symbols) or _file_level_approved_symbol(context, value):
        # Plans may have been indexed from a registered repository root whose
        # name is embedded in qualified_name, while execution indexes the
        # repository itself. Resolve only the exact approved candidate, within
        # its approved file, and only when the suffix remains unambiguous.
        candidates = [
            candidate
            for candidate in (*context.artifact.plan.direct_scope, *context.artifact.plan.dependent_scope)
            if value in {candidate.symbol_id, candidate.qualified_name}
            and (
                candidate.path in set(context.policy.symbol_scoped_files)
                if value in set(context.policy.allowed_symbols)
                else candidate.path in set(context.policy.allowed_files)
                and candidate.path not in set(context.policy.symbol_scoped_files)
            )
        ]
        aliases = [
            candidate
            for candidate in candidates
            if candidate.symbol_id == value or candidate.qualified_name == value
        ]
        resolved = []
        prefix = _index_prefix(context)
        for candidate in aliases:
            qualified = candidate.qualified_name or ""
            for symbol in _local_symbols(context, context.symbol_index.symbols):
                relative_path = symbol.path[len(prefix) :] if prefix else symbol.path
                if relative_path != candidate.path:
                    continue
                if symbol.identifier == candidate.symbol_id or _same_path_qualified_name(
                    qualified, symbol.qualified_name, candidate.path
                ):
                    resolved.append(symbol)
        resolved_found = list({symbol.identifier: symbol for symbol in resolved}.values())
        if resolved_found:
            found = resolved_found
    if len(found) != 1:
        raise ToolArgumentError(f"Symbol must resolve uniquely: {value}")
    return found[0]


def _enforce_worktree_scope(context: ToolContext, before_diff: str) -> tuple[str, ...]:
    try:
        # Later repairs may touch lines beyond the original symbol range.
        # Refresh from the mutated workspace before deriving patch effects so
        # an approved symbol's expanded body remains precisely attributable.
        refresh = getattr(context.symbol_index, "refresh", None)
        if callable(refresh):
            stats = refresh()
            failures = getattr(stats, "failures", {}) or {}
            if failures:
                restored = _restore_worktree_diff(context.repository, before_diff)
                if restored:
                    refresh()
                detail = "Updated symbol index could not parse the candidate: " + ", ".join(sorted(failures))
                if not restored:
                    detail += "; earlier task edits could not be restored and were discarded"
                return (detail,)
        scope = extract_patch_scope(
            worktree_diff(context.repository),
            tuple(context.symbol_index.symbols),
            _index_prefix(context),
        )
    except PatchValidationError as exc:
        restored = _restore_worktree_diff(context.repository, before_diff)
        detail = f"Post-mutation diff could not be validated: {exc}"
        if not restored:
            detail += "; earlier task edits could not be restored and were discarded"
        return (detail,)
    issues = validate_patch_scope(context.policy, scope)
    if not issues:
        return ()
    restored = _restore_worktree_diff(context.repository, before_diff)
    refresh = getattr(context.symbol_index, "refresh", None)
    if restored and callable(refresh):
        refresh()
    if not restored:
        issues = (*issues, "earlier task edits could not be restored and were discarded")
    return tuple(issues)


def _restore_worktree_diff(repository: Path, patch: str) -> bool:
    """Discard one rejected mutation while retaining earlier isolated edits."""
    _rollback_worktree(repository)
    if not patch.strip():
        return True
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".patch", delete=False) as stream:
            stream.write(patch)
            patch_path = Path(stream.name)
        try:
            restored = subprocess.run(
                ["git", "apply", "--recount", patch_path.as_posix()],
                cwd=repository,
                text=True,
                capture_output=True,
            )
        finally:
            patch_path.unlink(missing_ok=True)
        return restored.returncode == 0
    except OSError:
        return False


def _rollback_worktree(repository: Path) -> None:
    subprocess.run(["git", "restore", "--staged", "--worktree", "."], cwd=repository)
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=repository,
        text=True,
        capture_output=True,
    )
    for line in status.stdout.split("\0"):
        if line.startswith("?? "):
            candidate = _safe_path(repository, line[3:])
            if candidate.is_file():
                candidate.unlink()


def _python_body_range(path: Path, symbol) -> tuple[int, int, int]:
    if symbol.language != "python":
        raise ToolArgumentError("replace_symbol_body currently requires a Python symbol")
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError) as exc:
        raise ToolArgumentError(f"Cannot resolve current Python symbol body: {exc}") from exc
    candidates = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and node.name == symbol.name
        and node.lineno >= symbol.start_line
        and node.end_lineno <= symbol.end_line
    ]
    if len(candidates) != 1 or not candidates[0].body:
        raise ToolArgumentError("Symbol body cannot be resolved uniquely")
    node = candidates[0]
    first = node.body[0]
    return first.lineno, node.end_lineno, first.col_offset


def _dedent_python_body(content: str) -> str:
    lines = content.strip("\r\n").splitlines()
    code_indents = [
        len(line) - len(line.lstrip())
        for line in lines
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not code_indents:
        return textwrap.dedent("\n".join(lines))
    indent = min(code_indents)
    return "\n".join(
        line[min(indent, len(line) - len(line.lstrip())) :]
        if line.strip() else ""
        for line in lines
    )


def _validate_python_candidate(path: Path, content: str) -> None:
    if path.suffix != ".py":
        return
    try:
        ast.parse(content, filename=path.name)
    except SyntaxError as exc:
        raise ToolArgumentError(
            f"Python mutation rejected before writing: syntax error at line {exc.lineno}"
        ) from exc


def _normalize_symbol_body(content: str, path: Path, symbol) -> str:
    """Accept body statements or unwrap one signature-identical function safely."""
    candidate = textwrap.dedent(content.strip("\r\n"))
    candidate_lines = candidate.splitlines()
    while candidate_lines and (
        not candidate_lines[0].strip() or candidate_lines[0].lstrip().startswith("#")
    ):
        candidate_lines.pop(0)
    candidate = "\n".join(candidate_lines)
    if not candidate.lstrip().startswith(("def ", "async def ", "class ", "@")):
        return content
    try:
        replacement_tree = ast.parse(candidate)
        existing_tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError) as exc:
        raise ToolArgumentError("Full-function replacement must be valid Python") from exc
    if len(replacement_tree.body) != 1 or not isinstance(
        replacement_tree.body[0], (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    ):
        raise ToolArgumentError("Full-symbol replacement must contain exactly one function or class")
    replacement = replacement_tree.body[0]
    existing_matches = [
        item for item in ast.walk(existing_tree)
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and item.name == symbol.name
        and item.lineno >= symbol.start_line
        and item.end_lineno <= symbol.end_line
    ]
    if len(existing_matches) != 1 or type(existing_matches[0]) is not type(replacement):
        raise ToolArgumentError("Current symbol signature cannot be resolved uniquely")
    existing = existing_matches[0]
    if isinstance(replacement, ast.ClassDef) and isinstance(existing, ast.ClassDef):
        signature_matches = (
            replacement.name == existing.name
            and [ast.dump(item, include_attributes=False) for item in replacement.bases]
            == [ast.dump(item, include_attributes=False) for item in existing.bases]
            and [ast.dump(item, include_attributes=False) for item in replacement.keywords]
            == [ast.dump(item, include_attributes=False) for item in existing.keywords]
            and [ast.dump(item, include_attributes=False) for item in replacement.decorator_list]
            == [ast.dump(item, include_attributes=False) for item in existing.decorator_list]
            and [ast.dump(item, include_attributes=False)
                 for item in getattr(replacement, "type_params", [])]
            == [ast.dump(item, include_attributes=False)
                for item in getattr(existing, "type_params", [])]
        )
        existing_methods = {
            item.name: ast.dump(item.args, include_attributes=False)
            for item in existing.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        replacement_methods = {
            item.name: ast.dump(item.args, include_attributes=False)
            for item in replacement.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        if any(replacement_methods.get(name) != args for name, args in existing_methods.items()):
            raise ToolArgumentError("Full-class replacement cannot remove or change existing method signatures")
    else:
        signature_matches = (
            replacement.name == existing.name
            and ast.dump(replacement.args, include_attributes=False)
            == ast.dump(existing.args, include_attributes=False)
            and (ast.dump(replacement.returns, include_attributes=False) if replacement.returns else None)
            == (ast.dump(existing.returns, include_attributes=False) if existing.returns else None)
            and replacement.type_comment == existing.type_comment
            and [ast.dump(item, include_attributes=False) for item in replacement.decorator_list]
            == [ast.dump(item, include_attributes=False) for item in existing.decorator_list]
        )
    if not signature_matches:
        raise ToolArgumentError("Full-symbol replacement cannot change the approved signature")
    if not replacement.body:
        raise ToolArgumentError("Full-function replacement must contain a body")
    lines = candidate.splitlines()
    return textwrap.dedent("\n".join(lines[replacement.body[0].lineno - 1 : replacement.end_lineno]))


def _refresh_task_symbol(path: Path, symbol):
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (OSError, SyntaxError) as exc:
        raise ToolPermissionError("Task symbol cannot be safely refreshed after its approved edit") from exc
    matches = [
        item for item in ast.walk(tree)
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and item.name == symbol.name
    ]
    if len(matches) != 1:
        raise ToolPermissionError("Task symbol no longer resolves uniquely after its approved edit")
    node = matches[0]
    current_source = "\n".join(source.splitlines()[node.lineno - 1 : node.end_lineno])
    if symbol.language == "python":
        first, separator, rest = current_source.partition("\n")
        current_source = first.lstrip(" \t") + separator + rest
    return replace(
        symbol,
        start_line=node.lineno,
        end_line=node.end_lineno,
        source=current_source,
        source_hash=hashlib.sha256(current_source.encode()).hexdigest(),
    )


def _handler_for_command(timeout: int) -> Handler:
    def handler(context: ToolContext, arguments: dict) -> ToolObservation:
        requested = min(timeout, max(1, int(arguments.get("timeout", timeout))))
        before = worktree_diff(context.repository)
        sandbox_arguments = (
            {
                "sandbox": context.sandbox,
                "task_root": context.sandbox_task_root,
                "resources": context.sandbox_resources,
                "network": context.sandbox_network,
                "cancel_check": context.cancel_check,
            }
            if context.sandbox is not None
            else {}
        )
        result = run_allowed_command(
            arguments["command"], context.repository, requested, **sandbox_arguments
        )
        after = worktree_diff(context.repository)
        if after != before:
            _rollback_worktree(context.repository)
            return ToolObservation(
                "scope_rejection",
                False,
                "Validation command changed repository state; transaction rolled back",
                {"return_code": result.return_code},
                result.stdout,
                result.stderr,
                result.timed_out,
            )
        return ToolObservation(
            "command",
            result.return_code == 0 and not result.timed_out,
            "Command timed out" if result.timed_out else "Command completed" if result.return_code == 0 else "Command failed",
            {"return_code": result.return_code},
            result.stdout,
            result.stderr,
            result.timed_out,
        )
    return handler
