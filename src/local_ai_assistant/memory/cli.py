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
    remember.add_argument("--supersedes")
    remember.add_argument("--expires-at")
    recall = commands.add_parser("recall")
    recall.add_argument("subject")
    recall.add_argument("--limit", type=int, default=20)
    search = commands.add_parser("search")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=20)
    forget = commands.add_parser("forget")
    forget.add_argument("memory_id")
    resolve = commands.add_parser("resolve-conflict")
    resolve.add_argument("memory_id")
    resolution = resolve.add_mutually_exclusive_group(required=True)
    resolution.add_argument("--keep", action="store_true")
    resolution.add_argument("--discard", action="store_true")
    relate = commands.add_parser("relate")
    relate.add_argument("source_subject")
    relate.add_argument("relationship")
    relate.add_argument("target_subject")
    relate.add_argument("--provenance", required=True)
    relate.add_argument("--confidence", type=float, required=True)
    relationships = commands.add_parser("relationships")
    relationships.add_argument("subject")
    relationships.add_argument("--limit", type=int, default=20)
    forget_relation = commands.add_parser("forget-relation")
    forget_relation.add_argument("relationship_id")
    commands.add_parser("retention")
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
            supersedes=args.supersedes,
            expires_at=args.expires_at,
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
    elif args.command == "forget":
        memory.forget(args.memory_id)
    elif args.command == "resolve-conflict":
        print(json.dumps(asdict(memory.resolve_conflict(args.memory_id, keep=args.keep))))
    elif args.command == "relate":
        print(
            json.dumps(
                asdict(
                    memory.relate(
                        source_subject=args.source_subject,
                        relationship=args.relationship,
                        target_subject=args.target_subject,
                        provenance=args.provenance,
                        confidence=args.confidence,
                    )
                ),
                default=str,
            )
        )
    elif args.command == "relationships":
        print(
            json.dumps(
                [asdict(item) for item in memory.relationships(args.subject, args.limit)],
                default=str,
            )
        )
    elif args.command == "forget-relation":
        memory.forget_relationship(args.relationship_id)
    else:
        print(json.dumps(asdict(memory.enforce_retention())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
