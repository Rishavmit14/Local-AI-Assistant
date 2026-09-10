"""Typed Career Forge curriculum records; no self-report mastery state exists."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class MasteryLevel(StrEnum):
    UNVERIFIED = "unverified"
    RECOGNIZE = "recognize"
    EXPLAIN = "explain"
    APPLY_WITH_HELP = "apply_with_help"
    APPLY_INDEPENDENTLY = "apply_independently"
    TRANSFER_DEBUG = "transfer_debug"
    TEACH_DEFEND = "teach_defend"


@dataclass(frozen=True, slots=True)
class Competency:
    competency_id: str
    domain: str
    title: str
    prerequisites: tuple[str, ...] = ()
    project_family: str | None = None

