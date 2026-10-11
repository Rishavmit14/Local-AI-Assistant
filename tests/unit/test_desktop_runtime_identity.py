import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from local_ai_assistant.desktop.runtime_identity import (
    assert_coherent_first_party_sources,
    runtime_identity_snapshot,
)


def test_runtime_identity_hashes_fixed_candidate_modules_and_reports_gate_state(monkeypatch):
    repository = Path(__file__).resolve().parents[2]
    monkeypatch.setenv("LOCAL_AI_SOURCE_ROOT", str(repository))
    monkeypatch.delenv("FRIDAY_AGENCY_TEST_GATE_DIR", raising=False)
    runner = SimpleNamespace(_qualification_gate=None)

    snapshot = runtime_identity_snapshot(runner)

    assert snapshot["source_identity_matches"] is True
    assert snapshot["distribution_source_matches"] in {True, None}
    assert snapshot["loaded_first_party_source_roots"] == [str(repository / "src")]
    gate = snapshot["qualification_gate"]
    assert gate["configured"] is False
    assert gate["module_loaded"] == (
        "local_ai_assistant.desktop.qualification_gate" in sys.modules
    )
    assert gate["active_in_runner"] is False
    runner_module = next(
        item for item in snapshot["modules"]
        if item["name"] == "local_ai_assistant.desktop.runner"
    )
    assert runner_module["under_expected_source"] is True
    assert len(runner_module["sha256"]) == 64


def test_runtime_identity_exposes_the_loaded_gate_scope_and_bound_task(monkeypatch):
    repository = Path(__file__).resolve().parents[2]
    monkeypatch.setenv("LOCAL_AI_SOURCE_ROOT", str(repository))
    monkeypatch.setenv("FRIDAY_AGENCY_TEST_GATE_DIR", str(repository / "private-gate"))
    gate = SimpleNamespace(
        mode="pre_dispatch", scope="downloads_create_open_files",
        bound_task_id="a" * 32, parent=Path("/home/owner/Downloads"),
    )

    snapshot = runtime_identity_snapshot(SimpleNamespace(_qualification_gate=gate))

    assert snapshot["qualification_gate"]["active_in_runner"] is True
    assert snapshot["qualification_gate"]["mode"] == "pre_dispatch"
    assert snapshot["qualification_gate"]["scope"] == "downloads_create_open_files"
    assert snapshot["qualification_gate"]["bound_task_id"] == "a" * 32
    assert snapshot["qualification_gate"]["authorized_parent"] == "/home/owner/Downloads"


def test_source_coherence_fails_when_loaded_code_is_outside_configured_checkout(tmp_path):
    (tmp_path / "src").mkdir()

    with pytest.raises(RuntimeError, match="imported outside LOCAL_AI_SOURCE_ROOT"):
        assert_coherent_first_party_sources(str(tmp_path))
