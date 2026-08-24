"""Stage 4 execution and tool-policy CLI."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from local_ai_assistant.code_index.repository import CodeRAG
from local_ai_assistant.common.config import get_config
from local_ai_assistant.planning.analysis import scope_guard_from_plan
from local_ai_assistant.planning.models import plan_approval_token
from local_ai_assistant.planning.service import PlannerService

from .history import load_report, persist_report
from .loop import ExecutionLoop, LoopLimits
from .models import ExecutionReport
from .registry import ToolContext, default_registry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan-bound controlled coding execution")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("show-tools")
    policy = sub.add_parser("show-policy")
    policy.add_argument("plan", type=Path)
    history = sub.add_parser("show-history")
    history.add_argument("history", type=Path)
    execute = sub.add_parser("execute")
    execute.add_argument("repo")
    execute.add_argument("plan", type=Path)
    execute.add_argument("--dry-run", action="store_true")
    execute.add_argument("--approval-token")
    execute.add_argument("--max-steps", type=int)
    execute.add_argument("--max-repairs", type=int)
    execute.add_argument("--human-review", action="store_true")
    execute.add_argument("--report", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    registry = default_registry()
    if args.command == "show-tools":
        print(json.dumps([asdict(item) for item in registry.specs()], indent=2))
        return 0
    if args.command == "show-history":
        print(json.dumps(load_report(args.history), indent=2))
        return 0
    artifact = PlannerService.load(args.plan)
    policy = scope_guard_from_plan(artifact.plan)
    if args.command == "show-policy":
        print(json.dumps(asdict(policy), indent=2))
        return 0
    if not args.dry_run and not args.human_review:
        raise SystemExit(
            "Mutating execution requires local-ai-code-agent --tool-loop with the full Git safety bundle."
        )
    config = get_config()
    repository = (config.paths.code_repo_dir / args.repo).resolve()
    rag = CodeRAG(config=config)
    if not rag.load():
        raise SystemExit("No code index found; refresh it before execution.")
    service = PlannerService(
        repository,
        rag.symbol_index,
        rag.llm,
        config.paths.code_index_dir / "plans" / args.repo,
        rag.retrieve,
    )
    identity = service.identity_issues(artifact)
    if identity:
        raise SystemExit(identity[0].message)
    if args.human_review and not args.dry_run:
        print("Human review stop: no mutation performed.")
        return 0
    context = ToolContext(repository, artifact, policy, rag.symbol_index, args.approval_token)
    limits = config.execution
    result = ExecutionLoop(
        rag.llm,
        default_registry(config.execution),
        context,
        LoopLimits(
            max_steps=max(1, args.max_steps or limits.max_steps),
            max_mutations=limits.max_mutations,
            max_repairs=max(
                0, args.max_repairs if args.max_repairs is not None else limits.max_repairs
            ),
            max_replans=limits.max_replans,
            context_characters=limits.context_characters,
        ),
    ).run(dry_run=args.dry_run)
    report = ExecutionReport(
        1,
        artifact.plan.task_id,
        plan_approval_token(artifact.plan),
        str(repository),
        artifact.starting_commit,
        result.status,
        (plan_approval_token(artifact.plan),),
        tuple(context.events),
        repairs=result.repairs,
        replans=result.replans,
    )
    destination = (
        args.report or config.paths.code_index_dir / "executions" / f"{artifact.plan.task_id}.json"
    )
    persist_report(report, destination)
    print(json.dumps(report.to_dict(), indent=2))
    return 0 if result.status == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
