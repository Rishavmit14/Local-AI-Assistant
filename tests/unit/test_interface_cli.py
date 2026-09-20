from __future__ import annotations

import signal
from types import SimpleNamespace

import uvicorn

from local_ai_assistant.interface.cli import FridayUvicornServer, _repository_mappings


async def _app(scope, receive, send):
    del scope, receive, send


def test_first_server_exit_signal_closes_voice_before_http_exit():
    observed = []
    server = FridayUvicornServer(
        uvicorn.Config(_app),
        before_exit=lambda: observed.append(server.should_exit),
    )

    server.handle_exit(signal.SIGTERM, None)

    assert observed == [False]
    assert server.should_exit

    server.handle_exit(signal.SIGINT, None)
    assert observed == [False]
    assert server.force_exit


def test_voice_close_failure_still_stops_http_server():
    def fail():
        raise RuntimeError("voice close failed")

    server = FridayUvicornServer(uvicorn.Config(_app), before_exit=fail)

    try:
        server.handle_exit(signal.SIGTERM, None)
    except RuntimeError as exc:
        assert str(exc) == "voice close failed"
    else:
        raise AssertionError("voice close failure was not surfaced")

    assert server.should_exit


def test_repository_mappings_require_explicit_onboarded_github_identity(tmp_path):
    mapped = tmp_path / "mapped"
    local_only = tmp_path / "local-only"
    (mapped / ".git").mkdir(parents=True)
    (local_only / ".git").mkdir(parents=True)
    profiles = (
        SimpleNamespace(
            canonical_root=str(mapped), repository_id="fraud-shield",
            publication_mapping="acme/fraud-shield",
        ),
    )

    mappings = _repository_mappings(tmp_path, profiles)

    assert {(item.repository_id, item.github_owner, item.github_name) for item in mappings} == {
        ("fraud-shield", "acme", "fraud-shield"),
        ("local-only", "", ""),
    }
