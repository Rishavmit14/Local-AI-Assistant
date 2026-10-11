"""Audited bridge from direct voice intent to existing computer agency."""

from __future__ import annotations

import re
import threading
from collections.abc import Callable, Iterator

from local_ai_assistant.desktop.runner import ComputerAgencyRunner
from local_ai_assistant.desktop.targets import OpenCommand, is_friday_ui_target
from local_ai_assistant.desktop.visible_targets import (
    VisibleTargetAmbiguous,
    parse_visible_target_clarification,
    parse_visible_target_intent,
)

from .events import FridayEventType
from .runtime import FridayRuntime


class VoiceComputerActionService:
    """Create an owner-bound task, acknowledge it, and use the Stage 26 runner."""

    def __init__(self, runner: ComputerAgencyRunner, runtime: FridayRuntime,
                 owner_principal: Callable[[], str | None]) -> None:
        self.runner = runner
        self.runtime = runtime
        self.owner_principal = owner_principal
        self._active_lock = threading.RLock()
        self._active_task_id: str | None = None
        self._pending_task_id: str | None = None
        self._pending_clarification_task_id: str | None = None
        self._active_stop_listener_task_id: str | None = None
        self._start_active_stop_listener: Callable[[str], None] | None = None
        self._stop_active_stop_listener: Callable[[str], None] | None = None
        self.last_response_kind: str | None = None
        self.last_initial_segment_kind: str | None = None

    def bind_active_task_stop_listener(
        self, *, start: Callable[[str], None], stop: Callable[[str], None],
    ) -> None:
        """Bind the wake-only listener used while a voice computer task runs."""
        if not callable(start) or not callable(stop):
            raise ValueError("active task Stop listener callbacks are required")
        with self._active_lock:
            if self._active_task_id is not None or self._active_stop_listener_task_id is not None:
                raise RuntimeError("cannot replace an active task Stop listener")
            self._start_active_stop_listener = start
            self._stop_active_stop_listener = stop

    def start_active_task_stop_listener(self) -> bool:
        """Arm strict wake capture before acknowledging or executing a task."""
        with self._active_lock:
            task_id = self._active_task_id
            callback = self._start_active_stop_listener
            if task_id is None or callback is None:
                return False
            if self._active_stop_listener_task_id == task_id:
                return True
            self._active_stop_listener_task_id = task_id
        try:
            callback(task_id)
        except BaseException:
            with self._active_lock:
                if self._active_stop_listener_task_id == task_id:
                    self._active_stop_listener_task_id = None
            request_cancel = getattr(self.runner, "request_cancel", None)
            try:
                if callable(request_cancel):
                    request_cancel(task_id)
                else:
                    self.runner.ledger.request_cancel(task_id)
            except (OSError, RuntimeError, ValueError):
                pass
            raise
        with self._active_lock:
            still_active = (
                self._active_task_id == task_id
                and self._active_stop_listener_task_id == task_id
            )
        if not still_active:
            stop = self._stop_active_stop_listener
            if stop is not None:
                stop(task_id)
            return False
        return True

    def stop_active_task_stop_listener(self, task_id: str) -> None:
        """Pause the dedicated listener on every runner exit path."""
        with self._active_lock:
            if self._active_stop_listener_task_id != task_id:
                return
            self._active_stop_listener_task_id = None
            callback = self._stop_active_stop_listener
        if callback is not None:
            callback(task_id)

    @property
    def active_task_stop_listener_running(self) -> bool:
        with self._active_lock:
            return bool(
                self._active_task_id is not None
                and self._active_stop_listener_task_id == self._active_task_id
            )

    def has_pending_clarification(self) -> bool:
        """Whether this trusted local owner has a delivered question awaiting an answer."""
        try:
            owner = self.owner_principal()
            return bool(owner and self.runner.ledger.pending_clarification(owner))
        except (OSError, RuntimeError, ValueError):
            return False

    def cancel_active(self) -> bool:
        """Request Stop for the currently streamed owner computer task."""
        with self._active_lock:
            task_id = self._active_task_id
            clarification_task_id = self._pending_clarification_task_id
        if task_id is None and clarification_task_id is not None:
            try:
                task = self.runner.ledger.task(clarification_task_id)
                cancelled = self.runner.ledger.cancel_clarification(
                    clarification_task_id, task.owner_id,
                )
                with self._active_lock:
                    self._pending_clarification_task_id = None
                self.runtime.emit(
                    FridayEventType.COMPUTER_TASK_FAILED,
                    task_id=clarification_task_id,
                    metadata={"state": cancelled.state, "action_count": cancelled.action_count,
                              "clarification_ended": True},
                    transient=True,
                )
                return True
            except (OSError, RuntimeError, ValueError):
                return False
        if task_id is None:
            return False
        request_cancel = getattr(self.runner, "request_cancel", None)
        try:
            if callable(request_cancel):
                request_cancel(task_id)
            else:
                self.runner.ledger.request_cancel(task_id)
        except ValueError:
            # Completion can race a UI disconnect; a terminal task is already stopped.
            pass
        return True

    def _clear_active(self, task_id: str) -> None:
        with self._active_lock:
            if self._active_task_id == task_id:
                self._active_task_id = None

    def complete_after_playback(self) -> bool:
        """Mark a voice computer task complete only after its final speech played."""
        with self._active_lock:
            task_id = self._pending_task_id
            clarification_task_id = self._pending_clarification_task_id
            if task_id is None and clarification_task_id is not None:
                self._pending_clarification_task_id = None
            elif task_id is not None:
                self._pending_task_id = None
        if task_id is None and clarification_task_id is not None:
            try:
                clarification = self.runner.ledger.record_clarification_delivery(
                    clarification_task_id, played=True,
                )
                self.runtime.emit(
                    FridayEventType.COMPUTER_TASK_CLARIFICATION_DELIVERED,
                    task_id=clarification_task_id,
                    metadata={"state": "awaiting_clarification", "clarification_played": True,
                              "delivery_state": clarification.delivery_state},
                    transient=True,
                )
                return True
            except (OSError, RuntimeError, ValueError):
                return False
            finally:
                self._clear_active(clarification_task_id)
        if task_id is None:
            return False
        try:
            current = self.runner.ledger.task(task_id)
            if current.state != "active":
                completed = current
            else:
                try:
                    completed = self.runner.ledger.complete(task_id, succeeded=True)
                except ValueError:
                    if not self.runner.ledger.cancellation_requested(task_id):
                        raise
                    completed = self.runner.ledger.cancel(task_id)
            if completed.state != "succeeded":
                self.runtime.emit(
                    FridayEventType.COMPUTER_TASK_FAILED,
                    task_id=task_id,
                    metadata={"state": completed.state, "action_count": completed.action_count},
                    transient=True,
                )
                return False
            self.runtime.emit(
                FridayEventType.COMPUTER_TASK_COMPLETED,
                task_id=task_id,
                metadata={"state": completed.state, "action_count": completed.action_count,
                          "verified": True, "spoken_result": True},
                transient=True,
            )
            return True
        finally:
            self.stop_active_task_stop_listener(task_id)
            self._clear_active(task_id)

    def fail_after_playback(self, *, cancelled: bool = False) -> bool:
        """Fail a verified computer action whose final spoken result did not finish."""
        with self._active_lock:
            task_id = self._pending_task_id
            clarification_task_id = self._pending_clarification_task_id
            if task_id is None and clarification_task_id is not None:
                self._pending_clarification_task_id = None
            elif task_id is not None:
                self._pending_task_id = None
        if task_id is None and clarification_task_id is not None:
            try:
                self.runner.ledger.record_clarification_delivery(
                    clarification_task_id, played=False,
                )
                self.runtime.emit(
                    FridayEventType.COMPUTER_TASK_CLARIFICATION_DELIVERY_FAILED,
                    task_id=clarification_task_id,
                    metadata={"state": "awaiting_clarification", "clarification_played": False},
                    transient=True,
                )
                return True
            except (OSError, RuntimeError, ValueError):
                return False
            finally:
                self._clear_active(clarification_task_id)
        if task_id is None:
            return False
        try:
            current = self.runner.ledger.task(task_id)
            if current.state == "active":
                current = (self.runner.ledger.cancel(task_id)
                           if cancelled or self.runner.ledger.cancellation_requested(task_id)
                           else self.runner.ledger.complete(
                               task_id, succeeded=False, failure_reason="execution_failed",
                           ))
            self.runtime.emit(
                FridayEventType.COMPUTER_TASK_FAILED,
                task_id=task_id,
                metadata={"state": current.state, "action_count": current.action_count,
                          "spoken_result": False},
                transient=True,
            )
            return True
        finally:
            self.stop_active_task_stop_listener(task_id)
            self._clear_active(task_id)

    def stream_response(self, prompt: str, command: OpenCommand | None,
                        *, mark: Callable[[str], None],
                        progress: Callable[..., None] | None = None) -> Iterator[str]:
        self.last_response_kind = None
        self.last_initial_segment_kind = "acknowledgment"
        try:
            owner = self.owner_principal()
        except (OSError, RuntimeError, ValueError):
            owner = None
        if not owner:
            self.last_initial_segment_kind = "final_response"
            self.last_response_kind = "failure"
            mark("VOICE_ACTION_FAILED")
            mark("VOICE_ACTION_FINAL_RESPONSE_READY")
            yield "Local Owner trust is unavailable, so I did not control the computer."
            return

        label = self._spoken_target(command.target) if command is not None else "that"
        try:
            task = self.runner.ledger.create(owner, prompt, action_budget=20)
        except (OSError, RuntimeError, ValueError):
            self.last_initial_segment_kind = "final_response"
            self.last_response_kind = "failure"
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
        with self._active_lock:
            self._active_task_id = task.task_id
        try:
            self.start_active_task_stop_listener()
        except Exception:
            try:
                self.runner.ledger.cancel(task.task_id)
            except (OSError, RuntimeError, ValueError):
                pass
            self._clear_active(task.task_id)
            self.runtime.emit(
                FridayEventType.COMPUTER_TASK_FAILED,
                task_id=task.task_id,
                metadata={"state": "cancelled", "action_count": 0,
                          "stop_listener_ready": False},
                transient=True,
            )
            self.last_response_kind = "failure"
            self.last_initial_segment_kind = "final_response"
            mark("VOICE_ACTION_FAILED")
            mark("VOICE_ACTION_FINAL_RESPONSE_READY")
            yield "I couldn't safely keep Stop available, so I didn't start that computer task."
            return
        mark("VOICE_ACTION_ACKNOWLEDGMENT_READY")
        self.last_response_kind = "acknowledgment"
        try:
            yield f"Opening {label}." if command is not None else "I'll take care of that."
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
            self.stop_active_task_stop_listener(task.task_id)
            self._clear_active(task.task_id)
            mark("VOICE_ACTION_FAILED")
            raise
        mark("VOICE_ACTION_DISPATCHED")

        try:
            completed = self.runner.run(
                task.task_id, on_progress=progress or (lambda *_args, **_kwargs: None),
                defer_completion=True,
            )
        except Exception as exc:
            self.stop_active_task_stop_listener(task.task_id)
            clarification = None
            try:
                current = self.runner.ledger.task(task.task_id)
            except (OSError, RuntimeError, ValueError):
                current = task
            if (isinstance(exc, VisibleTargetAmbiguous) and current.state == "active"
                    and self.runner.ledger.can_await_clarification(task.task_id)):
                try:
                    clarification = self.runner.ledger.await_clarification(
                        task.task_id, str(exc)[:1000],
                        unresolved_referent=(parse_visible_target_intent(prompt).plan_target
                                             if parse_visible_target_intent(prompt) is not None else ""),
                    )
                except (OSError, RuntimeError, ValueError):
                    clarification = None
                if clarification is not None:
                    with self._active_lock:
                        self._pending_clarification_task_id = task.task_id
                    self.last_response_kind = "clarification"
                    current = self.runner.ledger.task(task.task_id)
                elif current.state == "active":
                    try:
                        current = self.runner.ledger.complete(
                            task.task_id, succeeded=False, failure_reason="target_unresolved",
                        )
                    except (OSError, RuntimeError, ValueError):
                        pass
            elif current.state == "active" and current.action_count == 0:
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
                result = (str(exc)[:240] if isinstance(exc, VisibleTargetAmbiguous)
                          else "I stopped the computer action.")
            elif current.state == "recovery_required":
                result = "I couldn't verify the computer action. It is paused for recovery and won't be replayed."
            elif isinstance(exc, VisibleTargetAmbiguous):
                result = str(exc)[:240]
            else:
                result = (f"I couldn't verify that {label} opened, so I stopped."
                          if command is not None else
                          "I couldn't verify the requested computer task, so I stopped.")
            self.runtime.emit(
                (FridayEventType.COMPUTER_TASK_AWAITING_CLARIFICATION
                 if current.state == "awaiting_clarification"
                 else FridayEventType.COMPUTER_TASK_FAILED),
                task_id=task.task_id,
                metadata={"state": current.state, "action_count": current.action_count,
                          **({"observation_id_present": clarification.observation_id is not None}
                             if clarification is not None else {})},
                transient=True,
            )
            mark("VOICE_CLARIFICATION_READY" if current.state == "awaiting_clarification"
                 else "VOICE_ACTION_FAILED")
            if current.state != "awaiting_clarification":
                self.last_response_kind = "failure"
        else:
            if completed.state != "active":
                self.stop_active_task_stop_listener(task.task_id)
                self.runtime.emit(
                    FridayEventType.COMPUTER_TASK_FAILED,
                    task_id=task.task_id,
                    metadata={"state": completed.state, "action_count": completed.action_count},
                    transient=True,
                )
                mark("VOICE_ACTION_FAILED")
                result = (f"I couldn't verify that {label} opened, so I stopped."
                          if command is not None else
                          "I couldn't verify the requested computer task, so I stopped.")
            else:
                self.last_response_kind = "final_result"
                mark("VOICE_ACTION_VERIFIED")
                result = (f"{label} is open." if command is not None else
                          self.runner.result_summary(task.task_id)
                          or "The requested computer task completed and was verified.")
                with self._active_lock:
                    self._pending_task_id = task.task_id

        if self._pending_task_id != task.task_id:
            self._clear_active(task.task_id)
        mark("VOICE_ACTION_FINAL_RESPONSE_READY")
        try:
            yield result
        except GeneratorExit:
            if self._pending_task_id == task.task_id:
                self.fail_after_playback(cancelled=True)
            raise

    def stream_clarification_response(self, prompt: str, *, mark: Callable[[str], None],
                                      progress: Callable[..., None] | None = None) -> Iterator[str]:
        """Re-ground a delivered clarification response before any action can resume."""
        self.last_response_kind = None
        self.last_initial_segment_kind = None
        try:
            owner = self.owner_principal()
            clarification = (self.runner.ledger.pending_clarification(owner)
                             if owner else None)
        except (OSError, RuntimeError, ValueError):
            clarification = None
        if clarification is None:
            self.last_response_kind = "failure"
            self.last_initial_segment_kind = "final_response"
            yield "There isn't a delivered computer question waiting for an answer."
            return

        task = self.runner.ledger.task(clarification.task_id)
        intent = parse_visible_target_intent(task.request)
        if re.fullmatch(r"\s*(?:cancel|stop|never mind|nevermind|end that)\s*[.!]?\s*",
                        prompt, re.I):
            cancelled = self.runner.ledger.cancel_clarification(task.task_id, clarification.owner_id)
            self.last_response_kind = "failure"
            self.last_initial_segment_kind = "final_response"
            self.runtime.emit(
                FridayEventType.COMPUTER_TASK_FAILED, task_id=task.task_id,
                metadata={"state": cancelled.state, "action_count": cancelled.action_count,
                          "clarification_ended": True}, transient=True,
            )
            yield "Okay, I stopped that computer task."
            return
        resolved_intent = parse_visible_target_clarification(task.request, prompt)
        if intent is not None and resolved_intent is None:
            try:
                self.runner.ledger.resume_clarification(task.task_id, clarification.owner_id, prompt)
                next_question = (
                    "Please tell me the visible folder ordinal or selected item to use."
                )
                self.runner.ledger.await_clarification(
                    task.task_id, next_question,
                    unresolved_referent=clarification.unresolved_referent,
                    observation_id=clarification.observation_id,
                )
            except (OSError, RuntimeError, ValueError):
                self.last_response_kind = "failure"
                yield "I couldn't safely retain that computer clarification."
                return
            with self._active_lock:
                self._pending_clarification_task_id = task.task_id
            self.last_response_kind = "clarification"
            self.last_initial_segment_kind = "clarification"
            self.runtime.emit(
                FridayEventType.COMPUTER_TASK_AWAITING_CLARIFICATION,
                task_id=task.task_id,
                metadata={"state": "awaiting_clarification", "action_count": task.action_count,
                          "observation_id_present": clarification.observation_id is not None},
                transient=True,
            )
            yield next_question
            return

        try:
            self.runner.ledger.resume_clarification(task.task_id, clarification.owner_id, prompt)
        except (OSError, RuntimeError, ValueError):
            self.last_response_kind = "failure"
            yield "I couldn't safely resume that computer task."
            return
        with self._active_lock:
            self._active_task_id = task.task_id
        mark("VOICE_CLARIFICATION_RESPONSE_RECEIVED")
        self.last_initial_segment_kind = "status"
        yield "I'll recheck the current window."
        try:
            completed = self.runner.run(
                task.task_id, on_progress=progress or (lambda *_args, **_kwargs: None),
                defer_completion=True, clarification_answer=prompt,
            )
        except Exception as exc:
            current = self.runner.ledger.task(task.task_id)
            if (isinstance(exc, VisibleTargetAmbiguous) and current.state == "active"
                    and self.runner.ledger.can_await_clarification(task.task_id)):
                question = str(exc)[:1000]
                pending = self.runner.ledger.await_clarification(
                    task.task_id, question, unresolved_referent=clarification.unresolved_referent,
                )
                with self._active_lock:
                    self._pending_clarification_task_id = task.task_id
                self.last_response_kind = "clarification"
                self.runtime.emit(
                    FridayEventType.COMPUTER_TASK_AWAITING_CLARIFICATION,
                    task_id=task.task_id,
                    metadata={"state": "awaiting_clarification",
                              "action_count": current.action_count,
                              "observation_id_present": pending.observation_id is not None},
                    transient=True,
                )
                self.last_initial_segment_kind = "status"
                yield question
            else:
                if current.state == "active":
                    current = self.runner.ledger.complete(
                        task.task_id, succeeded=False, failure_reason="target_unresolved",
                    )
                self.last_response_kind = "failure"
                self.last_initial_segment_kind = "status"
                yield "I still couldn't verify a safe target, so I stopped."
        else:
            if completed.state != "active":
                self.last_response_kind = "failure"
                yield "I couldn't verify the requested action, so I stopped."
            else:
                with self._active_lock:
                    self._pending_task_id = task.task_id
                self.last_response_kind = "final_result"
                self.last_initial_segment_kind = "status"
                yield (self.runner.result_summary(task.task_id)
                       or "The requested computer task completed and was verified.")

    @staticmethod
    def _spoken_target(target: str) -> str:
        if is_friday_ui_target(target):
            return "Friday's interface"
        cleaned = " ".join(target.strip().rstrip(".!?").split())
        return cleaned[:100] or "that"


__all__ = ["VoiceComputerActionService"]
