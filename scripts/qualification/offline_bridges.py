#!/usr/bin/env python3
"""Fixed-destination AF_UNIX qualification bridges for Phase 18B only.

The candidate adapter accepts only the configured model's OpenAI chat-completion
operation on namespace-local loopback. It sends a small framed RPC over a private
pathname AF_UNIX socket. The host relay has no destination inputs and forwards
only that operation to the fixed local Qwen endpoint.
"""

from __future__ import annotations

import argparse
import http.server
import json
import os
import socket
import socketserver
import struct
from pathlib import Path
from typing import Any

import httpx

MAX_REQUEST_BYTES = 1 * 1024 * 1024
MAX_RESPONSE_BYTES = 32 * 1024 * 1024
MAX_FRAME_HEADER_BYTES = 4096
QWEN_URL = "http://127.0.0.1:8080/v1/chat/completions"
QWEN_PATH = "/v1/chat/completions"
QWEN_OPERATION = "chat.completions"
CANDIDATE_QWEN_HOST = "127.0.0.1"
CANDIDATE_QWEN_PORT = 18080
_REQUEST_KEYS = {"model", "messages", "temperature", "max_tokens", "stream"}
_DESTINATION_HEADERS = {
    "forwarded", "proxy-authorization", "proxy-connection", "x-forwarded-host",
    "x-forwarded-proto", "x-original-host", "x-original-url", "x-original-uri",
}


class BridgeRequestError(ValueError):
    """A request did not match the fixed relay contract."""


def validate_chat_request(
    method: str,
    target: str,
    headers: list[tuple[str, str]],
    body: bytes,
    *,
    expected_host: str,
    model: str,
) -> dict[str, Any]:
    """Validate the candidate loopback HTTP request without opening any socket."""
    if method != "POST" or target != QWEN_PATH:
        raise BridgeRequestError("only POST /v1/chat/completions is accepted")
    lowered: dict[str, list[str]] = {}
    for name, value in headers:
        lowered.setdefault(name.lower(), []).append(value.strip())
    if lowered.get("host") != [expected_host]:
        raise BridgeRequestError("Host must be the candidate loopback endpoint")
    if any(name in lowered for name in _DESTINATION_HEADERS):
        raise BridgeRequestError("destination-style headers are not accepted")
    if "transfer-encoding" in lowered or "content-encoding" in lowered:
        raise BridgeRequestError("encoded request bodies are not accepted")
    if lowered.get("content-type", [""])[0].split(";", 1)[0].strip().lower() != "application/json":
        raise BridgeRequestError("application/json is required")
    if lowered.get("authorization") != ["Bearer local"]:
        raise BridgeRequestError("the configured local API credential is required")
    lengths = lowered.get("content-length", [])
    if len(lengths) != 1 or not lengths[0].isdigit() or int(lengths[0]) != len(body):
        raise BridgeRequestError("a single exact Content-Length is required")
    if not body or len(body) > MAX_REQUEST_BYTES:
        raise BridgeRequestError("request body is empty or exceeds the size limit")
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BridgeRequestError("request body must be valid JSON") from exc
    if not isinstance(payload, dict) or set(payload) - _REQUEST_KEYS:
        raise BridgeRequestError("unsupported chat-completion fields")
    if payload.get("model") != model:
        raise BridgeRequestError("request model does not match configured local model")
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages or len(messages) > 64:
        raise BridgeRequestError("bounded chat messages are required")
    if "stream" in payload and type(payload["stream"]) is not bool:
        raise BridgeRequestError("stream must be a boolean")
    return payload


def validate_rpc_header(header: object, body_length: int) -> None:
    """Validate the UDS protocol; it intentionally has no host/port/URL fields."""
    if not isinstance(header, dict) or set(header) != {"operation", "body_length"}:
        raise BridgeRequestError("invalid relay operation frame")
    if header.get("operation") != QWEN_OPERATION:
        raise BridgeRequestError("unsupported relay operation")
    length = header.get("body_length")
    if type(length) is not int or length != body_length or not 1 <= length <= MAX_REQUEST_BYTES:
        raise BridgeRequestError("invalid relay body length")


