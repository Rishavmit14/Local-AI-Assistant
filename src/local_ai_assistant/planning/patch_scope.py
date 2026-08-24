"""Deterministic unified-diff scope extraction and plan-policy enforcement."""

from __future__ import annotations

import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import PurePosixPath

from local_ai_assistant.code_index.models import SymbolRecord
from local_ai_assistant.common.errors import PatchValidationError

from .analysis import is_dependency_file, is_protected_path
from .models import ScopeGuardPolicy

HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
DEFINITION_PATTERNS = (
    re.compile(r"^[+-]\s*(?:async\s+def|def|class)\s+([A-Za-z_]\w*)"),
    re.compile(
        r"^[+-]\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?(?:fn|struct|trait|enum|type|const|static|mod)\s+([A-Za-z_]\w*)"
    ),
    re.compile(
        r"^[+-]\s*(?:abstract\s+)?(?:contract|interface|library|function|modifier|event|error|struct|enum)\s+([A-Za-z_]\w*)"
    ),
    re.compile(
        r"^[+-]\s*(?:export\s+)?(?:async\s+)?(?:function|class|interface|type|enum|namespace)\s+([A-Za-z_$][\w$]*)"
    ),
    re.compile(
        r"^[+-]\s*(?:public|private|protected|static|final|abstract|async|extern|inline|virtual|constexpr|\s)*\s*(?:class|struct|enum|interface|record|namespace)\s+([A-Za-z_]\w*)"
    ),
    re.compile(r"^[+-]\s*(?:function\s+)?([A-Za-z_]\w*)\s*\(\)\s*\{"),
)


@dataclass(frozen=True, slots=True)
class SymbolEffect:
    effect: str
    path: str
    symbol: str | None
    confidence: str


def worktree_diff(repository) -> str:
    result = subprocess.run(
        ["git", "diff", "HEAD", "--binary", "--find-renames"],
        cwd=repository,
        text=True,
        capture_output=True,
    )
    output = result.stdout
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=repository,
        text=True,
        capture_output=True,
    )
    for line in status.stdout.split("\0"):
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
    if not diff.strip():
        raise PatchValidationError("Patch is empty")
    if "GIT binary patch" in diff or re.search(r"^Binary files .* differ$", diff, re.MULTILINE):
        raise PatchValidationError(
            "Binary patches are not supported by deterministic scope analysis"
        )
    modified, created, deleted, renamed = [], [], [], []
    touched: set[str] = set()
    current_old = current_new = None
    ranges: list[tuple[str, int, int]] = []
    definition_changes: list[tuple[str, str, str]] = []
    sections = 0
    section_changed = False
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            if sections and not section_changed:
                raise PatchValidationError("Malformed patch section has no change metadata")
            try:
                parts = shlex.split(line)
            except ValueError as exc:
                raise PatchValidationError(f"Malformed patch header: {exc}") from exc
            if len(parts) != 4:
                raise PatchValidationError("Malformed diff --git header")
            current_old = _patch_path(parts[2], "a/")
            current_new = _patch_path(parts[3], "b/")
            sections += 1
            section_changed = False
        elif line.startswith("rename from "):
            current_old = _metadata_path(line.removeprefix("rename from "))
        elif line.startswith("rename to "):
            current_new = _metadata_path(line.removeprefix("rename to "))
            renamed.append((current_old, current_new))
            section_changed = True
        elif line.startswith("new file mode ") and current_new:
            created.append(current_new)
            section_changed = True
        elif line.startswith("deleted file mode ") and current_old:
            deleted.append(current_old)
            section_changed = True
        else:
            match = HUNK.match(line)
            if match and current_old:
                start = int(match.group(1))
                count = int(match.group(2) or 1)
                ranges.append((current_old, start, max(start, start + count - 1)))
                section_changed = True
            definition = next(
                (pattern.match(line) for pattern in DEFINITION_PATTERNS if pattern.match(line)),
                None,
            )
            if definition and (current_new or current_old):
                definition_changes.append(
                    (
                        "added" if line.startswith("+") else "deleted",
                        current_new if line.startswith("+") else current_old,
                        definition.group(1),
                    )
                )
    if not sections or not section_changed:
        raise PatchValidationError("Malformed patch contains no deterministic file changes")
    special = set(created) | set(deleted) | {item for pair in renamed for item in pair}
    current_new = None
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            parts = shlex.split(line)
            current_new = _patch_path(parts[3], "b/")
            if current_new not in special:
                modified.append(current_new)
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
    known_ranges = {
        (path, start, end)
        for path, start, end in ranges
        if any(
            (symbol.path[len(repository_prefix) :] if repository_prefix else symbol.path) == path
            and start <= symbol.end_line
            and end >= symbol.start_line
            for symbol in symbols
            if symbol.kind.value != "module"
        )
    }
    analyzable_existing_paths = set(modified) | {old for old, _ in renamed}
    unknown = tuple(
        dict.fromkeys(
            [
                path
                for path in analyzable_existing_paths
                if not any(item.path == path for item in effects)
            ]
            + [
                path
                for path, start, end in ranges
                if path in analyzable_existing_paths and (path, start, end) not in known_ranges
            ]
        )
    )
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
        (item.path, item.symbol)
        for item in scope.symbol_effects
        if item.effect == "symbol_added" and item.symbol
    }
    unexpected_added_symbols = {
        f"{path}:{name}"
        for path, name in added_symbols
        if not _new_symbol_allowed(path, name, policy.allowed_new_symbols)
    }
    all_paths = set(scope.changed_files) | {old for old, _ in scope.renamed_files}
    protected = {path for path in all_paths if is_protected_path(path)}
    dependencies = {path for path in all_paths if is_dependency_file(path)}
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
    uncertain_symbol_files = set(scope.unknown_effects) & set(policy.symbol_scoped_files)
    if uncertain_symbol_files:
        issues.append(
            "Unknown symbol effects require renewed file-level approval: "
            + ", ".join(sorted(uncertain_symbol_files))
        )
    return tuple(issues)


def _patch_path(value: str, prefix: str) -> str:
    if not value.startswith(prefix):
        raise PatchValidationError(f"Patch path is missing {prefix!r} prefix: {value!r}")
    return _validate_relative_path(value[len(prefix) :])


def _metadata_path(value: str) -> str:
    try:
        parts = shlex.split(value)
    except ValueError as exc:
        raise PatchValidationError(f"Malformed patch path: {exc}") from exc
    if len(parts) != 1:
        raise PatchValidationError(f"Malformed patch path: {value!r}")
    return _validate_relative_path(parts[0])


def _validate_relative_path(value: str) -> str:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or value in {".", "/dev/null"}:
        raise PatchValidationError(f"Unsafe patch path: {value!r}")
    return path.as_posix()


def _new_symbol_allowed(path: str, name: str, allowed: tuple[str, ...]) -> bool:
    module = PurePosixPath(path).with_suffix("").as_posix().replace("/", ".")
    if module.endswith(".__init__"):
        module = module[: -len(".__init__")]
    return any(
        value == name or value.endswith((f".{name}", f"::{name}")) or value == f"{module}.{name}"
        for value in allowed
    )


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
