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


class ScreenQuestionMode(StrEnum):
    SEMANTIC = "semantic"
    VISUAL = "visual"


class VoiceLearningAction(StrEnum):
    CONTINUE = "continue"
    EXPLAIN = "explain"
    REPEAT = "repeat"
    ANSWER = "answer"
    CORRECT = "correct"
    CONFIRM = "confirm"
    CANCEL = "cancel"
    CHECK = "check"
    PROGRESS = "progress"


@dataclass(frozen=True, slots=True)
class FridayVoiceIntent:
    kind: FridayVoiceIntentType
    open_command: OpenCommand | None = None
    computer_goal: str | None = None
    capability_key: str | None = None
    screen_mode: ScreenQuestionMode | None = None
    learning_action: VoiceLearningAction | None = None
    learning_topic: str | None = None


_SCREEN_QUESTION = re.compile(
    r"\b(?:screen|display|desktop|window)\b|\bwhat (?:do|can) you see\b"
    r"|\b(?:what|which)\s+(?:app(?:lication)?|program)\b"
    r"|\bwhat\s+(?:button|control|element)\s+is\s+(?:currently\s+)?focused\b"
    r"|\bwhat(?:'s| is)\s+(?:currently\s+)?focused\b"
    r"|\b(?:what|why|how|read|explain|describe|inspect|analy[sz]e|identify|interpret|help|think|look)\b"
    r".{0,64}\b(?:this|that|here)\b"
    r"|\b(?:what|which)\b.{0,32}\b(?:error|terminal|chart|diagram|image)\b",
    re.I,
)
_SEMANTIC_SCREEN_QUESTION = re.compile(
    r"\b(?:what|which)\s+(?:app(?:lication)?|program|window)\b.{0,48}"
    r"\b(?:open|active|current|showing|visible|am i in)\b"
    r"|\bwhat\s+(?:button|control|element)\s+is\s+(?:currently\s+)?focused\b"
    r"|\bwhat(?:'s| is)\s+(?:currently\s+)?focused\b",
    re.I,
)
_VISUAL_SCREEN_QUESTION = re.compile(
    r"\bwhat\s+(?:do|can)\s+you\s+see\b"
    r"|\bwhat(?:'s| is)\s+(?:on|in|visible on|showing on)\s+(?:my\s+|the\s+)?"
    r"(?:screen|display|desktop|window)\b"
    r"|\b(?:read|describe|inspect|analy[sz]e|interpret)\b.{0,64}"
    r"\b(?:screen|display|desktop|window|image|diagram|chart|error|terminal)\b"
    r"|\b(?:error|wrong|failing|broken)\b.{0,48}\b(?:see|screen|visible|this|that|here)\b"
    r"|\bwhat\s+error\b.{0,48}\b(?:see|visible|screen)\b",
    re.I,
)
_LONG_RUNNING_TASK = re.compile(
    r"\b(?:start|run|continue|work on|complete|execute)\b.{0,80}\b(?:task|objective|project|workflow|research)\b",
    re.I,
)
_COMPUTER_GOAL = re.compile(
    r"^\s*(?:(?:hey\s+)?friday[,\s]+)?(?:please\s+)?"
    r"(?:open|launch|start|visit|focus|go\s+to|navigate\s+to|show\s+me|"
    r"search|find|create|make|rename|move|copy|click|press|scroll|type|"
    r"run|execute|close|switch|select|go\s+back|enter)\b",
    re.I,
)
_RESEARCH_MEMORY_OBJECTIVE = re.compile(r"\b(?:research|memory|remember|objective|automate|automation)\b", re.I)
_LEARNING = re.compile(r"\b(?:learn|learning|career forge|practice lab|competenc|mission|tutor|project)\b", re.I)
_WAKE_PREFIX = re.compile(r"^\s*(?:(?:hey\s+)?friday[,:]?\s+)+", re.I)
_CONTINUE_LEARNING = re.compile(
    r"\b(?:continue|resume|pick up|keep going with)\b.{0,72}"
    r"\b(?:course|learning|path|lesson|topic|machine learning|\bml\b)\b",
    re.I,
)
_REPEAT_LEARNING = re.compile(
    r"\b(?:explain|say|go over|teach)\b.{0,40}\b(?:that|it|the lesson|again|once more)\b"
    r"|\b(?:repeat|revisit)\b.{0,35}\b(?:lesson|topic|that|it)\b"
    r"|\b(?:explain that again|explain it again|say that again)\b",
    re.I,
)
_PROGRESS_LEARNING = re.compile(
    r"\b(?:how much|what|show me|tell me)\b.{0,56}\b(?:learned|learning progress|progress|mastered)\b"
    r"|\b(?:show|check|tell me about)\b.{0,32}\b(?:my )?(?:learning )?progress\b",
    re.I,
)
_ANSWER_LEARNING = re.compile(r"^(?:my answer is|my answer:|the answer is)\s*(.+)$", re.I | re.S)
_CORRECTION_LEARNING = re.compile(
    r"^(?:correction(?: is)?[: ,]+|i meant[: ,]+|replace (?:that|my answer)(?: with)?[: ,]+|"
    r"no[, ]+my answer is[: ,]+)(.+)$",
    re.I | re.S,
)
_CONFIRM_LEARNING = re.compile(
    r"^(?:yes|yeah|yep|correct|confirm|submit(?: it)?|go ahead|that's right|that is right|"
    r"yes[, ]+(?:submit|confirm)(?: it)?)[.! ]*$",
    re.I,
)
_CANCEL_LEARNING = re.compile(
    r"^(?:cancel(?: that| it| my answer)?|discard(?: that| it)?|no(?:[, ]+don't submit)?|"
    r"forget it|never mind|nevermind)[.! ]*$",
    re.I,
)
_CHECK_LEARNING = re.compile(r"\b(?:check|review|evaluate)\s+my answer\b", re.I)
_EXPLAIN_LEARNING = re.compile(
    r"^(?:please )?(?:explain|teach me|help me understand|clarify)\b\s*(.*)$",
    re.I | re.S,
)


