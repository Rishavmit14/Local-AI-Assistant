#!/usr/bin/env python3
"""Start the unmodified Friday presentation app on a private AF_UNIX socket."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

_VOICE_WORKERS = {
    "parakeet_full.py": "Parakeet",
    "moonshine_medium.py": "Moonshine",
    "pocket_worker.py": "Pocket/Anna",
}


def _friday_service_state() -> str:
    """Read the production supervisor state, failing closed if it is unknown."""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-active", "friday-local-ai.service"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(
            "cannot verify production Friday service state; refusing a wake-enabled candidate"
        ) from exc
    state = result.stdout.strip()
    if result.returncode not in {0, 3} or state not in {"active", "inactive"}:
        raise RuntimeError(
            "production Friday service state is unknown; refusing a wake-enabled candidate"
        )
    return state


def _voice_processes() -> list[str]:
    """Find any resident wake/TTS worker or default-device capture process."""
    matches: list[str] = []
    proc_root = Path("/proc")
    for entry in proc_root.iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            command = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode(
                "utf-8", errors="replace"
            )
        except (OSError, ProcessLookupError):
            continue
        for marker, label in _VOICE_WORKERS.items():
            if marker in command:
                matches.append(f"{label} worker (PID {entry.name})")
                break
        else:
            parts = command.split()
            if (
                parts
                and Path(parts[0]).name == "arecord"
                and "-D" in parts
                and parts[parts.index("-D") + 1 : parts.index("-D") + 2] == ["default"]
            ):
                matches.append(f"default ALSA capture (PID {entry.name})")
    return matches


def assert_single_voice_stack() -> None:
    """Refuse a wake-enabled isolated runtime beside production voice workers."""
    state = _friday_service_state()
    if state != "inactive":
        raise RuntimeError(
            "production Friday is active; stop friday-local-ai.service before starting "
            "a wake-enabled candidate to prevent duplicate workers and microphone contention"
        )
    workers = _voice_processes()
    if workers:
        raise RuntimeError(
            "voice workers or a default-device capture process are already running: "
            + ", ".join(workers)
        )


def _candidate_environment(
    state_root: Path,
    model: str,
    qwen_port: int,
    *,
    wake_enabled: bool = False,
) -> None:
    for name in tuple(os.environ):
        if name.startswith("LOCAL_AI_"):
            os.environ.pop(name, None)
    os.environ.update({
        "LOCAL_AI_VAR_DIR": str(state_root),
        "LOCAL_AI_BASE_URL": f"http://127.0.0.1:{qwen_port}/v1",
        "LOCAL_AI_MODEL": model,
        "LOCAL_AI_API_KEY": "local",
        "LOCAL_AI_LLM_TIMEOUT": "120",
        "LOCAL_AI_WAKE_ENABLED": "true" if wake_enabled else "false",
        "LOCAL_AI_PROACTIVE_ENABLED": "false",
        "LOCAL_AI_GATEWAY_ENABLED": "false",
        "LOCAL_AI_GITHUB_ENABLED": "false",
        "LOCAL_AI_REQUIRE_STRONG_ISOLATION": "true",
        "LOCAL_AI_SANDBOX_NETWORK": "deny",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1",
    })


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--api-socket", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--qwen-port", type=int, default=18080)
    parser.add_argument(
        "--enable-wake",
        action="store_true",
        help="start real microphone/wake workers; requires production Friday to be stopped",
    )
    args = parser.parse_args()
    state_root = args.state_root.resolve()
    if Path("/tmp") not in state_root.parents:
        parser.error("disposable candidate state must be below /tmp")
    if args.qwen_port != 18080:
        parser.error("the candidate Qwen adapter port is fixed at 18080")
    if args.api_socket.exists():
        parser.error("refusing to replace an existing candidate API socket")
    if not args.model.strip():
        parser.error("model must not be empty")
    if args.enable_wake:
        assert_single_voice_stack()
    state_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    _candidate_environment(
        state_root,
        args.model,
        args.qwen_port,
        wake_enabled=args.enable_wake,
    )

    import uvicorn

    from local_ai_assistant.common.config import get_config
    from local_ai_assistant.interface.cli import build_presentation_components

    config = get_config()
    app, wake_voice = build_presentation_components(config)
    if wake_voice is not None:
        wake_voice.start()
    print("offline_candidate_starting transport=private-af-unix state=disposable", flush=True)
    try:
        uvicorn.run(
            app,
            uds=str(args.api_socket),
            log_level="info",
            access_log=False,
        )
    finally:
        if wake_voice is not None:
            wake_voice.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
