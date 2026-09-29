#!/usr/bin/env python3
"""Candidate-only, fixed Owner Sovereign qualification sequence.

Run as the main process of the transient user unit named by the broker policy.
It exposes no request listener and accepts no model-, document-, or browser-
provided commands. Its only root actions are disposable acceptance probes.
"""

from __future__ import annotations

import grp
import json
import os
import pwd
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

from local_ai_assistant.admin.client import (
    AdminCredentialStatus,
    AdministratorCredentialService,
    PrivilegedExecutor,
)

QUALIFICATION_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(QUALIFICATION_ROOT / "scripts/qualification"))

UNIT_PREFIX = "friday-owner-sovereign-check-"
TASK_ID = "owner-sovereign-candidate-qualification"
NETWORK_CHECK_SCRIPT = (
    "import json,socket\n"
    "def reachable(host,port):\n"
    " try:\n"
    "  s=socket.create_connection((host,port),timeout=1); s.close(); return True\n"
    " except OSError: return False\n"
    "print(json.dumps({'external':reachable('1.1.1.1',443),"
    "'friday':reachable('127.0.0.1',8765),'qwen':reachable('127.0.0.1',8080)}))"
)


class QualificationFailure(RuntimeError):
    pass


def _run(executor: PrivilegedExecutor, executable: str, argv: list[str], action: str,
         timeout: int = 20):
    result = executor.execute(
        executable,
        argv,
        task_id=TASK_ID,
        action_id=action,
        timeout_seconds=timeout,
    )
    if result.return_code or result.timed_out:
        raise QualificationFailure(f"{action} failed with return code {result.return_code}")
    return result


def _root_file_probe(executor: PrivilegedExecutor) -> None:
    path = f"/tmp/friday-admin-qualification-{uuid.uuid4().hex}"
    contents = b"friday-owner-sovereign-qualification\n"
    try:
        created = executor.execute(
            "/usr/bin/tee", ["--", path], task_id=TASK_ID,
            action_id="root-file-write", stdin=contents,
        )
        if created.return_code or created.timed_out:
            raise QualificationFailure("disposable qualification file could not be written")
        owner = _run(executor, "/usr/bin/stat", ["-c", "%u:%g", "--", path], "root-file-inspect")
        if owner.stdout.strip() != "0:0":
            raise QualificationFailure("disposable file UID/GID was not root:root")
        observed = _run(executor, "/usr/bin/cat", ["--", path], "root-file-content-inspect")
        if observed.stdout.encode() != contents:
            raise QualificationFailure("disposable file contents did not match")
    finally:
        _run(executor, "/usr/bin/rm", ["-f", "--", path], "root-file-remove")


def _systemd_probe(executor: PrivilegedExecutor) -> None:
    unit = f"{UNIT_PREFIX}{uuid.uuid4().hex}.service"
    started = False
    try:
        _run(
            executor,
            "/usr/bin/systemd-run",
            ["--unit", unit, "--collect", "--property=Type=exec", "/usr/bin/sleep", "60"],
            "transient-service-start",
        )
        started = True
        state = _run(
            executor, "/usr/bin/systemctl",
            ["show", unit, "--property=ActiveState", "--property=MainPID", "--property=User",
             "--property=Group", "--property=FragmentPath", "--no-pager"],
            "transient-service-inspect",
        )
        properties = _property_map(state.stdout)
        pid = int(properties.get("MainPID", "0"))
        if (
            properties.get("ActiveState") != "active"
            or pid <= 1
            or properties.get("User", "") not in {"", "root", "0"}
            or properties.get("Group", "") not in {"", "root", "0"}
            or not properties.get("FragmentPath", "").startswith("/run/systemd/transient/")
        ):
            raise QualificationFailure("transient system service inspection did not match the disposable root probe")
        uid = _run(executor, "/usr/bin/grep", ["^Uid:", f"/proc/{pid}/status"], "transient-service-uid-inspect")
        if int(uid.stdout.split()[1]) != 0:
            raise QualificationFailure("transient system service was not running as root")
    finally:
        if started:
            _run(executor, "/usr/bin/systemctl", ["stop", unit], "transient-service-stop")


def _restart_persistence_probe(executor: PrivilegedExecutor) -> None:
    before = _run(
        executor, "/usr/bin/systemctl",
        ["show", "friday-admin-broker.service", "--property=MainPID", "--value"],
        "broker-pid-before-restart",
    )
    before_pid = int(before.stdout.strip())
    if before_pid <= 1:
        raise QualificationFailure("administrator broker was not active before restart")
    unit = f"{UNIT_PREFIX}{uuid.uuid4().hex}.service"
    _run(
        executor,
        "/usr/bin/systemd-run",
        [
            "--unit", unit, "--collect", "--on-active=2s",
            "/usr/bin/systemctl", "restart", "friday-admin-broker.service",
        ],
        "broker-restart-schedule",
    )
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        try:
            current = _run(
                executor, "/usr/bin/systemctl",
                ["show", "friday-admin-broker.service", "--property=MainPID", "--value"],
                "broker-pid-after-restart",
            )
            current_pid = int(current.stdout.strip())
            if current_pid <= 1 or current_pid == before_pid:
                time.sleep(0.25)
                continue
        except (OSError, RuntimeError):
            time.sleep(0.25)
            continue
        try:
            status = AdministratorCredentialService().status()
        except (OSError, RuntimeError):
            time.sleep(0.25)
            continue
        if status is AdminCredentialStatus.AVAILABLE:
            _root_file_probe(executor)
            return
        time.sleep(0.25)
    raise QualificationFailure("broker PID did not change and recover the credential after restart")


