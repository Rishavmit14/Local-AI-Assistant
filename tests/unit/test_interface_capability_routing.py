from local_ai_assistant.career_forge import CareerForgeService
from local_ai_assistant.interface.capabilities import (
    CapabilityStatus,
    FridayCapability,
    FridayCapabilityRegistry,
)
from local_ai_assistant.interface.capability_routing import (
    ConversationIntent,
    FridayConversationCapabilityRouter,
)
from local_ai_assistant.interface.conversation import FridayConversationService
from local_ai_assistant.interface.runtime import FridayRuntime
from local_ai_assistant.memory import FridayMemoryService


class FakeLLM:
    def __init__(self):
        self.calls = []

    def stream_chat(self, prompt, system_prompt="", temperature=0.2, max_tokens=1024):
        self.calls.append((prompt, system_prompt))
        yield "tutor response"


def router(tmp_path):
    registry = FridayCapabilityRegistry((
        FridayCapability("career_forge", "Career Forge", CapabilityStatus.INTEGRATED, True, True, True, "local", None),
        FridayCapability("persistent_memory", "Persistent memory", CapabilityStatus.INTEGRATED, True, True, True, "local", None),
        FridayCapability("practice_lab", "Practice Lab", CapabilityStatus.ABSENT, False, False, False, "none", "not installed"),
    ))
    return FridayConversationCapabilityRouter(
        registry,
        career_forge=CareerForgeService(tmp_path / "career.sqlite3"),
        memory=FridayMemoryService(tmp_path / "memory.sqlite3", embed=lambda values: [[1.0] for _ in values]),
    )


def test_career_forge_invocation_starts_canonical_mission_and_hands_off_to_existing_conversation(tmp_path):
    capability_router = router(tmp_path)
    llm = FakeLLM()
    service = FridayConversationService(llm, FridayRuntime("route"), capability_router=capability_router)

    assert "tutor response" == "".join(service.stream_response("Teach me machine learning."))
    assert "Career Forge handoff is active" in llm.calls[0][1]
    assert "Career Forge handoff is active" in service.session.capability_context()
    assert "tutor response" == "".join(service.stream_response("What should I try first?"))
    assert "Active capability handoff" in llm.calls[1][1]


def test_status_and_practice_lab_are_deterministic_and_do_not_call_the_model(tmp_path):
    capability_router = router(tmp_path)
    llm = FakeLLM()
    service = FridayConversationService(llm, FridayRuntime("route-status"), capability_router=capability_router)

    opened = "".join(service.stream_response("Friday, open Career Forge."))
    absent = "".join(service.stream_response("Open the Practice Lab."))

    assert "integrated local ML/AI Engineer apprenticeship" in opened
    assert "Practice Lab is absent" in absent
    assert not llm.calls


def test_explicit_memory_route_preserves_owner_only_mutation_and_governed_deletion(tmp_path):
    capability_router = router(tmp_path)
    llm = FakeLLM()
    service = FridayConversationService(llm, FridayRuntime("memory-route"), capability_router=capability_router)

    saved = "".join(service.stream_response("Friday, remember that my temporary qualification word is orbit."))
    recalled = "".join(service.stream_response("What do you remember about temporary qualification word?"))
    deleted = "".join(service.stream_response("Friday, forget my temporary qualification word."))

    assert "saved that as durable memory" in saved
    assert "temporary qualification word = orbit" in recalled
    assert "marked the durable memory" in deleted
    assert not llm.calls


def test_ambiguous_memory_mutation_fails_without_writing(tmp_path):
    capability_router = router(tmp_path)
    llm = FakeLLM()
    service = FridayConversationService(llm, FridayRuntime("memory-ambiguous"), capability_router=capability_router)

    response = "".join(service.stream_response("Friday, remember that turtles are patient."))

    assert "only in the form" in response
    assert not llm.calls
    assert not capability_router.adapters["persistent_memory"].service.search("turtles")


def test_information_and_invocation_intents_remain_distinct(tmp_path):
    capability_router = router(tmp_path)
    info = capability_router.route("What is Career Forge inside you?")
    invoke = capability_router.route("Teach me machine learning")

    assert info is not None and info.intent is ConversationIntent.INFORMATION and info.response
    assert invoke is not None and invoke.intent is ConversationIntent.INVOCATION and invoke.system_context


def test_bounded_known_wake_asr_variants_reach_career_forge_not_generic_conversation(tmp_path):
    capability_router = router(tmp_path)
    llm = FakeLLM()
    service = FridayConversationService(llm, FridayRuntime("asr-route"), capability_router=capability_router)

    opened = "".join(service.stream_response("Friday, open carrier force."))
    resumed = "".join(service.stream_response("Resume my career forward mission."))

    assert "Career Forge is Friday's integrated" in opened
    assert "There is no persisted active Career Forge mission" in resumed
    assert not llm.calls
