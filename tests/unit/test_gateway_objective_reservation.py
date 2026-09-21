from __future__ import annotations

import subprocess

from local_ai_assistant.gateway.models import RepositoryMapping
from local_ai_assistant.gateway.service import IntegrationGatewayService
from local_ai_assistant.history.service import TaskHistoryService
from local_ai_assistant.history.store import TaskHistoryStore


def test_objective_reservation_uses_publication_eligible_isolated_branch(tmp_path):
    repository = tmp_path / "project"
    repository.mkdir()
    subprocess.run(("git", "init", "-q", str(repository)), check=True)
    (repository / "README.md").write_text("fixture\n")
    subprocess.run(("git", "-C", str(repository), "add", "README.md"), check=True)
    subprocess.run(
        ("git", "-C", str(repository), "-c", "user.name=Friday", "-c",
         "user.email=friday@example.invalid", "commit", "-qm", "initial"),
        check=True,
    )
    history = TaskHistoryService(TaskHistoryStore(tmp_path / "history.sqlite3"))
    gateway = IntegrationGatewayService(
        history,
        (RepositoryMapping("project", str(repository), "owner", "project"),),
    )
    task_id = "task_" + "a" * 20
    try:
        task = gateway.reserve_objective_task("project", "Build the artifact", task_id)
        recovered = gateway.reserve_objective_task("project", "Build the artifact", task_id)
    finally:
        gateway.close()

    assert task.task_id == recovered.task_id == task_id
    assert task.branch == recovered.branch == f"friday/task/{task_id}"
