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


def test_objective_binds_only_a_validated_plan_hash_without_execution(tmp_path):
    service = ObjectiveService(tmp_path / "objectives.sqlite3")
    objective = service.create("Plan only")
    planned = service.bind_plan(objective.objective_id, "a" * 64)
    assert planned.state == "planned"
    assert planned.plan_hash == "a" * 64
    with pytest.raises(ValueError, match="validated"):
        service.bind_plan(objective.objective_id, "not-a-plan")
