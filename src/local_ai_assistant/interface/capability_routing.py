"""Bounded deterministic bridge from owner conversation to existing capabilities.

The registry remains descriptive.  This module is the separately composed
authority boundary: it can call only adapters explicitly registered here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from local_ai_assistant.career_forge import (
    CareerForgeService,
    LessonPhase,
    PracticeLabService,
    TutorMode,
)
from local_ai_assistant.learning_paths.service import CurriculumGenerationError, LearningPathService
from local_ai_assistant.memory import FridayMemoryService, MemoryKind

from .capabilities import CapabilityStatus, FridayCapabilityRegistry
from .task_explanation import TaskExplanationNotFound, TaskExplanationService


class ConversationIntent(StrEnum):
    INFORMATION = "information"
    INVOCATION = "invocation"


@dataclass(frozen=True, slots=True)
class CapabilityRoute:
    intent: ConversationIntent
    capability_key: str
    response: str | None = None
    system_context: str | None = None
    mode: str | None = None


class CareerForgeConversationAdapter:
    """Read/owner-pace operations over the existing Learner Twin authority."""

    def __init__(self, service: CareerForgeService, practice_lab: PracticeLabService | None = None) -> None:
        self.service = service
        self.practice_lab = practice_lab

    @staticmethod
    def _mentions_career_forge(text: str) -> bool:
        """Accept bounded wake-ASR variants of Friday's registered capability name."""
        return any(name in text for name in (
            "career forge", "careerforce", "career force", "carrier force", "career forward",
        ))

    def route(self, text: str) -> CapabilityRoute | None:
        normalized = text.strip().lower()
        is_practice_request = any(phrase in normalized for phrase in (
            "practice lab", "let's practice", "lets practice", "practice this",
            "give me a coding exercise", "let me try it", "continue my exercise",
        ))
        if is_practice_request:
            if self.practice_lab is None:
                return CapabilityRoute(ConversationIntent.INFORMATION, "practice_lab",
                    "Practice Lab is not available through Friday right now.")
            mission = self.service.resume()
            if mission is None:
                brief = self.service.next_mission_brief()
                if brief is None:
                    return CapabilityRoute(ConversationIntent.INVOCATION, "practice_lab",
                        "There is no dependency-ready Career Forge mission for a practice exercise.")
                mission = self.service.start_mission(brief.competency_id, brief.title)
            try:
                lab = self.practice_lab.open(mission.mission_id)
            except ValueError as exc:
                return CapabilityRoute(ConversationIntent.INFORMATION, "practice_lab", str(exc))
            return CapabilityRoute(
                ConversationIntent.INVOCATION, "practice_lab",
                f"Practice Lab is ready for '{lab.exercise.title}'. Open the Practice Lab panel to write, run, test, and submit your work. "
                "I will tutor from this active exercise without replacing your solution.",
                system_context=self.practice_lab.tutor_context(mission.mission_id),
                mode=f"career_forge:guide:{mission.mission_id}",
            )
        mentions = self._mentions_career_forge(normalized)
        is_status = any(phrase in normalized for phrase in (
            "where am i", "what should i learn next", "what am i currently learning",
            "what am i learning", "what was i working on", "resume my career forge mission", "how am i doing",
            "what have i completed", "what did i struggle with", "what mistakes did i make",
            "what hints have i needed", "what hints did i need", "what evidence have i earned",
            "what am i strongest at", "what still needs work", "show me my recent learning history",
            "show me my recent career forge history",
        ))
        is_teach = "teach me" in normalized and ("machine learning" in normalized or mentions)
        if not (mentions or is_status or is_teach):
            return None

        if "what is career forge" in normalized or "what's career forge" in normalized:
            return CapabilityRoute(ConversationIntent.INFORMATION, "career_forge", self._overview())

        if "this conversation" in normalized or "just now" in normalized:
            return CapabilityRoute(ConversationIntent.INFORMATION, "career_forge",
                "For this current conversation, I use the temporary active-session context rather than durable Career Forge history. "
                "Ordinary voice conversation is not stored as learning evidence; only governed lesson attempts, assistance, feedback, and evidence are durable.")

        if "how am i doing" in normalized or "progress" in normalized:
            return CapabilityRoute(ConversationIntent.INFORMATION, "career_forge", self._progress_summary())
        if "what have i completed" in normalized:
            return CapabilityRoute(ConversationIntent.INFORMATION, "career_forge", self._completed())
        if "struggle" in normalized or "mistake" in normalized or "still needs work" in normalized:
            return CapabilityRoute(ConversationIntent.INFORMATION, "career_forge", self._struggles())
        if "hint" in normalized or "assistance" in normalized or "help" in normalized:
            return CapabilityRoute(ConversationIntent.INFORMATION, "career_forge", self._assistance())
        if "evidence" in normalized:
            return CapabilityRoute(ConversationIntent.INFORMATION, "career_forge", self._evidence())
        if "strongest" in normalized:
            return CapabilityRoute(ConversationIntent.INFORMATION, "career_forge", self._strengths())
        if "recent" in normalized and "history" in normalized:
            return CapabilityRoute(ConversationIntent.INFORMATION, "career_forge", self._history())

        if ("resume" in normalized or "continue" in normalized) and (mentions or "mission" in normalized):
            mission = self.service.resume()
            if mission is None:
                return CapabilityRoute(ConversationIntent.INVOCATION, "career_forge",
                    "There is no persisted active Career Forge mission to resume. " + self._next())
            return self._tutor_route(mission.mission_id, TutorMode.EXPLAIN, "Resume the persisted mission from its recorded resume point.")

        if "where am i" in normalized or "currently learning" in normalized or "what am i learning" in normalized or "what was i working on" in normalized:
            mission = self.service.resume()
            return CapabilityRoute(ConversationIntent.INFORMATION, "career_forge", self._mission_status(mission))

        if "what should i learn next" in normalized:
            return CapabilityRoute(ConversationIntent.INFORMATION, "career_forge", self._next())

        if "interview mode" in normalized:
            mission = self.service.resume()
            if mission is None:
                return CapabilityRoute(ConversationIntent.INVOCATION, "career_forge",
                    "Interview mode is implemented but needs an active Career Forge mission; " + self._next())
            return self._tutor_route(mission.mission_id, TutorMode.INTERVIEW,
                "Run an evidence-oriented interview practice conversation. Do not claim mastery or write learner state.")

        if is_teach:
            mission = self.service.resume()
            if mission is None:
                brief = self.service.next_mission_brief()
                if brief is None:
                    return CapabilityRoute(ConversationIntent.INVOCATION, "career_forge",
                        "Career Forge has no dependency-ready mission to start.")
                mission = self.service.start_mission(brief.competency_id, brief.title)
            return self._tutor_route(mission.mission_id, TutorMode.EXPLAIN,
                "Teach from the active canonical mission using minimum useful assistance.")

        if "open" in normalized and mentions:
            return CapabilityRoute(ConversationIntent.INVOCATION, "career_forge", self._overview())
        return None

    def _tutor_route(self, mission_id: str, mode: TutorMode, lead: str) -> CapabilityRoute:
        mission = self.service.mission(mission_id)
        brief = self.service.next_mission_brief()
        if brief is None or brief.competency_id != mission.competency_id:
            return CapabilityRoute(ConversationIntent.INVOCATION, "career_forge",
                "That persisted mission is not currently teachable under the dependency graph.")
        if not mission.resume_point:
            # Starting a canonical lesson establishes an explicit question context;
            # only later owner answers in that context can become attempts.
            mission = self.service.update_resume(mission_id, {
                "phase": LessonPhase.QUESTION,
                "question_id": "mission_verification",
            })
        context = (
            f"Career Forge handoff is active in {mode.value} mode. {lead} "
            "Use Friday's one identity. Do not claim mastery, record evidence, assistance, or alter Learner Twin state. "
            "Teach in this order when appropriate: why it matters, mental model, a small example, one guided question, "
            "owner attempt, minimum progressive help, evaluation, teach-back, then the next learning action. "
            "For voice, keep each response under 120 words, use plain spoken language, and do not read code blocks unless the owner explicitly asks. "
            f"Mission: {brief.title}\nWhy: {brief.why_it_matters}\nVerification: {brief.verification}\n"
            f"Mental model: {brief.mental_model}\nOwner attempt: {brief.owner_attempt}\nTeach-back: {brief.teach_back}"
        )
        return CapabilityRoute(ConversationIntent.INVOCATION, "career_forge", system_context=context,
            mode=f"career_forge:{mode.value}:{mission.mission_id}")

    def _overview(self) -> str:
        mission = self.service.resume()
        return (
            "Career Forge is Friday's integrated local ML/AI Engineer apprenticeship. "
            "It uses the persisted Learner Twin, dependency graph, canonical missions, and evidence-backed mastery boundary. "
            + self._mission_status(mission)
            + " Practice Lab supports its bounded Python exercise, explicit arbitrary code selection, Friday-initiated code questions, and explicit retained-screen tutoring."
        )

    def _mission_status(self, mission) -> str:
        if mission is None:
            return "No active mission is persisted. " + self._next()
        competency = self.service.graph[mission.competency_id]
        phase = str(mission.resume_point.get("phase", "the beginning")).replace("_", " ")
        question = mission.resume_point.get("question_id")
        detail = f" at the recorded {phase} phase" + (f" for {question}" if question else "")
        return (f"Your active mission is '{mission.title}' for {competency.title}; "
                f"it is {mission.state}{detail}. ")

    def _next(self) -> str:
        return self.service.progress().next_action

    def _progress_summary(self) -> str:
        progress = self.service.progress()
        active = self._mission_status(progress.active_mission)
        return (
            active + f" You have recorded mastery rungs for {len(progress.evidenced_competencies)} competencies; "
            f"{len(progress.evidence)} evidence records and {len(progress.recent_attempts)} recent governed attempts are recorded. "
            + self._next()
        )

    def _completed(self) -> str:
        completed = self.service.progress().evidenced_competencies
        if not completed:
            return "No competency has qualifying mastery evidence yet. Recorded evidence exists separately and does not promote mastery by itself."
        details = "; ".join(f"{item.competency.title} ({item.mastery.value.replace('_', ' ')})" for item in completed)
        return "Competencies with qualifying mastery state: " + details + "."

    def _struggles(self) -> str:
        retries = self.service.progress().unresolved_retries
        if not retries:
            return "There are no unresolved governed Career Forge retries in the recorded learning history. That does not claim there were no unrecorded conversational difficulties."
        details = "; ".join(
            f"{item.question_id}: {item.evaluation.value}; feedback: {(item.feedback or 'no feedback recorded')[:500]}"
            for item in retries[:5]
        )
        return "Recorded Career Forge retries or struggles: " + details + ". " + self._next()

    def _assistance(self) -> str:
        records = self.service.progress().assistance
        if not records:
            return "No governed Career Forge assistance records are stored yet."
        details = "; ".join(item.level.value.replace("_", " ") for item in records[:5])
        return f"Recorded Career Forge assistance, newest first: {details}. This records help used; it does not imply independent mastery."

    def _evidence(self) -> str:
        records = self.service.progress().evidence
        if not records:
            return "No Career Forge evidence records are stored yet. Evidence is required for mastery, but it does not promote mastery automatically."
        details = "; ".join(
            f"{item.evidence_type.replace('_', ' ')}" + (f" with {item.assistance_level.value.replace('_', ' ')} assistance" if item.assistance_level else "")
            for item in records[:5]
        )
        return "Career Forge evidence, newest first: " + details + ". Mastery remains at its recorded rung until an explicit matching-evidence decision."

    def _strengths(self) -> str:
        records = self.service.progress().evidenced_competencies
        if not records:
            return "I do not yet have qualifying mastery evidence to call any competency a strength."
        return "Your evidence-backed strengths are: " + "; ".join(
            f"{item.competency.title} ({item.mastery.value.replace('_', ' ')})" for item in records
        ) + "."

    def _history(self) -> str:
        history = self.service.progress().history
        if not history:
            return "No governed Career Forge learning history is stored yet. Ordinary conversation is not learning history."
        return "Recent Career Forge history, newest first: " + " ".join(item.summary for item in history[:10])


