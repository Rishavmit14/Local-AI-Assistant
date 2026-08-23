"""Central typed tool registry and plan-bound invocation boundary."""

from __future__ import annotations

import os
import subprocess
import tempfile
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
from local_ai_assistant.planning.patch_scope import (
    extract_patch_scope,
    validate_patch_scope,
    worktree_diff,
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
        observation = None
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
                    (
                        (observation.summary + " " + observation.stderr[:500]).strip()
                        if observation
                        else "failed/rejected"
                    ),
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
            ),
            _handler_for_mutation(name),
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
            return ToolObservation(
                "repository_map", True, "Repository map", {"map": index.repository_map()}
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
            return ToolObservation(
                "graph", True, f"{len(values)} results", {"results": [str(item) for item in values]}
            )
        if name in {"find_imports", "find_reverse_imports"}:
            values = (
                index.imports_of(arguments["module"])
                if name == "find_imports"
                else index.imported_by(arguments["module"])
            )
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
            issues = validate_patch_scope(context.policy, scope)
            if issues:
                raise ToolPermissionError("; ".join(issues))
            if name == "create_patch":
                return ToolObservation(
                    "patch",
                    True,
                    "Patch scope accepted",
                    {"files": scope.changed_files, "symbols": scope.changed_symbols},
                )
            with tempfile.NamedTemporaryFile("w", suffix=".patch", delete=False) as stream:
                stream.write(arguments["patch"])
                patch_path = stream.name
            check = subprocess.run(
                ["git", "apply", "--check", "--recount", patch_path],
                cwd=context.repository,
                text=True,
                capture_output=True,
            )
            if check.returncode:
                os.unlink(patch_path)
                return ToolObservation(
                    "patch_rejection", False, "Patch preflight failed", stderr=check.stderr
                )
            applied = subprocess.run(
                ["git", "apply", "--recount", patch_path],
                cwd=context.repository,
                text=True,
                capture_output=True,
            )
            os.unlink(patch_path)
            if applied.returncode:
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
                subprocess.run(["git", "restore", "."], cwd=context.repository)
                return ToolObservation("scope_rejection", False, "; ".join(post_issues))
            return ToolObservation(
                "mutation", True, "Patch applied within scope", {"files": post.changed_files}
            )
        if name == "revert_current_changes":
            subprocess.run(["git", "restore", "."], cwd=context.repository, check=True)
            return ToolObservation("mutation", True, "Tracked changes reverted")
        if name in {"replace_symbol_body", "insert_before_symbol", "insert_after_symbol"}:
            symbol = _resolve_symbol(context, arguments["symbol"])
            prefix = _index_prefix(context)
            relative = symbol.path[len(prefix) :] if prefix else symbol.path
            path = _safe_path(context.repository, relative)
            lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
            content = arguments["content"]
            if content and not content.endswith("\n"):
                content += "\n"
            if name == "replace_symbol_body":
                lines[symbol.start_line - 1 : symbol.end_line] = [content]
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
    if repository.resolve() not in path.parents or is_protected_path(value):
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
    scope = extract_patch_scope(
        worktree_diff(context.repository),
        tuple(context.symbol_index.symbols),
        _index_prefix(context),
    )
    issues = validate_patch_scope(context.policy, scope)
    if not issues:
        return
    subprocess.run(["git", "restore", "."], cwd=context.repository)
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=context.repository,
        text=True,
        capture_output=True,
    )
    for line in status.stdout.splitlines():
        if line.startswith("?? "):
            candidate = _safe_path(context.repository, line[3:])
            if candidate.is_file():
                candidate.unlink()
    raise ToolPermissionError("Post-mutation scope violation: " + "; ".join(issues))


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
