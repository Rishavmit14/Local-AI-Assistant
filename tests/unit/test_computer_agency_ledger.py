import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from datetime import UTC, datetime, timedelta

import pytest

from local_ai_assistant.desktop.agency_ledger import ComputerAgencyLedger
from local_ai_assistant.desktop.observation import AccessibleElement, DesktopObservation


def observation(marker: str, digest_marker: str | None = None,
                *, moved: bool = False) -> DesktopObservation:
    element = AccessibleElement((0, 0), "Test", "button", "Open", (20 if moved else 10, 10, 40, 30),
                                ("click",), True)
    return DesktopObservation(f"observation_{marker * 32}", datetime.now(UTC).isoformat(),
                              (digest_marker or marker) * 64, (element,))


def test_action_claim_requires_matching_observation_and_post_action_evidence(tmp_path):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "agency.sqlite3")
    task = ledger.create("owner", "Open a safe page", action_budget=1)
    before, after = observation("a"), observation("b")
    ledger.record_observation(task.task_id, before)
    action = ledger.prepare(task.task_id, kind="open_uri", observation_id=before.observation_id,
                            target_digest="c" * 64, risk="low")
    fresh = observation("c", "a")
    assert ledger.claim(action.action_id, fresh_observation=fresh).state == "in_flight"
    assert ledger.action(action.action_id).claim_observation_id == fresh.observation_id
    with pytest.raises(ValueError, match="cannot be claimed"):
        ledger.claim(action.action_id, fresh_observation=observation("d", "a"))
    assert ledger.finish(action.action_id, result_observation=after,
                         verified=True, outcome="postcondition_verified").state == "verified"
    assert ledger.task(task.task_id).action_count == 1
    with pytest.raises(ValueError, match="budget exhausted"):
        ledger.prepare(task.task_id, kind="open_uri", observation_id=after.observation_id,
                       target_digest="d" * 64, risk="low")
    private = tmp_path / "private"
    assert private.stat().st_mode & 0o777 == 0o700
    assert (private / "agency.sqlite3").stat().st_mode & 0o777 == 0o600


def test_current_state_claim_records_one_fresh_snapshot_without_a_second_scan(tmp_path):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "agency.sqlite3")
    task = ledger.create("owner", "Open a fresh VS Code terminal", action_budget=1)
    previous = observation("a")
    current = observation("b", "a")
    ledger.record_observation(task.task_id, previous)
    ledger.record_observation(task.task_id, current)
    action = ledger.prepare(
        task.task_id, kind="hotkey", observation_id=current.observation_id,
        target_digest=ledger.fingerprint(current, current.elements[0]), risk="low",
    )

    claimed = ledger.claim_current(action.action_id, observation=current)

    assert claimed.state == "in_flight"
    assert claimed.observation_id == current.observation_id
    assert claimed.claim_observation_id == current.observation_id
    assert ledger.task(task.task_id).action_count == 1


def test_stale_observation_is_recorded_and_never_claimed(tmp_path):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "agency.sqlite3")
    task = ledger.create("owner", "Open page")
    before = observation("a")
    ledger.record_observation(task.task_id, before)
    action = ledger.prepare(task.task_id, kind="click", observation_id=before.observation_id,
                            target_digest=ledger.fingerprint(before, before.elements[0]), risk="medium")
    with pytest.raises(ValueError, match="stale"):
        ledger.claim(action.action_id, fresh_observation=observation("e", moved=True))
    assert ledger.action(action.action_id).state == "stale"
    assert ledger.task(task.task_id).action_count == 0


