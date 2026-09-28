#!/usr/bin/env python3
"""Loopback-only Astra API bridge to one fixed candidate AF_UNIX socket."""

from __future__ import annotations

import argparse
import http.client
import http.server
import socket
import urllib.parse
from pathlib import Path
from typing import Any

MAX_API_BODY_BYTES = 2 * 1024 * 1024
PRESENTATION_HOST = "127.0.0.1"
PRESENTATION_PORT = 8768
ALLOWED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}
ALLOWED_HEADERS = {
    "accept", "cache-control", "content-type", "cookie", "last-event-id",
    "origin", "x-friday-csrf",
}
ALLOWED_ORIGINS = {"http://127.0.0.1:5192", "http://localhost:5192"}


def validate_presentation_request(
    method: str,
    target: str,
    headers: list[tuple[str, str]],
    body_length: int,
) -> str:
    """Return the candidate API path or reject a non-local proxy request."""
    lowered: dict[str, list[str]] = {}
    for name, value in headers:
        lowered.setdefault(name.lower(), []).append(value.strip())
    if method not in ALLOWED_METHODS or lowered.get("host") != [f"{PRESENTATION_HOST}:{PRESENTATION_PORT}"]:
        raise ValueError("invalid local presentation authority")
    if not target.startswith("/") or target.startswith("//"):
        raise ValueError("only origin-form API paths are accepted")
    parsed = urllib.parse.urlsplit(target)
    if parsed.scheme or parsed.netloc or parsed.fragment or not (
        parsed.path == "/health" or parsed.path.startswith("/api/v1/")
    ):
        raise ValueError("path is outside the candidate presentation API")
    origins = lowered.get("origin", [])
    if origins and (len(origins) != 1 or origins[0] not in ALLOWED_ORIGINS):
        raise ValueError("origin is outside the disposable Astra candidate")
    if "transfer-encoding" in lowered:
        raise ValueError("chunked request bodies are not accepted")
    lengths = lowered.get("content-length", [])
    if len(lengths) > 1 or (lengths and (not lengths[0].isdigit() or int(lengths[0]) != body_length)):
        raise ValueError("invalid request length")
    if body_length < 0 or body_length > MAX_API_BODY_BYTES:
        raise ValueError("request exceeds candidate bridge limit")
    return target


class _UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, socket_path: Path):
        super().__init__("friday-candidate-api", timeout=120)
        self.socket_path = socket_path

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(str(self.socket_path))


class _PresentationHandler(http.server.BaseHTTPRequestHandler):
    server: _PresentationServer
    protocol_version = "HTTP/1.1"

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def _error(self, status: int, message: str) -> None:
        body = ("{\"detail\":\"" + message + "\"}").encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def _proxy(self) -> None:
        request_headers = list(self.headers.raw_items())
        lengths = [value.strip() for name, value in request_headers if name.lower() == "content-length"]
        body_length = int(lengths[0]) if len(lengths) == 1 and lengths[0].isdigit() else (-1 if lengths else 0)
        try:
            validate_presentation_request(self.command, self.path, request_headers, body_length)
        except ValueError as exc:
            self._error(400, str(exc))
            return
        body = self.rfile.read(body_length) if body_length else b""
        if len(body) != body_length:
            self._error(400, "truncated request body")
            return
        headers = {
            name: value
            for name in ALLOWED_HEADERS
            if (value := self.headers.get(name)) is not None
        }
        headers["Host"] = "friday-candidate-api"
        if body:
            headers["Content-Length"] = str(len(body))
        connection = _UnixHTTPConnection(self.server.api_socket)
        response_started = False
        try:
            connection.request(self.command, self.path, body=body, headers=headers)
            response = connection.getresponse()
            self.send_response(response.status)
            response_headers = response.getheaders()
            for name, value in response_headers:
                if name.lower() in {"content-type", "cache-control", "set-cookie", "content-encoding"}:
                    self.send_header(name, value)
            if response.status in {204, 304}:
                self.end_headers()
                return
            self.send_header("Transfer-Encoding", "chunked")
            self.send_header("Connection", "close")
            self.end_headers()
            response_started = True
            self.close_connection = True
            # read1 preserves streamed Conversation/SSE chunks instead of
            # waiting for a full buffer or the upstream stream to close.
            while chunk := response.read1(64 * 1024):
                self.wfile.write(f"{len(chunk):x}\r\n".encode("ascii"))
                self.wfile.write(chunk)
                self.wfile.write(b"\r\n")
                self.wfile.flush()
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
        except (OSError, http.client.HTTPException):
            if not response_started and not self.wfile.closed:
                try:
                    self._error(502, "candidate API is unavailable")
                except OSError:
                    pass
        finally:
            connection.close()

    do_GET = _proxy
    do_POST = _proxy
    do_PUT = _proxy
    do_PATCH = _proxy
    do_DELETE = _proxy
    do_OPTIONS = _proxy


class _PresentationServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, api_socket: Path):
        if not api_socket.is_socket():
            raise FileNotFoundError(f"candidate API socket is unavailable: {api_socket}")
        super().__init__((PRESENTATION_HOST, PRESENTATION_PORT), _PresentationHandler)
        self.api_socket = api_socket


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-socket", type=Path, required=True)
    args = parser.parse_args()
    server = _PresentationServer(args.api_socket)
    print(f"candidate_presentation_proxy_listening={PRESENTATION_HOST}:{PRESENTATION_PORT}", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
