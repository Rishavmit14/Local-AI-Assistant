#!/usr/bin/env python3
"""Run isolated Stage 31 multi-topic learning browser qualification."""

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
        print("STAGE31_FIXTURE teacher_call", flush=True)
        return (
            "FraudShield lesson: map a validated row to a deterministic risk score. "
            "For example, a boolean fraud flag can map to 1 or 0. Practice: explain "
            "how you would test both values and what the score does not prove."
        )


class FixtureReviewer:
    def chat(self, prompt: str, **_kwargs: object) -> str:
        print("STAGE31_FIXTURE reviewer_call", flush=True)
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


class FixtureAssessor:
    """Deterministic Stage 31 evaluator; never executes learner code."""

    def chat(self, prompt: str, **_kwargs: object) -> str:
        print("STAGE31_FIXTURE assessor_call", flush=True)
        question_id = prompt.split("QUESTION ID: ", 1)[-1].splitlines()[0].strip()
        answer = prompt.rsplit("OWNER ANSWER: ", 1)[-1].lower()
        if "intentionally incomplete" in answer or "accuracy is enough" in answer:
            return "ASSESSMENT: incorrect\nThe response misses leakage and class-sensitive evaluation. Revisit the split and metric exercise."
        required = {
            "data-leakage-reasoning-v1": ("train", "validation", "test", "leak", "precision", "recall"),
            "data-metrics-practical-v1": ("precision", "recall", "train", "validation", "test"),
            "logistic-probability-reasoning-v1": ("sigmoid", "log loss", "threshold"),
            "logistic-python-practical-v1": ("logisticregression", "validation", "threshold", "test", "precision"),
            "trees-overfit-reasoning-v1": ("nonlinear", "overfit", "logistic", "validation"),
            "fraud-model-comparison-practical-v1": ("logistic", "tree", "same", "validation", "test"),
        }.get(question_id, ())
        missing = [token for token in required if token not in answer]
        if missing:
            return "ASSESSMENT: incorrect\nThe answer needs these contract elements: " + ", ".join(missing) + ". Rework the specific exercise and retry."
        return "ASSESSMENT: correct\nThe response addresses the exact question contract with independent reasoning. Evidence is recorded for this attempt only; mastery still follows Career Forge's multi-question threshold."


class FixtureCurriculumDesigner:
    def __init__(self, proposal: dict[str, object]):
        self.proposal = proposal

    def chat(self, _prompt: str, **_kwargs: object) -> str:
        print("STAGE31_FIXTURE curriculum_proposal", flush=True)
        return json.dumps(self.proposal)


def build_fixture_app(data_dir: Path, ui_origin: str, credential: str):
    print("STAGE31_API importing isolated fixture services", flush=True)
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
    from local_ai_assistant.learning_paths.evidence import CareerForgeEvidenceProjection
    from tests.fixtures.stage31_ml_curriculum import stage31_ml_engineering_curriculum

    data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    print("STAGE31_API creating temporary learner stores", flush=True)
    paths = LearningPathService(
        data_dir / "learning-paths.sqlite3",
        generator=LocalCurriculumGenerator(FixtureCurriculumDesigner(stage31_ml_engineering_curriculum())),
    )
    identity_file = data_dir / "fixture-identity.json"
    identity: dict[str, str] = {}
    if identity_file.exists():
        identity = json.loads(identity_file.read_text())
        if identity.get("path_id"):
            paths.detail(identity["path_id"])
    forge = CareerForgeService(data_dir / "career-forge.sqlite3")
    paths.evidence_provider = CareerForgeEvidenceProjection(forge)
    projects = ProjectService(data_dir / "projects.sqlite3")
    objectives = ObjectiveService(data_dir / "objectives.sqlite3")
    sessions = OwnerBrowserSessions(hashlib.sha256(credential.encode()).hexdigest())
    runtime = FridayRuntime("stage31-ml-engineering-journey-fixture")
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
            TutorMode.TEACH_BACK: FixtureAssessor(),
        },
    )
    print("STAGE31_API app constructed", flush=True)
    return app, identity


