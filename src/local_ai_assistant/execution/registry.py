"""Central typed tool registry and plan-bound invocation boundary."""

from __future__ import annotations

import ast
import hashlib
import subprocess
import tempfile
import textwrap
import time
from collections.abc import Callable
from dataclasses import dataclass, field
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
        except ToolExecutionError:
            if spec.mutates:
                _rollback_worktree(context.repository)
            raise
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            if spec.mutates:
                _rollback_worktree(context.repository)
            raise ToolExecutionError(f"Tool {name} failed safely: {exc}") from exc
        finally:
            context.events.append(
                _event(
                    context,
                    name,
                    arguments,
                    round(time.monotonic() - started, 6),
                    success,
                    (
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
    if symbol and symbol not in set(context.policy.allowed_symbols):
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
            scope = extract_patch_scope(
                arguments["patch"], tuple(context.symbol_index.symbols), _index_prefix(context)
            )
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
                _rollback_worktree(context.repository)
                return ToolObservation("scope_rejection", False, "; ".join(post_issues))
            return ToolObservation(
                "mutation", True, "Patch applied within scope", {"files": post.changed_files}
            )
        if name == "revert_current_changes":
            _rollback_worktree(context.repository)
            return ToolObservation("mutation", True, "Current changes reverted")
        if name in {"replace_symbol_body", "insert_before_symbol", "insert_after_symbol"}:
            symbol = _resolve_symbol(context, arguments["symbol"])
            prefix = _index_prefix(context)
            relative = symbol.path[len(prefix) :] if prefix else symbol.path
            path = _safe_path(context.repository, relative)
            lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
            current_source = "".join(lines[symbol.start_line - 1 : symbol.end_line]).rstrip("\r\n")
            if hashlib.sha256(current_source.encode()).hexdigest() != symbol.source_hash:
                raise ToolPermissionError(
                    "Symbol source/range is stale; refresh the index and revalidate the plan"
                )
            content = arguments["content"]
            if content and not content.endswith("\n"):
                content += "\n"
            if name == "replace_symbol_body":
                body_start, body_end, indentation = _python_body_range(path, symbol)
                replacement = textwrap.indent(content.strip("\r\n"), " " * indentation) + "\n"
                lines[body_start - 1 : body_end] = [replacement]
            elif name == "insert_before_symbol":
                lines[symbol.start_line - 1 : symbol.start_line - 1] = [content]
            else:
                lines[symbol.end_line : symbol.end_line] = [content]
            path.write_text("".join(lines), encoding="utf-8")
            _enforce_worktree_scope(context)
            return ToolObservation(
                "mutation",
                True,
                f"{name} completed",
                {"path": relative, "symbol": symbol.identifier},
            )
        if "path" not in arguments:
            return ToolObservation("mutation", False, f"{name} requires structured editor context")
        path = _safe_path(context.repository, arguments["path"])
        if name in {"create_file", "replace_file"}:
            if name == "create_file" and path.exists():
                raise ToolArgumentError("create_file target already exists")
            if name == "replace_file" and not path.is_file():
                raise ToolArgumentError("replace_file target does not exist")
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
        _enforce_worktree_scope(context)
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
        relative = (
            context.repository.resolve()
            .relative_to(context.symbol_index.repository.resolve())
            .as_posix()
        )
        return "" if relative == "." else relative + "/"
    except ValueError:
        return ""


def _local_symbols(context: ToolContext, symbols):
    prefix = _index_prefix(context)
    return [item for item in symbols if not prefix or item.path.startswith(prefix)]


def _resolve_symbol(context: ToolContext, value: str):
    found = _local_symbols(context, context.symbol_index.find_exact(value))
    if len(found) != 1:
        raise ToolArgumentError(f"Symbol must resolve uniquely: {value}")
    return found[0]


def _enforce_worktree_scope(context: ToolContext) -> None:
    try:
        scope = extract_patch_scope(
            worktree_diff(context.repository),
            tuple(context.symbol_index.symbols),
            _index_prefix(context),
        )
    except PatchValidationError as exc:
        _rollback_worktree(context.repository)
        raise ToolPermissionError(f"Post-mutation diff could not be validated: {exc}") from exc
    issues = validate_patch_scope(context.policy, scope)
    if not issues:
        return
    _rollback_worktree(context.repository)
    raise ToolPermissionError("Post-mutation scope violation: " + "; ".join(issues))


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


def _handler_for_command(timeout: int) -> Handler:
    def handler(context: ToolContext, arguments: dict) -> ToolObservation:
        requested = min(timeout, max(1, int(arguments.get("timeout", timeout))))
        before = worktree_diff(context.repository)
        result = run_allowed_command(arguments["command"], context.repository, requested)
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