class MemoryConversationAdapter:
    """Explicit owner-language memory controls; no model text becomes memory."""

    _REMEMBER = re.compile(r"^(?:friday,?\s*)?remember that my (?P<subject>.+?) is (?P<content>.+)$", re.I)
    _RECALL = re.compile(r"^(?:what do you remember about|what do you remember of) (?P<query>.+)\??$", re.I)
    _FORGET = re.compile(r"^(?:friday,?\s*)?forget (?:my )?(?P<query>.+)$", re.I)

    def __init__(self, service: FridayMemoryService) -> None:
        self.service = service

    def route(self, text: str) -> CapabilityRoute | None:
        if match := self._REMEMBER.match(text.strip()):
            subject, content = match.group("subject").strip(), match.group("content").strip()
            record = self.service.remember(kind=MemoryKind.FACT, subject=subject, content=content,
                provenance="owner_explicit_conversation", confidence=1.0)
            return CapabilityRoute(ConversationIntent.INVOCATION, "persistent_memory",
                f"I saved that as durable memory: {record.subject} = {record.content}. It is separate from this active session.")
        if text.strip().lower().startswith(("friday, remember", "friday remember", "remember that")):
            return CapabilityRoute(ConversationIntent.INVOCATION, "persistent_memory",
                "I can save an explicit durable fact only in the form: 'Friday, remember that my <subject> is <value>'.")
        if match := self._RECALL.match(text.strip()):
            records = self.service.search(match.group("query"), limit=5)
            if not records:
                return CapabilityRoute(ConversationIntent.INFORMATION, "persistent_memory",
                    "I found no matching durable memory. That does not rule out information in our current active session.")
            details = "; ".join(f"{record.subject} = {record.content}" for record in records)
            return CapabilityRoute(ConversationIntent.INFORMATION, "persistent_memory",
                f"Durable memory records: {details}.")
        if match := self._FORGET.match(text.strip()):
            records = self.service.search(match.group("query"), limit=2)
            if len(records) != 1:
                return CapabilityRoute(ConversationIntent.INVOCATION, "persistent_memory",
                    "I could not identify exactly one durable memory to forget, so I made no change.")
            self.service.forget(records[0].memory_id)
            return CapabilityRoute(ConversationIntent.INVOCATION, "persistent_memory",
                f"I marked the durable memory '{records[0].subject}' deleted. Current-session context remains separate.")
        return None


