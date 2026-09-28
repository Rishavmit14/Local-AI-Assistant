"""Minimal Friday presentation candidate used only by model-swap qualification."""

from __future__ import annotations

import argparse

import uvicorn

from local_ai_assistant.common.config import AppConfig
from local_ai_assistant.interface.api import create_presentation_app
from local_ai_assistant.interface.conversation import FridayConversationService
from local_ai_assistant.interface.runtime import FridayRuntime
from local_ai_assistant.llm.client import LocalLLM
from local_ai_assistant.roles import Role, RoleOrchestrator


def build_app():
    config = AppConfig.from_env()
    model = LocalLLM(config=config)
    roles = RoleOrchestrator(model)
    runtime = FridayRuntime(session_id="disposable-model-swap-qualification")
    conversation = FridayConversationService(
        roles.client(Role.CONVERSATION),
        runtime,
        memory_context=lambda _prompt: "Synthetic qualification memory: memory-evidence-7319.",
        capability_context=lambda: "Synthetic qualification capabilities are read-only.",
        preference_context=lambda: "",
    )
    return create_presentation_app(runtime, conversation)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    uvicorn.run(build_app(), host="127.0.0.1", port=args.port, log_level="critical")


if __name__ == "__main__":
    main()
