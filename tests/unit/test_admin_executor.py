from __future__ import annotations

import importlib.util
import io
import json
import os
import socket
import stat
import struct
import sys
import tempfile
import threading
from pathlib import Path

import pytest

from local_ai_assistant.admin.client import PrivilegedExecutor, _recv_exact
from local_ai_assistant.admin.enrollment import (
    CredentialLifecycle,
    EnrollmentError,
    _run_sudo_command,
    _safe_failure_category,
)
from local_ai_assistant.admin.enrollment import (
    main as enrollment_main,
)
from local_ai_assistant.isolation.models import CapabilityState, NetworkPolicy, ResourcePolicy
from local_ai_assistant.isolation.sandbox import BubblewrapSandbox

BROKER_PATH = Path(__file__).parents[2] / "scripts/admin/friday-admin-broker.py"
SPEC = importlib.util.spec_from_file_location("friday_admin_broker_test", BROKER_PATH)
assert SPEC and SPEC.loader
broker_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = broker_module
SPEC.loader.exec_module(broker_module)
PROBE_PATH = Path(__file__).parents[2] / "scripts/admin/friday-admin-qualification-probe.py"
PROBE_SPEC = importlib.util.spec_from_file_location("friday_admin_probe_test", PROBE_PATH)
assert PROBE_SPEC and PROBE_SPEC.loader
probe_module = importlib.util.module_from_spec(PROBE_SPEC)
sys.modules[PROBE_SPEC.name] = probe_module
PROBE_SPEC.loader.exec_module(probe_module)


class FakeStore:
    def __init__(self, value=b"synthetic-admin-password"):
        self.value = bytearray(value)

    def exists(self):
        return bool(self.value)

    def retrieve(self):
        return bytearray(self.value)


class FakeVerifier:
    def __init__(self, allowed=True):
        self.allowed = allowed
        self.config = type("Policy", (), {"owner_uid": 1000})()

    def allows(self, peer):
        return self.allowed


class FakeRunner:
    def __init__(self, result=None):
        self.calls = []
        self.result = result or {
            "return_code": 0, "stdout": "done", "stderr": "",
            "timed_out": False, "duration_seconds": 0.01,
            "authentication_failed": False,
        }

    def execute(self, executable, argv, password, **kwargs):
        self.calls.append((executable, tuple(argv), bytes(password), kwargs))
        return dict(self.result)


def request(executable="/usr/bin/id", argv=None):
    import base64

    return {
        "op": "execute", "operation_id": "op-1", "task_id": "task-1",
        "action_id": "action-1", "executable": executable,
        "argv": argv or ["-u"], "cwd": "/tmp", "environment": {},
        "stdin_b64": base64.b64encode(b"input").decode(), "timeout_seconds": 5,
    }


def test_broker_executes_general_absolute_argv_without_exporting_password(tmp_path):
    store = FakeStore()
    runner = FakeRunner()
    broker = broker_module.AdminBroker(
        store, FakeVerifier(), runner, audit_path=tmp_path / "audit.jsonl",
        invalid_marker=tmp_path / "credential-invalid",
    )

    result = broker.handle(broker_module.Peer(42, 1000, 1000), request())

    assert result["ok"] is True
    assert runner.calls[0][0] == "/usr/bin/id"
    assert runner.calls[0][1] == ("-u",)
    assert runner.calls[0][2] == b"synthetic-admin-password"
    assert runner.calls[0][3]["stdin"] == b"input"
    assert "synthetic-admin-password" not in json.dumps(result)
    audit = (tmp_path / "audit.jsonl").read_text()
    assert "synthetic-admin-password" not in audit
    assert '"task_id":"task-1"' in audit


def test_broker_rejects_secret_in_operation_arguments_without_audit_leak(tmp_path):
    password = b"synthetic-admin-password"
    broker = broker_module.AdminBroker(
        FakeStore(password), FakeVerifier(), FakeRunner(), audit_path=tmp_path / "audit.jsonl",
        invalid_marker=tmp_path / "credential-invalid",
    )
    payload = request(argv=[f"--value={password.decode()}"])

    result = broker.handle(broker_module.Peer(42, 1000, 1000), payload)

    assert result == {
        "ok": False,
        "error": "credential material is not valid operation input",
    }
    assert broker.runner.calls == []
    assert not (tmp_path / "audit.jsonl").exists()


