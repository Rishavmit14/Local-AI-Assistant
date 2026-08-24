"""Deterministic operational metrics over task history."""

from __future__ import annotations

from .models import MetricsSnapshot
from .store import TaskHistoryStore


def aggregate_metrics(store: TaskHistoryStore) -> MetricsSnapshot:
    with store._connect() as connection:
        total = connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        status = _counts(connection, "SELECT status, COUNT(*) FROM tasks GROUP BY status")
        classification = _counts(
            connection, "SELECT classification, COUNT(*) FROM tasks GROUP BY classification"
        )
        risk = _counts(connection, "SELECT risk, COUNT(*) FROM tasks GROUP BY risk")
        repositories = _counts(
            connection, "SELECT repository, COUNT(*) FROM tasks GROUP BY repository"
        )
        over_time = _counts(
            connection,
            "SELECT substr(created_at, 1, 10), COUNT(*) FROM tasks GROUP BY substr(created_at, 1, 10) ORDER BY 1",
        )
        outcome = _counts(connection, "SELECT COALESCE(outcome, 'unknown'), COUNT(*) FROM tasks GROUP BY outcome")
        language = _counts(
            connection,
            "SELECT language, COUNT(DISTINCT task_id) FROM affected_files WHERE language IS NOT NULL GROUP BY language",
        )
        failures = _counts(
            connection,
            "SELECT failure_category, COUNT(*) FROM metrics_summary WHERE failure_category IS NOT NULL GROUP BY failure_category",
        )
        row = connection.execute(
            """SELECT AVG(duration_seconds), AVG(planning_seconds), AVG(validation_seconds),
                      AVG(repairs), SUM(scope_violations), SUM(reapprovals), SUM(rollbacks),
                      SUM(validation_failures), SUM(security_blocking_findings), SUM(tests_run),
                      SUM(tool_calls), SUM(model_calls), SUM(input_tokens), SUM(output_tokens),
                      AVG(index_refresh_seconds),
                      AVG(CASE WHEN first_pass_success IS NOT NULL THEN first_pass_success END),
                      AVG(plan_validation_success), AVG(patch_preflight_success),
                      AVG(first_targeted_test_pass), AVG(first_full_suite_pass),
                      SUM(repeated_failures), SUM(review_blocking_findings), AVG(commit_success)
               FROM tasks LEFT JOIN metrics_summary USING(task_id)"""
        ).fetchone()
    succeeded = status.get("succeeded", 0)
    return MetricsSnapshot(
        total, status, classification, risk, repositories, language, over_time, outcome, failures,
        succeeded / total if total else 0.0,
        row[0], row[1], row[2], float(row[3] or 0), float(row[15] or 0),
        int(row[4] or 0), int(row[5] or 0), int(row[6] or 0), int(row[7] or 0),
        int(row[8] or 0), int(row[9] or 0), int(row[10] or 0), int(row[11] or 0),
        int(row[12]) if row[12] is not None else None,
        int(row[13]) if row[13] is not None else None,
        row[14], row[16], row[17], row[18], row[19], int(row[20] or 0),
        int(row[21] or 0), row[22],
    )


def _counts(connection, query: str) -> dict[str, int]:
    return {str(row[0]): int(row[1]) for row in connection.execute(query)}
