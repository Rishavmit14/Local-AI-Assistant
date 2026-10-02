# ADR 0039 — Persistent local single-user Owner trust

- Status: Accepted for the local single-user Stage 22 candidate
- Date: 2026-10-02
- Authority: explicit owner request replacing repeated manual unlocks for personal Friday
- Extends ADR 0037; interactive mode remains the default for unconfigured installations

## Decision

`LOCAL_AI_OWNER_TRUST_MODE=local_single_user` explicitly selects the personal
Unix-account trust boundary. Both API and trusted UI server receive the path
`LOCAL_AI_OWNER_CAPABILITY_FILE` and exact `LOCAL_AI_OWNER_INSTALLATION` root.
The backend creates a cryptographically random 256-bit capability outside Git
in an owner-owned 0700 directory and 0600 regular file. Ownership, permissions,
installation identity, link count, and symlink exclusion are checked before use.
No human login password is involved. A file is used because this service must
start unattended without depending on an unlocked desktop keyring.

The loopback UI server alone reads that file. Its proxy strips any incoming
capability header and injects its own only for the exact POST restoration route,
exact UI Host and Origin, and local socket peer. The backend independently
requires configured Origin/Host, loopback peer and the correct capability.
It returns an ephemeral HttpOnly/SameSite=Strict session cookie (Secure on HTTPS)
and a CSRF token with Cache-Control: no-store. The capability is never a browser
response, JavaScript build variable, URL, prompt, log field or Git artifact.

The API launcher binds 127.0.0.1 and disables forwarded-header trust. The UI
bridge rejects non-loopback configuration. Arbitrary remote clients, missing
capabilities and unconfigured/interactive deployments do not inherit trust.
The supported candidate adapter is the server-only Vite proxy; another UI
hosting adapter must implement this same boundary before enabling the mode.
Do not expose this development server or forward its port to remote clients.

Repeated and concurrent restoration requests within one API process reuse the
same unexpired browser session and CSRF token, avoiding cookie/CSRF races across
focus events and tabs. API restart or session expiry creates a fresh session.
Restoration grants only session identity. Exact-plan review/approval, current
plan hash, revoked approvals, SUBMIT_APPROVAL, REQUEST_EXECUTION, audit,
isolation, bounded repair, validation and rollback stay independently enforced.
Browser reload and periodic/focus restoration recover the same session while
valid and mint a fresh session after an API restart. No canonical task is
executed by restoration. Deleting/rotating the
capability stops new restoration immediately; restart the API to invalidate
already-issued ten-minute sessions, or use session lock for that browser.
Disabling the explicit mode and restarting both servers removes the bridge.

## Future machine privilege boundary

Owner UI identity is not root authority. Future laptop administration continues
through Friday's dedicated action/administrator broker with typed operations,
policy enforcement, OS-managed service authorization, audit and recovery. This
capability does not add shell concatenation, sudo passwords, NOPASSWD grants or
root access. ADR 0033's separately enabled Owner Sovereign broker remains its
own authority; this change neither enrolls nor reads its human credentials.

## Acceptance

Deterministic restoration/restart, private storage, origin/peer negatives,
server proxy stripping, CSRF, scope and exact-plan regressions are required.
Real browser reload and candidate API restart reconstructed the completed
FraudShield Project and returned the browser to an active Owner session without
a password prompt. The Stage 22 handoff records the secret/bundle audit and
complete execution/evidence lifecycle. This qualification does not extend the
mode beyond the explicitly configured local single-user installation.