def test_stale_attempt_persists_reason_and_both_observation_ids_without_claiming_action(tmp_path):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "agency.sqlite3")
    task = ledger.create("owner", "Open the second item")
    before = observation("a")
    changed = observation("b", "c")
    ledger.record_observation(task.task_id, before)

    rejected = ledger.record_stale_attempt(
        task.task_id, kind="click", observation_id=before.observation_id,
        target_digest=ledger.fingerprint(before, before.elements[0]),
        fresh_observation=changed, reason="stale_collection_changed",
        target_summary=("Test", "Open"), target_window=None,
    )

    assert rejected.state == "stale"
    assert rejected.observation_id == before.observation_id
    assert rejected.claim_observation_id == changed.observation_id
    status = ledger.recent_actions(task.task_id)[0]
    assert (status.state, status.outcome) == ("stale", "stale_collection_changed")
    assert ledger.task(task.task_id).action_count == 0
    with pytest.raises(ValueError, match="cannot be claimed"):
        ledger.claim(rejected.action_id, fresh_observation=observation("c"))


@pytest.mark.parametrize("kind", ("open_uri", "launch_app"))
def test_resolved_target_claim_survives_unrelated_desktop_change(tmp_path, kind):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "agency.sqlite3")
    task = ledger.create("owner", "Open a resolved target", action_budget=1)
    before = observation("a")
    ledger.record_observation(task.task_id, before)
    action = ledger.prepare(
        task.task_id, kind=kind, observation_id=before.observation_id,
        target_digest="c" * 64, risk="low", target_summary=(kind, "resolved target"),
    )

    # A fresh observation is required, but focus/name/bounds churn is unrelated
    # to the runner's separately resolved URI or installed desktop entry.
    changed = DesktopObservation(
        "observation_" + "d" * 32, datetime.now(UTC).isoformat(), "e" * 64,
        (AccessibleElement((0, 0), "Other app", "window", "Changed", (20, 30, 50, 40), (), True),),
    )
    assert ledger.claim(action.action_id, fresh_observation=changed).state == "in_flight"
    assert ledger.action(action.action_id).claim_observation_id == changed.observation_id
    assert ledger.task(task.task_id).action_count == 1


def test_unresolved_window_action_still_requires_unchanged_desktop(tmp_path):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "agency.sqlite3")
    task = ledger.create("owner", "Focus a window")
    before = observation("a")
    ledger.record_observation(task.task_id, before)
    action = ledger.prepare(task.task_id, kind="focus_app", observation_id=before.observation_id,
                            target_digest="c" * 64, risk="low")
    with pytest.raises(ValueError, match="stale"):
        ledger.claim(action.action_id, fresh_observation=observation("e", "f"))
    assert ledger.action(action.action_id).state == "stale"
    assert ledger.task(task.task_id).action_count == 0


def test_consequential_claim_needs_separate_approval_and_cancel_stops_new_actions(tmp_path):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "agency.sqlite3")
    task = ledger.create("owner", "Fill but do not submit")
    before = observation("a")
    ledger.record_observation(task.task_id, before)
    action = ledger.prepare(task.task_id, kind="click", observation_id=before.observation_id,
                            target_digest=ledger.fingerprint(before, before.elements[0]), risk="consequential")
    with pytest.raises(ValueError, match="requires canonical approval"):
        ledger.claim(action.action_id, fresh_observation=observation("c", "a"))
    assert ledger.action(action.action_id).state == "prepared"
    assert ledger.cancel(task.task_id).state == "cancelled"
    assert ledger.cancellation_requested(task.task_id)
    assert ledger.action(action.action_id).state == "cancelled"
    with pytest.raises(ValueError, match="cannot be claimed"):
        ledger.claim(action.action_id, fresh_observation=observation("d", "a"))


