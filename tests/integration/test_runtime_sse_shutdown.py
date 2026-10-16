"""Exercise the production FastAPI SSE path through the CLI's Uvicorn server."""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

from local_ai_assistant.learning_paths import LearningPathService
from tests.fixtures.learning_path_curricula import curriculum

_SERVER_PROGRAM = r"""
import faulthandler
import json
import os
import signal
import sys
import threading
import traceback
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from local_ai_assistant.interface.api import create_presentation_app
from local_ai_assistant.interface.cli import (
    FridayUvicornServer,
    _begin_presentation_shutdown,
)
from local_ai_assistant.interface.conversation import FridayConversationService
from local_ai_assistant.interface.events import FridayEventType
from local_ai_assistant.interface.runtime import FridayRuntime
from local_ai_assistant.learning_paths import LearningPathService


class NoInference:
    def stream_chat(self, *_args, **_kwargs):
        raise AssertionError("shutdown qualification must not call a model")


root = Path(os.environ["FRIDAY_SSE_TEST_ROOT"])
stack_file = open(root / "stacks.txt", "w")
faulthandler.register(signal.SIGUSR1, stack_file, all_threads=True)
runtime = FridayRuntime("isolated-sse-shutdown")
event_count = int(os.environ["FRIDAY_SSE_TEST_EVENT_COUNT"])
for index in range(event_count):
    runtime.emit(
        FridayEventType.SYSTEM_HEALTH,
        text="x" * 20_000,
        metadata={"qualification": "replay"} if index == 0 else {"sample": index},
        transient=True,
    )
learning_paths = LearningPathService(os.environ["FRIDAY_SSE_TEST_DB"])
path_id = os.environ["FRIDAY_SSE_TEST_PATH_ID"]
def on_shutdown():
    path = learning_paths.detail(path_id)["path"]
    frames = sys._current_frames()
    stacks = {
        thread.name: "".join(traceback.format_stack(frames[thread.ident]))
        for thread in threading.enumerate()
        if thread.ident in frames
    }
    (root / "lifespan.json").write_text(json.dumps({
        "subscribers": runtime.subscriber_count,
        "path_id": path.path_id,
        "version": path.current_version,
        "state": path.state,
        "threads": sorted(stacks),
        "stacks": stacks,
    }))

app = create_presentation_app(
    runtime,
    FridayConversationService(NoInference(), runtime),
    learning_paths=learning_paths,
    on_shutdown=on_shutdown,
)

@app.get("/__qualification/runtime")
def qualification_runtime():
    return {
        "subscribers": runtime.subscriber_count,
        "shutting_down": runtime.shutting_down,
    }

server = FridayUvicornServer(
    uvicorn.Config(
        app,
        host="127.0.0.1",
        port=int(os.environ["FRIDAY_SSE_TEST_PORT"]),
        log_level="info",
        access_log=False,
    ),
    before_exit=lambda: _begin_presentation_shutdown(runtime, None),
)
server.run()
"""


def _free_loopback_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _wait_for_subscriber_count(
    client: httpx.Client,
    base_url: str,
    expected: int,
) -> None:
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        try:
            response = client.get(f"{base_url}/__qualification/runtime")
            if response.status_code == 200 and response.json()["subscribers"] == expected:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.025)
    raise AssertionError(f"SSE subscriber count did not become {expected}")


def _open_stream(client: httpx.Client, base_url: str):
    context = client.stream("GET", f"{base_url}/api/v1/runtime/events/stream?cursor=0")
    response = context.__enter__()
    iterator = response.iter_lines()
    assert next(iterator) == "id: 1"
    assert '"qualification": "replay"' in next(iterator)
    return context, response, iterator


def _consume_replay(iterator, event_count: int) -> None:
    delivered = 0
    while delivered < event_count:
        assert next(iterator).startswith("id: ")
        assert next(iterator).startswith("data: ")
        next(iterator)
        delivered += 1


