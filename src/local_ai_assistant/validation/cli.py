"""Validation/review/security command-line interface."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path

from local_ai_assistant.common.config import get_config
from local_ai_assistant.execution.history import redacted_json
from local_ai_assistant.planning.analysis import scope_guard_from_plan
from local_ai_assistant.planning.patch_scope import worktree_diff
from local_ai_assistant.planning.service import PlannerService

from .errors import ValidationArtifactError
from .failures import classify_failure
from .review import deterministic_review
from .security import scan_changed_content
from .service import (
    ValidationService,
    load_validation_plan,
    load_validation_report,
    persist_validation_plan,
    persist_validation_report,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deterministic Stage 5 validation intelligence")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build-plan")
    build.add_argument("plan", type=Path)
    build.add_argument("--output", type=Path, required=True)
    show = commands.add_parser("show-plan")
    show.add_argument("validation_plan", type=Path)
    for name in ("run-targeted", "run-required"):
        run = commands.add_parser(name)
        run.add_argument("plan", type=Path)
        run.add_argument("validation_plan", type=Path)
        run.add_argument("--output", type=Path)
    failure = commands.add_parser("classify-failure")
    failure.add_argument("command_text")
    failure.add_argument("output", type=Path)
    failure.add_argument("--exit-code", type=int, default=1)
    review = commands.add_parser("review-diff")
    review.add_argument("plan", type=Path)
    security = commands.add_parser("security-scan")
    security.add_argument("--diff", type=Path)
    findings = commands.add_parser("show-findings")
    findings.add_argument("report", type=Path)
    export = commands.add_parser("export-report")
    export.add_argument("report", type=Path)
    export.add_argument("destination", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "show-plan":
        print(json.dumps(load_validation_plan(args.validation_plan).to_dict(), indent=2))
        return 0
    if args.command == "classify-failure":
        value = classify_failure(
            args.command_text,
            args.exit_code,
            args.output.read_text(errors="replace"),
        )
        print(json.dumps(_json(value), indent=2))
        return 0
    if args.command == "show-findings":
        value = load_validation_report(args.report)
        print(json.dumps(value.get("review", {}).get("findings", ()), indent=2))
        return 0
    if args.command == "export-report":
        value = load_validation_report(args.report)
        destination = _safe_output_path(args.destination)
        destination.write_text(redacted_json(value, indent=2) + "\n")
        return 0
    config = get_config()
    if args.command == "security-scan":
        diff = args.diff.read_text() if args.diff else worktree_diff(Path.cwd())
        findings = scan_changed_content(diff)
        print(json.dumps([_json(item) for item in findings], indent=2))
        return 1 if any(item.blocking for item in findings) else 0
    artifact = PlannerService.load(args.plan)
    repository = Path(artifact.repository).resolve()
    service = ValidationService(
        repository,
        config.paths.code_index_dir / "validation-cache.json",
    )
    if args.command == "build-plan":
        plan = service.build(artifact)
        persist_validation_plan(plan, _safe_output_path(args.output))
        print(json.dumps(plan.to_dict(), indent=2))
        return 0
    if args.command == "review-diff":
        review = deterministic_review(
            repository,
            artifact.plan,
            scope_guard_from_plan(artifact.plan),
            worktree_diff(repository),
        )
        print(json.dumps(_json(review), indent=2))
        return 1 if any(item.blocking for item in review.findings) else 0
    validation_plan = load_validation_plan(args.validation_plan)
    report = service.run(
        artifact,
        validation_plan,
        targeted_only=args.command == "run-targeted",
        perform_review=args.command == "run-required",
    )
    if args.output:
        persist_validation_report(report, _safe_output_path(args.output))
    print(json.dumps(report.to_dict(), indent=2))
    return 0 if report.decision.status.value.startswith("pass") else 1


def _json(value):
    return asdict(value) if is_dataclass(value) else value


def _safe_output_path(path: Path) -> Path:
    if path.is_absolute() or ".." in path.parts:
        raise ValidationArtifactError("Export destination must be repository-relative")
    destination = (Path.cwd() / path).resolve()
    root = Path.cwd().resolve()
    if destination != root and root not in destination.parents:
        raise ValidationArtifactError("Export destination escapes the working repository")
    destination.parent.mkdir(parents=True, exist_ok=True)
    return destination


if __name__ == "__main__":
    raise SystemExit(main())