def test_restart_marks_uncertain_physical_effect_in_doubt_without_replay(tmp_path):
    database = tmp_path / "private" / "agency.sqlite3"
    ledger = ComputerAgencyLedger(database)
    task = ledger.create("owner", "Open editor")
    before = observation("a")
    ledger.record_observation(task.task_id, before)
    action = ledger.prepare(task.task_id, kind="launch_app", observation_id=before.observation_id,
                            target_digest="b" * 64, risk="medium")
    ledger.claim(action.action_id, fresh_observation=observation("c", "a"))
    ledger.mark_execution_started(action.action_id)

    restarted = ComputerAgencyLedger(database)
    assert restarted.task(task.task_id).state == "recovery_required"
    assert restarted.action(action.action_id).state == "in_doubt"
    assert restarted.recent_actions(task.task_id)[0].execution_started
    with pytest.raises(ValueError, match="cannot be claimed"):
        restarted.claim(action.action_id, fresh_observation=observation("d", "a"))
    assert restarted.cancel(task.task_id).state == "cancelled"


def test_crash_before_actor_boundary_records_no_execution_start(tmp_path):
    database = tmp_path / "private" / "agency.sqlite3"
    ledger = ComputerAgencyLedger(database)
    task = ledger.create("owner", "Open details")
    before = observation("a")
    ledger.record_observation(task.task_id, before)
    action = ledger.prepare(task.task_id, kind="activate_accessible", observation_id=before.observation_id,
                            target_digest=ledger.fingerprint(before, before.elements[0]), risk="low",
                            target_summary=("Test", "Open details"))
    ledger.claim(action.action_id, fresh_observation=observation("c", "a"))
    restarted = ComputerAgencyLedger(database)
    assert restarted.task(task.task_id).state == "recovery_required"
    assert restarted.action(action.action_id).state == "in_doubt"
    assert not restarted.recent_actions(task.task_id)[0].execution_started
    with pytest.raises(ValueError, match="execution cannot start"):
        restarted.mark_execution_started(action.action_id)
    assert restarted.resume_native_plan(task.task_id, step_count=1) == 0
    assert restarted.task(task.task_id).state == "active"
    assert restarted.action(action.action_id).state == "not_executed"
    assert restarted.task(task.task_id).action_count == 1
    with pytest.raises(ValueError, match="cannot be resumed"):
        restarted.resume_native_plan(task.task_id, step_count=1)


def test_stop_intent_blocks_actor_start_while_current_guard_is_held(tmp_path):
    database = tmp_path / "private" / "agency.sqlite3"
    ledger = ComputerAgencyLedger(database)
    task = ledger.create("owner", "Open editor")
    before = observation("a")
    ledger.record_observation(task.task_id, before)
    action = ledger.prepare(task.task_id, kind="launch_app", observation_id=before.observation_id,
                            target_digest="b" * 64, risk="low")
    with ThreadPoolExecutor(max_workers=1) as pool:
        with ledger.execution_guard():
            ledger.claim(action.action_id, fresh_observation=observation("c", "a"))
            future = pool.submit(ledger.cancel, task.task_id)
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                with sqlite3.connect(database) as db:
                    if db.execute("SELECT cancel_requested FROM computer_tasks WHERE task_id=?",
                                  (task.task_id,)).fetchone()[0]:
                        break
                time.sleep(0.01)
            else:
                pytest.fail("cancel intent was not persisted")
            with pytest.raises(ValueError, match="execution cannot start"):
                ledger.mark_execution_started(action.action_id)
            ledger.mark_in_doubt(action.action_id)
        assert future.result(timeout=2).state == "cancelled"
    assert not ledger.recent_actions(task.task_id)[0].execution_started


def test_restart_recovery_waits_for_live_physical_action_to_settle(tmp_path):
    database = tmp_path / "private" / "agency.sqlite3"
    ledger = ComputerAgencyLedger(database)
    task = ledger.create("owner", "Open editor")
    before = observation("a")
    ledger.record_observation(task.task_id, before)
    action = ledger.prepare(task.task_id, kind="launch_app", observation_id=before.observation_id,
                            target_digest="b" * 64, risk="low")
    with ThreadPoolExecutor(max_workers=1) as pool:
        with ledger.execution_guard():
            ledger.claim(action.action_id, fresh_observation=observation("c", "a"))
            future = pool.submit(ComputerAgencyLedger, database)
            with pytest.raises(FutureTimeout):
                future.result(timeout=0.1)
            ledger.finish(action.action_id, result_observation=observation("d"),
                          verified=True, outcome="postcondition_verified")
        restarted = future.result(timeout=2)
    assert restarted.task(task.task_id).state == "active"
    assert restarted.action(action.action_id).state == "verified"
    assert (tmp_path / "private" / "agency.sqlite3.action.lock").stat().st_mode & 0o777 == 0o600


