import threading
import time

from local_ai_assistant.desktop.agency_ledger import ComputerAgencyLedger
from local_ai_assistant.desktop.targets import OpenCommand
from local_ai_assistant.desktop.visible_targets import VisibleTargetAmbiguous
from local_ai_assistant.interface.events import FridayEventType
from local_ai_assistant.interface.runtime import FridayRuntime
from local_ai_assistant.interface.voice_actions import VoiceComputerActionService


class CompletingRunner:
    def __init__(self, ledger):
        self.ledger = ledger
        self.task_ids = []
        self.clarification_answers = []

    def run(self, task_id, *, on_progress=lambda *_args, **_kwargs: None,
            defer_completion=False, clarification_answer=None):
        self.task_ids.append(task_id)
        if clarification_answer is not None:
            self.clarification_answers.append(clarification_answer)
        return (self.ledger.task(task_id) if defer_completion
                else self.ledger.complete(task_id, succeeded=True))

    @staticmethod
    def result_summary(_task_id):
        return "The requested folder is open and verified."


class FailingBeforeActionRunner:
    def __init__(self, ledger):
        self.ledger = ledger
        self.task_ids = []

    def run(self, task_id, *, on_progress=lambda *_args, **_kwargs: None, defer_completion=False):
        self.task_ids.append(task_id)
        raise RuntimeError("desktop permission requires owner recovery")


class CancelledRunner:
    def __init__(self, ledger):
        self.ledger = ledger
        self.task_ids = []

    def run(self, task_id, *, on_progress=lambda *_args, **_kwargs: None, defer_completion=False):
        self.task_ids.append(task_id)
        self.ledger.cancel(task_id)
        raise RuntimeError("stop requested")


def test_voice_action_is_owner_bound_durable_acknowledged_and_verified(tmp_path):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "computer.sqlite3")
    runner = CompletingRunner(ledger)
    runtime = FridayRuntime("voice-action-service")
    marks = []
    service = VoiceComputerActionService(runner, runtime, lambda: "local-owner")

    result = list(service.stream_response(
        "Friday, open YouTube", OpenCommand("open", "YouTube"), mark=marks.append,
    ))

    assert result == ["Opening YouTube.", "YouTube is open."]
    task = ledger.task(runner.task_ids[0])
    assert (task.owner_id, task.request, task.state) == (
        "local-owner", "Friday, open YouTube", "active",
    )
    assert marks == ["VOICE_ACTION_ACKNOWLEDGMENT_READY", "VOICE_ACTION_DISPATCHED", "VOICE_ACTION_VERIFIED",
                     "VOICE_ACTION_FINAL_RESPONSE_READY"]
    assert [event.event_type for event in runtime.events_since()] == [
        FridayEventType.COMPUTER_TASK_STARTED,
    ]
    assert service.complete_after_playback() is True
    assert ledger.task(task.task_id).state == "succeeded"
    completed = runtime.events_since()[-1]
    assert completed.event_type is FridayEventType.COMPUTER_TASK_COMPLETED
    assert completed.metadata["spoken_result"] is True


def test_voice_action_fails_closed_without_local_owner_trust(tmp_path):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "computer.sqlite3")
    runner = CompletingRunner(ledger)
    runtime = FridayRuntime("voice-action-no-trust")
    service = VoiceComputerActionService(runner, runtime, lambda: None)
    marks = []

    assert list(service.stream_response(
        "open Files", OpenCommand("open", "Files"), mark=marks.append,
    )) == ["Local Owner trust is unavailable, so I did not control the computer."]
    assert runner.task_ids == []
    assert ledger.recent_tasks("local-owner") == ()
    assert runtime.events_since() == ()
    assert marks == ["VOICE_ACTION_FAILED", "VOICE_ACTION_FINAL_RESPONSE_READY"]


def test_revoked_owner_trust_prevents_task_creation(tmp_path):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "computer.sqlite3")
    runner = CompletingRunner(ledger)
    runtime = FridayRuntime("voice-action-revoked-trust")

    def revoked():
        raise RuntimeError("revoked")

    service = VoiceComputerActionService(runner, runtime, revoked)
    assert list(service.stream_response(
        "open Files", OpenCommand("open", "Files"), mark=lambda _stage: None,
    )) == ["Local Owner trust is unavailable, so I did not control the computer."]
    assert runner.task_ids == []
    assert runtime.events_since() == ()


