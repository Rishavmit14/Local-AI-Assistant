"""Bounded, redacted projections of canonical Stage 5 evidence."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from local_ai_assistant.execution.history import redact_data
from local_ai_assistant.validation.service import load_validation_report


def _latest(records: tuple[dict, ...]) -> dict | None:
    return records[0] if records else None


def validation_summary(history, task_id: str, *, limit: int = 20) -> dict[str, Any]:
    record = _latest(history.store.artifact_records(task_id, "validations", limit))
    if record is None:
        return {"task_id": task_id, "available": False, "results": []}
    path = Path(str(record.get("artifact_path", "")))
    try:
        report = load_validation_report(history.validate_artifact_path(path))
    except Exception:
        report = _bounded_json(history, path)
    if report is None:
        return {"task_id": task_id, "available": False, "artifact": {"id": record.get("artifact_id"), "hash": record.get("artifact_hash")}, "results": []}
    results = []
    for item in report.get("results", [])[:200]:
        results.append({
            "validator_id": str(item.get("step_id", ""))[:200],
            "name": str(item.get("step_id", ""))[:200],
            "status": "skipped" if item.get("skipped") else ("passed" if item.get("success") else "failed"),
            "requirement": _requirement(report, item.get("step_id")),
            "failure_classification": _failure_classification(report, item.get("step_id")),
            "duration_seconds": item.get("duration_seconds"),
            "cached": bool(item.get("cached", False)),
            "message": str(item.get("summary", ""))[:500],
            "provenance": redact_data(item.get("provenance")) if item.get("provenance") else None,
        })
    decision = report.get("decision", {})
    return {"task_id": task_id, "available": True, "overall_decision": decision.get("status"), "required_passed": all(r["status"] in {"passed", "skipped"} for r in results if r["requirement"] == "required"), "results": results, "artifact": {"id": record.get("artifact_id"), "hash": record.get("artifact_hash")}}


def review_summary(history, task_id: str, *, limit: int = 20) -> dict[str, Any]:
    record = _latest(history.store.artifact_records(task_id, "validations", limit))
    if record is None:
        return {"task_id": task_id, "available": False, "findings": []}
    try:
        report = load_validation_report(history.validate_artifact_path(Path(str(record["artifact_path"]))))
    except Exception:
        report = _bounded_json(history, Path(str(record["artifact_path"])))
    if report is None:
        return {"task_id": task_id, "available": False, "findings": []}
    review = report.get("review", {})
    findings = []
    for index, item in enumerate(review.get("findings", [])[:200]):
        source = str(item.get("origin", "deterministic"))
        findings.append({"finding_id": f"{task_id}:review:{index}", "source": source, "category": str(item.get("category", "unknown"))[:120], "severity": str(item.get("severity", "info")), "blocking": bool(item.get("blocking", False)), "file": item.get("file"), "symbol": item.get("symbol"), "evidence": str(item.get("evidence", ""))[:500], "provenance": str(item.get("check_name", "review"))[:120]})
    return {"task_id": task_id, "available": True, "final_decision": report.get("decision", {}).get("status"), "blocking_count": sum(1 for f in findings if f["blocking"]), "security_count": sum(1 for f in findings if f["category"] == "security" or "security" in f["category"]), "deterministic_count": sum(1 for f in findings if f["source"] == "deterministic"), "model_assisted_count": sum(1 for f in findings if f["source"] == "model"), "findings": findings}


def _requirement(report: dict, step_id: str | None) -> str:
    for group in (report.get("plan", {}).get("targeted_steps", []), report.get("plan", {}).get("final_steps", [])):
        for step in group:
            if step.get("step_id") == step_id:
                return str(step.get("requirement", "required"))
    return "required"


def _failure_classification(report: dict, step_id: str | None) -> str | None:
    for failure in report.get("failures", []):
        if step_id in failure.get("affected_tests", ()) or not step_id:
            return str(failure.get("category", "unknown"))
    return None


def _bounded_json(history, path: Path) -> dict | None:
    """Fallback for older valid artifacts: still enforce roots and a small read."""
    try:
        safe = history.validate_artifact_path(path)
        if safe.stat().st_size > 2_000_000:
            return None
        value = json.loads(safe.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or not isinstance(value.get("results"), list):
            return None
        return value
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None