class TaskExplanationConversationAdapter:
    """Exact-ID, deterministic read-only task/objective explanations."""

    _task_id = re.compile(r"\btask_[0-9a-f]{20}\b", re.IGNORECASE)
    _objective_id = re.compile(r"\bobjective\s+([0-9a-f]{32})\b", re.IGNORECASE)

    def __init__(self, service: TaskExplanationService | None) -> None:
        self.service = service

    @staticmethod
    def _explanation_intent(text: str) -> bool:
        return any(phrase in text for phrase in (
            "explain", "what happened", "what did", "why is", "why did",
            "did this", "did task", "did it execute", "what evidence",
        ))

    def route(self, text: str) -> CapabilityRoute | None:
        normalized = text.strip().lower()
        task_ids = self._task_id.findall(normalized)
        objective_ids = self._objective_id.findall(normalized)
        refers_to_record = any(term in normalized for term in ("task", "objective"))
        generic_question = "what did you do" in normalized or "explain what happened" in normalized
        if not (task_ids or objective_ids or ((refers_to_record or generic_question) and self._explanation_intent(normalized))):
            return None
        if len(task_ids) + len(objective_ids) > 1:
            return CapabilityRoute(
                ConversationIntent.INFORMATION,
                "task_explanation",
                "Please ask about one exact task ID or objective ID at a time. I will not choose between records.",
            )
        if self.service is None:
            return CapabilityRoute(
                ConversationIntent.INFORMATION,
                "task_explanation",
                "Canonical task explanation is unavailable right now.",
            )
        if task_ids:
            try:
                response = self.service.task(task_ids[0]).conversation_text()
            except TaskExplanationNotFound as exc:
                response = str(exc)
            return CapabilityRoute(ConversationIntent.INFORMATION, "task_explanation", response)
        if objective_ids:
            try:
                response = self.service.objective(objective_ids[0]).conversation_text()
            except TaskExplanationNotFound as exc:
                response = str(exc)
            return CapabilityRoute(ConversationIntent.INFORMATION, "task_explanation", response)
        if any(word in normalized for word in ("task", "objective", "this succeeded", "what did you do")):
            return CapabilityRoute(
                ConversationIntent.INFORMATION,
                "task_explanation",
                "Please include the exact task ID (`task_` followed by 20 hexadecimal characters) or objective ID. I will not guess which record you mean.",
            )
        return None