def test_broker_rejects_untrusted_same_uid_process_before_credential_access(tmp_path):
    runner = FakeRunner()
    broker = broker_module.AdminBroker(
        FakeStore(), FakeVerifier(False), runner,
        audit_path=tmp_path / "audit.jsonl",
        invalid_marker=tmp_path / "credential-invalid",
    )

    result = broker.handle(broker_module.Peer(43, 1000, 1000), request())

    assert result == {"ok": False, "error": "untrusted administrator client"}
    assert runner.calls == []


def test_broker_marks_bad_stored_credential_invalid_and_stops_retries(tmp_path):
    runner = FakeRunner({
        "return_code": 1, "stdout": "", "stderr": "",
        "timed_out": False, "duration_seconds": 0.01,
        "authentication_failed": True,
    })
    broker = broker_module.AdminBroker(
        FakeStore(), FakeVerifier(), runner,
        audit_path=tmp_path / "audit.jsonl",
        invalid_marker=tmp_path / "credential-invalid",
    )
    peer = broker_module.Peer(42, 1000, 1000)

    result = broker.handle(peer, request())
    next_result = broker.handle(peer, request())

    assert result["error"] == "administrator_credential_invalid"
    assert next_result["error"] == "administrator_credential_invalid"
    assert len(runner.calls) == 1
    restarted = broker_module.AdminBroker(
        FakeStore(), FakeVerifier(), FakeRunner(),
        audit_path=tmp_path / "audit.jsonl",
        invalid_marker=tmp_path / "credential-invalid",
    )
    assert restarted.handle(broker_module.Peer(42, 1000, 1000), request())["error"] == (
        "administrator_credential_invalid"
    )
    assert restarted.runner.calls == []
    assert (tmp_path / "credential-invalid").exists()


@pytest.mark.parametrize(
    "patch",
    [
        {"executable": "relative"},
        {"cwd": "relative"},
        {"argv": ["bad\x00arg"]},
        {"environment": {"LD_PRELOAD": "/tmp/x.so"}},
        {"environment": {"PATH": "/tmp"}},
        {"timeout_seconds": 301},
    ],
)
def test_broker_rejects_invalid_operation_before_execution(tmp_path, patch):
    runner = FakeRunner()
    broker = broker_module.AdminBroker(
        FakeStore(), FakeVerifier(), runner,
        audit_path=tmp_path / "audit.jsonl",
        invalid_marker=tmp_path / "credential-invalid",
    )
    payload = request()
    payload.update(patch)

    result = broker.handle(broker_module.Peer(42, 1000, 1000), payload)

    assert result == {"ok": False, "error": "invalid privileged operation"}
    assert runner.calls == []


def test_sudo_runner_keeps_secret_out_of_argv_and_environment():
    password = b"synthetic-only-secret"
    captured = {}

    class FakeProcess:
        def __init__(self, command, **kwargs):
            captured["command"] = command
            captured["environment"] = kwargs["env"]
            self.stdin = TrackingInput()
            captured["stdin"] = self.stdin
            self.stdout = io.BytesIO(
                broker_module.STDIN_READY_MARKER + b"synthetic-only-secret"
            )
            self.stderr = io.BytesIO()
            self.pid = 999
            self.returncode = 0

        def wait(self, timeout=None):
            return 0

    runner = broker_module.SudoRunner(
        broker_module.BrokerConfig(1000, 1000, (), ()), popen=FakeProcess
    )
    result = runner.execute(
        "/usr/bin/id", ["-u"], bytearray(password), cwd="/tmp",
        environment={"LANG": "C"}, stdin=b"command-input", timeout=5,
    )

    joined_argv = "\x00".join(captured["command"])
    assert password.decode() not in joined_argv
    assert password.decode() not in json.dumps(captured["environment"])
    assert captured["stdin"].written == password + b"\ncommand-input"
    assert b"[REDACTED]" in result["stdout"].encode()
    assert result["authentication_failed"] is False


class TrackingInput:
    def __init__(self):
        self.written = b""
        self.closed = False

    def write(self, value):
        self.written += bytes(value)

    def flush(self):
        return None

    def close(self):
        self.closed = True


