import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from local_ai_assistant.career_forge import CareerForgeService, PracticeLabService
from local_ai_assistant.career_forge.models import AttemptEvaluation, MasteryLevel, TutorMode


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


def test_concurrent_practice_open_reuses_one_canonical_draft(lab):
    _, mission, service = lab
    with ThreadPoolExecutor(max_workers=8) as pool:
        opened = list(pool.map(lambda _: service.open(mission.mission_id), range(16)))
    assert len({item.draft_code for item in opened}) == 1
    with service._db() as db:
        assert db.execute(
            "SELECT count(*) FROM practice_lab_drafts WHERE mission_id=?", (mission.mission_id,)
        ).fetchone()[0] == 1


def test_friday_code_question_selects_exact_region_and_survives_restart(lab):
    forge, mission, service = lab
    fixed = fixed_code(service.open(mission.mission_id).draft_code)
    service.save_draft(mission.mission_id, fixed)

    question = service.ask_about_code(mission.mission_id)

    assert question.question_id.startswith("code_attention:")
    assert question.start_line == 1
    assert "def append_item" in question.selected_code
    assert "if __name__" not in question.selected_code
    assert len(question.source_hash) == 64
    restored = PracticeLabService(
        CareerForgeService(forge.path), service.workspace_root,
    ).current_code_question(mission.mission_id)
    assert restored == question


def test_code_question_rejects_changed_or_missing_source(lab):
    forge, mission, service = lab
    original = service.open(mission.mission_id).draft_code
    service.ask_about_code(mission.mission_id)
    service.save_draft(mission.mission_id, fixed_code(original))
    with pytest.raises(ValueError, match="source changed"):
        service.current_code_question(mission.mission_id)
    service.save_draft(mission.mission_id, original)
    with service._db() as db:
        db.execute("DELETE FROM practice_lab_drafts WHERE mission_id=?", (mission.mission_id,))
    with pytest.raises(ValueError, match="source changed"):
        service.current_code_question(mission.mission_id)
    assert forge.evidence_history() == ()


def test_code_question_reconciles_pending_answer_after_source_changes(lab):
    forge, mission, service = lab
    original = service.open(mission.mission_id).draft_code
    question = service.ask_about_code(mission.mission_id)
    pending = forge.record_attempt(
        mission.mission_id, question.question_id, "The default list is reused.", mode=TutorMode.CHALLENGE,
    )
    assert service.ask_about_code(mission.mission_id) == question
    service.save_draft(mission.mission_id, fixed_code(original))
    replacement = service.ask_about_code(mission.mission_id)
    assert replacement.question_id != question.question_id
    assert forge.attempt(pending.attempt_id).evaluation is AttemptEvaluation.UNCERTAIN
    assert forge.evidence_history() == ()


def test_physical_file_question_binds_exact_source_and_rejects_stale_file(lab, tmp_path):
    forge, mission, service = lab
    root = tmp_path / "project"
    root.mkdir()
    source = root / "defaults.py"
    source.write_text("def append_item(item, bucket=[]):\n    bucket.append(item)\n    return bucket\n")
    reader = PracticeLabService(forge, service.workspace_root, source_roots=(root,))
    question = reader.ask_about_file(mission.mission_id, str(source), 1, 3, symbol="append_item")
    assert question.source_kind == "local_file"
    assert question.source_path == str(source.resolve())
    assert question.selected_hash and question.source_version
    assert PracticeLabService(forge, service.workspace_root, source_roots=(root,)).current_code_question(mission.mission_id) == question
    source.write_text("def append_item(item, bucket=None):\n    return [item]\n")
    with pytest.raises(ValueError, match="source changed"):
        reader.current_code_question(mission.mission_id)
    assert forge.evidence_history() == ()


def test_physical_file_question_negative_source_controls(lab, tmp_path):
    forge, mission, service = lab
    root = tmp_path / "project"
    root.mkdir()
    source = root / "defaults.py"
    source.write_text("def append_item(item, bucket=[]):\n    return bucket\n")
    reader = PracticeLabService(forge, service.workspace_root, source_roots=(root,))
    (tmp_path / "other.py").write_text(source.read_text())
    with pytest.raises(ValueError, match="outside allowed"):
        reader.ask_about_file(mission.mission_id, str(tmp_path / "other.py"), 1, 1)
    with pytest.raises(ValueError, match="range"):
        reader.ask_about_file(mission.mission_id, str(source), 1, 8)
    with pytest.raises(ValueError, match="symbol"):
        reader.ask_about_file(mission.mission_id, str(source), 1, 1, symbol="not_here")
    question = reader.ask_about_file(mission.mission_id, str(source), 1, 2)
    source.unlink()
    with pytest.raises(ValueError, match="missing"):
        reader.current_code_question(mission.mission_id)
    twin = root / "same.py"
    twin.write_text(question.selected_code + "\n")
    replacement = reader.ask_about_file(mission.mission_id, str(twin), 1, 2)
    assert replacement.source_hash == question.source_hash
    assert replacement.source_path != question.source_path


def test_physical_file_question_rejects_version_and_selection_digest_drift(lab, tmp_path):
    forge, mission, service = lab
    root = tmp_path / "project"
    root.mkdir()
    source = root / "defaults.py"
    source.write_text("def append_item(item, bucket=[]):\n    return bucket\n")
    reader = PracticeLabService(forge, service.workspace_root, source_roots=(root,))
    question = reader.ask_about_file(mission.mission_id, str(source), 1, 2)
    before = source.stat()
    os.utime(source, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000))
    with pytest.raises(ValueError, match="source changed"):
        reader.current_code_question(mission.mission_id)
    fresh = reader.ask_about_file(mission.mission_id, str(source), 1, 2)
    resume = forge.mission(mission.mission_id).resume_point
    resume["code_attention"]["selected_hash"] = "0" * 64
    forge.update_resume(mission.mission_id, resume)
    with pytest.raises(ValueError, match="range or symbol"):
        reader.current_code_question(mission.mission_id)
    assert fresh.question_id != question.question_id
    assert forge.evidence_history() == ()


def test_physical_file_question_requires_supported_competency_contract(lab, tmp_path, monkeypatch):
    forge, mission, service = lab
    root = tmp_path / "project"
    root.mkdir()
    source = root / "defaults.py"
    source.write_text("def append_item(item, bucket=[]):\n    return bucket\n")
    reader = PracticeLabService(forge, service.workspace_root, source_roots=(root,))

    def unsupported(_competency_id):
        raise KeyError("no supported competency contract")

    monkeypatch.setattr(forge, "mission_brief_for", unsupported)
    with pytest.raises(KeyError, match="supported competency contract"):
        reader.ask_about_file(mission.mission_id, str(source), 1, 2)
    assert "code_attention" not in forge.mission(mission.mission_id).resume_point
    assert forge.evidence_history() == ()


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
