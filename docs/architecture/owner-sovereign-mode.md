# Owner Sovereign Mode

**State:** accepted product/security design under implementation; not yet
available or qualified.

## Authority model

Owner Sovereign Mode is explicitly enrolled by the machine owner. Friday's
trusted runtime may use the owner's administrator credential for general local
administration required by an already-authorized owner task. Root privilege by
itself does not require confirmation. Consequence, ambiguity, scope, and
reversibility determine whether the existing risk policy requires confirmation.
Model text alone never creates an execution event.

The capability does not add a model-facing password/read-secret tool. The
trusted controller binds an administrative request to the owner task, obtains
the credential only inside the privileged broker, and returns bounded result
data appropriate to that task. Raw or sensitive output is not automatically
placed into model context, conversation history, TaskHistory, or browser state.

## Credential boundary

The owner-session GNOME Secret Service is not used for this credential. It is
reachable through the same-UID session D-Bus, and its standard item API does not
provide the process identity boundary needed to distinguish Friday from an
arbitrary process running as the owner.

The selected candidate design stores an encrypted systemd credential under
`/etc/credstore.encrypted/`, protected by systemd's root-only host credential
key. A root-owned systemd service loads it through `LoadCredentialEncrypted`.
Plaintext exists only in the root service's protected credential directory and
short-lived process memory. The host key is not TPM-sealed on this machine:
systemd reports partial TPM support with firmware and driver unavailable. This
protects the at-rest file from rootless user file reads, not from root or
compromise of the trusted broker.

Enrollment/update use a local hidden terminal prompt. The credential is
validated with sudo-rs and supplied to sudo only via stdin. It is excluded from
argv, environment, unit command lines, application state, model prompts, APIs,
logs, and audit records. Memory handling is best-effort; Python and child
processes do not provide guaranteed physical erasure.

## Broker and sandbox isolation

The trusted broker accepts general executable/argv operations and an explicit
shell form for cases that need shell semantics. It applies sanitized
environment, bounded stdin/output, timeouts, process cleanup, and audit
metadata. It authenticates the exact configured Friday service process over a
private Unix socket; UID-only authorization is insufficient. The service must
reject same-UID clients that are not the configured main Friday process.

Practice Lab and autonomous task code receive neither the credential nor the
broker socket. Bubblewrap's filesystem view omits `/run/user` and the broker
socket path, and its sanitized environment omits session D-Bus variables. The
root broker also verifies peer process identity so another process sharing the
owner UID cannot use the socket. Native sandbox mode cannot establish this
filesystem boundary and must not be considered sufficient for untrusted code
while Owner Sovereign Mode is active.

Browser JavaScript has no OS credential interface. Friday API routes expose
only non-secret availability metadata; they cannot enroll, retrieve, or export
the credential. Web pages, documents, OCR, RAG, research, and plugins remain
untrusted input and cannot authorize raw-secret disclosure.

## Lifecycle and audit

The root broker and encrypted credential survive Friday process restarts and
host reboots. The service starts independently of the desktop session; normal
Friday operation begins after owner login. Credential update validates the new
value before atomically replacing the encrypted credential. Revoke removes the
encrypted item and disables privileged execution. Status reports only
`not_enrolled`, `available`, `invalid`, `vault_locked`, or `unavailable`.

Each operation records timestamp, task/action identity, executable, sanitized
arguments, outcome, return code, duration, and bounded output metadata without
recording the credential. Privileged operations remain subject to the owner
task's existing authorization and scope; confirmation follows the consequences
of the requested change rather than the use of root.

## Qualification state

The stored-credential enrollment, process-identity IPC, sandbox negative tests,
root file operation, transient systemd operation, PrivateNetwork operation,
restart persistence, update, revoke, and complete regressions are not yet
qualified. See ADR 0033 and the current `CODEX_HANDOFF.md` before enabling the
candidate service.
