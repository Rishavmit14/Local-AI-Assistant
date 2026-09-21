from pathlib import Path

import pytest

from local_ai_assistant.career_forge import CareerForgeService, PracticeLabService
from local_ai_assistant.career_forge.models import MasteryLevel


@pytest.fixture
def lab(tmp_path: Path):
    forge = CareerForgeService(tmp_path / "learner.sqlite3")
    brief = forge.next_mission_brief()
    assert brief is not None
    mission = forge.start_mission(brief.competency_id, brief.title)
    return forge, mission, PracticeLabService(forge, tmp_path / "lab")


def fixed_code(code: str) -> str:
    return code.replace("bucket=[]", "bucket=None").replace(
        "    bucket.append(item)", "    if bucket is None:\n        bucket = []\n    bucket.append(item)"
    )


def test_run_test_submit_and_evidence_boundary(lab):
    forge, mission, service = lab
    opened = service.open(mission.mission_id)
    run = service.run(mission.mission_id)
    assert run.kind == "run" and run.passed is None
    failed = service.test(mission.mission_id)
    assert failed.passed is False and failed.stderr
    submitted = service.submit(mission.mission_id)
    assert submitted.attempt.retry_needed is True
    assert submitted.attempt.evidence_type is None
    assert forge.competencies()[0].mastery is MasteryLevel.UNVERIFIED
    service.save_draft(mission.mission_id, fixed_code(opened.draft_code))
    passed = service.test(mission.mission_id)
    assert passed.passed is True
    with service._db() as db:
        run_count = db.execute(
            "SELECT count(*) FROM practice_lab_runs WHERE mission_id=?",
            (mission.mission_id,),
        ).fetchone()[0]
    submitted = service.submit(mission.mission_id)
    assert submitted.attempt.evidence_type == "practice_lab_bounded_test"
    with service._db() as db:
        assert db.execute(
            "SELECT count(*) FROM practice_lab_runs WHERE mission_id=?",
            (mission.mission_id,),
        ).fetchone()[0] == run_count
    assert forge.competencies()[0].mastery is MasteryLevel.UNVERIFIED


def test_draft_resume_and_attempt_diff(lab):
    forge, mission, service = lab
    draft = fixed_code(service.open(mission.mission_id).draft_code)
    service.save_draft(mission.mission_id, draft)
    service.submit(mission.mission_id)
    resumed = PracticeLabService(forge, service.workspace_root).open(mission.mission_id)
    assert resumed.draft_code == draft
    assert len(resumed.attempts) == 1
    assert "bucket=None" in resumed.attempts[0].diff


def test_friday_code_question_selects_exact_region_and_survives_restart(lab):
    forge, mission, service = lab
    fixed = fixed_code(service.open(mission.mission_id).draft_code)
    service.save_draft(mission.mission_id, fixed)

    question = service.ask_about_code(mission.mission_id)

    assert question.question_id.startswith("code_attention:")
    assert question.start_line == 1
    assert "def append_item" in question.selected_code
    assert "if __name__" not in question.selected_code
    restored = PracticeLabService(
        CareerForgeService(forge.path), service.workspace_root,
    ).current_code_question(mission.mission_id)
    assert restored == question


def test_untrusted_code_cannot_read_host_etc(lab):
    _, mission, service = lab
    hostile = "print(open('/etc/passwd').read())"
    result = service.run(mission.mission_id, hostile)
    assert result.return_code != 0
    assert "root:" not in result.stdout


def test_runaway_code_is_bounded(lab):
    _, mission, service = lab
    result = service.run(mission.mission_id, "while True: pass")
    assert result.timed_out is True
    assert "resource limit" in result.stderr


def test_code_is_bounded(lab):
    _, mission, service = lab
    with pytest.raises(ValueError, match="learner code"):
        service.save_draft(mission.mission_id, "x" * 32_001)


def test_career_forge_sqlite_connections_close_after_short_operations(lab):
    forge, mission, service = lab
    service.open(mission.mission_id)
    for _ in range(20):
        forge.progress()
        service.projection(mission.mission_id)
    with forge._db() as connection:
        connection.execute("SELECT 1")
    with pytest.raises(Exception):
        connection.execute("SELECT 1")
