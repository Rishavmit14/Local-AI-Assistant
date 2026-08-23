"""Deterministic task signals and conservative classification."""

from __future__ import annotations

from .models import TaskCategory, TaskClassification

SIGNALS = {
    TaskCategory.AUTHENTICATION_AUTHORIZATION: ("auth", "login", "permission", "authorize", "token"),
    TaskCategory.SECURITY_SENSITIVE: ("security", "secret", "credential", "crypto", "vulnerability"),
    TaskCategory.DATABASE_MIGRATION: ("migration", "schema", "drop table", "alter table", "database"),
    TaskCategory.DEPLOYMENT_OPERATIONS: ("deploy", "systemd", "service", "production", "docker"),
    TaskCategory.DEPENDENCY_CHANGE: ("dependency", "package", "upgrade", "requirements", "pyproject"),
    TaskCategory.BUG_FIX: ("fix", "bug", "broken", "failure", "regression"),
    TaskCategory.FEATURE: ("add", "implement", "feature", "support"),
    TaskCategory.REFACTOR: ("refactor", "restructure", "rename", "cleanup"),
    TaskCategory.TEST: ("test", "pytest", "coverage"),
    TaskCategory.DOCUMENTATION: ("document", "readme", "docstring", "documentation"),
    TaskCategory.CONFIGURATION: ("config", "setting", "environment variable"),
    TaskCategory.EXPLAIN: ("explain", "describe", "how does", "what is"),
}


def classify_task(request: str) -> TaskClassification:
    normalized = request.lower()
    matches = [
        (category, [word for word in words if word in normalized])
        for category, words in SIGNALS.items()
        if any(word in normalized for word in words)
    ]
    if not matches:
        return TaskClassification(TaskCategory.UNKNOWN_MIXED, 0.2, ("No deterministic category signal matched.",), request)
    specific = [
        item
        for item in matches
        if item[0] not in {TaskCategory.FEATURE, TaskCategory.BUG_FIX}
    ]
    if specific:
        matches = specific
    highest = matches[0]
    competing = matches[1:]
    if competing and highest[0] not in {
        TaskCategory.AUTHENTICATION_AUTHORIZATION,
        TaskCategory.SECURITY_SENSITIVE,
        TaskCategory.DATABASE_MIGRATION,
        TaskCategory.DEPLOYMENT_OPERATIONS,
        TaskCategory.DEPENDENCY_CHANGE,
    }:
        reasons = tuple(f"{category.value}: {', '.join(words)}" for category, words in matches)
        return TaskClassification(TaskCategory.UNKNOWN_MIXED, 0.45, reasons, request)
    return TaskClassification(highest[0], min(0.95, 0.65 + 0.1 * len(highest[1])), (f"Matched deterministic signals: {', '.join(highest[1])}.",), request)
