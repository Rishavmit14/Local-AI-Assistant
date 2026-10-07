from local_ai_assistant.desktop.agency_ledger import ComputerAgencyLedger
from local_ai_assistant.desktop.targets import OpenCommand
from local_ai_assistant.interface.events import FridayEventType
from local_ai_assistant.interface.runtime import FridayRuntime
from local_ai_assistant.interface.voice_actions import VoiceComputerActionService


class CompletingRunner:
    def __init__(self, ledger):
        self.ledger = ledger
        self.task_ids = []

    def run(self, task_id):
        self.task_ids.append(task_id)
        return self.ledger.complete(task_id, succeeded=True)


class FailingBeforeActionRunner:
    def __init__(self, ledger):
        self.ledger = ledger
        self.task_ids = []

    def run(self, task_id):
        self.task_ids.append(task_id)
        raise RuntimeError("desktop permission requires owner recovery")


class CancelledRunner:
    def __init__(self, ledger):
        self.ledger = ledger
        self.task_ids = []

    def run(self, task_id):
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
        "local-owner", "Friday, open YouTube", "succeeded",
    )
    assert marks == ["VOICE_ACTION_DISPATCHED", "VOICE_ACTION_VERIFIED",
                     "VOICE_ACTION_FINAL_RESPONSE_READY"]
    assert [event.event_type for event in runtime.events_since()] == [
        FridayEventType.COMPUTER_TASK_STARTED,
        FridayEventType.COMPUTER_TASK_COMPLETED,
    ]


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
    assert marks == ["VOICE_ACTION_FAILED"]


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


def test_stop_during_agency_run_reports_cancelled_task(tmp_path):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "computer.sqlite3")
    runner = CancelledRunner(ledger)
    runtime = FridayRuntime("voice-action-stop")
    service = VoiceComputerActionService(runner, runtime, lambda: "local-owner")

    assert list(service.stream_response(
        "open Files", OpenCommand("open", "Files"), mark=lambda _stage: None,
    )) == ["Opening Files.", "I stopped the computer action."]
    assert ledger.task(runner.task_ids[0]).state == "cancelled"
