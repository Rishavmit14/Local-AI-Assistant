"""Deterministic unified-diff scope extraction and plan-policy enforcement."""

from __future__ import annotations

import re
from dataclasses import dataclass

from local_ai_assistant.code_index.models import SymbolRecord

from .models import ScopeGuardPolicy

HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


@dataclass(frozen=True, slots=True)
class PatchScope:
    modified_files: tuple[str, ...]
    created_files: tuple[str, ...]
    deleted_files: tuple[str, ...]
    renamed_files: tuple[tuple[str, str], ...]
    changed_symbols: tuple[str, ...]

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
    return PatchScope(
        tuple(dict.fromkeys(modified)),
        tuple(dict.fromkeys(created)),
        tuple(dict.fromkeys(deleted)),
        tuple(dict.fromkeys(renamed)),
        tuple(sorted(touched)),
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
    for label, values in (
        ("modified", unexpected_modified),
        ("created", unexpected_created),
        ("deleted", unexpected_deleted),
        ("renamed", unexpected_renames),
        ("symbols", unexpected_symbols),
    ):
        if values:
            issues.append(f"Unplanned {label}: {', '.join(sorted(values))}")
    if len(scope.changed_files) > policy.max_file_count:
        issues.append("Patch exceeds planned file count.")
    if len(scope.changed_symbols) > policy.max_symbol_count:
        issues.append("Patch exceeds planned symbol count.")
    return tuple(issues)
