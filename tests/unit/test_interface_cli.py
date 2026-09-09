from __future__ import annotations

import signal

import uvicorn

from local_ai_assistant.interface.cli import FridayUvicornServer


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
