"""Low-cost, typed intent classification for the normal Friday voice path."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from local_ai_assistant.desktop.targets import (
    OpenCommand,
    is_friday_internal_route,
    is_friday_ui_target,
    parse_open_command,
)


class FridayVoiceIntentType(StrEnum):
    CONVERSATIONAL_KNOWLEDGE = "conversational_knowledge"
    COMPUTER_ACTION = "computer_action"
    SCREEN_CONTEXT_QUESTION = "screen_context_question"
    FRIDAY_INTERNAL_NAVIGATION = "friday_internal_navigation"
    LEARNING_CAREER_PROJECT = "learning_career_project"
    RESEARCH_MEMORY_OBJECTIVE = "research_memory_objective"
    LONG_RUNNING_TASK = "long_running_task"


@dataclass(frozen=True, slots=True)
class FridayVoiceIntent:
    kind: FridayVoiceIntentType
    open_command: OpenCommand | None = None
    capability_key: str | None = None


_SCREEN_QUESTION = re.compile(
    r"\b(?:screen|display|desktop|window)\b|\bwhat (?:do|can) you see\b|\bwhat's on (?:my|the) screen\b",
    re.I,
)
_LONG_RUNNING_TASK = re.compile(
    r"\b(?:start|run|continue|work on|complete|execute)\b.{0,80}\b(?:task|objective|project|workflow|research)\b",
    re.I,
)
_RESEARCH_MEMORY_OBJECTIVE = re.compile(r"\b(?:research|memory|remember|objective|automate|automation)\b", re.I)
_LEARNING = re.compile(r"\b(?:learn|learning|career forge|practice lab|competenc|mission|tutor|project)\b", re.I)


class FridayVoiceIntentRouter:
    """Classify broad request families while leaving target resolution to capabilities."""

    def classify(self, prompt: str, *, capability_route=None) -> FridayVoiceIntent:
        command = parse_open_command(prompt)
        if command is not None:
            if is_friday_ui_target(command.target) or is_friday_internal_route(command.target):
                return FridayVoiceIntent(FridayVoiceIntentType.FRIDAY_INTERNAL_NAVIGATION, command)
            return FridayVoiceIntent(FridayVoiceIntentType.COMPUTER_ACTION, command)

        if _SCREEN_QUESTION.search(prompt):
            return FridayVoiceIntent(FridayVoiceIntentType.SCREEN_CONTEXT_QUESTION)

        capability_key = getattr(capability_route, "capability_key", None)
        if capability_key in {"career_forge", "learning_paths", "practice_lab"}:
            return FridayVoiceIntent(FridayVoiceIntentType.LEARNING_CAREER_PROJECT,
                                     capability_key=capability_key)
        if capability_key in {"persistent_memory", "research", "objectives"}:
            return FridayVoiceIntent(FridayVoiceIntentType.RESEARCH_MEMORY_OBJECTIVE,
                                     capability_key=capability_key)
        if _LONG_RUNNING_TASK.search(prompt):
            return FridayVoiceIntent(FridayVoiceIntentType.LONG_RUNNING_TASK,
                                     capability_key=capability_key)
        if _RESEARCH_MEMORY_OBJECTIVE.search(prompt):
            return FridayVoiceIntent(FridayVoiceIntentType.RESEARCH_MEMORY_OBJECTIVE,
                                     capability_key=capability_key)
        if _LEARNING.search(prompt):
            return FridayVoiceIntent(FridayVoiceIntentType.LEARNING_CAREER_PROJECT,
                                     capability_key=capability_key)
        return FridayVoiceIntent(FridayVoiceIntentType.CONVERSATIONAL_KNOWLEDGE,
                                 capability_key=capability_key)


__all__ = ["FridayVoiceIntent", "FridayVoiceIntentRouter", "FridayVoiceIntentType"]