def test_broker_status_exposes_only_safe_metadata(tmp_path):
    broker = broker_module.AdminBroker(
        FakeStore(), FakeVerifier(), FakeRunner(), audit_path=Path("/dev/null"),
        invalid_marker=tmp_path / "credential-invalid",
    )

    result = broker.handle(broker_module.Peer(42, 1000, 1000), {"op": "status"})

    assert result == {"ok": True, "status": "available"}
    assert "password" not in json.dumps(result)


def test_owner_status_does_not_require_privileged_execution_identity(tmp_path):
    broker = broker_module.AdminBroker(
        FakeStore(), FakeVerifier(False), FakeRunner(), audit_path=tmp_path / "audit.jsonl",
        invalid_marker=tmp_path / "credential-invalid",
    )
    result = broker.handle(broker_module.Peer(123, 1000, 1000), {"op": "status"})
    assert result == {"ok": True, "status": "available"}


@pytest.mark.parametrize(
    ("store", "expected"),
    [
        (FakeStore(b""), "not_enrolled"),
        (
            type(
                "BrokenStore",
                (),
                {
                    "exists": lambda self: True,
                    "retrieve": lambda self: (_ for _ in ()).throw(RuntimeError()),
                },
            )(),
            "degraded",
        ),
    ],
)
def test_broker_status_reports_only_safe_vault_state(tmp_path, store, expected):
    broker = broker_module.AdminBroker(
        store, FakeVerifier(), FakeRunner(), audit_path=Path("/dev/null"),
        invalid_marker=tmp_path / "credential-invalid",
    )
    assert broker.handle(broker_module.Peer(42, 1000, 1000), {"op": "status"}) == {
        "ok": True, "status": expected
    }


def test_client_protocol_uses_af_unix_and_never_sends_a_password(tmp_path):
    path = tmp_path / "admin.sock"
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(path))
    server.listen(1)
    captured = {}

    def serve():
        conn, _ = server.accept()
        with conn:
            size = struct.unpack("!I", _recv_exact(conn, 4))[0]
            captured.update(json.loads(_recv_exact(conn, size)))
            body = json.dumps({
                "ok": True, "operation_id": "op", "return_code": 0,
                "stdout": "", "stderr": "", "timed_out": False,
                "duration_seconds": 0.0,
            }).encode()
            conn.sendall(struct.pack("!I", len(body)) + body)

    worker = threading.Thread(target=serve)
    worker.start()
    result = PrivilegedExecutor(path).execute(
        "/usr/bin/id", ["-u"], task_id="task", action_id="action"
    )
    worker.join(timeout=2)
    server.close()

    assert result.return_code == 0
    assert captured["op"] == "execute"
    assert "password" not in json.dumps(captured).lower()
    assert "secret" not in captured


def test_hidden_enrollment_validates_encrypts_verifies_and_atomically_installs(monkeypatch):
    password = "synthetic-enrollment-only"
    monkeypatch.setattr("local_ai_assistant.admin.enrollment.getpass.getpass", lambda _: password)
    calls = []

    def sudo_executor(command, *, secret, input, timeout, env):
        calls.append((command, bytes(secret), input, env))
        assert bytes(secret) == password.encode()
        operation = command[1:]
        if "/usr/bin/test" in operation:
            return broker_module.subprocess.CompletedProcess(command, 1, b"", b"")
        if "encrypt" in operation:
            assert input == password.encode()
            return broker_module.subprocess.CompletedProcess(command, 0, b"synthetic-ciphertext", b"")
        if "decrypt" in operation:
            return broker_module.subprocess.CompletedProcess(command, 0, password.encode(), b"")
        return broker_module.subprocess.CompletedProcess(command, 0, b"", b"")

    lifecycle = CredentialLifecycle(
        sudo_executor=sudo_executor,
        store="/tmp/friday-admin-test/credential",
        store_dir="/tmp/friday-admin-test",
    )
    lifecycle.enroll_from_terminal()

    assert all(password not in "\x00".join(call[0]) for call in calls)
    assert all(password.encode() not in call[3].get("PATH", "").encode() for call in calls)
    assert all(call[1] == password.encode() for call in calls)
    assert any("encrypt" in call[0] and call[2] == password.encode() for call in calls)
    assert any("decrypt" in call[0] for call in calls)
    assert any(
        "/usr/bin/mv" in call[0] and call[0][-1] == "/tmp/friday-admin-test/credential"
        for call in calls
    )
    assert all(call[0][0] == "/usr/bin/sudo" for call in calls)


