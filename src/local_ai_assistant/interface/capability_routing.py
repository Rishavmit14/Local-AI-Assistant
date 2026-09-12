"""Bounded deterministic bridge from owner conversation to existing capabilities.

The registry remains descriptive.  This module is the separately composed
authority boundary: it can call only adapters explicitly registered here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from local_ai_assistant.career_forge import CareerForgeService, TutorMode
from local_ai_assistant.memory import FridayMemoryService, MemoryKind

from .capabilities import CapabilityStatus, FridayCapabilityRegistry


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

    def __init__(self, service: CareerForgeService) -> None:
        self.service = service

    @staticmethod
    def _mentions_career_forge(text: str) -> bool:
        """Accept bounded wake-ASR variants of Friday's registered capability name."""
        return any(name in text for name in (
            "career forge", "careerforce", "career force", "carrier force", "career forward",
        ))

    def route(self, text: str) -> CapabilityRoute | None:
        normalized = text.strip().lower()
        mentions = self._mentions_career_forge(normalized)
        is_status = any(phrase in normalized for phrase in (
            "where am i", "what should i learn next", "what am i currently learning",
            "what am i learning", "resume my career forge mission",
        ))
        is_teach = "teach me" in normalized and ("machine learning" in normalized or mentions)
        if not (mentions or is_status or is_teach):
            return None

        if "practice lab" in normalized:
            return CapabilityRoute(ConversationIntent.INFORMATION, "practice_lab",
                "Practice Lab is absent: Friday does not currently have an executable learning workspace. "
                "Career Forge's existing local mission and tutor boundaries remain available.")

        if "what is career forge" in normalized or "what's career forge" in normalized:
            return CapabilityRoute(ConversationIntent.INFORMATION, "career_forge", self._overview())

        if "resume" in normalized and (mentions or "mission" in normalized):
            mission = self.service.resume()
            if mission is None:
                return CapabilityRoute(ConversationIntent.INVOCATION, "career_forge",
                    "There is no persisted active Career Forge mission to resume. " + self._next())
            return self._tutor_route(mission.mission_id, TutorMode.EXPLAIN, "Resume the persisted mission from its recorded resume point.")

        if "where am i" in normalized or "currently learning" in normalized or "what am i learning" in normalized:
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
        context = (
            f"Career Forge handoff is active in {mode.value} mode. {lead} "
            "Use Friday's one identity. Do not claim mastery, record evidence, assistance, or alter Learner Twin state. "
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
            + self._mission_status(mission) + " Practice Lab and screen-aware tutoring are not available."
        )

    def _mission_status(self, mission) -> str:
        if mission is None:
            return "No active mission is persisted. " + self._next()
        competency = self.service.graph[mission.competency_id]
        return (f"Your active mission is '{mission.title}' for {competency.title}; "
                f"it is {mission.state} at resume point {mission.resume_point or 'the beginning'}. ")

    def _next(self) -> str:
        item = self.service.next_competency()
        if item is None:
            return "The Learner Twin has no dependency-ready next competency."
        return f"The dependency-ready next competency is {item.title}."


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


class FridayConversationCapabilityRouter:
    """Classify deterministic intents and dispatch only registered adapters."""

    def __init__(self, registry: FridayCapabilityRegistry, *, career_forge: CareerForgeService,
                 memory: FridayMemoryService) -> None:
        self.registry = registry
        self.adapters = {
            "career_forge": CareerForgeConversationAdapter(career_forge),
            "persistent_memory": MemoryConversationAdapter(memory),
        }

    def route(self, prompt: str) -> CapabilityRoute | None:
        if "practice lab" in prompt.lower():
            return CapabilityRoute(ConversationIntent.INFORMATION, "practice_lab",
                "Practice Lab is absent: Friday does not currently have an executable learning workspace. "
                "Career Forge's existing local mission and tutor boundaries remain available.")
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
