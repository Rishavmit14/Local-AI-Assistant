"""Owner-controlled command-line access to local Friday memory."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from local_ai_assistant.common.config import get_config

from .service import FridayMemoryService, MemoryKind


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local Friday memory")
    parser.add_argument("--database", type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    remember = commands.add_parser("remember")
    remember.add_argument("kind", choices=tuple(item.value for item in MemoryKind))
    remember.add_argument("subject")
    remember.add_argument("content")
    remember.add_argument("--provenance", required=True)
    remember.add_argument("--confidence", type=float, required=True)
    recall = commands.add_parser("recall")
    recall.add_argument("subject")
    recall.add_argument("--limit", type=int, default=20)
    search = commands.add_parser("search")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=20)
    forget = commands.add_parser("forget")
    forget.add_argument("memory_id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    memory = FridayMemoryService(args.database or get_config().paths.memory_db)
    if args.command == "remember":
        record = memory.remember(
            kind=MemoryKind(args.kind),
            subject=args.subject,
            content=args.content,
            provenance=args.provenance,
            confidence=args.confidence,
        )
        print(json.dumps(asdict(record), default=str))
    elif args.command == "recall":
        print(
            json.dumps(
                [asdict(item) for item in memory.recall(args.subject, args.limit)], default=str
            )
        )
    elif args.command == "search":
        print(
            json.dumps(
                [asdict(item) for item in memory.search(args.query, args.limit)], default=str
            )
        )
    else:
        memory.forget(args.memory_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
