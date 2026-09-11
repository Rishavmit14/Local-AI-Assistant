import pytest

from local_ai_assistant.autonomy import ObjectiveService


def test_objective_lifecycle_is_local_bounded_and_cancellable(tmp_path):
    service = ObjectiveService(tmp_path / "objectives.sqlite3")
    objective = service.create("Inspect and validate a repository")
    assert service.resume(objective.objective_id).state == "planning"
    assert service.cancel(objective.objective_id).state == "cancelled"
    with pytest.raises(ValueError, match="cannot resume"):
        service.resume(objective.objective_id)


def test_objective_requires_bounded_text(tmp_path):
    service = ObjectiveService(tmp_path / "objectives.sqlite3")
    with pytest.raises(ValueError, match="between"):
        service.create(" ")


def test_objective_recent_is_bounded_and_newest_first(tmp_path):
    service = ObjectiveService(tmp_path / "objectives.sqlite3")
    first = service.create("First")
    second = service.create("Second")
    assert [item.objective_id for item in service.recent()] == [second.objective_id, first.objective_id]
    assert service.recent(1) == (second,)
    with pytest.raises(ValueError, match="limit"):
        service.recent(0)


def test_objective_binds_only_a_canonical_task_plan_without_execution(tmp_path):
    task_id = "task_" + "a" * 20
    service = ObjectiveService(
        tmp_path / "objectives.sqlite3",
        plan_hash_for_task=lambda value: "b" * 64 if value == task_id else None,
    )
    objective = service.create("Plan only")
    planned = service.bind_plan(objective.objective_id, task_id)
    assert planned.state == "planned"
    assert planned.plan_hash == "b" * 64
    assert planned.task_id == task_id
    with pytest.raises(ValueError, match="canonical planned"):
        service.bind_plan(objective.objective_id, "not-a-task")


def test_objective_requests_and_retries_only_one_canonical_planning_task(tmp_path):
    task_id = "task_" + "a" * 20
    created: list[tuple[str, str]] = []
    requested: list[str] = []
    ready = False

    def create_task(text: str, repository_id: str) -> str:
        created.append((text, repository_id))
        return task_id

    def request_plan(value: str) -> None:
        nonlocal ready
        requested.append(value)
        if len(requested) == 1:
            raise RuntimeError("local planner unavailable")
        ready = True

    service = ObjectiveService(
        tmp_path / "objectives.sqlite3",
        plan_hash_for_task=lambda value: "b" * 64 if ready and value == task_id else None,
        create_task_for_objective=create_task,
        request_plan_for_task=request_plan,
    )
    objective = service.resume(service.create("Plan only").objective_id)
    with pytest.raises(RuntimeError, match="unavailable"):
        service.request_plan(objective.objective_id, "r1")
    assert service.get(objective.objective_id).task_id == task_id
    planned = service.request_plan(objective.objective_id, "ignored-on-retry")
    assert planned.state == "planned"
    assert created == [("Plan only", "r1")]
    assert requested == [task_id, task_id]


def test_objective_projects_linked_task_state_without_mutating_it(tmp_path):
    task_id = "task_" + "a" * 20
    states = {task_id: "awaiting_approval"}
    service = ObjectiveService(
        tmp_path / "objectives.sqlite3",
        plan_hash_for_task=lambda value: "b" * 64 if value == task_id else None,
        task_state_for_task=states.get,
    )
    objective = service.create("Plan only")
    service.bind_plan(objective.objective_id, task_id)

    assert service.get(objective.objective_id).task_state == "awaiting_approval"
    states[task_id] = "validating"
    assert service.get(objective.objective_id).task_state == "validating"


def test_objective_review_requires_the_exact_bound_canonical_plan(tmp_path):
    task_id = "task_" + "a" * 20
    service = ObjectiveService(
        tmp_path / "objectives.sqlite3",
        plan_hash_for_task=lambda value: "b" * 64 if value == task_id else None,
        plan_review_for_task=lambda value, token: {"task_id": value, "plan_hash": token},
    )
    objective = service.bind_plan(service.create("Plan only").objective_id, task_id)
    assert service.plan_review(objective.objective_id) == {"task_id": task_id, "plan_hash": "b" * 64}


