#!/usr/bin/env python3
"""Deterministic Stage 7 SQLite history benchmark."""

from __future__ import annotations

import argparse
import tempfile
import time
from dataclasses import asdict
from pathlib import Path

from local_ai_assistant.history.metrics import aggregate_metrics
from local_ai_assistant.history.models import TaskFilter
from local_ai_assistant.history.service import TaskHistoryService
from local_ai_assistant.history.store import TaskHistoryStore


def measure(action):
    started = time.perf_counter()
    result = action()
    return result, time.perf_counter() - started


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", type=int, default=3000)
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory(prefix="local-ai-history-") as directory:
        root = Path(directory)
        service = TaskHistoryService(TaskHistoryStore(root / "tasks.sqlite3"))
        durations = []
        for number in range(args.tasks):
            _, elapsed = measure(
                lambda number=number: service.create_task(
                    f"Synthetic task {number}", root / f"repo-{number % 8}",
                    f"{number:040x}", "main",
                    created_at=f"2026-01-{1 + number % 28:02d}T00:00:{number % 60:02d}+00:00",
                )
            )
            durations.append(elapsed)
        _, recent = measure(lambda: service.list(TaskFilter(limit=100)))
        _, filtered = measure(lambda: service.list(TaskFilter(repository=str((root / "repo-3").resolve()), limit=100)))
        task = service.list(TaskFilter(limit=1))[0]
        _, timeline = measure(lambda: service.timeline(task.task_id))
        metrics, aggregation = measure(lambda: aggregate_metrics(service.store))
        print(
            {
                "tasks": args.tasks,
                "average_write_ms": sum(durations) / len(durations) * 1000,
                "recent_query_ms": recent * 1000,
                "filtered_query_ms": filtered * 1000,
                "timeline_ms": timeline * 1000,
                "metrics_ms": aggregation * 1000,
                "database_bytes": service.store.path.stat().st_size,
                "metrics": asdict(metrics),
            }
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