def test_closing_before_dispatch_cancels_the_durable_task(tmp_path):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "computer.sqlite3")
    runner = CompletingRunner(ledger)
    runtime = FridayRuntime("voice-action-cancel-before-dispatch")
    marks = []
    service = VoiceComputerActionService(runner, runtime, lambda: "local-owner")
    response = service.stream_response(
        "open Files", OpenCommand("open", "Files"), mark=marks.append,
    )

    assert next(response) == "Opening Files."
    task = ledger.recent_tasks("local-owner")[0]
    response.close()

    assert ledger.task(task.task_id).state == "cancelled"
    assert runner.task_ids == []
    assert [event.event_type for event in runtime.events_since()] == [
        FridayEventType.COMPUTER_TASK_STARTED,
        FridayEventType.COMPUTER_TASK_FAILED,
    ]
    assert marks == ["VOICE_ACTION_ACKNOWLEDGMENT_READY", "VOICE_ACTION_FAILED"]


def test_closing_during_final_speech_does_not_mark_verified_task_complete(tmp_path):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "computer.sqlite3")
    runner = CompletingRunner(ledger)
    runtime = FridayRuntime("voice-action-cancel-final-speech")
    service = VoiceComputerActionService(runner, runtime, lambda: "local-owner")
    response = service.stream_response(
        "Friday, open YouTube", OpenCommand("open", "YouTube"), mark=lambda _stage: None,
    )

    assert next(response) == "Opening YouTube."
    assert next(response) == "YouTube is open."
    task = ledger.task(runner.task_ids[0])
    assert task.state == "active"
    response.close()

    assert ledger.task(task.task_id).state == "cancelled"
    assert runtime.events_since()[-1].event_type is FridayEventType.COMPUTER_TASK_FAILED


def test_preflight_failure_closes_the_zero_action_task(tmp_path):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "computer.sqlite3")
    runner = FailingBeforeActionRunner(ledger)
    runtime = FridayRuntime("voice-action-preflight-failure")
    service = VoiceComputerActionService(runner, runtime, lambda: "local-owner")

    assert list(service.stream_response(
        "open Files", OpenCommand("open", "Files"), mark=lambda _stage: None,
    )) == ["Opening Files.", "I couldn't verify that Files opened, so I stopped."]
    task = ledger.task(runner.task_ids[0])
    assert (task.state, task.action_count) == ("failed", 0)


def test_visible_target_ambiguity_is_spoken_as_a_clarification(tmp_path):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "computer.sqlite3")

    class AmbiguousRunner(FailingBeforeActionRunner):
        def __init__(self, agency_ledger):
            super().__init__(agency_ledger)
            self.clarification_answers = []

        @staticmethod
        def result_summary(_task_id):
            return "The requested folder is open and verified."

        def run(self, task_id, *, on_progress=lambda *_args, **_kwargs: None,
                defer_completion=False, clarification_answer=None):
            self.task_ids.append(task_id)
            if clarification_answer is not None:
                self.clarification_answers.append(clarification_answer)
                return self.ledger.task(task_id)
            raise VisibleTargetAmbiguous("I can't establish the visible order reliably. Which folder do you mean?")

    runner = AmbiguousRunner(ledger)
    service = VoiceComputerActionService(runner, FridayRuntime("voice-visible-clarification"),
                                         lambda: "local-owner")

    assert list(service.stream_response(
        "Open the second folder", None, mark=lambda _stage: None,
    )) == ["I'll take care of that.",
          "I can't establish the visible order reliably. Which folder do you mean?"]
    task_id = runner.task_ids[0]
    assert ledger.task(task_id).state == "awaiting_clarification"
    assert ledger.task(task_id).failure_reason is None
    assert ledger.pending_clarification("local-owner") is None
    assert service.complete_after_playback() is True
    assert service.has_pending_clarification()

    follow_up = list(service.stream_clarification_response(
        "Yes, the third folder.", mark=lambda _stage: None,
    ))
    assert follow_up == ["I'll recheck the current window.",
                         "The requested folder is open and verified."]
    assert runner.clarification_answers == ["Yes, the third folder."]
    assert ledger.task(task_id).state == "active"
    assert service.complete_after_playback() is True
    completed = ledger.task(task_id)
    assert completed.state == "succeeded"


def test_stop_during_agency_run_reports_cancelled_task(tmp_path):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "computer.sqlite3")
    runner = CancelledRunner(ledger)
    runtime = FridayRuntime("voice-action-stop")
    service = VoiceComputerActionService(runner, runtime, lambda: "local-owner")

    assert list(service.stream_response(
        "open Files", OpenCommand("open", "Files"), mark=lambda _stage: None,
    )) == ["Opening Files.", "I stopped the computer action."]
    assert ledger.task(runner.task_ids[0]).state == "cancelled"