class LearningPathConversationAdapter:
    """Explicit, deterministic owner intent for canonical learning paths."""

    def __init__(self, service: LearningPathService):
        self.service = service

    def route(self, text: str) -> CapabilityRoute | None:
        normalized = " ".join(text.strip().lower().split())
        normalized = re.sub(r"^(?:hey\s+)?friday[, ]+", "", normalized)
        create_prefixes = ("create a learning path for ", "create a learning path to learn ",
                           "build me a roadmap to learn ", "teach me ", "i want to learn ")
        goal = None
        explicit = False
        for prefix in create_prefixes:
            if normalized.startswith(prefix):
                suffix = normalized[len(prefix):]
                if prefix == "teach me " and "machine learning" in suffix:
                    continue
                explicit = True
                goal = suffix
                goal = re.sub(r"\s+from beginner to advanced.*$", "", goal)
                goal = re.sub(r"\s+(?:in|over)\s+(?:\d{1,2}|one|two|three|four|five|six)\s+(?:weeks?|months?).*$", "", goal)
                goal = goal.strip(" .?!")
                break
        if not explicit:
            match = re.match(r"create a (\d{1,2})-week (.+?) path[.!?]*$", normalized)
            if match:
                explicit = True
                weeks = int(match.group(1))
                goal = re.sub(r"\s+interview preparation$", " interview preparation", match.group(2)).strip()
                normalized += f" in {weeks} weeks"
        if explicit and goal:
            try:
                timeframe = re.search(r"\b(?:in|over)\s+(\d{1,2}|one|two|three|four|five|six)\s+(weeks?|months?)\b", normalized)
                time_value = timeframe.group(1) if timeframe else None
                week_count = ({"one":1,"two":2,"three":3,"four":4,"five":5,"six":6}[time_value]
                              if time_value in {"one", "two", "three", "four", "five", "six"}
                              else int(time_value) if time_value else None)
                pace = re.search(r"\b(\d{1,2}(?:\.\d)?)\s+hours?\s+(?:per|a)\s+week\b", normalized)
                level = re.search(r"\bfrom\s+(?:beginner|novice)\s+to\s+(beginner|intermediate|advanced|expert)\b", normalized)
                target_level = level.group(1) if level else "unspecified"
                interview = "interview" in normalized and (timeframe is not None or "deadline" in normalized)
                target_date = ((datetime.now(UTC) + (timedelta(weeks=week_count) if timeframe.group(2).startswith("week") else timedelta(days=round(week_count * 30.4)))).date().isoformat() if timeframe else None)
                path = self.service.generate(goal, mode="deadline_interview" if interview else "goal_timeframe" if timeframe else "topic",
                    target_level=target_level, target_date=target_date,
                    hours_per_week=float(pace.group(1)) if pace else None)
                version = self.service.repository.version(path.path_id, path.current_version)
                return CapabilityRoute(ConversationIntent.INVOCATION, "learning_paths",
                    f"Created '{path.title}' as a draft learning path ({len(version.modules)} modules, {len(version.nodes)} nodes). It is saved as {path.path_id}. Open Learn to review and start it.")
            except (CurriculumGenerationError, ValueError):
                return CapabilityRoute(ConversationIntent.INFORMATION, "learning_paths",
                    "I couldn't create that learning path from the local curriculum proposal. No path was saved; you can try a more specific topic.")
        if any(p in normalized for p in ("show my learning paths", "list my learning paths", "what learning paths do i have")):
            paths = self.service.repository.list()
            if not paths:
                return CapabilityRoute(ConversationIntent.INFORMATION, "learning_paths", "You don't have any saved learning paths yet. Ask me to create one, for example: ‘Create a learning path for DSA.’")
            current = self.service.repository.current_path_id()
            return CapabilityRoute(ConversationIntent.INFORMATION, "learning_paths", "Your learning paths: " + "; ".join(f"{p.title} ({p.state}{', current' if p.path_id == current else ''})" for p in paths) + ".")
        current = self.service.current()
        if any(p in normalized for p in ("what learning path am i on", "what path am i currently following", "what's my current learning path", "what is my current learning path")):
            return CapabilityRoute(ConversationIntent.INFORMATION, "learning_paths", f"Your current learning path is '{current.title}' ({current.state})." if current else "You haven't selected a current learning path yet. Choose one in Learn.")
        if any(p in normalized for p in ("what's next in my current learning path", "what is next in my current learning path", "what's next in my learning path", "why is this topic blocked", "why do i need review first")):
            if current is None:
                return CapabilityRoute(ConversationIntent.INFORMATION, "learning_paths", "No current learning path is selected. Choose one in Learn first.")
            sequence = self.service.sequence(current.path_id)
            by_id = {n["node_id"]: n for n in sequence["nodes"]}
            nodes = self.service.repository.version(current.path_id, current.current_version).nodes
            title = {n["node_id"]: n["title"] for n in nodes}
            if sequence["candidate_next_nodes"]:
                return CapabilityRoute(ConversationIntent.INFORMATION, "learning_paths", "Next candidates: " + "; ".join(f"{title[i]} — {by_id[i]['reason']}" for i in sequence["candidate_next_nodes"]) + ".")
            return CapabilityRoute(ConversationIntent.INFORMATION, "learning_paths", "There are no eligible next nodes in this path right now. " + "; ".join(f"{title[n['node_id']]}: {n['reason']}" for n in sequence["nodes"][:5]))
        if normalized.startswith(("open my ", "open the ")) and "learning path" in normalized:
            paths = self.service.repository.list()
            match = next((p for p in paths if p.title.lower() in normalized or p.goal.lower() in normalized), None)
            if match:
                self.service.select(match.path_id)
                return CapabilityRoute(ConversationIntent.INVOCATION, "learning_paths", f"Selected '{match.title}' as your current learning path. Open Learn to continue.")
            return CapabilityRoute(ConversationIntent.INFORMATION, "learning_paths", "I couldn't match that learning path to a saved path. Ask to see your learning paths.")
        return None