def test_objective_refuses_unready_or_replaced_canonical_plan(tmp_path):
    task_id = "task_" + "a" * 20
    other_task_id = "task_" + "b" * 20
    service = ObjectiveService(
        tmp_path / "objectives.sqlite3",
        plan_hash_for_task=lambda value: {task_id: "c" * 64, other_task_id: "d" * 64}.get(value),
    )
    objective = service.create("Plan only")
    with pytest.raises(ValueError, match="no canonical plan"):
        service.bind_plan(objective.objective_id, "task_" + "e" * 20)
    service.bind_plan(objective.objective_id, task_id)
    with pytest.raises(ValueError, match="different canonical plan"):
        service.bind_plan(objective.objective_id, other_task_id)


def test_cancelling_a_bound_objective_cancels_its_canonical_task_first(tmp_path):
    task_id = "task_" + "a" * 20
    cancelled = []
    service = ObjectiveService(
        tmp_path / "objectives.sqlite3",
        plan_hash_for_task=lambda value: "b" * 64 if value == task_id else None,
        cancel_task=cancelled.append,
    )
    objective = service.create("Plan only")
    service.bind_plan(objective.objective_id, task_id)

    assert service.cancel(objective.objective_id).state == "cancelled"
    assert cancelled == [task_id]


def test_failed_canonical_task_cancellation_keeps_objective_nonterminal(tmp_path):
    task_id = "task_" + "a" * 20

    def fail_cancel(_task_id: str) -> None:
        raise ValueError("task cannot cancel")

    service = ObjectiveService(
        tmp_path / "objectives.sqlite3",
        plan_hash_for_task=lambda value: "b" * 64 if value == task_id else None,
        cancel_task=fail_cancel,
    )
    objective = service.create("Plan only")
    service.bind_plan(objective.objective_id, task_id)

    with pytest.raises(ValueError, match="cannot cancel"):
        service.cancel(objective.objective_id)
    assert service.get(objective.objective_id).state == "planned"


@pytest.mark.parametrize("operation", ["resume", "bind_plan"])
def test_late_objective_transition_cannot_revive_cancellation(tmp_path, monkeypatch, operation):
    database = tmp_path / "objectives.sqlite3"
    service = ObjectiveService(database, plan_hash_for_task=lambda _task: "b" * 64)
    competitor = ObjectiveService(database)
    objective = service.create("Cancel before the late write")
    original_get = service.get

    def stale_read(objective_id):
        item = original_get(objective_id)
        monkeypatch.setattr(service, "get", original_get)
        competitor.cancel(objective_id)
        return item

    monkeypatch.setattr(service, "get", stale_read)
    with pytest.raises(ValueError, match="cancelled"):
        if operation == "resume":
            service.resume(objective.objective_id)
        else:
            service.bind_plan(objective.objective_id, "task_" + "a" * 20)
    assert competitor.get(objective.objective_id).state == "cancelled"
    assert competitor.get(objective.objective_id).task_id is None


def test_late_binding_cannot_replace_a_concurrently_bound_plan(tmp_path, monkeypatch):
    database = tmp_path / "objectives.sqlite3"
    service = ObjectiveService(database, plan_hash_for_task=lambda _task: "b" * 64)
    competitor = ObjectiveService(database, plan_hash_for_task=lambda _task: "c" * 64)
    objective = service.create("Bind only one canonical plan")
    original_get = service.get
    winning_task = "task_" + "d" * 20

    def stale_read(objective_id):
        item = original_get(objective_id)
        monkeypatch.setattr(service, "get", original_get)
        competitor.bind_plan(objective_id, winning_task)
        return item

    monkeypatch.setattr(service, "get", stale_read)
    with pytest.raises(ValueError, match="changed concurrently"):
        service.bind_plan(objective.objective_id, "task_" + "a" * 20)
    assert competitor.get(objective.objective_id).task_id == winning_task
    assert competitor.get(objective.objective_id).plan_hash == "c" * 64