def test_stream_cancellation_requests_stop_during_active_computer_run(tmp_path):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "computer.sqlite3")

    class BlockingRunner:
        def __init__(self):
            self.ledger = ledger
            self.started = threading.Event()
            self.task_ids = []

        def run(self, task_id, *, on_progress=lambda *_args, **_kwargs: None, defer_completion=False):
            self.task_ids.append(task_id)
            self.started.set()
            while not self.ledger.cancellation_requested(task_id):
                time.sleep(0.005)
            self.ledger.cancel(task_id)
            raise RuntimeError("stop requested")

    runner = BlockingRunner()
    service = VoiceComputerActionService(
        runner, FridayRuntime("voice-action-stream-stop"), lambda: "local-owner",
    )
    response = service.stream_response(
        "open Files", OpenCommand("open", "Files"), mark=lambda _stage: None,
    )
    assert next(response) == "Opening Files."
    result = []
    advancing = threading.Thread(target=lambda: result.append(next(response)))
    advancing.start()
    assert runner.started.wait(timeout=1)
    assert service.cancel_active() is True
    advancing.join(timeout=2)
    assert not advancing.is_alive()
    assert result == ["I stopped the computer action."]
    assert ledger.task(runner.task_ids[0]).state == "cancelled"
    response.close()


def test_active_task_stop_listener_spans_ack_task_and_final_playback(tmp_path):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "computer.sqlite3")
    class ListenerCheckingRunner(CompletingRunner):
        def run(self, task_id, **kwargs):
            assert service.active_task_stop_listener_running is True
            return super().run(task_id, **kwargs)

    runner = ListenerCheckingRunner(ledger)
    service = VoiceComputerActionService(
        runner, FridayRuntime("voice-action-active-stop-listener"), lambda: "local-owner",
    )
    lifecycle = []
    service.bind_active_task_stop_listener(
        start=lambda task_id: lifecycle.append(("start", task_id)),
        stop=lambda task_id: lifecycle.append(("stop", task_id)),
    )
    response = service.stream_response(
        "open Files", OpenCommand("open", "Files"), mark=lambda _stage: None,
    )

    assert next(response) == "Opening Files."
    task_id = ledger.recent_tasks("local-owner")[0].task_id
    assert lifecycle == [("start", task_id)]
    assert service.active_task_stop_listener_running is True
    assert next(response) == "Files is open."
    assert lifecycle == [("start", task_id)]
    assert service.active_task_stop_listener_running is True
    assert service.complete_after_playback() is True
    assert lifecycle == [("start", task_id), ("stop", task_id)]
    assert service.active_task_stop_listener_running is False
    response.close()


def test_task_is_cancelled_without_execution_when_stop_listener_cannot_arm(tmp_path):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "computer.sqlite3")
    runner = CompletingRunner(ledger)
    service = VoiceComputerActionService(
        runner, FridayRuntime("voice-action-stop-listener-failure"), lambda: "local-owner",
    )
    service.bind_active_task_stop_listener(
        start=lambda _task_id: (_ for _ in ()).throw(RuntimeError("capture unavailable")),
        stop=lambda _task_id: None,
    )

    assert list(service.stream_response(
        "open Files", OpenCommand("open", "Files"), mark=lambda _stage: None,
    )) == ["I couldn't safely keep Stop available, so I didn't start that computer task."]
    task = ledger.recent_tasks("local-owner")[0]
    assert task.state == "cancelled"
    assert task.action_count == 0
    assert runner.task_ids == []
    assert service.active_task_stop_listener_running is False


def test_delayed_playback_success_cannot_revive_cancelled_task(tmp_path):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "computer.sqlite3")
    runner = CompletingRunner(ledger)
    service = VoiceComputerActionService(
        runner, FridayRuntime("voice-action-delayed-cancel"), lambda: "local-owner",
    )

    assert list(service.stream_response(
        "open Files", OpenCommand("open", "Files"), mark=lambda _stage: None,
    )) == ["Opening Files.", "Files is open."]
    task_id = runner.task_ids[0]
    assert ledger.task(task_id).state == "active"

    ledger.request_cancel(task_id)
    assert service.complete_after_playback() is False
    assert ledger.task(task_id).state == "cancelled"
