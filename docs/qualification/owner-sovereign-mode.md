# Phase 19 — Local Intelligence Sovereignty qualification (row 59)

**Result:** QUALIFIED within the bounded candidate scope recorded in
`docs/qualification/PRODUCT_INTEGRATION_MATRIX.md`.

## Owner Sovereign native qualification

The one-time owner enrollment was available through the trusted broker. The
candidate policy allowed only `friday-owner-sovereign-probe.service` (UID/GID
1000); no production Friday unit was trusted. The probe ran as the normal owner
process and used the enrolled credential internally through the root broker.
Production `friday-local-ai.service` does not use this broker, and production
credential UI/API integration is outside this qualification.

The native sequence invalidated sudo authentication timestamps before
credential use. With no password prompts, it created a disposable root-owned
file, verified UID/GID `0:0` and exact content, then removed it; created and
inspected a transient systemd service, then stopped it; restarted the broker and
proved persisted-credential reuse; then created a transient system-level
namespace anchor with `PrivateNetwork=yes`, `PrivateUsers=no`, owner UID/GID,
and `NoNewPrivileges=yes`. The service ran under UID/GID 1000, remained in the
host user namespace, used a distinct network namespace, and could not reach an
external IP or host-loopback Friday/Qwen listeners. Candidate units and
qualification files were removed after evidence capture.

Deterministic tests cover enrollment/update/revoke lifecycle, encrypted vault
storage and retrieval, same-UID unauthorized-client rejection, protocol and
result/audit redaction, sudo secret separation from argv/environment, broker
restart recovery, and Bubblewrap isolation from the credential store, broker
socket, session bus, and credential environment. Practice Lab's disposable DENY
path and model-facing role authority negative control remain intact. The broker
has no raw-secret retrieval API; the frontend and API expose no enrollment,
retrieve, or export path. Trusted unrestricted root is explicitly inside the
trust boundary and is not claimed to be unable to recover the credential.

## Integrated local-Qwen scenario

The qualification used the configured loopback Qwen model and explicit offline
embedding flags. It passed:

- local `Role.REASONING` over a synthetic Research record containing an
  injection attempt and a deterministic evidence marker;
- real local Conversation with synthetic Memory-backed recall;
- Career Forge teacher cognition, deterministic attempt evaluation, and
  CognitiveController routing;
- CodeRAG indexing/reload and Qwen planning against a disposable local source
  repository, with no plan persisted;
- Reviewer and Security roles over synthetic untrusted instructions, with no
  model-facing privileged `execute` method;
- a representative GitHub transport failure inside its own transient private
  network service using only a synthetic token, followed immediately by a
  successful local Conversation.

No owner private documents were scanned. All created Research, Memory, Career
Forge, CodeRAG, and planner state was synthetic and disposable. The E2E does not
prove every Friday capability works offline, browser-process network isolation,
first-time installation/download availability, or confidentiality against
trusted root. Optional external features remain optional and fail closed.

## Product and machine boundaries

ADR 0014 remains authoritative: core reasoning and the exercised knowledge,
learning, planning, and orchestration paths use owner-controlled local compute.
The optional external adapter did not become a reasoning fallback. No host
network settings changed. Production Friday on `127.0.0.1:8765`, production
Qwen on `127.0.0.1:8080`, and the protected Pocket/Anna checkout were not
modified or restarted. Owner Career Forge state was not used by the synthetic
scenario.

The host's encrypted systemd credential, broker service/socket, and exact
qualification evidence are local runtime state, not repository artifacts. The
qualification probe policy trusts only the disposable probe unit. Credential
plaintext is never recorded in qualification output or documentation.