def test_enrollment_fails_closed_on_invalid_password(monkeypatch):
    monkeypatch.setattr("local_ai_assistant.admin.enrollment.getpass.getpass", lambda _: "bad")
    calls = []

    def sudo_executor(command, **kwargs):
        calls.append(command)
        return broker_module.subprocess.CompletedProcess(
            command, 1, b"", b"sudo: interactive authentication is required"
        )

    lifecycle = CredentialLifecycle(sudo_executor=sudo_executor)
    with pytest.raises(EnrollmentError, match="credential validation failed"):
        lifecycle.enroll_from_terminal()
    assert not any("encrypt" in command for command in calls)


def test_enrollment_failure_categories_are_fixed_and_do_not_echo_stderr():
    assert _safe_failure_category(b"sudo: interactive authentication is required") == (
        "sudo authorization was unavailable to the privileged command"
    )
    assert _safe_failure_category(b"systemd-creds: host key unavailable secret-value") == (
        "systemd host credential key operation failed"
    )
    assert _safe_failure_category(b"private unexpected diagnostic secret-value") == (
        "privileged command reported an unclassified error"
    )


def test_sudo_enrollment_runner_separates_password_and_command_stdin(tmp_path):
    fake_sudo = tmp_path / "sudo-fixture"
    fake_sudo.write_text(
        "#!/usr/bin/python3\n"
        "import os,sys\n"
        "assert sys.stdin.buffer.readline().rstrip(b'\\n') == b'fixture-password'\n"
        "index = sys.argv.index('--') + 1\n"
        "os.execv(sys.argv[index], sys.argv[index:])\n"
    )
    fake_sudo.chmod(0o700)
    result = _run_sudo_command(
        [str(fake_sudo), "/bin/cat"],
        secret=bytearray(b"fixture-password"), input=b"command-stdin",
        timeout=3, env={"PATH": "/usr/bin:/bin", "LANG": "C"},
    )
    assert result.returncode == 0
    assert result.stdout == b"command-stdin"
    assert b"fixture-password" not in result.stdout + result.stderr


def test_update_uses_one_hidden_input_and_replaces_encrypted_record(monkeypatch):
    password = "synthetic-updated-password"
    prompts = []
    monkeypatch.setattr(
        "local_ai_assistant.admin.enrollment.getpass.getpass",
        lambda prompt: prompts.append(prompt) or password,
    )
    calls = []

    def sudo_executor(command, *, secret, input, timeout, env):
        calls.append((command, bytes(secret), input))
        operation = command[1:]
        if "/usr/bin/test" in operation:
            return broker_module.subprocess.CompletedProcess(command, 0, b"", b"")
        if "encrypt" in operation:
            return broker_module.subprocess.CompletedProcess(command, 0, b"new-ciphertext", b"")
        if "decrypt" in operation:
            return broker_module.subprocess.CompletedProcess(command, 0, password.encode(), b"")
        return broker_module.subprocess.CompletedProcess(command, 0, b"", b"")

    lifecycle = CredentialLifecycle(
        sudo_executor=sudo_executor, store="/tmp/friday-admin-test/credential", store_dir="/tmp/friday-admin-test"
    )
    lifecycle.enroll_from_terminal(update=True)

    assert len(prompts) == 1 and "new administrator password" in prompts[0]
    assert all(call[1] == password.encode() for call in calls)
    assert any("mv" in " ".join(command) and command[-1].endswith("/credential") for command, _, _ in calls)


def test_cli_lifecycle_refuses_noninteractive_input(monkeypatch):
    class NotTerminal(io.StringIO):
        def isatty(self):
            return False

    monkeypatch.setattr("local_ai_assistant.admin.enrollment.sys.stdin", NotTerminal())
    monkeypatch.setattr("local_ai_assistant.admin.enrollment.sys.stderr", NotTerminal())
    monkeypatch.setattr(
        "local_ai_assistant.admin.enrollment.getpass.getpass",
        lambda *_: pytest.fail("hidden input must not be requested without a terminal"),
    )
    assert enrollment_main(["enroll"]) == 2


