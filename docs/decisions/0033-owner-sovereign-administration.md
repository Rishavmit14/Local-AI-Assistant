# ADR 0033: Owner Sovereign Administration

- Status: accepted; bounded candidate Owner Sovereign boundary qualified for Phase 19; production integration unqualified
- Date: 2026-09-29

## Context

The owner explicitly requires Friday to retain and use a local administrator
credential for broad owner-requested machine administration without repeating
sudo/password prompts. Earlier product text made sudo/root use itself a
confirmation trigger. The owner has superseded that blanket rule. Model text
must still pass through Friday's trusted task controller; the credential must
not be disclosed to the model or untrusted subprocesses.

The host has GNOME Secret Service on the owner session bus. That bus is available
to same-UID processes, and the standard Secret Service interface does not
provide the process-identity boundary required for this credential. Bubblewrap
does not expose `/run/user` or the D-Bus address to its isolated learner/task
processes, but the Secret Service alone is not accepted as the administrator
credential boundary.

The host provides systemd 259 and `systemd-creds`. TPM probing reports partial
support without TPM firmware/driver availability. The systemd host credential
key is root-only and persistent; it is not TPM-sealed and therefore does not
protect against a privileged compromise of this installation.

## Decision

- Owner Sovereign Mode is an explicit local enrollment state. The trusted
  Friday runtime may use the enrolled administrator credential for general
  local operations. Root privilege alone does not trigger confirmation.
- Store only the encrypted credential at rest using systemd's host-key
  credential encryption. A root-owned system service decrypts it internally;
  plaintext is available only in that trusted service's memory and the
  short-lived credential-use path. Do not store the password in Secret Service,
  application databases, config, environment, or ordinary files.
- The system service exposes a private Unix-socket executor. It authenticates
  the exact trusted Friday service process, not merely UID 1000, before
  accepting a request. Isolated learner/autonomous subprocesses cannot access
  its socket. The exact process-authentication mechanism must be validated
  against the installed systemd and cgroup behavior before enrollment.
- The executor accepts a general executable plus argv, working directory,
  bounded stdin, sanitized environment, timeout, and output limits. An explicit
  shell operation may be used when shell semantics are necessary. The secret is
  supplied to sudo only over stdin and never appears in argv, environment,
  shell source, or logs. The broker does not offer a raw-secret retrieval API.
- Requests remain bound to an already-authorized owner task and its controller
  scope. Model output alone never starts execution. Confirmation is determined
  by consequence, ambiguity, and reversibility, not by root privilege.
- Privileged output is untrusted. The controller returns only bounded,
  redacted result data appropriate to the owner task; sensitive/raw output is
  not automatically copied into model context, history, or browser state.
- The trusted administrative runtime is part of the machine's highest-trust
  computing base. Unrestricted root can ultimately recover or disclose the
  credential; normal interfaces and untrusted components must not expose it,
  but this design does not claim confidentiality against a malicious or
  compromised trusted root executor.
- Enrollment, update, and revoke are local hidden-input operations. Revoke
  removes the encrypted credential and disables broker access. The vault
  becomes available across Friday restarts and host boots; operations require
  the system service and host credential key to remain available.

## Accepted risk and consequences

Owner Sovereign Mode intentionally makes Friday's trusted administrative
runtime part of the machine's highest-trust computing base. Compromise can
result in full machine compromise, owner-data access, credential disclosure,
security configuration changes, and arbitrary root execution. The owner
knowingly accepts this risk for uninterrupted full local autonomy. Host-key
encryption protects stored credential material at rest from ordinary untrusted
processes; it is not a defense against root, host-key theft, or a compromised
trusted broker. The normal credential API permits privileged use but has no
raw-secret export operation. This design does not weaken global sudoers or
polkit policy and does not add `NOPASSWD: ALL`.

Phase 19 qualification proved the enrolled runtime can use the persisted
credential after broker restart and with sudo timestamps invalidated; perform
root-owned file, transient systemd, and `PrivateNetwork=yes` actions; and deny
same-UID, Practice Lab, and untrusted model/document paths access to the
credential or broker. Fixture tests cover update and revoke lifecycle. The
integrated local-Qwen scenario exercised Conversation, synthetic Research,
Memory, Career Forge cognition/evaluation, CodeRAG/planning, Reviewer/Security,
authority negative controls, and optional external-adapter failure followed
by local recovery. See `docs/qualification/owner-sovereign-mode.md`.

This is a bounded candidate qualification, not a claim that every Friday
capability, administrative action, or first-install path has been proven
offline. The candidate policy trusts only the disposable qualification probe;
production `friday-local-ai.service` is not trusted by this broker and has no
qualified administrative UI/API integration. Trusted root remains inside the
highest-trust computing base and can recover the credential. Row 59 is
QUALIFIED only within the scope stated in the product integration matrix; no
new matrix row is added.
