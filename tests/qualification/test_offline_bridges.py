from __future__ import annotations

import json
import socket
import struct
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

from scripts.qualification import offline_bridges as bridges
from scripts.qualification import offline_presentation_proxy as presentation

MODEL = "configured-local-qwen"
BODY = json.dumps({
    "model": MODEL,
    "messages": [{"role": "user", "content": "synthetic probe"}],
    "temperature": 0.2,
    "max_tokens": 16,
}, separators=(",", ":")).encode()


def request_headers(body: bytes = BODY, **replace: str) -> list[tuple[str, str]]:
    values = [
        ("Host", "127.0.0.1:18080"),
        ("Content-Type", "application/json"),
        ("Authorization", "Bearer local"),
        ("Content-Length", str(len(body))),
    ]
    for name, value in replace.items():
        key = name.replace("_", "-")
        values = [(n, v) for n, v in values if n.lower() != key.lower()]
        values.append((key, value))
    return values


def validate(
    method: str = "POST",
    target: str = bridges.QWEN_PATH,
    headers: list[tuple[str, str]] | None = None,
    body: bytes = BODY,
) -> dict[str, Any]:
    return bridges.validate_chat_request(
        method, target, request_headers(body) if headers is None else headers,
        body, expected_host="127.0.0.1:18080", model=MODEL,
    )


def test_accepts_only_configured_chat_completion_request() -> None:
    payload = validate()
    assert payload["model"] == MODEL
    assert bridges.QWEN_URL == "http://127.0.0.1:8080/v1/chat/completions"


@pytest.mark.parametrize(
    ("method", "target"),
    [
        ("CONNECT", "127.0.0.1:8080"),
        ("GET", bridges.QWEN_PATH),
        ("POST", "/v1/models"),
        ("POST", "http://127.0.0.1:8080/v1/chat/completions"),
        ("POST", "/v1/%63hat/completions"),
        ("POST", "/v1/chat/completions?url=http://example.com"),
    ],
)
def test_rejects_noncanonical_method_or_request_target(method: str, target: str) -> None:
    with pytest.raises(bridges.BridgeRequestError):
        validate(method, target)


@pytest.mark.parametrize(
    "headers",
    [
        request_headers(host="example.com"),
        request_headers(host="127.0.0.1:8080"),
        request_headers() + [("Host", "127.0.0.1:18080")],
        request_headers() + [("X-Forwarded-Host", "example.com")],
        request_headers() + [("Forwarded", "host=example.com")],
        request_headers() + [("Proxy-Authorization", "Basic abc")],
    ],
)
def test_rejects_host_alternation_and_destination_headers(headers: list[tuple[str, str]]) -> None:
    with pytest.raises(bridges.BridgeRequestError):
        validate(headers=headers)


def test_rejects_oversized_and_malformed_requests() -> None:
    large = b"x" * (bridges.MAX_REQUEST_BYTES + 1)
    with pytest.raises(bridges.BridgeRequestError):
        validate(headers=request_headers(large), body=large)
    malformed = b"{not-json"
    with pytest.raises(bridges.BridgeRequestError):
        validate(headers=request_headers(malformed), body=malformed)


def test_rejects_injected_or_malformed_rpc_destination_fields() -> None:
    good = {"operation": bridges.QWEN_OPERATION, "body_length": len(BODY)}
    bridges.validate_rpc_header(good, len(BODY))
    for header in (
        {**good, "host": "example.com"},
        {**good, "port": 443},
        {**good, "url": "https://example.com"},
        {"operation": "tcp-tunnel", "body_length": len(BODY)},
    ):
        with pytest.raises(bridges.BridgeRequestError):
            bridges.validate_rpc_header(header, len(BODY))
    with pytest.raises(bridges.BridgeRequestError):
        bridges.validate_rpc_body(BODY.replace(MODEL.encode(), b"other-model"), model=MODEL)
    with pytest.raises(bridges.BridgeRequestError):
        bridges.validate_rpc_body(b"{bad", model=MODEL)


class _FixedQwenHandler(BaseHTTPRequestHandler):
    requests: list[tuple[str, dict[str, Any]]]

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length))
        self.server.requests.append((self.path, payload))
        result = json.dumps({"id": "fixture", "choices": []}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(result)))
        self.end_headers()
        self.wfile.write(result)


class _FixedQwenServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), _FixedQwenHandler)
        self.requests: list[tuple[str, dict[str, Any]]] = []
        self.thread = threading.Thread(target=self.serve_forever, daemon=True)
        self.thread.start()

    def close(self) -> None:
        self.shutdown()
        self.server_close()
        self.thread.join(timeout=2)


def _read_exact(sock: socket.socket, length: int) -> bytes:
    data = bytearray()
    while len(data) < length:
        chunk = sock.recv(length - len(data))
        if not chunk:
            raise EOFError
        data.extend(chunk)
    return bytes(data)


def test_host_relay_uses_fixed_qwen_operation(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    fake = _FixedQwenServer()
    monkeypatch.setattr(
        bridges, "QWEN_URL",
        f"http://127.0.0.1:{fake.server_port}/v1/chat/completions",
    )
    server = bridges._QwenRelayServer(tmp_path / "relay.sock", MODEL)
    relay_peer, client_peer = socket.socketpair()
    try:
        thread = threading.Thread(target=server.forward, args=(relay_peer, BODY, json.loads(BODY)))
        thread.start()
        header_size = struct.unpack("!I", _read_exact(client_peer, 4))[0]
        response_header = json.loads(_read_exact(client_peer, header_size))
        response_body = bytearray()
        while True:
            size = struct.unpack("!I", _read_exact(client_peer, 4))[0]
            if not size:
                break
            response_body.extend(_read_exact(client_peer, size))
        thread.join(timeout=2)
        assert response_header["status"] == 200
        assert json.loads(response_body)["id"] == "fixture"
        assert fake.requests == [(bridges.QWEN_PATH, json.loads(BODY))]
    finally:
        relay_peer.close()
        client_peer.close()
        server.server_close()
        fake.close()


def test_presentation_bridge_is_fixed_to_local_candidate_api() -> None:
    headers = [("Host", f"127.0.0.1:{presentation.PRESENTATION_PORT}"), ("Origin", "http://127.0.0.1:5192")]
    assert presentation.validate_presentation_request(
        "GET", "/api/v1/runtime/state", headers, 0,
    ) == "/api/v1/runtime/state"
    blocked = [
        ("GET", "http://example.com/api/v1/runtime/state", headers),
        ("CONNECT", f"127.0.0.1:{presentation.PRESENTATION_PORT}", headers),
        ("GET", "/proxy/http://example.com", headers),
        ("GET", "/health", [("Host", "127.0.0.1:9999")]),
        ("POST", "/api/v1/memory/records", headers + [("Origin", "https://example.com")]),
        ("POST", "/api/v1/memory/records", headers + [("Transfer-Encoding", "chunked")]),
        ("GET", "/api/v1/runtime/state", headers + [("Host", "example.com")]),
    ]
    for method, target, request_headers in blocked:
        with pytest.raises(ValueError):
            presentation.validate_presentation_request(method, target, request_headers, 0)
    with pytest.raises(ValueError):
        presentation.validate_presentation_request(
            "POST", "/api/v1/memory/records", headers, presentation.MAX_API_BODY_BYTES + 1,
        )