def test_in_doubt_action_can_record_visible_result_without_replay_or_task_resume(tmp_path):
    database = tmp_path / "private" / "agency.sqlite3"
    ledger = ComputerAgencyLedger(database)
    task = ledger.create("owner", "Click Open and verify Details ready appears")
    frame = AccessibleElement((0,), "Test", "frame", "Fixture", (0, 0, 300, 200), (), True)
    initial = observation("a")
    before = DesktopObservation(initial.observation_id, initial.observed_at,
                                initial.digest, (frame, *initial.elements))
    ledger.record_observation(task.task_id, before)
    action = ledger.prepare(task.task_id, kind="activate_accessible",
                            observation_id=before.observation_id,
                            target_digest=ledger.fingerprint(before, before.elements[1]),
                            risk="low", expected_result=("Test", "*", "Details ready"),
                            target_summary=("Test", "Open"),
                            target_window=("Test", "frame", "Fixture"))
    claim_observation = observation("b", "a")
    ledger.claim(action.action_id, fresh_observation=DesktopObservation(
        claim_observation.observation_id, claim_observation.observed_at,
        claim_observation.digest, (frame, *claim_observation.elements)))
    ledger.mark_execution_started(action.action_id)
    restarted = ComputerAgencyLedger(database)
    assert restarted.action(action.action_id).state == "in_doubt"
    initial_status = restarted.recent_actions(task.task_id)[0]
    assert (initial_status.target_app, initial_status.target_name,
            initial_status.expected_name, initial_status.execution_started,
            initial_status.recovery_status, initial_status.target_window,
            initial_status.recovery_observation_id) == (
                "Test", "Open", "Details ready", True, None,
                ("Test", "frame", "Fixture"), None)
    assert not restarted.reconcile_visible_result(action.action_id, observation("c"))
    assert restarted.recent_actions(task.task_id)[0].recovery_status == "not_observed"
    other = AccessibleElement((1,), "Test", "frame", "Other window", (300, 0, 300, 200), (), False)
    spoof = AccessibleElement((1, 0), "Test", "label", "Details ready",
                              (310, 40, 90, 25), (), False)
    wrong_window = DesktopObservation("observation_" + "8" * 32,
                                      datetime.now(UTC).isoformat(), "8" * 64,
                                      (*before.elements, other, spoof))
    assert not restarted.reconcile_visible_result(action.action_id, wrong_window)
    assert restarted.recent_actions(task.task_id)[0].recovery_status == "not_observed"
    result = AccessibleElement((0, 1), "Test", "label", "Details ready", (10, 40, 90, 25),
                               (), True)
    duplicate = AccessibleElement((0, 2), "Test", "label", "Details ready", (10, 70, 90, 25),
                                  (), True)
    ambiguous = DesktopObservation("observation_" + "e" * 32, datetime.now(UTC).isoformat(),
                                   "e" * 64, (*before.elements, result, duplicate))
    assert not restarted.reconcile_visible_result(action.action_id, ambiguous)
    assert restarted.recent_actions(task.task_id)[0].recovery_status == "ambiguous"
    visible = DesktopObservation("observation_" + "d" * 32, datetime.now(UTC).isoformat(),
                                 "d" * 64, (*before.elements, result))
    assert restarted.reconcile_visible_result(action.action_id, visible)
    assert restarted.action(action.action_id).state == "result_present"
    assert restarted.recent_actions(task.task_id)[0].recovery_status == "result_present"
    assert restarted.recent_actions(task.task_id)[0].recovery_observation_id == visible.observation_id
    assert restarted.reconcile_visible_result(action.action_id, visible)
    assert restarted.task(task.task_id).state == "recovery_required"
    with pytest.raises(ValueError, match="fresh result evidence"):
        restarted.resume_native_plan(task.task_id, step_count=1)
    with pytest.raises(ValueError, match="no longer uniquely visible"):
        restarted.resume_native_plan(task.task_id, step_count=1,
                                     fresh_observation=observation("f"))
    fresh_visible = DesktopObservation("observation_" + "9" * 32, datetime.now(UTC).isoformat(),
                                       "9" * 64, (*before.elements, result))
    assert restarted.resume_native_plan(task.task_id, step_count=1,
                                        fresh_observation=fresh_visible) == 1
    assert restarted.task(task.task_id).action_count == 1
    assert restarted.complete(task.task_id, succeeded=True).state == "succeeded"