def _invalidate_sudo_timestamp() -> None:
    """Clear sudo-rs timestamps so following proof depends on enrolled data."""
    result = subprocess.run(
        ["/usr/bin/sudo", "-K"], capture_output=True, timeout=5, check=False,
        env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C"},
    )
    if result.returncode:
        raise QualificationFailure("sudo authentication timestamp could not be invalidated")


def _property_map(output: str) -> dict[str, str]:
    return dict(line.split("=", 1) for line in output.splitlines() if "=" in line)


def _private_network_probe(executor: PrivilegedExecutor) -> None:
    unit = f"{UNIT_PREFIX}{uuid.uuid4().hex}.service"
    uid, gid = os.getuid(), os.getgid()
    username = pwd.getpwuid(uid).pw_name
    groupname = grp.getgrgid(gid).gr_name
    started = False
    try:
        _run(
            executor,
            "/usr/bin/systemd-run",
            [
                "--unit", unit, "--collect", "--property=Type=exec",
                "--property=PrivateNetwork=yes", "--property=PrivateUsers=no",
                f"--property=User={uid}", f"--property=Group={gid}",
                "--property=NoNewPrivileges=yes", "/usr/bin/sleep", "60",
            ],
            "private-network-anchor-start",
        )
        started = True
        details = _run(
            executor,
            "/usr/bin/systemctl",
            [
                "show", unit, "--property=MainPID", "--property=User", "--property=Group",
                "--property=PrivateNetwork", "--property=PrivateUsers",
                "--property=NoNewPrivileges", "--no-pager",
            ],
            "private-network-anchor-inspect",
        )
        properties = _property_map(details.stdout)
        pid = int(properties.get("MainPID", "0"))
        if (
            pid <= 1
            or properties.get("User") not in {str(uid), username}
            or properties.get("Group") not in {str(gid), groupname}
            or properties.get("PrivateNetwork") != "yes"
            or properties.get("PrivateUsers") != "no"
            or properties.get("NoNewPrivileges") != "yes"
        ):
            raise QualificationFailure("private-network anchor properties did not match policy")

        status = _run(executor, "/usr/bin/grep", ["^Uid:", f"/proc/{pid}/status"], "anchor-uid-inspect")
        if int(status.stdout.split()[1]) != uid:
            raise QualificationFailure("private-network anchor UID mismatch")
        network = _run(executor, "/usr/bin/readlink", [f"/proc/{pid}/ns/net"], "anchor-netns-inspect")
        user = _run(executor, "/usr/bin/readlink", [f"/proc/{pid}/ns/user"], "anchor-userns-inspect")
        if network.stdout.strip() == os.readlink("/proc/self/ns/net"):
            raise QualificationFailure("private-network anchor shares host network namespace")
        host_user_namespace = os.readlink("/proc/self/ns/user")
        if user.stdout.strip() != host_user_namespace:
            raise QualificationFailure("PrivateUsers=no did not preserve the host user namespace")
    finally:
        if started:
            _run(executor, "/usr/bin/systemctl", ["stop", unit], "private-network-anchor-stop")

    check_unit = f"{UNIT_PREFIX}{uuid.uuid4().hex}.service"
    denial = _run(
        executor,
        "/usr/bin/systemd-run",
        [
            "--unit", check_unit, "--wait", "--pipe", "--collect", "--quiet",
            "--property=PrivateNetwork=yes", "--property=PrivateUsers=no",
            f"--property=User={uid}", f"--property=Group={gid}",
            "--property=NoNewPrivileges=yes", "/usr/bin/python3", "-c", NETWORK_CHECK_SCRIPT,
        ],
        "private-network-egress-negative-control",
        timeout=15,
    )
    try:
        denied = json.loads(denial.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError) as exc:
        raise QualificationFailure("private-network negative control returned invalid evidence") from exc
    if any(denied.values()):
        raise QualificationFailure("private-network service reached a prohibited endpoint")


def qualify() -> dict[str, str]:
    status = AdministratorCredentialService().status()
    if status is not AdminCredentialStatus.AVAILABLE:
        raise QualificationFailure(f"credential status is {status.value}")
    executor = PrivilegedExecutor()
    evidence: dict[str, str] = {"credential_status": status.value}
    _invalidate_sudo_timestamp()
    evidence["sudo_cache_before_root_file"] = "invalidated"
    _root_file_probe(executor)
    evidence["root_file"] = "passed"
    _invalidate_sudo_timestamp()
    evidence["sudo_cache_before_transient_systemd"] = "invalidated"
    _systemd_probe(executor)
    evidence["transient_systemd"] = "passed"
    _restart_persistence_probe(executor)
    evidence["broker_restart_and_reuse"] = "passed"
    _invalidate_sudo_timestamp()
    evidence["sudo_cache_before_private_network"] = "invalidated"
    _private_network_probe(executor)
    evidence["private_network"] = "passed"
    return evidence


def main() -> int:
    try:
        native = qualify()
        from phase19_sovereignty_e2e import qualify as qualify_phase19

        phase19 = qualify_phase19()
        print(json.dumps({"owner_sovereign": native, "phase19": phase19}, sort_keys=True), flush=True)
    except (OSError, RuntimeError, QualificationFailure, ValueError) as exc:
        print(f"Owner Sovereign qualification failed: {exc}", file=sys.stderr, flush=True)
        return 1
    stop = False

    def request_stop(_signal_number: int, _frame: object) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    while not stop:
        time.sleep(0.25)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