def test_revoke_requires_local_hidden_validation_and_removes_only_credential(monkeypatch):
    password = "synthetic-revoke-only"
    monkeypatch.setattr("local_ai_assistant.admin.enrollment.getpass.getpass", lambda _: password)
    calls = []

    def sudo_executor(command, *, secret, input, timeout, env):
        calls.append((command, bytes(secret), input))
        return broker_module.subprocess.CompletedProcess(command, 0, b"", b"")

    lifecycle = CredentialLifecycle(sudo_executor=sudo_executor, store="/tmp/friday-admin-test/credential")
    lifecycle.revoke_from_terminal()
    assert calls[0][0][-4:] == ["/usr/bin/rm", "-f", "--", "/tmp/friday-admin-test/credential"]
    assert all(password not in "\x00".join(command) for command, _, _ in calls)
    assert all(secret == password.encode() for _, secret, _ in calls)


def test_candidate_client_policy_excludes_production_friday():
    policy = json.loads(
        (Path(__file__).parents[2] / "config/services/friday-admin-clients.example.json")
        .read_text()
    )
    allowed = policy["system_units"] + policy["user_units"]
    assert allowed == ["friday-owner-sovereign-probe.service"]
    assert "friday-local-ai.service" not in allowed


def test_main_process_verifier_checks_configured_systemd_main_pid():
    calls = []
    unit = "friday-owner-sovereign-probe.service"

    def command_runner(command, **kwargs):
        calls.append(command)
        return broker_module.subprocess.CompletedProcess(
            command, 0, "4242\n", ""
        )

    config = broker_module.BrokerConfig(
        os.getuid(), os.getgid(), (unit,), ()
    )
    with tempfile.TemporaryDirectory(prefix="friday-admin-proc-") as temporary:
        fake_proc = Path(temporary) / "4242"
        fake_proc.mkdir()
        (fake_proc / "cgroup").write_text(f"0::/user.slice/{unit}\n")
        verifier = broker_module.MainProcessVerifier(
            config, command_runner=command_runner, proc_root=Path(temporary)
        )

        assert verifier.allows(broker_module.Peer(4242, os.getuid(), os.getgid()))
        assert calls[0][2] == unit
        assert not verifier.allows(broker_module.Peer(4242, os.getuid() + 1, os.getgid()))


def test_broker_has_no_raw_secret_export_operation(tmp_path):
    broker = broker_module.AdminBroker(
        FakeStore(), FakeVerifier(), FakeRunner(), audit_path=tmp_path / "audit.jsonl",
        invalid_marker=tmp_path / "credential-invalid",
    )
    result = broker.handle(
        broker_module.Peer(42, 1000, 1000), {"op": "read_admin_secret"}
    )
    assert result == {"ok": False, "error": "unsupported administrator operation"}


def test_broker_restart_keeps_persistent_store_and_requires_no_reenrollment(tmp_path):
    store = FakeStore()
    audit_path = tmp_path / "audit.jsonl"
    first = broker_module.AdminBroker(
        store, FakeVerifier(), FakeRunner(), audit_path=audit_path,
        invalid_marker=tmp_path / "credential-invalid",
    )
    second = broker_module.AdminBroker(
        store, FakeVerifier(), FakeRunner(), audit_path=audit_path,
        invalid_marker=tmp_path / "credential-invalid",
    )

    assert first.handle(broker_module.Peer(42, 1000, 1000), {"op": "status"}) == {
        "ok": True, "status": "available"
    }
    result = second.handle(broker_module.Peer(42, 1000, 1000), request())
    assert result["ok"] is True
    assert second.runner.calls[0][2] == b"synthetic-admin-password"


def test_systemd_credential_store_persists_ciphertext_retrieves_and_revokes(tmp_path, monkeypatch):
    password = b"synthetic-vault-password"
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        output = b"encrypted-test-blob" if "encrypt" in command else password
        return broker_module.subprocess.CompletedProcess(command, 0, output, b"")

    path = tmp_path / "friday-admin-password"
    store = broker_module.SystemdCredentialStore(path, runner=runner)
    store.replace(bytearray(password))
    assert path.read_bytes() == b"encrypted-test-blob"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert password not in path.read_bytes()
    monkeypatch.setattr(store, "exists", lambda: True)
    assert store.retrieve() == bytearray(password)
    assert all(password not in "\x00".join(command).encode() for command, _ in calls)
    assert all(password not in json.dumps(kwargs.get("env", {})).encode() for _, kwargs in calls)
    store.revoke()
    assert not path.exists()


