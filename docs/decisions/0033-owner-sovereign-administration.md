# ADR 0033: Owner Sovereign Administration

- Status: accepted product/security design; implementation and qualification pending
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
  credential encryption. A root-owned system service loads it with
  `LoadCredentialEncrypted`; plaintext is available only inside that trusted
  service's protected credential directory and process memory. Do not store the
  password in Secret Service, application databases, config, environment, or
  ordinary files.
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
- Enrollment, update, and revoke are local hidden-input operations. Revoke
  removes the encrypted credential and disables broker access. The vault
  becomes available across Friday restarts and host boots; operations require
  the system service and host credential key to remain available.

## Accepted risk and consequences

Compromise of Friday's trusted controller or administrator broker can result in
full local machine compromise. The owner knowingly accepts this tradeoff for
uninterrupted local autonomy. Host-key encryption protects stored credential
material at rest from ordinary owner-user file reads; it is not a defense
against root, host-key theft, or a compromised trusted broker. This design does
not weaken global sudoers or polkit policy and does not add `NOPASSWD: ALL`.

Qualification must prove same-UID sandbox denial, exact trusted-process IPC
authorization, no secret leakage, timestamp-independent sudo operation,
restart recovery, update/revoke, and root/systemd/PrivateNetwork actions. The
capability remains unqualified until that evidence and the complete repository
acceptance gates pass. Row 59 remains IMPLEMENTED; no new matrix row is added.