def test_exact_voice_stop_cancels_all_active_computer_tasks_without_replay(tmp_path):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "agency.sqlite3")
    first = ledger.create("owner", "Open browser")
    second = ledger.create("owner", "Fill safe field")
    done = ledger.create("owner", "Already done")
    ledger.complete(done.task_id, succeeded=True)
    assert set(ledger.cancel_active_tasks()) == {first.task_id, second.task_id}
    assert ledger.task(first.task_id).state == "cancelled"
    assert ledger.task(second.task_id).state == "cancelled"
    assert ledger.task(done.task_id).state == "succeeded"
    assert ledger.cancel_active_tasks() == ()


def test_task_failure_reason_is_a_bounded_durable_category(tmp_path):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    task = ledger.create("owner", "Inspect a local screen")

    failed = ledger.complete(task.task_id, succeeded=False,
                             failure_reason="planner_rejected")

    assert failed.state == "failed"
    assert failed.failure_reason == "planner_rejected"
    with pytest.raises(ValueError, match="failure reason is invalid"):
        ledger.complete(ledger.create("owner", "Another safe task").task_id,
                        succeeded=False, failure_reason="raw transcript and screen content")


def test_zero_action_task_can_wait_for_played_clarification_then_resume(tmp_path):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    task = ledger.create("owner", "Open the second folder")
    evidence = observation("a")
    ledger.record_observation(task.task_id, evidence)

    clarification = ledger.await_clarification(
        task.task_id, "Which visible folder should I use?",
        unresolved_referent="second:folder", observation_id=evidence.observation_id,
    )

    assert ledger.task(task.task_id).state == "awaiting_clarification"
    assert clarification.observation_id == evidence.observation_id
    assert ledger.pending_clarification("owner") is None
    assert ledger.record_clarification_delivery(task.task_id, played=True).delivery_state == "played"
    assert ledger.pending_clarification("owner").question == "Which visible folder should I use?"

    resumed = ledger.resume_clarification(task.task_id, "owner", "the third folder")

    assert (resumed.state, resumed.action_count, resumed.failure_reason) == ("active", 0, None)
    assert ledger.clarification(task.task_id).response == "the third folder"


def test_clarification_cannot_resume_until_playback_and_can_be_cancelled(tmp_path):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    task = ledger.create("owner", "Open the second folder")
    ledger.await_clarification(task.task_id, "Which folder?")

    with pytest.raises(ValueError, match="cannot be resumed"):
        ledger.resume_clarification(task.task_id, "owner", "the second folder")
    cancelled = ledger.cancel_clarification(task.task_id, "owner")

    assert cancelled.state == "cancelled"
    assert ledger.clarification(task.task_id).status == "cancelled"


