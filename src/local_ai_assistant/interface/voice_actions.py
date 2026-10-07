"""Audited bridge from direct voice intent to existing computer agency."""

from __future__ import annotations

from collections.abc import Callable, Iterator

from local_ai_assistant.desktop.runner import ComputerAgencyRunner
from local_ai_assistant.desktop.targets import OpenCommand, is_friday_ui_target

from .events import FridayEventType
from .runtime import FridayRuntime


class VoiceComputerActionService:
    """Create an owner-bound task, acknowledge it, and use the Stage 26 runner."""

    def __init__(self, runner: ComputerAgencyRunner, runtime: FridayRuntime,
                 owner_principal: Callable[[], str | None]) -> None:
        self.runner = runner
        self.runtime = runtime
        self.owner_principal = owner_principal

    def stream_response(self, prompt: str, command: OpenCommand,
                        *, mark: Callable[[str], None]) -> Iterator[str]:
        try:
            owner = self.owner_principal()
        except (OSError, RuntimeError, ValueError):
            owner = None
        if not owner:
            mark("VOICE_ACTION_FAILED")
            mark("VOICE_ACTION_FINAL_RESPONSE_READY")
            yield "Local Owner trust is unavailable, so I did not control the computer."
            return

        label = self._spoken_target(command.target)
        try:
            task = self.runner.ledger.create(owner, prompt, action_budget=20)
        except (OSError, RuntimeError, ValueError):
            mark("VOICE_ACTION_FAILED")
            mark("VOICE_ACTION_FINAL_RESPONSE_READY")
            yield "I couldn't start a safely tracked computer action."
            return

        self.runtime.emit(
            FridayEventType.COMPUTER_TASK_STARTED,
            task_id=task.task_id,
            metadata={"state": task.state, "source": "voice"},
            transient=True,
        )
        try:
            yield f"Opening {label}."
        except GeneratorExit:
            try:
                current = self.runner.ledger.task(task.task_id)
                if current.state == "active":
                    current = self.runner.ledger.cancel(task.task_id)
            except (OSError, RuntimeError, ValueError):
                current = task
            self.runtime.emit(
                FridayEventType.COMPUTER_TASK_FAILED,
                task_id=task.task_id,
                metadata={"state": current.state, "action_count": current.action_count},
                transient=True,
            )
            mark("VOICE_ACTION_FAILED")
            raise
        mark("VOICE_ACTION_DISPATCHED")

        try:
            completed = self.runner.run(task.task_id)
        except Exception:
            try:
                current = self.runner.ledger.task(task.task_id)
            except (OSError, RuntimeError, ValueError):
                current = task
            if current.state == "active" and current.action_count == 0:
                try:
                    current = self.runner.ledger.complete(task.task_id, succeeded=False)
                except (OSError, RuntimeError, ValueError):
                    pass
            elif current.state == "active" and current.action_count > 0:
                try:
                    current = self.runner.ledger.cancel(task.task_id)
                except (OSError, RuntimeError, ValueError):
                    pass
            if current.state == "cancelled":
                result = "I stopped the computer action."
            elif current.state == "recovery_required":
                result = "I couldn't verify the computer action. It is paused for recovery and won't be replayed."
            else:
                result = f"I couldn't verify that {label} opened, so I stopped."
            self.runtime.emit(
                FridayEventType.COMPUTER_TASK_FAILED,
                task_id=task.task_id,
                metadata={"state": current.state, "action_count": current.action_count},
                transient=True,
            )
            mark("VOICE_ACTION_FAILED")
        else:
            if completed.state != "succeeded":
                self.runtime.emit(
                    FridayEventType.COMPUTER_TASK_FAILED,
                    task_id=task.task_id,
                    metadata={"state": completed.state, "action_count": completed.action_count},
                    transient=True,
                )
                mark("VOICE_ACTION_FAILED")
                result = f"I couldn't verify that {label} opened, so I stopped."
            else:
                self.runtime.emit(
                    FridayEventType.COMPUTER_TASK_COMPLETED,
                    task_id=task.task_id,
                    metadata={"state": completed.state, "action_count": completed.action_count,
                              "verified": True},
                    transient=True,
                )
                mark("VOICE_ACTION_VERIFIED")
                result = f"{label} is open."

        mark("VOICE_ACTION_FINAL_RESPONSE_READY")
        yield result

    @staticmethod
    def _spoken_target(target: str) -> str:
        if is_friday_ui_target(target):
            return "Friday's interface"
        cleaned = " ".join(target.strip().rstrip(".!?").split())
        return cleaned[:100] or "that"


__all__ = ["VoiceComputerActionService"]
