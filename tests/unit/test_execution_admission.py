from concurrent.futures import Future, ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace

import pytest

from local_ai_assistant.gateway.execution_service import CodeAgentExecutionService
from local_ai_assistant.history.models import TaskStatus


def execution_fixture(tmp_path):
    task = SimpleNamespace(
        task_id="task_" + "a" * 20, status=TaskStatus.APPROVED,
        plan_hash="b" * 64, repository=str(tmp_path), starting_commit="c" * 40,
        original_request="Bounded fixture",
    )
    profile = SimpleNamespace(canonical_root=str(tmp_path), repository_id="fixture")
    onboarding = SimpleNamespace(
        list_profiles=lambda: [profile], assert_ready_for_mutation=lambda *args, **kwargs: None,
    )
    return CodeAgentExecutionService(None, None, onboarding), task


def test_simultaneous_dispatch_submits_only_one_worker(tmp_path):
    execution, task = execution_fixture(tmp_path)
    entered, release, duplicate = Event(), Event(), Event()
    submissions = []

    def submit(*_args):
        submissions.append(Future())
        if len(submissions) > 1:
            duplicate.set()
        entered.set()
        assert release.wait(3)
        return submissions[-1]

    execution._pool.shutdown()
    execution._pool = SimpleNamespace(submit=submit, shutdown=lambda **_kwargs: None)
    with ThreadPoolExecutor(max_workers=2) as callers:
        first = callers.submit(execution.execute_task, task)
        assert entered.wait(3)
        second = callers.submit(execution.execute_task, task)
        try:
            assert not duplicate.wait(0.2)
        finally:
            release.set()
        assert first.result(timeout=3) == second.result(timeout=3)
    assert len(submissions) == 1
    execution.close()


def test_cancelled_queued_future_reports_cancelled(tmp_path):
    execution, task = execution_fixture(tmp_path)
    pending = Future()
    execution._runs[f"run_{task.task_id}"] = pending
    pending.cancel()
    try:
        assert execution.get_status(task.task_id)["status"] == "cancelled"
    finally:
        execution.close()


def test_closed_executor_refuses_new_dispatch(tmp_path):
    execution, task = execution_fixture(tmp_path)
    execution.close()
    with pytest.raises(RuntimeError, match="closed"):
        execution.execute_task(task)


def test_shutdown_cancels_queued_work_but_keeps_running_handle(tmp_path, monkeypatch):
    execution, task = execution_fixture(tmp_path)
    entered, release = Event(), Event()

    def run(_argv):
        entered.set()
        assert release.wait(5)

    monkeypatch.setattr("local_ai_assistant.gateway.execution_service.code_agent.main", run)
    first = execution.execute_task(task)
    try:
        assert entered.wait(3)
        queued = SimpleNamespace(**{**vars(task), "task_id": "task_" + "d" * 20})
        execution.execute_task(queued)
        execution.close()
        assert execution.get_status(queued.task_id)["status"] == "cancelled"
        assert execution.get_status(task.task_id)["status"] == "running"
    finally:
        release.set()
        execution._runs[first.run_id].result(timeout=3)
        execution.close()