class FridayVoiceIntentRouter:
    """Classify broad request families while leaving target resolution to capabilities."""

    def classify(
        self,
        prompt: str,
        *,
        capability_route=None,
        pending_voice_answer: bool = False,
    ) -> FridayVoiceIntent:
        command = parse_open_command(prompt)
        if command is not None:
            if is_friday_ui_target(command.target) or is_friday_internal_route(command.target):
                return FridayVoiceIntent(FridayVoiceIntentType.FRIDAY_INTERNAL_NAVIGATION, command)
            return FridayVoiceIntent(FridayVoiceIntentType.COMPUTER_ACTION,
                                     open_command=command, computer_goal=prompt)

        if _SCREEN_QUESTION.search(prompt):
            semantic_only = _SEMANTIC_SCREEN_QUESTION.search(prompt) and not _VISUAL_SCREEN_QUESTION.search(prompt)
            return FridayVoiceIntent(
                FridayVoiceIntentType.SCREEN_CONTEXT_QUESTION,
                screen_mode=(ScreenQuestionMode.SEMANTIC if semantic_only else ScreenQuestionMode.VISUAL),
            )

        if _COMPUTER_GOAL.search(prompt):
            return FridayVoiceIntent(FridayVoiceIntentType.COMPUTER_ACTION,
                                     computer_goal=prompt)

        learning_text = _WAKE_PREFIX.sub("", prompt).strip()
        answer_match = _ANSWER_LEARNING.match(learning_text)
        correction_match = _CORRECTION_LEARNING.match(learning_text)
        if pending_voice_answer and correction_match and correction_match.group(1).strip():
            return FridayVoiceIntent(
                FridayVoiceIntentType.LEARNING_CAREER_PROJECT,
                capability_key="learning_paths",
                learning_action=VoiceLearningAction.CORRECT,
                learning_topic=correction_match.group(1).strip(),
            )
        if pending_voice_answer and answer_match and answer_match.group(1).strip():
            return FridayVoiceIntent(
                FridayVoiceIntentType.LEARNING_CAREER_PROJECT,
                capability_key="learning_paths",
                learning_action=VoiceLearningAction.CORRECT,
                learning_topic=answer_match.group(1).strip(),
            )
        if pending_voice_answer and _CONFIRM_LEARNING.fullmatch(learning_text):
            return FridayVoiceIntent(
                FridayVoiceIntentType.LEARNING_CAREER_PROJECT,
                capability_key="learning_paths",
                learning_action=VoiceLearningAction.CONFIRM,
            )
        if pending_voice_answer and _CANCEL_LEARNING.fullmatch(learning_text):
            return FridayVoiceIntent(
                FridayVoiceIntentType.LEARNING_CAREER_PROJECT,
                capability_key="learning_paths",
                learning_action=VoiceLearningAction.CANCEL,
            )
        if answer_match and answer_match.group(1).strip():
            return FridayVoiceIntent(
                FridayVoiceIntentType.LEARNING_CAREER_PROJECT,
                capability_key="learning_paths",
                learning_action=VoiceLearningAction.ANSWER,
                learning_topic=answer_match.group(1).strip(),
            )
        if _CHECK_LEARNING.search(learning_text):
            return FridayVoiceIntent(
                FridayVoiceIntentType.LEARNING_CAREER_PROJECT,
                capability_key="learning_paths",
                learning_action=VoiceLearningAction.CHECK,
            )
        if _PROGRESS_LEARNING.search(learning_text):
            return FridayVoiceIntent(
                FridayVoiceIntentType.LEARNING_CAREER_PROJECT,
                capability_key="learning_paths",
                learning_action=VoiceLearningAction.PROGRESS,
            )
        if _CONTINUE_LEARNING.search(learning_text):
            return FridayVoiceIntent(
                FridayVoiceIntentType.LEARNING_CAREER_PROJECT,
                capability_key="learning_paths",
                learning_action=VoiceLearningAction.CONTINUE,
            )
        if _REPEAT_LEARNING.search(learning_text):
            return FridayVoiceIntent(
                FridayVoiceIntentType.LEARNING_CAREER_PROJECT,
                capability_key="learning_paths",
                learning_action=VoiceLearningAction.REPEAT,
            )
        if _EXPLAIN_LEARNING.search(learning_text):
            match = _EXPLAIN_LEARNING.match(learning_text)
            topic = match.group(1).strip(" .?!,") if match else ""
            return FridayVoiceIntent(
                FridayVoiceIntentType.LEARNING_CAREER_PROJECT,
                capability_key="learning_paths",
                learning_action=VoiceLearningAction.EXPLAIN,
                learning_topic=topic or None,
            )

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


__all__ = [
    "FridayVoiceIntent", "FridayVoiceIntentRouter", "FridayVoiceIntentType",
    "ScreenQuestionMode", "VoiceLearningAction",
]