class FridayConversationCapabilityRouter:
    """Classify deterministic intents and dispatch only registered adapters."""

    def __init__(self, registry: FridayCapabilityRegistry, *, career_forge: CareerForgeService,
                 memory: FridayMemoryService, practice_lab: PracticeLabService | None = None,
                 task_explanation: TaskExplanationService | None = None,
                 learning_paths: LearningPathService | None = None) -> None:
        self.registry = registry
        self.adapters = {
            "task_explanation": TaskExplanationConversationAdapter(task_explanation),
            **({"learning_paths": LearningPathConversationAdapter(learning_paths)} if learning_paths else {}),
            "career_forge": CareerForgeConversationAdapter(career_forge, practice_lab),
            "persistent_memory": MemoryConversationAdapter(memory),
        }

    @property
    def career_forge(self) -> CareerForgeService:
        return self.adapters["career_forge"].service

    def route(self, prompt: str) -> CapabilityRoute | None:
        for key, adapter in self.adapters.items():
            route = adapter.route(prompt)
            if route is None:
                continue
            capability = next((item for item in self.registry.capabilities() if item.key == route.capability_key), None)
            if capability is None or capability.status is CapabilityStatus.ABSENT or not capability.configured or capability.healthy is False:
                return CapabilityRoute(route.intent, route.capability_key,
                    f"{route.capability_key.replace('_', ' ').title()} is not available through Friday right now.")
            return route
        return None


__all__ = ["CapabilityRoute", "ConversationIntent", "FridayConversationCapabilityRouter"]
