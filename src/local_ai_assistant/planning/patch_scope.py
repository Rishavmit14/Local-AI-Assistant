"""Deterministic unified-diff scope extraction and plan-policy enforcement."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass

from local_ai_assistant.code_index.models import SymbolRecord

from .analysis import is_dependency_file, is_protected_path
from .models import ScopeGuardPolicy

HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
DEFINITION = re.compile(r"^[+-]\s*(?:async\s+def|def|class)\s+([A-Za-z_]\w*)")


@dataclass(frozen=True, slots=True)
class SymbolEffect:
    effect: str
    path: str
    symbol: str | None
    confidence: str


def worktree_diff(repository) -> str:
    result = subprocess.run(
        ["git", "diff", "--binary", "--find-renames"],
        cwd=repository,
        text=True,
        capture_output=True,
    )
    output = result.stdout
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=repository,
        text=True,
        capture_output=True,
    )
    for line in status.stdout.splitlines():
        if line.startswith("?? "):
            path = line[3:]
            addition = subprocess.run(
                ["git", "diff", "--no-index", "--binary", "/dev/null", path],
                cwd=repository,
                text=True,
                capture_output=True,
            )
            output += addition.stdout
    return output


@dataclass(frozen=True, slots=True)
class PatchScope:
    modified_files: tuple[str, ...]
    created_files: tuple[str, ...]
    deleted_files: tuple[str, ...]
    renamed_files: tuple[tuple[str, str], ...]
    changed_symbols: tuple[str, ...]
    symbol_effects: tuple[SymbolEffect, ...] = ()
    unknown_effects: tuple[str, ...] = ()

    @property
    def changed_files(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                (
                    *self.modified_files,
                    *self.created_files,
                    *self.deleted_files,
                    *(new for _, new in self.renamed_files),
                )
            )
        )


def extract_patch_scope(
    diff: str,
    symbols: tuple[SymbolRecord, ...],
    repository_prefix: str = "",
) -> PatchScope:
    modified, created, deleted, renamed = [], [], [], []
    touched: set[str] = set()
    current_old = current_new = None
    ranges: list[tuple[str, int, int]] = []
    definition_changes: list[tuple[str, str, str]] = []
    for line in diff.splitlines():
        if line.startswith("diff --git a/"):
            parts = line.split()
            current_old, current_new = parts[2][2:], parts[3][2:]
        elif line.startswith("rename from "):
            current_old = line.removeprefix("rename from ")
        elif line.startswith("rename to "):
            current_new = line.removeprefix("rename to ")
            renamed.append((current_old, current_new))
        elif line.startswith("new file mode ") and current_new:
            created.append(current_new)
        elif line.startswith("deleted file mode ") and current_old:
            deleted.append(current_old)
        else:
            match = HUNK.match(line)
            if match and current_old:
                start = int(match.group(1))
                count = int(match.group(2) or 1)
                ranges.append((current_old, start, max(start, start + count - 1)))
            definition = DEFINITION.match(line)
            if definition and (current_new or current_old):
                definition_changes.append(
                    (
                        "added" if line.startswith("+") else "deleted",
                        current_new if line.startswith("+") else current_old,
                        definition.group(1),
                    )
                )
    special = set(created) | set(deleted) | {item for pair in renamed for item in pair}
    for line in diff.splitlines():
        if line.startswith("diff --git a/"):
            parts = line.split()
            path = parts[3][2:]
            if path not in special:
                modified.append(path)
    for symbol in symbols:
        if symbol.kind.value == "module":
            continue
        if repository_prefix and not symbol.path.startswith(repository_prefix):
            continue
        symbol_path = symbol.path[len(repository_prefix) :] if repository_prefix else symbol.path
        if any(
            path == symbol_path and start <= symbol.end_line and end >= symbol.start_line
            for path, start, end in ranges
        ):
            touched.add(symbol.identifier)
    effects = [
        SymbolEffect(
            "existing_symbol_modified",
            next(
                path
                for path, start, end in ranges
                if start <= symbol.end_line and end >= symbol.start_line and path == symbol_path
            ),
            symbol.identifier,
            "confirmed",
        )
        for symbol in symbols
        if symbol.identifier in touched
        for symbol_path in (
            [symbol.path[len(repository_prefix) :] if repository_prefix else symbol.path]
        )
    ]
    paired = {(path, name) for effect, path, name in definition_changes if effect == "added"} & {
        (path, name) for effect, path, name in definition_changes if effect == "deleted"
    }
    effects.extend(
        SymbolEffect(f"symbol_{effect}", path, name, "syntactic")
        for effect, path, name in definition_changes
        if (path, name) not in paired
    )
    unknown = tuple(path for path in modified if not any(item.path == path for item in effects))
    return PatchScope(
        tuple(dict.fromkeys(modified)),
        tuple(dict.fromkeys(created)),
        tuple(dict.fromkeys(deleted)),
        tuple(dict.fromkeys(renamed)),
        tuple(sorted(touched)),
        tuple(effects),
        unknown,
    )


def validate_patch_scope(policy: ScopeGuardPolicy, scope: PatchScope) -> tuple[str, ...]:
    issues = []
    unexpected_modified = set(scope.modified_files) - set(policy.allowed_files)
    unexpected_created = set(scope.created_files) - set(policy.allowed_new_files)
    allowed_delete = set(policy.allowed_deletes_or_renames)
    unexpected_deleted = set(scope.deleted_files) - allowed_delete
    unexpected_renames = {
        f"{old} -> {new}"
        for old, new in scope.renamed_files
        if old not in allowed_delete or new not in allowed_delete
    }
    unexpected_symbols = set(scope.changed_symbols) - set(policy.allowed_symbols)
    added_symbols = {
        item.symbol
        for item in scope.symbol_effects
        if item.effect == "symbol_added" and item.symbol
    }
    allowed_new_names = {value.rsplit(".", 1)[-1] for value in policy.allowed_new_symbols}
    unexpected_added_symbols = added_symbols - allowed_new_names
    protected = {path for path in scope.changed_files if is_protected_path(path)}
    dependencies = {path for path in scope.changed_files if is_dependency_file(path)}
    for label, values in (
        ("modified", unexpected_modified),
        ("created", unexpected_created),
        ("deleted", unexpected_deleted),
        ("renamed", unexpected_renames),
        ("symbols", unexpected_symbols),
        ("new symbols", unexpected_added_symbols),
    ):
        if values:
            issues.append(f"Unplanned {label}: {', '.join(sorted(values))}")
    if protected:
        issues.append("Protected/generated files: " + ", ".join(sorted(protected)))
    if dependencies and policy.dependency_file_policy != "approval_required":
        issues.append("Unapproved dependency/config files: " + ", ".join(sorted(dependencies)))
    if len(scope.changed_files) > policy.max_file_count:
        issues.append("Patch exceeds planned file count.")
    affected_symbol_count = len(
        {item.symbol for item in scope.symbol_effects if item.symbol} | set(scope.changed_symbols)
    )
    if affected_symbol_count > policy.max_symbol_count:
        issues.append("Patch exceeds planned symbol count.")
    return tuple(issues)


def render_patch_scope(scope: PatchScope) -> str:
    lines = [
        f"Files changed: {len(scope.changed_files)}",
        f"Symbols changed: {len(scope.symbol_effects)}",
    ]
    effects_by_path: dict[str, list[SymbolEffect]] = {}
    for effect in scope.symbol_effects:
        effects_by_path.setdefault(effect.path, []).append(effect)
    for path in scope.changed_files:
        lines.append("")
        lines.append(path)
        for effect in effects_by_path.get(path, ()):
            lines.append(f"  - {effect.effect}: {effect.symbol or 'unknown'} [{effect.confidence}]")
        if path in scope.unknown_effects:
            lines.append("  - file-level change outside known symbol [unknown]")
    return "\n".join(lines)
