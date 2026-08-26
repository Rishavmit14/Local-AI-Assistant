"""Backend interface services and runtime contracts for Friday clients."""

from .api import create_presentation_app
from .conversation import FridayConversationService, StreamingLLM
from .events import FridayEventType, FridayRuntimeEvent
from .runtime import FridayRuntime, InvalidRuntimeTransition
from .service import FridayInterfaceService, RepositorySnapshot
from .states import FridayRuntimeState

__all__ = [
    "FridayConversationService",
    "FridayEventType",
    "FridayInterfaceService",
    "FridayRuntime",
    "FridayRuntimeEvent",
    "FridayRuntimeState",
    "InvalidRuntimeTransition",
    "RepositorySnapshot",
    "StreamingLLM",
    "create_presentation_app",
]
