"""Deterministic validation for model-produced implementation plans."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from local_ai_assistant.code_index.symbol_index import SymbolIndex

from .analysis import detect_migration, is_dependency_file, is_protected_path
from .models import ImplementationPlan, IssueSeverity, ScopeCandidate, ValidationIssue


class PlanValidator:
    def __init__(self, repository: Path, symbols: SymbolIndex) -> None:
        self.repository = repository.resolve()
        self.symbols = symbols

    def validate(
        self, plan: ImplementationPlan, evidence: tuple[ScopeCandidate, ...]
    ) -> tuple[ValidationIssue, ...]:
        issues: list[ValidationIssue] = []
        existing_targets = tuple(
            dict.fromkeys((*plan.files_to_inspect, *plan.files_to_modify, *plan.files_to_delete_or_rename))
        )
        for path in existing_targets:
            if self._unsafe(path):
                issues.append(self._error("unsafe_path", "Path is absolute or escapes the repository.", path))
            elif is_protected_path(path):
                issues.append(self._error("protected_path", "Protected/generated path cannot be modified.", path))
            elif not (self.repository / path).is_file():
                issues.append(self._error("missing_file", "Referenced existing file does not exist.", path))
        for path in plan.files_to_create:
            if self._unsafe(path):
                issues.append(self._error("unsafe_new_path", "Proposed-new path is unsafe.", path))
            elif (self.repository / path).exists():
                issues.append(self._error("new_file_exists", "File marked proposed-new already exists.", path))
            elif is_protected_path(path):
                issues.append(self._error("protected_new_path", "Protected/generated path cannot be created.", path))
        known_symbols = {item.identifier for item in self.symbols.symbols} | {
            item.qualified_name for item in self.symbols.symbols
        }
        for symbol in plan.symbols_to_modify:
            if symbol not in known_symbols:
                issues.append(self._error("missing_symbol", "Referenced existing symbol does not exist.", symbol))
        for symbol in plan.symbols_to_create:
            if symbol in known_symbols:
                issues.append(self._error("new_symbol_exists", "Symbol marked proposed-new already exists.", symbol))
        all_files = tuple(dict.fromkeys((*plan.files_to_modify, *plan.files_to_create, *plan.files_to_delete_or_rename)))
        dependency_files = tuple(path for path in all_files if is_dependency_file(path))
        if dependency_files and not plan.dependency_changes:
            issues.append(self._error("unmarked_dependency_change", "Dependency manifest is in modification scope but dependency impact is not declared.", ", ".join(dependency_files)))
        if plan.dependency_changes and not dependency_files:
            issues.append(self._error("missing_dependency_manifest", "Dependency changes require an identified manifest file."))
        for change in plan.dependency_changes:
            if change.manifest not in all_files or not is_dependency_file(change.manifest):
                issues.append(self._error("invalid_dependency_manifest", "Declared dependency impact must reference an in-scope dependency manifest.", change.manifest))
        migration_signals = detect_migration(plan.original_request, all_files)
        migration_files = tuple(path for path in all_files if "migration" in path.lower() or path.endswith(".sql"))
        if migration_signals and not plan.migration_implications:
            issues.append(self._error("unmarked_migration", "Migration implications must be declared."))
        if plan.migration_implications and not migration_files:
            issues.append(self._warning("missing_migration_file", "Migration implications are declared without a migration/SQL target."))
        evidence_files = {item.path for item in evidence}
        unsupported = set(plan.files_to_modify) - evidence_files
        unsupported -= set(plan.files_to_create)
        if unsupported:
            unexplained = {
                path
                for path in unsupported
                if not any(path.lower() in assumption.lower() for assumption in plan.assumptions)
            }
            if unexplained:
                issues.append(self._error("unjustified_scope", "Modification scope exceeds deterministic evidence without a path-specific assumption.", ", ".join(sorted(unexplained))))
            else:
                issues.append(self._warning("scope_beyond_evidence", "Modification scope exceeds deterministic evidence but is explicitly justified.", ", ".join(sorted(unsupported))))
        if len(set(all_files)) > max(12, len(evidence_files) + 3):
            issues.append(self._error("scope_too_large", "Plan scope is wildly larger than deterministic evidence."))
        if len(plan.files_to_modify) != len(set(plan.files_to_modify)) or len(plan.symbols_to_modify) != len(set(plan.symbols_to_modify)):
            issues.append(self._error("duplicate_targets", "Duplicate modification targets must be normalized."))
        if not plan.steps:
            issues.append(self._error("missing_steps", "Implementation plan must contain ordered steps."))
        elif [step.order for step in plan.steps] != list(range(1, len(plan.steps) + 1)):
            issues.append(self._error("invalid_step_order", "Plan steps must be consecutively ordered from one."))
        if not plan.validation_commands:
            issues.append(self._warning("missing_validation", "No validation command is planned."))
        for test in plan.relevant_tests:
            if not test.reason.strip() or not test.command.strip():
                issues.append(self._error("unexplained_test", "Every relevant test requires a reason and command.", test.path))
            if test.path not in {".", "full-suite"} and not (self.repository / test.path).is_file():
                issues.append(self._error("missing_test", "Planned test file does not exist.", test.path))
        return tuple(issues)

    @staticmethod
    def _unsafe(path: str) -> bool:
        value = PurePosixPath(path)
        return value.is_absolute() or ".." in value.parts or not path.strip()

    @staticmethod
    def _error(code, message, target=None):
        return ValidationIssue(IssueSeverity.ERROR, code, message, target)

    @staticmethod
    def _warning(code, message, target=None):
        return ValidationIssue(IssueSeverity.WARNING, code, message, target)