def _start_isolated_server(
    root: Path,
    path_id: str,
    database: Path,
    event_count: int,
) -> subprocess.Popen[str]:
    port = _free_loopback_port()
    (root / "port.txt").write_text(str(port))
    env = {
        "PATH": os.defpath,
        "HOME": str(root),
        "TMPDIR": str(root),
        "PYTHONNOUSERSITE": "1",
        "PYTHONPATH": os.pathsep.join((str(Path(__file__).resolve().parents[2] / "src"),
                                         str(Path(__file__).resolve().parents[2]))),
        "FRIDAY_SSE_TEST_ROOT": str(root),
        "FRIDAY_SSE_TEST_PATH_ID": path_id,
        "FRIDAY_SSE_TEST_DB": str(database),
        "FRIDAY_SSE_TEST_PORT": str(port),
        "FRIDAY_SSE_TEST_EVENT_COUNT": str(event_count),
    }
    return subprocess.Popen(
        [sys.executable, "-c", _SERVER_PROGRAM],
        cwd=Path(__file__).resolve().parents[2],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _wait_for_health(client: httpx.Client, base_url: str, process: subprocess.Popen[str]) -> None:
    # The locked Stage 29 runtime took 33.6 seconds for a cold API import here.
    deadline = time.monotonic() + 60
    last_observation = "no response received"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            raise AssertionError(f"isolated API exited before health: {stdout}\n{stderr}")
        try:
            response = client.get(f"{base_url}/health")
            last_observation = f"HTTP {response.status_code}: {response.text[:500]}"
            if response.status_code == 200:
                return
        except httpx.HTTPError as exc:
            last_observation = f"{type(exc).__name__}: {exc}"
        time.sleep(0.025)
    raise AssertionError(f"isolated API did not become healthy; last observation: {last_observation}")


def test_real_uvicorn_sse_disconnect_and_shutdown_cycles_are_bounded(tmp_path):
    database = tmp_path / "paths.sqlite3"
    learning_paths = LearningPathService(database)
    path = learning_paths.create(curriculum())
    before = learning_paths.detail(path.path_id)
    initial = (before["path"].current_version, before["path"].state, before["current"])
    latencies = []
    cycle_results = []

    for cycle in range(3):
        root = tmp_path / f"cycle-{cycle}"
        root.mkdir()
        event_count = 1000 if cycle == 2 else 1
        process = _start_isolated_server(root, path.path_id, database, event_count)
        client = httpx.Client(timeout=httpx.Timeout(connect=2, read=5, write=2, pool=2))
        streams = []
        try:
            port = int((root / "port.txt").read_text())
            base_url = f"http://127.0.0.1:{port}"
            _wait_for_health(client, base_url, process)
            _wait_for_subscriber_count(client, base_url, 0)

            if cycle == 0:
                # A genuine disconnect must release the subscription promptly,
                # before the 30-second SSE heartbeat period.
                context, response, _ = _open_stream(client, base_url)
                streams.append((context, response, None, False))
                _wait_for_subscriber_count(client, base_url, 1)
                context.__exit__(None, None, None)
                streams.clear()
                _wait_for_subscriber_count(client, base_url, 0)

            if cycle != 1:
                for index in range(3):
                    context = client.stream(
                        "GET", f"{base_url}/api/v1/runtime/events/stream?cursor=0"
                    )
                    response = context.__enter__()
                    iterator = response.iter_lines()
                    if index < 2:
                        _consume_replay(iterator, event_count)
                    # The third client intentionally leaves its bounded replay unread.
                    streams.append((context, response, iterator, index == 2 and event_count > 1))
                _wait_for_subscriber_count(client, base_url, 3)

            child_list = Path(f"/proc/{process.pid}/task/{process.pid}/children")
            assert child_list.exists()
            children_before_stop = child_list.read_text().strip()
            assert not children_before_stop, children_before_stop
            started = time.monotonic()
            process.send_signal(signal.SIGTERM)
            # Read each open response through EOF. The idle queue has no new
            # events, so only explicit shutdown cancellation can end the streams.
            eof_results = []
            cancelled_streams = 0
            for _, response, iterator, may_be_cancelled in streams:
                if may_be_cancelled:
                    continue
                if iterator is None:
                    iterator = response.iter_lines()
                try:
                    eof_results.append(list(iterator))
                except httpx.HTTPError:
                    raise
            try:
                exit_status = process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.send_signal(signal.SIGUSR1)
                time.sleep(0.1)
                stacks = (root / "stacks.txt").read_text()
                process.kill()
                process.wait(timeout=2)
                stdout, stderr = process.communicate(timeout=2)
                raise AssertionError(
                    f"isolated API failed to stop; stacks={stacks}\nstdout={stdout}\nstderr={stderr}"
                )
            latencies.append(time.monotonic() - started)
            for _, response, iterator, may_be_cancelled in streams:
                if not may_be_cancelled:
                    continue
                try:
                    iterator = iterator or response.iter_lines()
                    eof_results.append(list(iterator))
                except httpx.HTTPError:
                    cancelled_streams += 1
            stdout, stderr = process.communicate(timeout=2)
            assert exit_status in (0, -signal.SIGTERM), (exit_status, stdout, stderr)
            assert all(
                all(line == "" or line.startswith("id: ") or line.startswith("data: ") for line in lines)
                for lines in eof_results
            )
            assert (root / "lifespan.json").exists(), stderr
            lifespan = json.loads((root / "lifespan.json").read_text())
            assert lifespan["subscribers"] == 0
            assert lifespan["path_id"] == path.path_id
            assert lifespan["version"] == initial[0]
            assert lifespan["state"] == initial[1]
            assert not any(
                "runtime_event_stream" in stack
                or ("queue.py" in stack and " in get" in stack and "interface/api.py" in stack)
                for stack in lifespan["stacks"].values()
            ), lifespan["stacks"]
            assert "Application shutdown complete" in stderr
            assert "Timed out waiting" not in stderr
            if cycle == 2:
                assert cancelled_streams == 1, stderr
            assert not Path(f"/proc/{process.pid}").exists()
            cycle_results.append({
                "cycle": cycle,
                "exit_latency_seconds": latencies[-1],
                "process_returncode": exit_status,
                "streams_closed": len(eof_results),
                "streams_cancelled_for_backpressure": cancelled_streams,
                "subscribers_at_lifespan_shutdown": lifespan["subscribers"],
                "threads_at_lifespan_shutdown": lifespan["threads"],
                "no_blocked_sse_reader": True,
                "no_child_process": True,
            })
        finally:
            for context, _, _, _ in streams:
                try:
                    context.__exit__(None, None, None)
                except Exception:
                    pass
            client.close()
            if process.poll() is None:
                process.kill()
                process.wait(timeout=2)

    assert len(latencies) == 3
    assert max(latencies) < 10, latencies
    after = LearningPathService(database).detail(path.path_id)
    assert (after["path"].current_version, after["path"].state, after["current"]) == initial
    (tmp_path / "shutdown-results.json").write_text(json.dumps(cycle_results, indent=2) + "\n")
