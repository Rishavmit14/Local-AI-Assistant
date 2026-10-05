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
