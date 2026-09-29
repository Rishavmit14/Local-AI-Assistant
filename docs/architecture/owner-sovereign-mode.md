# Owner Sovereign Mode

**State:** implemented and qualified as a bounded Phase 19 candidate
Owner Sovereign boundary. Production Friday is not yet trusted by this broker;
production administration UI/API integration remains unqualified.

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
key. A root-owned service decrypts it internally for privileged use. Plaintext
exists only in trusted service memory and the short-lived credential-use path.
The host key is not TPM-sealed on this machine: systemd reports partial TPM
support with firmware and driver unavailable. This protects the at-rest file
from ordinary untrusted processes, not from root or compromise of the trusted
broker.

Enrollment/update use a local hidden terminal prompt. The credential is
validated with sudo-rs and supplied to sudo only via stdin. Normal executor
pathways keep it out of argv, environment, unit command lines, application
state, model prompts, APIs, logs, and audit records. The target command's stdin
is delivered only after sudo has authenticated and started the target. Memory
handling is best-effort; Python and child processes do not provide guaranteed
physical erasure.

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

This is a normal-interface boundary; it does not claim to withstand malicious
commands executed by trusted root. Friday's trusted administrative runtime is
part of the machine's highest-trust computing base. Its compromise may expose
the credential, owner data, security configuration, and arbitrary root access;
the owner knowingly accepts this consequence for uninterrupted local autonomy.

Browser JavaScript has no OS credential interface. Friday API routes expose
only non-secret availability metadata; they cannot enroll, retrieve, or export
the credential. Web pages, documents, OCR, RAG, research, and plugins remain
untrusted input and cannot authorize raw-secret disclosure.

## Lifecycle and audit

The encrypted credential survives Friday process restarts and host reboots.
Candidate broker/socket unit definitions are installed under `/run` and are not
enabled at boot; production Friday is excluded during candidate qualification.
Credential update validates the new value before atomically replacing the
encrypted credential. Revoke removes the encrypted item and disables candidate
broker access. Status reports only `not_enrolled`, `available`, `invalid`,
`degraded`, or `unavailable`.

Each operation records timestamp, task/action identity, executable, sanitized
arguments, outcome, return code, duration, and bounded output metadata without
recording the credential. Privileged operations remain subject to the owner
task's existing authorization and scope; confirmation follows the consequences
of the requested change rather than the use of root.

## Qualification state

The owner-enrolled credential was retrieved internally by the trusted broker
before and after broker restart. With sudo timestamps invalidated, qualification
performed and removed a disposable root-owned file, inspected and removed a
transient system service, and created/inspected/removed a normal-owner
`PrivateNetwork=yes`, `PrivateUsers=no`, `NoNewPrivileges=yes` namespace anchor.
External and host-loopback probes were denied. Deterministic tests cover
credential update/revoke, secret exclusion from argv/environment/audit and
client protocol, same-UID process rejection, Bubblewrap isolation, and
systemd-credential persistence.

The integrated Phase 19 run used the configured local Qwen for Conversation,
synthetic Research reasoning, synthetic Memory-backed Conversation, Career
Forge cognition/evaluation, CodeRAG and planning against a disposable local
repository, Reviewer/Security roles, and immediate local recovery after an
optional GitHub adapter failed inside a private network namespace. No owner
documents were scanned and no model plan was persisted. See
`docs/qualification/owner-sovereign-mode.md` for evidence and explicit limits.
