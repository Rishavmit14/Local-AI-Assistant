from __future__ import annotations

import json

import pytest

from local_ai_assistant.gateway.github import GitHubHttpTransport


class _Response:
    def __init__(self, body): self.body = body
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, _limit=-1): return self.body


@pytest.mark.parametrize("failure", [TimeoutError(), OSError("connect"), ValueError("bad json")])
def test_production_transport_failure_paths_are_bounded(monkeypatch, failure):
    def fail(*_args, **_kwargs):
        raise failure
    monkeypatch.setattr("local_ai_assistant.gateway.github.urlopen", fail)
    client = GitHubHttpTransport("github_pat_STAGE9_SECRET_XYZ321", timeout=0.01)
    with pytest.raises((RuntimeError, TimeoutError, OSError, ValueError)):
        client.get_issue("acme", "demo", 1)


def test_production_transport_malformed_and_oversized_response(monkeypatch):
    monkeypatch.setattr("local_ai_assistant.gateway.github.urlopen", lambda *_a, **_k: _Response(b"not-json"))
    with pytest.raises((RuntimeError, ValueError, json.JSONDecodeError)):
        GitHubHttpTransport("token").get_issue("acme", "demo", 1)
    monkeypatch.setattr("local_ai_assistant.gateway.github.urlopen", lambda *_a, **_k: _Response(b"x" * (2 * 1024 * 1024 + 1)))
    with pytest.raises(ValueError):
        GitHubHttpTransport("token").get_issue("acme", "demo", 1)
