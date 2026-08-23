"""Planning-only command line interface."""

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import asdict
from pathlib import Path

from local_ai_assistant.code_index.repository import CodeRAG
from local_ai_assistant.common.config import get_config
from local_ai_assistant.common.logging import configure_logging

from .service import PlannerService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local deterministic-scope implementation planner")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("analyze", "generate"):
        command = commands.add_parser(name)
        command.add_argument("repo")
        command.add_argument("request")
        if name == "generate":
            command.add_argument("--output", type=Path)
    validate = commands.add_parser("validate")
    validate.add_argument("repo")
    validate.add_argument("plan", type=Path)
    for name in ("show-files", "show-symbols", "show-risk", "show-approval"):
        command = commands.add_parser(name)
        command.add_argument("plan", type=Path)
    export = commands.add_parser("export")
    export.add_argument("plan", type=Path)
    export.add_argument("output", type=Path)
    return parser


def _service(repo_name: str):
    config = get_config()
    repository = (config.paths.code_repo_dir / repo_name).resolve()
    rag = CodeRAG(config=config)
    if not rag.load():
        raise SystemExit("No code index found; run local-ai-code-rag --reindex first.")
    if not repository.is_dir():
        raise SystemExit(f"Repository not found: {repository}")
    return PlannerService(
        repository,
        rag.symbol_index,
        rag.llm,
        config.paths.code_index_dir / "plans" / repo_name,
        rag.retrieve,
    )


def main(argv: list[str] | None = None) -> int:
    config = get_config()
    configure_logging(config.runtime)
    args = build_parser().parse_args(argv)
    if args.command.startswith("show-"):
        artifact = PlannerService.load(args.plan)
        if args.command == "show-files":
            value = {"inspect": artifact.plan.files_to_inspect, "modify": artifact.plan.files_to_modify, "create": artifact.plan.files_to_create, "delete_or_rename": artifact.plan.files_to_delete_or_rename}
        elif args.command == "show-symbols":
            value = {"modify": artifact.plan.symbols_to_modify, "create": artifact.plan.symbols_to_create}
        elif args.command == "show-risk":
            value = asdict(artifact.plan.risk)
        else:
            value = asdict(artifact.plan.approval)
        print(json.dumps(value, indent=2))
        return 0
    if args.command == "export":
        PlannerService.load(args.plan)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(args.plan, args.output)
        print(args.output)
        return 0
    service = _service(args.repo)
    if args.command == "analyze":
        classification, candidates = service.analyze(args.request)
        print(json.dumps({"classification": asdict(classification), "scope_candidates": [asdict(item) for item in candidates]}, indent=2))
        return 0
    if args.command == "generate":
        artifact = service.generate(args.request)
        destination = service.persist(artifact, args.output)
        print(json.dumps(artifact.to_dict(), indent=2))
        print(f"Plan saved: {destination}")
        return 0
    artifact = PlannerService.load(args.plan)
    issues = (
        *service.identity_issues(artifact),
        *service.validator.validate(artifact.plan, artifact.scope_candidates),
    )
    print(json.dumps([asdict(issue) for issue in issues], indent=2))
    return 1 if any(issue.severity.value == "error" for issue in issues) else 0


if __name__ == "__main__":
    raise SystemExit(main())
