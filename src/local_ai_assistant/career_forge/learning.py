"""Bounded owner-facing Career Forge lesson state over the Learner Twin."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import AssistanceLevel, AttemptEvaluation, LessonPhase, TutorMode
from .service import CareerForgeService, Mission


@dataclass(frozen=True, slots=True)
class LearningDirective:
    mission_id: str
    action: str
    system_context: str
    attempt_id: str | None = None
    assistance_level: AssistanceLevel | None = None
    response: str | None = None


class CareerForgeLearningLoop:
    """Turns explicit lesson intent into auditable learner state, never mastery."""

    def __init__(self, service: CareerForgeService) -> None:
        self.service = service

    def prepare(self, prompt: str, *, mode: str | None) -> LearningDirective | None:
        if not mode or not mode.startswith("career_forge:"):
            return None
        _, mode_name, mission_id = mode.split(":", 2)
        mission = self.service.mission(mission_id)
        tutor_mode = TutorMode(mode_name)
        text = prompt.strip().lower()
        phase = str(mission.resume_point.get("phase", "why_it_matters"))
        question_id = str(mission.resume_point.get("question_id", "mission_verification"))

        if self._is_hint_request(text):
            level = self._next_assistance(mission_id)
            return LearningDirective(mission_id, "assistance", "", assistance_level=level,
                response=self._assistance_response(mission, level, withhold_answer=("don't tell" in text or "do not tell" in text)))
        if "show me an example" in text or "give me an example" in text:
            self.service.update_resume(mission_id, {"phase": LessonPhase.EXAMPLE, "question_id": question_id}, assistance_level=mission.assistance_level)
            return LearningDirective(mission_id, "example", self._tutor_context(mission, TutorMode.EXPLAIN,
                "Give one small worked example, explain why it works, then ask a new bounded question. Do not claim mastery."))
        if "let me try" in text or "ask me again" in text or "ask a question" in text:
            self.service.update_resume(mission_id, {"phase": LessonPhase.QUESTION, "question_id": question_id}, assistance_level=mission.assistance_level)
            return LearningDirective(mission_id, "question", self._tutor_context(mission, tutor_mode,
                "Ask one meaningful, bounded question from the mission. Wait for the owner answer; do not provide it."))
        if "test me" in text or "teach-back" in text or "teach back" in text:
            self.service.update_resume(mission_id, {"phase": LessonPhase.TEACH_BACK, "question_id": "teach_back"}, assistance_level=mission.assistance_level)
            return LearningDirective(mission_id, "teach_back_prompt", self._tutor_context(mission, TutorMode.TEACH_BACK,
                "Ask the owner to explain the concept back in their own words. State the bounded criteria you will use: mechanism, consequence, and one verification or failure mode."))
        if self._is_evaluation_request(text):
            attempt = self.service.latest_attempt(mission_id, pending_only=True)
            if attempt is None:
                return LearningDirective(mission_id, "no_attempt", "", response="I need an explicit answer to the current lesson question before I can evaluate it.")
            return LearningDirective(mission_id, "evaluate", self._evaluation_context(mission, attempt.response, attempt.question_id), attempt.attempt_id)
        if "retry" in text or "let me answer again" in text:
            self.service.update_resume(mission_id, {"phase": LessonPhase.QUESTION, "question_id": question_id}, assistance_level=mission.assistance_level)
            return LearningDirective(mission_id, "retry_prompt", "", response="Please try the current lesson question again in your own words. I will record this as a new attempt, not overwrite the earlier one.")
        if phase in {LessonPhase.QUESTION, LessonPhase.TEACH_BACK, LessonPhase.EVALUATION} and self._looks_like_attempt(text):
            attempt = self.service.record_attempt(mission_id, question_id, prompt, mode=tutor_mode,
                                                 assistance_level=self.service.latest_assistance_level(mission_id))
            if phase == LessonPhase.TEACH_BACK:
                return LearningDirective(mission_id, "teach_back_evaluate", self._evaluation_context(
                    mission, attempt.response, attempt.question_id
                ), attempt.attempt_id)
            return LearningDirective(mission_id, "attempt_received", "", attempt.attempt_id,
                response="I recorded that as your lesson attempt. Say 'check my answer' when you want a bounded evaluation, or ask for a hint first.")
        if "move on" in text:
            return LearningDirective(mission_id, "next", self._tutor_context(mission, tutor_mode,
                "State the current evidence boundary truthfully. Do not advance mastery. Give the next learning action or ask for a teach-back."))
        if "what did i struggle with" in text:
            attempts = self.service.attempts(mission_id)
            recorded = "; ".join(
                f"attempt {item.attempt_order}: {item.evaluation.value}, help={item.assistance_level or 'none'}, feedback={item.feedback or 'pending'}"
                for item in attempts
            ) or "no evaluated attempts"
            return LearningDirective(mission_id, "struggles", self._tutor_context(mission, TutorMode.REVIEW,
                "Summarize only these recorded assistance and evaluated attempts: " + recorded + ". Do not infer unrecorded struggles or claim mastery."))
        return None

    def complete(self, directive: LearningDirective, response: str) -> None:
        if directive.action == "assistance" and directive.assistance_level is not None:
            self.service.offer_assistance(directive.mission_id, TutorMode.HINT, directive.assistance_level, response)
        elif directive.action in {"evaluate", "teach_back_evaluate"} and directive.attempt_id is not None:
            evaluation, feedback = self._parse_evaluation(response)
            evidence_type = (
                "teach_back" if directive.action == "teach_back_evaluate" else "quiz_response"
            ) if evaluation is AttemptEvaluation.CORRECT else None
            self.service.evaluate_attempt(directive.attempt_id, evaluation, feedback, evidence_type=evidence_type)
        elif directive.action in {"question", "example"}:
            mission = self.service.mission(directive.mission_id)
            self.service.update_resume(directive.mission_id, {"phase": LessonPhase.QUESTION, "question_id": "mission_verification"}, assistance_level=mission.assistance_level)

    @staticmethod
    def _looks_like_attempt(text: str) -> bool:
        return len(text) >= 8 and len(text.split()) >= 4 and not any(token in text for token in (
            "hint", "example", "don't tell", "do not tell", "why", "what did i",
            "what should", "what do", "how do", "can you", "could you", "guess what",
        ))

    @staticmethod
    def _is_hint_request(text: str) -> bool:
        # The voice ASR can drop articles, so accept bounded tutoring language
        # only while the Career Forge lesson mode is already active.
        return (
            bool(re.search(r"\b(hint|clue)\b", text))
            or "i don't understand" in text
            or "i do not understand" in text
            or "help me" in text
            or "give me a hand" in text
        )

    @staticmethod
    def _is_evaluation_request(text: str) -> bool:
        return bool(re.search(r"\bcheck\s+(?:my|me|the)?\s*answer\b", text)) or "why is my answer wrong" in text or "evaluate my answer" in text

    def _next_assistance(self, mission_id: str) -> AssistanceLevel:
        levels = tuple(AssistanceLevel)
        current = self.service.latest_assistance_level(mission_id)
        return levels[0] if current is None else levels[min(levels.index(current) + 1, len(levels) - 1)]

    def _assistance_response(self, mission: Mission, level: AssistanceLevel, *, withhold_answer: bool) -> str:
        brief = self.service.next_mission_brief()
        mental_model = brief.mental_model if brief and brief.competency_id == mission.competency_id else "Return to the concept's mechanism before choosing an answer."
        responses = {
            AssistanceLevel.PROMPT: "Hint: make a prediction before changing anything. What object exists before either function call?",
            AssistanceLevel.CONCEPTUAL_HINT: f"Conceptual hint: {mental_model}",
            AssistanceLevel.STRONG_HINT: "Strong hint: separate when the default object is created from when the function body runs.",
            AssistanceLevel.DECOMPOSITION: "Break it down: first identify the default object, then trace two calls, then state whether both calls can mutate that same object.",
            AssistanceLevel.PARTIAL_EXAMPLE: "Partial example: compare two calls that append different values, then inspect whether the second result contains the first value.",
            AssistanceLevel.FULL_DEMONSTRATION: "You have reached the final help level. I can now walk through a complete worked explanation; say 'show me an example'.",
        }
        answer = responses[level]
        if withhold_answer and level is not AssistanceLevel.FULL_DEMONSTRATION:
            answer += " I am intentionally not giving the final answer yet."
        return answer

    @staticmethod
    def _tutor_context(mission: Mission, mode: TutorMode, instruction: str) -> str:
        return (f"Career Forge lesson action in {mode.value} mode for mission {mission.mission_id}. {instruction} "
                "Use one Friday identity. The model cannot advance mastery or invent evidence.")

    @staticmethod
    def _evaluation_context(mission: Mission, answer: str, question_id: str) -> str:
        return (f"Evaluate this explicit Career Forge owner attempt for mission {mission.mission_id}, question {question_id}. "
                "Use the mission's bounded conceptual criteria, not lexical similarity. First line MUST be exactly "
                "ASSESSMENT: correct, ASSESSMENT: incorrect, or ASSESSMENT: uncertain. Then give concise feedback naming the mechanism, misconception if any, and retry action. "
                "Do not claim mastery or write learner state. Owner answer: " + answer)

    @staticmethod
    def _parse_evaluation(response: str) -> tuple[AttemptEvaluation, str]:
        match = re.search(r"^\s*ASSESSMENT:\s*(correct|incorrect|uncertain)\b", response, re.I)
        if match is None:
            return AttemptEvaluation.UNCERTAIN, "The bounded evaluator did not return a valid assessment label. " + response.strip()[:1500]
        return AttemptEvaluation(match.group(1).lower()), response.strip()[:4000]
