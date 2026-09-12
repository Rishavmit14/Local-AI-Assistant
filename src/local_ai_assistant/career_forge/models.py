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


class AssistanceLevel(StrEnum):
    PROMPT = "prompt"
    CONCEPTUAL_HINT = "conceptual_hint"
    STRONG_HINT = "strong_hint"
    DECOMPOSITION = "decomposition"
    PARTIAL_EXAMPLE = "partial_example"
    FULL_DEMONSTRATION = "full_demonstration"


class TutorMode(StrEnum):
    EXPLAIN = "explain"
    HINT = "hint"
    GUIDE = "guide"
    PAIR = "pair"
    REVIEW = "review"
    CHALLENGE = "challenge"
    TEACH_BACK = "teach_back"
    INTERVIEW = "interview"


class AttemptEvaluation(StrEnum):
    PENDING = "pending"
    CORRECT = "correct"
    INCORRECT = "incorrect"
    UNCERTAIN = "uncertain"


class LessonPhase(StrEnum):
    WHY = "why_it_matters"
    MENTAL_MODEL = "mental_model"
    EXAMPLE = "guided_example"
    QUESTION = "owner_attempt"
    EVALUATION = "evaluation"
    TEACH_BACK = "teach_back"
    NEXT = "next_action"


@dataclass(frozen=True, slots=True)
class Competency:
    competency_id: str
    domain: str
    title: str
    prerequisites: tuple[str, ...] = ()
    project_family: str | None = None
