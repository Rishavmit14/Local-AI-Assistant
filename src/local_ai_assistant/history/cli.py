"""Command-line access to task history, audit, metrics, and exports."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import zipfile
from dataclasses import asdict
from pathlib import Path

from local_ai_assistant.common.config import get_config

from .export import export_task
from .importer import ArtifactImporter
from .metrics import aggregate_metrics
from .models import TaskFilter
from .service import TaskHistoryService
from .store import TaskHistoryStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local Friday task history")
    parser.add_argument("--database", type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("repository", type=Path)
    create.add_argument("request")
    create.add_argument("--branch")
    create.add_argument("--starting-commit")
    import_command = commands.add_parser("import")
    import_command.add_argument("artifacts", nargs="+", type=Path)
    import_command.add_argument("--repository", type=Path)
    list_command = commands.add_parser("list")
    _filters(list_command)
    show = commands.add_parser("show")
    show.add_argument("task_id")
    search = commands.add_parser("search")
    search.add_argument("query")
    _filters(search)
    timeline = commands.add_parser("timeline")
    timeline.add_argument("task_id")
    commands.add_parser("metrics")
    export = commands.add_parser("export")
    export.add_argument("task_id")
    export.add_argument("destination", type=Path)
    export.add_argument("--format", choices=("json", "markdown"), default="json")
    archive = commands.add_parser("archive")
    archive.add_argument("task_id")
    archive.add_argument("destination", type=Path)
    commands.add_parser("orphans")
    prune = commands.add_parser("prune-orphans")
    prune.add_argument("--confirm", action="store_true")
    commands.add_parser("status")
    commands.add_parser("migrate")
    commands.add_parser("storage")
    commands.add_parser("vacuum")
    return parser


def _filters(parser):
    parser.add_argument("--repository")
    parser.add_argument("--branch")
    parser.add_argument("--status")
    parser.add_argument("--classification")
    parser.add_argument("--risk")
    parser.add_argument("--file", dest="affected_file")
    parser.add_argument("--symbol", dest="affected_symbol")
    parser.add_argument("--language")
    parser.add_argument("--outcome")
    parser.add_argument("--date-from")
    parser.add_argument("--date-to")
    parser.add_argument("--limit", type=int, default=100)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = get_config()
    store = TaskHistoryStore(args.database or config.paths.task_history_db)
    service = TaskHistoryService(store)
    if args.command in {"status", "migrate"}:
        print(json.dumps(store.status(), indent=2))
        return 0
    if args.command == "storage":
        print(json.dumps(store.status(), indent=2))
        return 0
    if args.command == "vacuum":
        store.vacuum()
        print(json.dumps(store.status(), indent=2))
        return 0
    if args.command in {"orphans", "prune-orphans"}:
        candidates = _orphan_temporaries(config.paths.var_dir)
        if args.command == "prune-orphans" and args.confirm:
            for path in candidates:
                path.unlink()
        print(json.dumps({"candidates": [str(path) for path in candidates], "deleted": len(candidates) if args.command == "prune-orphans" and args.confirm else 0}, indent=2))
        return 0
    if args.command == "create":
        repository = args.repository.resolve()
        branch = args.branch or _git(repository, "branch", "--show-current")
        commit = args.starting_commit or _git(repository, "rev-parse", "HEAD")
        metadata = {
            "runtime": {
                "model": Path(config.llama.model).name,
                "endpoint_profile": config.llama.base_url,
                "context_size": config.llama.context_size,
            }
        }
        print(json.dumps(service.create_task(args.request, repository, commit, branch, metadata=metadata).to_dict(), indent=2))
        return 0
    if args.command == "import":
        importer = ArtifactImporter(service)
        print(json.dumps([importer.import_path(path, repository=args.repository) for path in args.artifacts], indent=2))
        return 0
    if args.command in {"list", "search"}:
        filters = TaskFilter(
            repository=args.repository, branch=args.branch, status=args.status,
            classification=args.classification, risk=args.risk,
            date_from=args.date_from, date_to=args.date_to,
            affected_file=args.affected_file, affected_symbol=args.affected_symbol,
            language=args.language, outcome=args.outcome,
            text=args.query if args.command == "search" else None, limit=args.limit,
        )
        print(json.dumps([task.to_dict() for task in service.list(filters)], indent=2))
        return 0
    if args.command == "show":
        print(json.dumps(service.summary(args.task_id), indent=2, default=str))
        return 0
    if args.command == "timeline":
        print(json.dumps([asdict(item) for item in service.timeline(args.task_id)], indent=2))
        return 0
    if args.command == "metrics":
        print(json.dumps(asdict(aggregate_metrics(store)), indent=2))
        return 0
    if args.command == "export":
        print(export_task(service, args.task_id, args.destination, args.format))
        return 0
    if args.command == "archive":
        args.destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="local-ai-archive-") as directory:
            root = Path(directory)
            json_report = export_task(service, args.task_id, root / "task.json", "json")
            markdown_report = export_task(service, args.task_id, root / "task.md", "markdown")
            with zipfile.ZipFile(args.destination, "w", zipfile.ZIP_DEFLATED) as archive_file:
                archive_file.write(json_report, "task.json")
                archive_file.write(markdown_report, "task.md")
        print(args.destination)
        return 0
    return 2


def _git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=repository, text=True, capture_output=True, timeout=10
    )
    if result.returncode:
        raise SystemExit(result.stderr.strip() or "Git identity query failed")
    return result.stdout.strip()


def _orphan_temporaries(var_dir: Path) -> tuple[Path, ...]:
    root = var_dir.resolve()
    if not root.exists():
        return ()
    candidates = []
    for path in root.rglob(".*.tmp"):
        resolved = path.resolve()
        if path.is_file() and (resolved.parent == root or root in resolved.parents):
            candidates.append(path)
    return tuple(sorted(candidates))


if __name__ == "__main__":
    raise SystemExit(main())