def validate_rpc_body(body: bytes, *, model: str) -> dict[str, Any]:
    if not body or len(body) > MAX_REQUEST_BYTES:
        raise BridgeRequestError("relay body is empty or exceeds the size limit")
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BridgeRequestError("relay body must be valid JSON") from exc
    if not isinstance(payload, dict) or set(payload) - _REQUEST_KEYS:
        raise BridgeRequestError("unsupported chat-completion fields")
    if payload.get("model") != model or not isinstance(payload.get("messages"), list):
        raise BridgeRequestError("relay model or messages are invalid")
    if "stream" in payload and type(payload["stream"]) is not bool:
        raise BridgeRequestError("stream must be a boolean")
    return payload


def _read_exact(stream: socket.socket, length: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < length:
        chunk = stream.recv(length - len(chunks))
        if not chunk:
            raise ConnectionError("truncated relay frame")
        chunks.extend(chunk)
    return bytes(chunks)


def _recv_frame_header(connection: socket.socket, limit: int = MAX_FRAME_HEADER_BYTES) -> dict[str, Any]:
    length = struct.unpack("!I", _read_exact(connection, 4))[0]
    if not 1 <= length <= limit:
        raise BridgeRequestError("invalid relay frame header size")
    header = json.loads(_read_exact(connection, length))
    if not isinstance(header, dict):
        raise BridgeRequestError("relay frame header must be an object")
    return header


def _send_frame_header(connection: socket.socket, header: dict[str, Any]) -> None:
    encoded = json.dumps(header, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_FRAME_HEADER_BYTES:
        raise BridgeRequestError("relay response header is too large")
    connection.sendall(struct.pack("!I", len(encoded)) + encoded)


def _send_chunk(connection: socket.socket, chunk: bytes) -> None:
    connection.sendall(struct.pack("!I", len(chunk)) + chunk)


def _peer_uid(connection: socket.socket) -> int:
    if not hasattr(socket, "SO_PEERCRED"):
        raise PermissionError("AF_UNIX peer credentials are unavailable")
    credentials = connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    _pid, uid, _gid = struct.unpack("3i", credentials)
    return uid


class _QwenRelayHandler(socketserver.BaseRequestHandler):
    server: _QwenRelayServer

    def handle(self) -> None:
        connection: socket.socket = self.request
        try:
            if _peer_uid(connection) != self.server.owner_uid:
                raise PermissionError("relay peer UID is not the owner UID")
            header = _recv_frame_header(connection)
            if set(header) != {"operation", "body_length"}:
                raise BridgeRequestError("invalid relay operation frame")
            length = header.get("body_length")
            if header.get("operation") != QWEN_OPERATION or type(length) is not int or not 1 <= length <= MAX_REQUEST_BYTES:
                raise BridgeRequestError("invalid fixed Qwen operation")
            body = _read_exact(connection, length)
            validate_rpc_header(header, len(body))
            payload = validate_rpc_body(body, model=self.server.model)
            self.server.forward(connection, body, payload)
        except Exception as exc:
            try:
                _send_frame_header(connection, {"status": 400, "content_type": "application/json", "error": type(exc).__name__})
                _send_chunk(connection, json.dumps({"error": "fixed local Qwen relay rejected the request"}).encode())
                _send_chunk(connection, b"")
            except OSError:
                pass


class _QwenRelayServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, socket_path: Path, model: str):
        if socket_path.exists():
            raise FileExistsError(f"refusing to replace existing relay path: {socket_path}")
        socket_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        socket_path.parent.chmod(0o700)
        super().__init__(str(socket_path), _QwenRelayHandler)
        socket_path.chmod(0o600)
        self.socket_path = socket_path
        self.model = model
        self.owner_uid = os.getuid()

    def forward(self, connection: socket.socket, body: bytes, payload: dict[str, Any]) -> None:
        headers = {"content-type": "application/json", "authorization": "Bearer local"}
        if payload.get("stream") is True:
            headers["accept"] = "text/event-stream"
        else:
            headers["accept"] = "application/json"
        try:
            with httpx.Client(timeout=120, trust_env=False, follow_redirects=False) as client:
                with client.stream("POST", QWEN_URL, content=body, headers=headers) as response:
                    content_type = response.headers.get("content-type", "application/json")
                    _send_frame_header(connection, {"status": response.status_code, "content_type": content_type})
                    total = 0
                    for chunk in response.iter_raw(64 * 1024):
                        total += len(chunk)
                        if total > MAX_RESPONSE_BYTES:
                            raise BridgeRequestError("Qwen response exceeded relay limit")
                        _send_chunk(connection, chunk)
                    _send_chunk(connection, b"")
        except Exception:
            try:
                _send_frame_header(connection, {"status": 502, "content_type": "application/json"})
                _send_chunk(connection, b'{"error":"fixed local Qwen endpoint unavailable"}')
                _send_chunk(connection, b"")
            except OSError:
                pass

    def server_close(self) -> None:
        try:
            super().server_close()
        finally:
            try:
                self.socket_path.unlink()
            except FileNotFoundError:
                pass


class _CandidateQwenHandler(http.server.BaseHTTPRequestHandler):
    server: _CandidateQwenServer
    protocol_version = "HTTP/1.0"

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def _reject(self, status: int = 400) -> None:
        data = b'{"error":"candidate Qwen adapter rejected the request"}'
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        headers = list(self.headers.raw_items())
        length_values = [v.strip() for n, v in headers if n.lower() == "content-length"]
        if len(length_values) != 1 or not length_values[0].isdigit():
            self._reject()
            return
        length = int(length_values[0])
        if not 1 <= length <= MAX_REQUEST_BYTES:
            self._reject(413)
            return
        try:
            body = self.rfile.read(length)
            if len(body) != length:
                raise BridgeRequestError("truncated HTTP request body")
            validate_chat_request(
                self.command,
                self.path,
                headers,
                body,
                expected_host=f"{CANDIDATE_QWEN_HOST}:{CANDIDATE_QWEN_PORT}",
                model=self.server.model,
            )
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as relay:
                relay.settimeout(120)
                relay.connect(str(self.server.socket_path))
                _send_frame_header(relay, {"operation": QWEN_OPERATION, "body_length": len(body)})
                relay.sendall(body)
                response = _recv_frame_header(relay)
                status = response.get("status")
                content_type = response.get("content_type")
                if type(status) is not int or not 100 <= status <= 599 or not isinstance(content_type, str):
                    raise BridgeRequestError("invalid fixed relay response")
                self.send_response(status)
                self.send_header("Content-Type", content_type[:256])
                self.send_header("Connection", "close")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.close_connection = True
                total = 0
                while True:
                    length = struct.unpack("!I", _read_exact(relay, 4))[0]
                    if length == 0:
                        break
                    if length > 64 * 1024:
                        raise BridgeRequestError("relay chunk exceeds frame limit")
                    total += length
                    if total > MAX_RESPONSE_BYTES:
                        raise BridgeRequestError("relay response exceeded limit")
                    self.wfile.write(_read_exact(relay, length))
                    self.wfile.flush()
        except (BridgeRequestError, OSError, ValueError, json.JSONDecodeError):
            if not self.wfile.closed:
                self._reject()

    def do_GET(self) -> None:
        self._reject(405)

    def do_PUT(self) -> None:
        self._reject(405)

    def do_CONNECT(self) -> None:
        self._reject(405)

    def do_DELETE(self) -> None:
        self._reject(405)


class _CandidateQwenServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, socket_path: Path, model: str):
        super().__init__((CANDIDATE_QWEN_HOST, CANDIDATE_QWEN_PORT), _CandidateQwenHandler)
        self.socket_path = socket_path
        self.model = model


def run_host_relay(socket_path: Path, model: str) -> None:
    server = _QwenRelayServer(socket_path, model)
    print(f"fixed_qwen_relay_listening={socket_path}", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        server.shutdown()
        server.server_close()


def run_candidate_adapter(socket_path: Path, model: str) -> None:
    server = _CandidateQwenServer(socket_path, model)
    print(f"candidate_qwen_adapter_listening={CANDIDATE_QWEN_HOST}:{CANDIDATE_QWEN_PORT}", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        server.server_close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("host-qwen", "candidate-qwen"))
    parser.add_argument("--socket", type=Path, required=True)
    parser.add_argument("--model", required=True)
    args = parser.parse_args()
    if not args.model.strip():
        parser.error("--model must not be empty")
    if args.mode == "host-qwen":
        run_host_relay(args.socket, args.model)
    else:
        run_candidate_adapter(args.socket, args.model)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