def test_task_with_prepared_action_cannot_be_reclassified_as_clarification(tmp_path):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    task = ledger.create("owner", "Open a safe screen target")
    evidence = observation("a")
    ledger.record_observation(task.task_id, evidence)
    ledger.prepare(
        task.task_id, kind="click", observation_id=evidence.observation_id,
        target_digest=ledger.fingerprint(evidence, evidence.elements[0]), risk="low",
    )

    assert ledger.can_await_clarification(task.task_id) is False
    with pytest.raises(ValueError, match="cannot await clarification"):
        ledger.await_clarification(task.task_id, "Which target?")


def test_old_observation_and_expired_task_cannot_claim_desktop_action(tmp_path):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "agency.sqlite3")
    task = ledger.create("owner", "Open safe settings")
    old = observation("a")
    old = DesktopObservation(old.observation_id,
                             (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
                             old.digest, old.elements)
    ledger.record_observation(task.task_id, old)
    with pytest.raises(ValueError, match="too old"):
        ledger.prepare(task.task_id, kind="click", observation_id=old.observation_id,
                       target_digest=ledger.fingerprint(old, old.elements[0]), risk="low")
    with ledger._db() as db:
        db.execute("UPDATE computer_tasks SET created_at=? WHERE task_id=?", (
            (datetime.now(UTC) - timedelta(minutes=31)).isoformat(), task.task_id,
        ))
    with pytest.raises(ValueError, match="not active"):
        ledger.record_observation(task.task_id, observation("b"))


def test_in_doubt_vscode_terminal_shortcut_reconciles_focused_input_without_replay(tmp_path):
    database = tmp_path / "private" / "agency.sqlite3"
    ledger = ComputerAgencyLedger(database)
    task = ledger.create("owner", "Open a terminal in VS Code")
    frame = AccessibleElement(
        (0,), "code", "frame", "Local-AI-Assistant - Visual Studio Code",
        (0, 0, 1000, 700), (), True,
    )
    before = DesktopObservation(
        "observation_" + "a" * 32, datetime.now(UTC).isoformat(), "a" * 64, (frame,),
    )
    ledger.record_observation(task.task_id, before)
    action = ledger.prepare(
        task.task_id, kind="hotkey", observation_id=before.observation_id,
        target_digest=ledger.fingerprint(before, frame), risk="low",
        expected_result=("code", "__vscode_terminal_input__", "focused"),
        target_summary=("code", "workspace"),
        target_window=("code", "frame", frame.name),
    )
    claim_observation = DesktopObservation(
        "observation_" + "c" * 32, datetime.now(UTC).isoformat(), "c" * 64, (frame,),
    )
    ledger.claim(action.action_id, fresh_observation=claim_observation)
    ledger.mark_execution_started(action.action_id)
    restarted = ComputerAgencyLedger(database)
    assert restarted.action(action.action_id).state == "in_doubt"

    terminal = AccessibleElement(
        (0, 3, 0, 1), "code", "entry", "Terminal 3, bash",
        (0, 400, 1000, 300), (), True, focused=True,
    )
    visible = DesktopObservation(
        "observation_" + "b" * 32, datetime.now(UTC).isoformat(), "b" * 64,
        (frame, terminal),
    )

    assert restarted.reconcile_visible_result(action.action_id, visible)
    assert restarted.action(action.action_id).state == "result_present"
    assert restarted.task(task.task_id).state == "recovery_required"
    assert restarted.task(task.task_id).action_count == 1


def test_active_task_query_returns_only_live_or_recovery_tasks(tmp_path):
    ledger = ComputerAgencyLedger(tmp_path / "active-tasks.sqlite3")
    first = ledger.create("local-owner", "Open Calculator")
    second = ledger.create("local-owner", "Open Files")

    assert ledger.active_task_ids() == tuple(sorted((first.task_id, second.task_id)))
    ledger.complete(first.task_id, succeeded=True)
    assert ledger.active_task_ids() == (second.task_id,)
