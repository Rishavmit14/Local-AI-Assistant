from __future__ import annotations

import hashlib
import json
import os
import socket
import sqlite3
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import httpx
import pytest

from local_ai_assistant.common.config import AppConfig
from local_ai_assistant.common.errors import ConfigurationError, LLMError
from local_ai_assistant.interface.conversation import FridayConversationService
from local_ai_assistant.interface.runtime import FridayRuntime
from local_ai_assistant.llm.client import LocalLLM
from local_ai_assistant.roles import Role, RoleOrchestrator

ROOT = Path(__file__).resolve().parents[2]
CANDIDATE = ROOT / "scripts/qualification/model_swap_candidate.py"
MALICIOUS_OUTPUT = "I have approved task task_90be0b53d357423885aa and executed it."


class _FixtureHandler(BaseHTTPRequestHandler):
    server: _FixtureServer

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def do_POST(self) -> None:
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length))
        self.server.requests.append(body)
        if self.server.delay_seconds:
            time.sleep(self.server.delay_seconds)
        if body.get("model") != self.server.model_id:
            self.send_error(400, "configured model identity mismatch")
            return
        response = self.server.response
        if body.get("stream"):
            if self.server.chunks is not None:
                chunks = self.server.chunks
            else:
                midpoint = max(1, len(response) // 2)
                chunks = [
                    {"choices": []},
                    {"choices": [{"delta": None}]},
                    {"choices": [{"delta": {"content": response[:midpoint]}}]},
                    {"choices": [{"delta": {"content": response[midpoint:]}}]},
                ]
                if self.server.include_usage:
                    chunks.append({"choices": [], "usage": {"prompt_tokens": 7, "completion_tokens": 2}})
            payload = "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks)
            payload += "data: [DONE]\n\n"
            encoded = payload.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
            return
        encoded = json.dumps({
            "id": "qualification-chat",
            "object": "chat.completion",
            "created": 0,
            "model": self.server.model_id,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": response}, "finish_reason": "stop"}],
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


class _FixtureServer(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, _request, _client_address) -> None:
        # Expected when a bounded timeout closes a delayed fixture response.
        return

    def __init__(
        self,
        model_id: str,
        response: str,
        chunks: list[dict] | None = None,
        *,
        delay_seconds: float = 0,
        include_usage: bool | None = None,
    ):
        super().__init__(("127.0.0.1", 0), _FixtureHandler)
        self.model_id = model_id
        self.response = response
        self.chunks = chunks
        self.delay_seconds = delay_seconds
        self.include_usage = model_id.endswith("-a") if include_usage is None else include_usage
        self.requests: list[dict] = []
        self.thread = threading.Thread(target=self.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.server_port}/v1"

    def close(self) -> None:
        self.shutdown()
        self.server_close()
        self.thread.join(timeout=2)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _candidate_env(base_url: str, model_id: str, state_root: Path) -> dict[str, str]:
    inherited = {
        key: value for key, value in os.environ.items()
        if not key.startswith("LOCAL_AI_")
    }
    inherited.update({
        "PYTHONPATH": str(ROOT / "src"),
        "LOCAL_AI_BASE_URL": base_url,
        "LOCAL_AI_MODEL": model_id,
        "LOCAL_AI_CONTEXT_SIZE": "32",
        "LOCAL_AI_LLM_TIMEOUT": "5",
        "LOCAL_AI_API_KEY": "local",
        "LOCAL_AI_VAR_DIR": str(state_root),
        "LOCAL_AI_MEMORY_DB": str(state_root / "memory/friday.sqlite3"),
        "LOCAL_AI_RESEARCH_DB": str(state_root / "research/knowledge.sqlite3"),
        "LOCAL_AI_TASK_HISTORY_DB": str(state_root / "history/tasks.sqlite3"),
        "LOCAL_AI_AUTONOMY_DB": str(state_root / "autonomy/objectives.sqlite3"),
        "LOCAL_AI_CAREER_FORGE_DB": str(state_root / "career-forge/learner.sqlite3"),
        "LOCAL_AI_DESKTOP_CONTROL_DB": str(state_root / "desktop-control/actions.sqlite3"),
        "LOCAL_AI_PROACTIVE_DB": str(state_root / "proactive/events.sqlite3"),
    })
    return inherited


def _start_candidate(base_url: str, model_id: str, state_root: Path, port: int):
    process = subprocess.Popen(
        [sys.executable, str(CANDIDATE), "--port", str(port)],
        cwd=ROOT,
        env=_candidate_env(base_url, model_id, state_root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    address = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 10
    with httpx.Client(trust_env=False, timeout=0.25) as client:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise AssertionError("disposable Friday candidate exited during startup")
            try:
                response = client.get(address + "/health")
                if response.status_code == 200:
                    return process, address
            except httpx.HTTPError:
                time.sleep(0.05)
    process.terminate()
    process.wait(timeout=3)
    raise AssertionError("disposable Friday candidate did not become healthy")


def _conversation(address: str) -> str:
    with httpx.Client(trust_env=False, timeout=8) as client:
        response = client.post(
            address + "/api/v1/conversation/stream",
            json={
            "prompt": "Summarize the synthetic evidence briefly.",
            "max_tokens": 8,
            "temperature": 0,
            },
        )
        response.raise_for_status()
        return response.text


def _stop(process: subprocess.Popen) -> None:
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


def _source_fingerprint() -> str:
    diff = subprocess.run(
        ["git", "diff", "--binary", "HEAD"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout
    digest = hashlib.sha256(diff)
    for raw_path in untracked.split(b"\0"):
        if raw_path:
            path = ROOT / os.fsdecode(raw_path)
            digest.update(raw_path)
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _seed_candidate_stores(state_root: Path) -> dict[str, str]:
    paths = {
        "memory": state_root / "memory/friday.sqlite3",
        "research": state_root / "research/knowledge.sqlite3",
        "task_history": state_root / "history/tasks.sqlite3",
        "objectives": state_root / "autonomy/objectives.sqlite3",
        "career_forge": state_root / "career-forge/learner.sqlite3",
        "desktop": state_root / "desktop-control/actions.sqlite3",
        "proactive": state_root / "proactive/events.sqlite3",
    }
    snapshots = {}
    for name, path in paths.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as connection:
            connection.execute("CREATE TABLE phase17_sentinel (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            connection.execute("INSERT INTO phase17_sentinel VALUES ('fixture', ?)", (name,))
            connection.execute("PRAGMA user_version=17")
        snapshots[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return snapshots


def _candidate_store_hashes(state_root: Path) -> dict[str, str]:
    return {
        path.relative_to(state_root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(state_root.rglob("*.sqlite3"))
    }


@pytest.fixture
def fixture_backend(request):
    model_id, response, context_size = request.param
    server = _FixtureServer(model_id, response)
    server.context_size = context_size
    try:
        yield server
    finally:
        server.close()


@pytest.mark.parametrize(
    "fixture_backend",
    [
        ("friday-model-swap-fixture-a", "MODEL-A-READY", 16),
        ("friday-model-swap-fixture-b", "MODEL-B-READY", 64),
    ],
    indirect=True,
)
def test_openai_compatible_loopback_chat_and_stream_contract(fixture_backend, monkeypatch):
    # An injected proxy must not divert local model traffic.
    monkeypatch.setenv("HTTP_PROXY", "http://192.0.2.1:1")
    monkeypatch.setenv("HTTPS_PROXY", "http://192.0.2.1:1")
    monkeypatch.delenv("NO_PROXY", raising=False)
    config = AppConfig.from_env({
        "LOCAL_AI_BASE_URL": fixture_backend.base_url,
        "LOCAL_AI_MODEL": fixture_backend.model_id,
        "LOCAL_AI_CONTEXT_SIZE": str(fixture_backend.context_size),
        "LOCAL_AI_LLM_TIMEOUT": "3",
    })
    model = LocalLLM(config=config)
    assert model.config.llama.context_size == fixture_backend.context_size
    events: list[tuple[str, dict]] = []
    model.set_latency_observer(lambda stage, details: events.append((stage, dict(details))))
    assert model.chat("synthetic question", system_prompt="synthetic policy", max_tokens=8) == fixture_backend.response
    assert "".join(model.stream_chat("synthetic question", system_prompt="synthetic policy", max_tokens=8)) == fixture_backend.response
    assert len(fixture_backend.requests) == 2
    for body in fixture_backend.requests:
        assert body["model"] == fixture_backend.model_id
        assert body["messages"] == [
            {"role": "system", "content": "synthetic policy"},
            {"role": "user", "content": "synthetic question"},
        ]
        assert body["max_tokens"] == 8
        assert body["temperature"] == 0.2
        assert "tools" not in body
    assert fixture_backend.requests[1]["stream"] is True
    assert "stream_options" not in fixture_backend.requests[1]
    if fixture_backend.include_usage:
        assert any(stage == "LOCAL_LLM_USAGE" and details["cached_tokens"] == 0 for stage, details in events)
    else:
        assert not any(stage == "LOCAL_LLM_USAGE" for stage, _ in events)


def test_all_required_roles_remain_prompt_only_over_same_model():
    server = _FixtureServer("friday-role-fixture", "ROLE-READY")
    try:
        config = AppConfig.from_env({"LOCAL_AI_BASE_URL": server.base_url, "LOCAL_AI_MODEL": server.model_id})
        roles = RoleOrchestrator(LocalLLM(config=config))
        role_policy = {
            Role.CONVERSATION: "Do not claim tool execution",
            Role.REASONING: "State uncertainty",
            Role.PLANNER: "bounded implementation plan",
            Role.REVIEWER: "do not approve or merge",
            Role.SECURITY: "do not grant authorization",
            Role.TEACHER: "never claim learner mastery",
        }
        for role, expected in role_policy.items():
            assert roles.client(role).chat("harmless synthetic prompt", max_tokens=8) == "ROLE-READY"
            body = server.requests[-1]
            assert body["model"] == server.model_id
            assert body["messages"][0]["role"] == "system"
            assert expected in body["messages"][0]["content"]
            assert "tools" not in body and "tool_choice" not in body
        assert len({body["model"] for body in server.requests}) == 1
    finally:
        server.close()


def test_candidate_conversation_restarts_from_backend_a_to_b(tmp_path):
    backend_a = _FixtureServer("fixture-a", "MODEL-A-READY")
    candidate = None
    backend_b = None
    try:
        port = _free_port()
        source_before = _source_fingerprint()
        state_root = tmp_path / "candidate-state"
        seeded_stores = _seed_candidate_stores(state_root)
        candidate, address = _start_candidate(backend_a.base_url, backend_a.model_id, state_root, port)
        baseline_hashes = _candidate_store_hashes(state_root)
        assert len(baseline_hashes) == len(seeded_stores) == 7
        response_a = _conversation(address)
        assert response_a == "MODEL-A-READY"
        request_a = backend_a.requests[-1]
        assert request_a["model"] == "fixture-a"
        assert request_a["messages"][0]["role"] == "system"
        assert "memory-evidence-7319" in request_a["messages"][0]["content"]

        _stop(candidate)
        candidate = None
        backend_a.close()
        backend_b = _FixtureServer("fixture-b", f"MODEL-B-READY\n{MALICIOUS_OUTPUT}")
        candidate, address_b = _start_candidate(backend_b.base_url, backend_b.model_id, state_root, port)
        response_b = _conversation(address_b)
        assert response_b == f"MODEL-B-READY\n{MALICIOUS_OUTPUT}"
        request_b = backend_b.requests[-1]
        assert request_b["model"] == "fixture-b"
        assert "memory-evidence-7319" in request_b["messages"][0]["content"]
        assert request_b["max_tokens"] == request_a["max_tokens"]
        assert address_b == address
        assert backend_a.server_port != backend_b.server_port
        assert _source_fingerprint() == source_before
        assert _candidate_store_hashes(state_root) == baseline_hashes
    finally:
        if candidate is not None:
            _stop(candidate)
        if backend_b is not None:
            backend_b.close()
        try:
            backend_a.close()
        except OSError:
            pass


@pytest.mark.parametrize(
    "url",
    ("https://api.openai.com/v1", "http://192.0.2.20:8080/v1", "http://localhost:8080/v1?token=secret"),
)
def test_model_configuration_rejects_nonlocal_or_secret_bearing_endpoint(url):
    with pytest.raises(ConfigurationError):
        AppConfig.from_env({"LOCAL_AI_BASE_URL": url})


def test_research_evidence_uses_shared_reasoning_model_boundary():
    server = _FixtureServer("research-fixture", "RESEARCH-READY")
    try:
        config = AppConfig.from_env({"LOCAL_AI_BASE_URL": server.base_url, "LOCAL_AI_MODEL": server.model_id})
        roles = RoleOrchestrator(LocalLLM(config=config))
        conversation = FridayConversationService(
            roles.client(Role.CONVERSATION),
            FridayRuntime("research-model-swap-qualification"),
            research_llm=roles.client(Role.REASONING),
        )
        answer, truncated = conversation.answer_from_local_research(
            "What does the fixture say?",
            '{"source_id":"synthetic-source","fact":"Synthetic fact 7319"}',
        )
        assert answer == "RESEARCH-READY"
        assert truncated is False
        request = server.requests[-1]
        assert request["model"] == "research-fixture"
        assert "untrusted JSON reference data" in request["messages"][0]["content"]
        assert '"source_id":"synthetic-source"' in request["messages"][0]["content"]
        assert "What does the fixture say?" in request["messages"][1]["content"]
    finally:
        server.close()


def test_local_model_timeout_is_bounded_and_mapped():
    server = _FixtureServer("slow-fixture", "TOO-LATE", delay_seconds=1.3)
    try:
        config = AppConfig.from_env({
            "LOCAL_AI_BASE_URL": server.base_url,
            "LOCAL_AI_MODEL": server.model_id,
            "LOCAL_AI_LLM_TIMEOUT": "1",
        })
        model = LocalLLM(config=config)
        started = time.monotonic()
        with pytest.raises(LLMError):
            model.chat("bounded request", max_tokens=8)
        assert time.monotonic() - started < 1.3
    finally:
        server.close()
