#!/usr/bin/env python3
"""Run the isolated Stage 30 project-to-learning browser qualification."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

REPO = Path(__file__).resolve().parents[2]


class FixtureTeacher:
    def chat(self, _prompt: str, **_kwargs: object) -> str:
        print("STAGE30_FIXTURE teacher_call", flush=True)
        return (
            "FraudShield lesson: map a validated row to a deterministic risk score. "
            "For example, a boolean fraud flag can map to 1 or 0. Practice: explain "
            "how you would test both values and what the score does not prove."
        )


class FixtureReviewer:
    def chat(self, prompt: str, **_kwargs: object) -> str:
        print("STAGE30_FIXTURE reviewer_call", flush=True)
        if "return -1" in prompt:
            return (
                "EVIDENCE: The function assigns a negative score to every row and "
                "does not use the fraud flag.\nASSESSMENT: incorrect"
            )
        return (
            "EVIDENCE: The function maps the fraud flag to a stable binary score, "
            "and the explanation identifies that it has not been executed.\n"
            "ASSESSMENT: correct"
        )


class FixtureCurriculumDesigner:
    def __init__(self, proposal: dict[str, object]):
        self.proposal = proposal

    def chat(self, _prompt: str, **_kwargs: object) -> str:
        print("STAGE30_FIXTURE curriculum_proposal", flush=True)
        return json.dumps(self.proposal)


def build_fixture_app(data_dir: Path, ui_origin: str, credential: str):
    print("STAGE30_API importing isolated fixture services", flush=True)
    from local_ai_assistant.autonomy.service import ObjectiveService
    from local_ai_assistant.career_forge.models import TutorMode
    from local_ai_assistant.career_forge.service import CareerForgeService
    from local_ai_assistant.interface.api import create_presentation_app
    from local_ai_assistant.interface.conversation import FridayConversationService
    from local_ai_assistant.interface.runtime import FridayRuntime
    from local_ai_assistant.isolation.owner_rollback import OwnerBrowserSessions
    from local_ai_assistant.learning_paths import LearningPathService
    from local_ai_assistant.learning_paths.service import LocalCurriculumGenerator
    from local_ai_assistant.projects import ProjectService
    from tests.unit.test_projects import SatisfiedEvidence, project_curriculum

    data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    print("STAGE30_API creating temporary learner stores", flush=True)
    paths = LearningPathService(
        data_dir / "learning-paths.sqlite3",
        generator=LocalCurriculumGenerator(FixtureCurriculumDesigner(project_curriculum())),
    )
    identity_file = data_dir / "fixture-identity.json"
    identity: dict[str, str] = {}
    if identity_file.exists():
        identity = json.loads(identity_file.read_text())
        if identity.get("path_id"):
            paths.detail(identity["path_id"])
    paths.evidence_provider = SatisfiedEvidence()

    forge = CareerForgeService(data_dir / "career-forge.sqlite3")
    projects = ProjectService(data_dir / "projects.sqlite3")
    objectives = ObjectiveService(data_dir / "objectives.sqlite3")
    sessions = OwnerBrowserSessions(hashlib.sha256(credential.encode()).hexdigest())
    runtime = FridayRuntime("stage30-connected-journey-fixture")
    app = create_presentation_app(
        runtime,
        FridayConversationService(object(), runtime),
        learning_paths=paths,
        career_forge=forge,
        projects=projects,
        autonomy=objectives,
        project_execution_sessions=sessions,
        project_execution_allowed_origins=(ui_origin,),
        career_tutor_clients={
            TutorMode.EXPLAIN: FixtureTeacher(),
            TutorMode.REVIEW: FixtureReviewer(),
        },
    )
    print("STAGE30_API app constructed", flush=True)
    return app, identity


def api_child(args: argparse.Namespace) -> int:
    print("STAGE30_API fixture setup started", flush=True)
    import uvicorn

    data_dir = Path(os.environ["FRIDAY_STAGE30_DATA_DIR"])
    app, identity = build_fixture_app(
        data_dir,
        os.environ["FRIDAY_STAGE30_UI_ORIGIN"],
        os.environ["FRIDAY_STAGE30_FIXTURE_CREDENTIAL"],
    )
    print("STAGE30_API fixture setup complete", flush=True)
    if identity.get("path_id"):
        (data_dir / "fixture-identity.json").write_text(json.dumps(identity))
    print(f"STAGE30_API listening on isolated port {args.port}", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning", access_log=False)
    return 0


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def resources() -> dict[str, object]:
    memory: dict[str, int] = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith(("MemAvailable:", "SwapFree:", "SwapTotal:")):
            key, value, *_ = line.split()
            memory[key] = int(value)
    return {
        **memory,
        "memory_psi": Path("/proc/pressure/memory").read_text().strip(),
        "io_psi": Path("/proc/pressure/io").read_text().strip(),
    }


def process_group_rss(groups: list[int]) -> int:
    wanted = set(groups)
    total = 0
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            stat = (entry / "stat").read_text()
            fields = stat.rsplit(")", 1)[1].split()
            if int(fields[2]) not in wanted:
                continue
            for line in (entry / "status").read_text().splitlines():
                if line.startswith("VmRSS:"):
                    total += int(line.split()[1])
                    break
        except (OSError, ValueError, IndexError):
            continue
    return total


def full_memory_psi_avg10() -> float:
    for line in Path("/proc/pressure/memory").read_text().splitlines():
        if line.startswith("full "):
            for item in line.split():
                if item.startswith("avg10="):
                    return float(item.split("=", 1)[1])
    return 0.0


def stop_process(process: subprocess.Popen[bytes] | None) -> None:
    if process is None or process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=12)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)


def wait_http(
    url: str,
    process: subprocess.Popen[bytes],
    label: str,
    timeout: float = 120,
    log_path: Path | None = None,
) -> None:
    deadline = time.monotonic() + timeout
    last_error = "not ready"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"{label} exited early with status {process.returncode}: {last_error}")
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except Exception as exc:  # bounded local readiness probe
            last_error = str(exc)
        time.sleep(0.25)
    diagnostic = log_path.read_text(errors="replace")[-2000:] if log_path and log_path.exists() else ""
    raise TimeoutError(f"{label} did not become ready: {last_error}; startup output: {diagnostic}")


def run_browser_phase(
    label: str,
    command: list[str],
    env: dict[str, str],
    log_path: Path,
    groups: list[int],
) -> dict[str, object]:
    before = resources()
    started = time.monotonic()
    max_group_rss = process_group_rss(groups)
    severe_samples = 0
    process: subprocess.Popen[bytes] | None = None
    with log_path.open("wb") as log:
        process = subprocess.Popen(
            command,
            cwd=REPO,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        while True:
            try:
                process.wait(timeout=1)
                break
            except subprocess.TimeoutExpired:
                max_group_rss = max(max_group_rss, process_group_rss([*groups, process.pid]))
                state = resources()
                mem_available = int(state.get("MemAvailable:", 0))
                if mem_available < 2_097_152 or full_memory_psi_avg10() > 20:
                    severe_samples += 1
                else:
                    severe_samples = 0
                if severe_samples >= 15:
                    stop_process(process)
                    break
    after = resources()
    result = {
        "phase": label,
        "exit": process.returncode if process is not None else 127,
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "test_owned_peak_rss_kib": max_group_rss,
        "started_resources": before,
        "finished_resources": after,
        "resource_guard_stopped": severe_samples >= 15,
        "log": str(log_path),
    }
    if result["exit"] == 0 and not result["resource_guard_stopped"]:
        return result
    tail = log_path.read_text(errors="replace")[-3000:]
    raise RuntimeError(f"{label} failed: {json.dumps(result)}\n{tail}")


def start_api(api_port: int, ui_origin: str, data_dir: Path, credential: str, logs: Path, suffix: str):
    child_env = {
        **os.environ,
        "PYTHONPATH": f"{REPO / 'src'}:{REPO}",
        "FRIDAY_STAGE30_DATA_DIR": str(data_dir),
        "FRIDAY_STAGE30_UI_ORIGIN": ui_origin,
        "FRIDAY_STAGE30_FIXTURE_CREDENTIAL": credential,
    }
    log = (logs / f"api-{suffix}.log").open("wb")
    process = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "--api-child", "--port", str(api_port)],
        cwd=REPO,
        env=child_env,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    return process, log


def run_qualification(evidence_dir: Path) -> dict[str, object]:
    browser = shutil.which("google-chrome") or shutil.which("google-chrome-stable")
    if not browser:
        raise RuntimeError("Google Chrome is required for the actual-browser Stage 30 qualification")
    evidence_dir.mkdir(parents=True, exist_ok=True)
    ports: set[int] = set()
    while len(ports) < 3:
        ports.add(free_port())
    api_port, ui_port, cdp_port = ports
    ui_origin = f"http://127.0.0.1:{ui_port}"
    credential = "stage30-" + os.urandom(24).hex()
    with tempfile.TemporaryDirectory(prefix="friday-stage30-journey-") as tmp:
        temp_root = Path(tmp)
        os.chmod(temp_root, 0o700)
        data_dir = temp_root / "sqlite"
        data_dir.mkdir(mode=0o700)
        chrome_profile = temp_root / "chrome-profile"
        chrome_profile.mkdir(mode=0o700)
        api_process = ui_process = chrome_process = None
        api_log = ui_log = chrome_log = None
        resource_log: list[dict[str, object]] = []
        try:
            api_process, api_log = start_api(api_port, ui_origin, data_dir, credential, evidence_dir, "initial")
            wait_http(f"http://127.0.0.1:{api_port}/health", api_process, "isolated Stage 30 API", log_path=evidence_dir / "api-initial.log")
            ui_env = {
                **os.environ,
                "FRIDAY_UI_PORT": str(ui_port),
                "LOCAL_AI_OWNER_UI_ORIGIN": ui_origin,
                "VITE_FRIDAY_API_ORIGIN": f"http://127.0.0.1:{api_port}",
            }
            ui_log = (evidence_dir / "ui.log").open("wb")
            ui_process = subprocess.Popen(
                ["node", str(REPO / "frontend/server/local-ui.mjs")],
                cwd=REPO / "frontend",
                env=ui_env,
                stdout=ui_log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            wait_http(ui_origin, ui_process, "isolated Stage 30 UI", log_path=evidence_dir / "ui.log")
            chrome_log = (evidence_dir / "chrome.log").open("wb")
            chrome_process = subprocess.Popen(
                [
                    browser,
                    "--headless=new",
                    "--disable-gpu",
                    "--disable-dev-shm-usage",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--no-sandbox",
                    "--remote-debugging-address=127.0.0.1",
                    f"--remote-debugging-port={cdp_port}",
                    f"--user-data-dir={chrome_profile}",
                    "--window-size=1280,1000",
                    "about:blank",
                ],
                stdout=chrome_log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            wait_http(f"http://127.0.0.1:{cdp_port}/json/version", chrome_process, "isolated headless Chrome", log_path=evidence_dir / "chrome.log")
            common_env = {
                **os.environ,
                "FRIDAY_STAGE30_CDP_PORT": str(cdp_port),
                "FRIDAY_STAGE30_UI_ORIGIN": ui_origin,
                "FRIDAY_STAGE30_FIXTURE_CREDENTIAL": credential,
            }
            groups = [api_process.pid, ui_process.pid, chrome_process.pid]
            first = run_browser_phase(
                "actual_browser_project_learning_review_and_reload",
                ["node", str(REPO / "scripts/qualification/stage30_connected_journey_browser.mjs"), "journey"],
                common_env,
                evidence_dir / "browser-journey.log",
                groups,
            )
            phase_output = (evidence_dir / "browser-journey.log").read_text(errors="replace")
            payload = next(
                (json.loads(line.removeprefix("STAGE30_RESULT ")) for line in phase_output.splitlines()
                 if line.startswith("STAGE30_RESULT ")),
                None,
            )
            if not payload:
                raise RuntimeError("browser journey finished without its acceptance result")
            resource_log.append(first)

            identity = {
                "path_id": payload["path_id"],
                "target_node_id": payload["target_node_id"],
            }
            (data_dir / "fixture-identity.json").write_text(json.dumps(identity))

            restart_before = resources()
            stop_process(api_process)
            api_log.close()
            api_process, api_log = start_api(api_port, ui_origin, data_dir, credential, evidence_dir, "restarted")
            wait_http(f"http://127.0.0.1:{api_port}/health", api_process, "restarted isolated Stage 30 API", log_path=evidence_dir / "api-restarted.log")
            resource_log.append({
                "phase": "isolated_api_restart",
                "exit": 0,
                "started_resources": restart_before,
                "finished_resources": resources(),
            })

            recovery_env = {
                **common_env,
                "FRIDAY_STAGE30_PATH_ID": identity["path_id"],
                "FRIDAY_STAGE30_TARGET_NODE_ID": identity["target_node_id"],
                "FRIDAY_STAGE30_PROJECT_ID": payload["project_id"],
                "FRIDAY_STAGE30_EXPECTED_MASTERY": json.dumps(payload["mastery_after_review"]),
            }
            second = run_browser_phase(
                "actual_browser_api_restart_durability",
                ["node", str(REPO / "scripts/qualification/stage30_connected_journey_browser.mjs"), "recovery"],
                recovery_env,
                evidence_dir / "browser-recovery.log",
                groups,
            )
            resource_log.append(second)
            result = {
                "status": "passed",
                "branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=REPO, text=True).strip(),
                "path_id": payload["path_id"],
                "project_id": payload["project_id"],
                "navigation_no_writes": payload["navigation_no_writes"],
                "unauthenticated_create_status": payload["unauthenticated_create_status"],
                "authorized_create_status": payload["authorized_create_status"],
                "project_assignment_idempotent": payload["project_assignment_idempotent"],
                "negative_auth_status": payload["negative_auth_status"],
                "incorrect_review": payload["incorrect_review"],
                "accepted_review": payload["accepted_review"],
                "recommendation_after_incorrect": payload["recommendation_after_incorrect"],
                "recommendation_after_correct": payload["recommendation_after_correct"],
                "evidence_count": payload["evidence_count"],
                "objective_task_id": payload["objective_task_id"],
                "mastery_before": payload["mastery_before"],
                "mastery_after_review": payload["mastery_after_review"],
                "durability_after_api_restart": True,
                "browser": "Google Chrome headless via CDP",
                "resources": resource_log,
                "evidence_dir": str(evidence_dir),
            }
            (evidence_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n")
            print(json.dumps(result, indent=2))
            return result
        finally:
            for process in (chrome_process, ui_process, api_process):
                stop_process(process)
            for handle in (chrome_log, ui_log, api_log):
                if handle is not None and not handle.closed:
                    handle.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-child", action="store_true")
    parser.add_argument("--port", type=int)
    parser.add_argument("--evidence-dir", type=Path)
    args = parser.parse_args()
    if args.api_child:
        if not args.port:
            parser.error("--port is required for --api-child")
        return api_child(args)
    if args.evidence_dir is None:
        parser.error("--evidence-dir is required")
    try:
        run_qualification(args.evidence_dir.resolve())
    except Exception as exc:
        print(f"Stage 30 browser qualification failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
