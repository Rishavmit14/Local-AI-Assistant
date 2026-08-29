"""Backend interface services and runtime contracts for Friday clients."""

from .api import create_presentation_app
from .conversation import FridayConversationService, StreamingLLM
from .events import FridayEventType, FridayRuntimeEvent
from .runtime import FridayRuntime, InvalidRuntimeTransition
from .service import FridayInterfaceService, RepositorySnapshot
from .states import FridayRuntimeState
from .voice_conversation import FridayVoiceConversationService, VoiceTranscriber

__all__ = [
    "FridayConversationService",
    "FridayEventType",
    "FridayInterfaceService",
    "FridayRuntime",
    "FridayRuntimeEvent",
    "FridayRuntimeState",
    "FridayVoiceConversationService",
    "InvalidRuntimeTransition",
    "RepositorySnapshot",
    "StreamingLLM",
    "VoiceTranscriber",
    "create_presentation_app",
]
