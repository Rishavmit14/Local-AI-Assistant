from __future__ import annotations

import os

import pytest

from scripts.qualification import offline_candidate_runtime as candidate


def test_wake_enabled_candidate_refuses_active_production(monkeypatch):
    monkeypatch.setattr(candidate, "_friday_service_state", lambda: "active")
    monkeypatch.setattr(candidate, "_voice_processes", lambda: [])

    with pytest.raises(RuntimeError, match="production Friday is active"):
        candidate.assert_single_voice_stack()


def test_wake_enabled_candidate_refuses_orphan_voice_workers(monkeypatch):
    monkeypatch.setattr(candidate, "_friday_service_state", lambda: "inactive")
    monkeypatch.setattr(
        candidate,
        "_voice_processes",
        lambda: ["Parakeet worker (PID 1234)"],
    )

    with pytest.raises(RuntimeError, match="Parakeet worker"):
        candidate.assert_single_voice_stack()


def test_wake_enabled_candidate_accepts_one_owned_stack(monkeypatch):
    monkeypatch.setattr(candidate, "_friday_service_state", lambda: "inactive")
    monkeypatch.setattr(candidate, "_voice_processes", lambda: [])

    assert candidate.assert_single_voice_stack() is None


def test_candidate_environment_keeps_wake_disabled_by_default(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCAL_AI_WAKE_ENABLED", "true")

    candidate._candidate_environment(tmp_path / "state", "local-qwen", 18080)

    assert os.environ["LOCAL_AI_WAKE_ENABLED"] == "false"


def test_candidate_environment_enables_wake_only_when_requested(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCAL_AI_WAKE_ENABLED", "false")

    candidate._candidate_environment(
        tmp_path / "state",
        "local-qwen",
        18080,
        wake_enabled=True,
    )

    assert os.environ["LOCAL_AI_WAKE_ENABLED"] == "true"
