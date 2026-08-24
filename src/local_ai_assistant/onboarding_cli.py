"""Safe repository onboarding CLI; it performs no project execution."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .common.config import get_config
from .onboarding import RepositoryOnboardingError, RepositoryOnboardingService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="local-ai-repo")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    inspect = sub.add_parser("inspect"); inspect.add_argument("repository_id")
    scan = sub.add_parser("scan"); scan.add_argument("repository_id"); scan.add_argument("path", type=Path)
    readiness = sub.add_parser("readiness"); readiness.add_argument("repository_id")
    dry = sub.add_parser("dry-run"); dry.add_argument("repository_id"); dry.add_argument("task")
    args = parser.parse_args(argv)
    service = RepositoryOnboardingService(get_config())
    try:
        if args.command == "list":
            value = [item.to_dict() for item in service.list_profiles()]
        elif args.command == "inspect":
            value = service.get(args.repository_id)
            if value is None:
                raise RepositoryOnboardingError("unknown repository")
            value = value.to_dict()
        elif args.command == "scan":
            value = service.register(args.repository_id, args.path).to_dict()
        elif args.command == "readiness":
            value = service.readiness(args.repository_id).to_dict()
        else:
            value = service.dry_run(args.repository_id, args.task)
    except RepositoryOnboardingError as exc:
        parser.exit(2, f"repository onboarding error: {exc}\n")
    print(json.dumps(value, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
