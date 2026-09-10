"""Small deterministic V1 mission briefs before adaptive generation is qualified."""

from __future__ import annotations

from dataclasses import dataclass

from .models import Competency


@dataclass(frozen=True, slots=True)
class MissionBrief:
    competency_id: str
    title: str
    why_it_matters: str
    verification: str
    mental_model: str
    owner_attempt: str
    teach_back: str
    project_family: str | None


_BRIEFS = {
    "se.python": MissionBrief(
        "se.python", "Verify Python state and functions",
        "ML systems are software systems: silent mutation and unclear contracts corrupt experiments.",
        "Explain the difference between a mutable default argument and a fresh local list, then predict each result.",
        "A function call binds names; mutable objects are shared only when the same object is reused.",
        "Write a small function and tests that expose then repair a mutable-default bug.",
        "Defend why the repaired version is safe and name one test that would catch a regression.",
        None,
    ),
}


def mission_brief(competency: Competency) -> MissionBrief:
    return _BRIEFS.get(
        competency.competency_id,
        MissionBrief(
            competency.competency_id,
            f"Verify {competency.title}",
            "This capability supports dependable ML/AI engineering work.",
            f"Give a concise explanation or small demonstration of {competency.title}.",
            "Connect the concept to observed model, data, or software behavior.",
            "Complete a small local implementation, experiment, or diagnosis.",
            "Explain the result, assumptions, and a failure mode back to Friday.",
            competency.project_family,
        ),
    )
