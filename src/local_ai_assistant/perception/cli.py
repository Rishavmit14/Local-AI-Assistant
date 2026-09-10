"""Owner-only local perception recovery and ingestion commands."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from local_ai_assistant.common.config import get_config

from .screen import ScreenCaptureService


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage private Friday perception captures.")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("ingest", help="Copy an owner-selected screenshot into private retention.")
    ingest.add_argument("image", type=Path)
    commands.add_parser("list", help="Show capture metadata only.")
    args = parser.parse_args()
    service = ScreenCaptureService(get_config().paths.perception_dir)
    if args.command == "ingest":
        print(json.dumps(asdict(service.ingest_owner_file(args.image)), sort_keys=True))
    else:
        print(json.dumps([asdict(item) for item in service.recent()], sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
