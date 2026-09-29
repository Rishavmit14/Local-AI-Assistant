"""Typed DLP records. They deliberately contain no learner mastery state."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class LearningPath:
    path_id: str
    title: str
    goal: str
    mode: str
    target_level: str
    target_profile: tuple[str, ...]
    target_date: str | None
    hours_per_week: float | None
    target_feasibility: str
    state: str
    current_version: int
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class LearningPathVersion:
    path_id: str
    version: int
    reason: str
    provenance: str
    summary: str
    created_at: str
    metadata: dict[str, Any]
    modules: tuple[dict[str, Any], ...]
    nodes: tuple[dict[str, Any], ...]
    prerequisites: tuple[dict[str, str], ...]
    milestones: tuple[dict[str, Any], ...]
    topological_order: tuple[str, ...]
    adaptation: dict[str, Any] = field(default_factory=dict)


def canonical_curriculum(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize a proposal's curriculum fields without adding inferred facts."""
    path_id = str(payload.get("path_id") or uuid4().hex)
    target_date = payload.get("target_date")
    if isinstance(target_date, date):
        target_date = target_date.isoformat()
    hours = payload.get("hours_per_week")
    return {
        "path_id": path_id,
        "title": payload.get("title", ""),
        "goal": payload.get("goal", ""),
        "mode": payload.get("mode", "topic"),
        "target_level": payload.get("target_level", "unspecified"),
        "target_profile": payload.get("target_profile", []),
        "target_date": target_date,
        "hours_per_week": hours,
        "target_feasibility": payload.get("target_feasibility", "not_assessed"),
        "state": payload.get("state", "draft"),
        "summary": payload.get("summary", ""),
        "reason": payload.get("reason", "initial_generation"),
        "provenance": payload.get("provenance", "owner_supplied"),
        "modules": payload.get("modules", []),
        "nodes": payload.get("nodes", []),
        "prerequisites": payload.get("prerequisites", []),
        "milestones": payload.get("milestones", []),
        "adaptation": payload.get("adaptation", {}),
    }


def version_from_json(path_id: str, version: int, data: str) -> LearningPathVersion:
    import json

    value = json.loads(data)
    return LearningPathVersion(
        path_id,
        version,
        value["reason"],
        value["provenance"],
        value["summary"],
        value["created_at"],
        value["metadata"],
        tuple(value["modules"]),
        tuple(value["nodes"]),
        tuple(value["prerequisites"]),
        tuple(value["milestones"]),
        tuple(value["topological_order"]),
        value.get("adaptation", {}),
    )


def version_payload(curriculum: dict[str, Any], version: int, order: tuple[str, ...]) -> str:
    import json

    return json.dumps(
        {
            "reason": curriculum["reason"],
            "provenance": curriculum["provenance"],
            "summary": curriculum["summary"],
            "created_at": datetime.now(UTC).isoformat(),
            "metadata": {
                key: curriculum[key]
                for key in (
                    "title",
                    "goal",
                    "mode",
                    "target_level",
                    "target_profile",
                    "target_date",
                    "hours_per_week",
                    "target_feasibility",
                    "state",
                )
            },
            "modules": curriculum["modules"],
            "nodes": curriculum["nodes"],
            "prerequisites": curriculum["prerequisites"],
            "milestones": curriculum["milestones"],
            "topological_order": order,
            "adaptation": curriculum.get("adaptation", {}),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