def api_child(args: argparse.Namespace) -> int:
    print("STAGE31_API fixture setup started", flush=True)
    import uvicorn

    data_dir = Path(os.environ["FRIDAY_STAGE31_DATA_DIR"])
    app, identity = build_fixture_app(
        data_dir,
        os.environ["FRIDAY_STAGE31_UI_ORIGIN"],
        os.environ["FRIDAY_STAGE31_FIXTURE_CREDENTIAL"],
    )
    print("STAGE31_API fixture setup complete", flush=True)
    if identity.get("path_id"):
        (data_dir / "fixture-identity.json").write_text(json.dumps(identity))
    print(f"STAGE31_API listening on isolated port {args.port}", flush=True)
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
        "FRIDAY_STAGE31_DATA_DIR": str(data_dir),
        "FRIDAY_STAGE31_UI_ORIGIN": ui_origin,
        "FRIDAY_STAGE31_FIXTURE_CREDENTIAL": credential,
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
        raise RuntimeError("Google Chrome is required for the actual-browser Stage 31 qualification")
    evidence_dir.mkdir(parents=True, exist_ok=True)
    ports: set[int] = set()
    while len(ports) < 3:
        ports.add(free_port())
    api_port, ui_port, cdp_port = ports
    ui_origin = f"http://127.0.0.1:{ui_port}"
    credential = "stage31-" + os.urandom(24).hex()
    with tempfile.TemporaryDirectory(prefix="friday-stage31-journey-") as tmp:
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
            wait_http(f"http://127.0.0.1:{api_port}/health", api_process, "isolated Stage 31 API", log_path=evidence_dir / "api-initial.log")
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
            wait_http(ui_origin, ui_process, "isolated Stage 31 UI", log_path=evidence_dir / "ui.log")
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
                "FRIDAY_STAGE31_CDP_PORT": str(cdp_port),
                "FRIDAY_STAGE31_UI_ORIGIN": ui_origin,
                "FRIDAY_STAGE31_FIXTURE_CREDENTIAL": credential,
            }
            groups = [api_process.pid, ui_process.pid, chrome_process.pid]
            first = run_browser_phase(
                "actual_browser_three_topic_mastery_and_project_review",
                ["node", str(REPO / "scripts/qualification/stage31_ml_engineering_journey_browser.mjs"), "journey"],
                common_env,
                evidence_dir / "browser-journey.log",
                groups,
            )
            phase_output = (evidence_dir / "browser-journey.log").read_text(errors="replace")
            payload = next(
                (json.loads(line.removeprefix("STAGE31_RESULT ")) for line in phase_output.splitlines()
                 if line.startswith("STAGE31_RESULT ")),
                None,
            )
            if not payload:
                raise RuntimeError("browser journey finished without its acceptance result")
            resource_log.append(first)

            identity = {
                "path_id": payload["path_id"],
                "project_id": payload["project_id"],
            }
            (data_dir / "fixture-identity.json").write_text(json.dumps(identity))

            restart_before = resources()
            stop_process(api_process)
            api_log.close()
            api_process, api_log = start_api(api_port, ui_origin, data_dir, credential, evidence_dir, "restarted")
            wait_http(f"http://127.0.0.1:{api_port}/health", api_process, "restarted isolated Stage 31 API", log_path=evidence_dir / "api-restarted.log")
            resource_log.append({
                "phase": "isolated_api_restart",
                "exit": 0,
                "started_resources": restart_before,
                "finished_resources": resources(),
            })

            recovery_env = {
                **common_env,
                "FRIDAY_STAGE31_PATH_ID": identity["path_id"],
                "FRIDAY_STAGE31_EXPECTED_STATE": json.dumps({"project_id": identity["project_id"]}),
            }
            second = run_browser_phase(
                "actual_browser_api_restart_durability",
                ["node", str(REPO / "scripts/qualification/stage31_ml_engineering_journey_browser.mjs"), "recovery"],
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
                "unauthorized_create_status": payload["unauthorized_create_status"],
                "unauthorized_attempt_status": payload["unauthorized_attempt_status"],
                "invalid_question_status": payload["invalid_question_status"],
                "unauthorized_assignment_status": payload["unauthorized_assignment_status"],
                "mastery_by_node": payload["mastery"],
                "attempts_per_node": payload["attempts_per_node"],
                "remediation_after_failure": payload["node1_reinforcement_recommendation"],
                "prerequisite_progression": {
                    "node2_unlocked_after_node1": payload["node2_unlocked_after_node1"],
                    "node3_blocked_until_node2": payload["node3_blocked_until_node2"],
                    "node3_unlocked_after_node2": payload["node3_unlocked_after_node2"],
                },
                "rejected_artifact_state": payload["rejected_artifact_state"],
                "accepted_reviewer_evidence_count": payload["accepted_artifact_evidence_count"],
                "mastery_unchanged_by_project_artifact": payload["mastery_unchanged_by_project_artifact"],
                "objective_task_id": payload["objective_task_id"],
                "browser_reload_recovery": payload["browser_reload_recovery"],
                "api_restart_recovery": json.loads(
                    (evidence_dir / "browser-recovery.log").read_text(errors="replace")
                    .split("STAGE31_RECOVERY ", 1)[-1].splitlines()[0]
                ),
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
        print(f"Stage 31 browser qualification failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
