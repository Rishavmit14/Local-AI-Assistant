"""Controlled Stage 8 isolation inspection and lifecycle CLI."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from local_ai_assistant.common.config import get_config
from local_ai_assistant.history.models import TaskStatus
from local_ai_assistant.history.service import TaskHistoryService
from local_ai_assistant.history.store import TaskHistoryStore

from .checkpoints import CheckpointManager
from .errors import IsolationError
from .models import NetworkPolicy, ResourcePolicy
from .recovery import inspect_recovery
from .sandbox import select_backend
from .worktrees import WorktreeManager


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Friday task isolation operations")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("capabilities")
    create = subparsers.add_parser("create")
    create.add_argument("repository", type=Path)
    create.add_argument("task_id")
    create.add_argument("starting_commit")
    create.add_argument("plan_hash")
    create.add_argument("--approval-token", required=True)
    status = subparsers.add_parser("status")
    status.add_argument("repository", type=Path)
    status.add_argument("task_id")
    checkpoint = subparsers.add_parser("checkpoint")
    checkpoint.add_argument("repository", type=Path)
    checkpoint.add_argument("task_id")
    checkpoint.add_argument("plan_hash")
    checkpoint.add_argument("label")
    rollback = subparsers.add_parser("rollback")
    rollback.add_argument("repository", type=Path)
    rollback.add_argument("task_id")
    rollback.add_argument("plan_hash")
    rollback.add_argument("label")
    cleanup = subparsers.add_parser("cleanup")
    cleanup.add_argument("repository", type=Path)
    cleanup.add_argument("task_id")
    cleanup.add_argument("--delete-branch", action="store_true")
    subparsers.add_parser("recovery")
    subparsers.add_parser("smoke")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = get_config()
    manager = WorktreeManager(config.paths.worktree_dir)
    try:
        if args.command == "capabilities":
            print(json.dumps(asdict(select_backend(config.isolation.backend).capabilities()), default=str, indent=2))
        elif args.command == "create":
            if args.approval_token != args.plan_hash:
                raise IsolationError("Exact approved plan token is required")
            repository = args.repository.resolve(strict=True)
            history = TaskHistoryService(TaskHistoryStore(config.paths.task_history_db))
            task = history.get(args.task_id)
            if (
                task is None
                or Path(task.repository).resolve() != repository
                or task.starting_commit != args.starting_commit
                or task.plan_hash != args.plan_hash
                or task.status is not TaskStatus.APPROVED
            ):
                raise IsolationError(
                    "Persisted approved task identity does not match this worktree request"
                )
            identity = manager.create(
                repository, args.task_id, args.starting_commit, args.plan_hash
            )
            print(json.dumps(identity.to_dict(), indent=2))
        elif args.command == "status":
            print(json.dumps(manager.load(args.repository, args.task_id).to_dict(), indent=2))
        elif args.command == "checkpoint":
            identity = manager.load(
                args.repository, args.task_id, plan_hash=args.plan_hash
            )
            record = CheckpointManager(config.paths.isolation_dir / "checkpoints").create(
                Path(identity.worktree), args.task_id, args.plan_hash, args.label
            )
            print(json.dumps({"checkpoint_id": record.checkpoint_id, "head": record.head}, indent=2))
        elif args.command == "rollback":
            identity = manager.load(
                args.repository, args.task_id, plan_hash=args.plan_hash
            )
            checkpoints = CheckpointManager(config.paths.isolation_dir / "checkpoints")
            checkpoints.restore(
                Path(identity.worktree),
                checkpoints.load(args.task_id, args.label, args.plan_hash),
            )
            print(json.dumps({"status": "rolled_back", "task_id": args.task_id}))
        elif args.command == "cleanup":
            identity = manager.load(args.repository, args.task_id)
            print(json.dumps(manager.cleanup(identity, delete_branch=args.delete_branch).to_dict(), indent=2))
        elif args.command == "recovery":
            print(json.dumps([asdict(item) for item in inspect_recovery(config.paths.worktree_dir)], indent=2))
        elif args.command == "smoke":
            backend = select_backend(config.isolation.backend)
            result = backend.run(
                ("/usr/bin/true",),
                Path.cwd(),
                config.paths.isolation_dir / "smoke",
                resources=ResourcePolicy(wall_seconds=5),
                network=NetworkPolicy(config.isolation.network_policy),
            )
            print(json.dumps(asdict(result), default=str, indent=2))
        return 0
    except IsolationError as exc:
        print(f"Isolation error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