def test_executor_output_reader_enforces_hard_buffer_limit():
    output = bytearray()
    broker_module._read_limited(io.BytesIO(b"x" * (broker_module.MAX_OUTPUT + 8192)), output)
    assert len(output) == broker_module.MAX_OUTPUT


def test_private_network_probe_embedded_control_is_valid_python():
    compile(probe_module.NETWORK_CHECK_SCRIPT, "<offline-egress-probe>", "exec")


def test_qualification_root_file_checks_owner_group_and_exact_contents():
    calls = []
    contents = b"friday-owner-sovereign-qualification\n"

    class Executor:
        def execute(self, executable, argv, **kwargs):
            calls.append((executable, argv, kwargs))
            output = "0:0\n" if kwargs["action_id"] == "root-file-inspect" else (
                contents.decode() if kwargs["action_id"] == "root-file-content-inspect" else ""
            )
            return type("Result", (), {"return_code": 0, "timed_out": False, "stdout": output})()

    probe_module._root_file_probe(Executor())
    assert [call[2]["action_id"] for call in calls] == [
        "root-file-write", "root-file-inspect", "root-file-content-inspect", "root-file-remove"
    ]
    assert calls[0][0] == "/usr/bin/tee"
    assert calls[0][2]["stdin"] == contents
    assert calls[1][1][1] == "%u:%g"


def test_restart_persistence_waits_for_broker_pid_change(monkeypatch):
    calls = []

    class Executor:
        def execute(self, executable, argv, **kwargs):
            action = kwargs["action_id"]
            calls.append(action)
            output = "100\n" if action == "broker-pid-before-restart" else (
                "200\n" if action == "broker-pid-after-restart" else ""
            )
            return type("Result", (), {
                "return_code": 0, "timed_out": False,
                "stdout": output, "stderr": "",
            })()

    monkeypatch.setattr(
        probe_module.AdministratorCredentialService, "status",
        lambda _self: probe_module.AdminCredentialStatus.AVAILABLE,
    )
    monkeypatch.setattr(probe_module, "_root_file_probe", lambda _executor: calls.append("root-file-after-restart"))
    probe_module._restart_persistence_probe(Executor())
    assert calls[0] == "broker-pid-before-restart"
    assert "broker-restart-schedule" in calls
    assert "broker-pid-after-restart" in calls
    assert calls[-1] == "root-file-after-restart"


def test_sudo_timestamp_invalidation_is_passwordless_control(monkeypatch):
    captured = {}

    def run(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return broker_module.subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(probe_module.subprocess, "run", run)
    probe_module._invalidate_sudo_timestamp()
    assert captured["command"] == ["/usr/bin/sudo", "-K"]
    assert "input" not in captured
    assert "password" not in repr(captured).lower()


def test_practice_lab_bubblewrap_cannot_see_credential_store_or_broker_socket():
    sandbox = BubblewrapSandbox()
    if sandbox.capabilities().filesystem is not CapabilityState.SUPPORTED:
        pytest.skip("Bubblewrap filesystem isolation is unavailable")
    script = (
        "import json,os,pathlib; print(json.dumps({"
        "'credential_store':pathlib.Path('/etc/credstore.encrypted').exists(),"
        "'broker_socket':pathlib.Path('/run/friday-admin/broker.sock').exists(),"
        "'session_bus':pathlib.Path('/run/user/1000/bus').exists(),"
        "'credential_environment':any(('PASS' in k or 'CREDENTIAL' in k or 'SECRET' in k) for k in os.environ)}))"
    )
    with tempfile.TemporaryDirectory(prefix="friday-admin-sandbox-test-") as directory:
        result = sandbox.run(
            ("/usr/bin/python3", "-c", script),
            Path.cwd(),
            Path(directory),
            resources=ResourcePolicy(wall_seconds=10, cpu_seconds=5, max_processes=20),
            network=NetworkPolicy.DENY,
        )
    assert result.return_code == 0, result.stderr
    assert json.loads(result.stdout) == {
        "credential_store": False,
        "broker_socket": False,
        "session_bus": False,
        "credential_environment": False,
    }
