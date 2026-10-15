# ADR 0052 — Owner-authenticated HTTP learning-path creation

- Status: Accepted for the Stage 29 code release; production deployment pending
- Date: 2026-10-15
- Extends: ADR 0039 (local Owner trust), ADR 0042 (Owner-bound Conversation)

## Context

The DLP generation and direct curriculum-create HTTP routes could persist a
learning path without the established Owner session, Origin, or CSRF checks.
Deterministic path-creation intents on HTTP Conversation reached the same
generator and were an alternate route around any protection limited to the
generation endpoint. Learn's explicit Create request also lacked the Owner
CSRF header. Path creation persists durable DLP state and may invoke the local
curriculum model, so browser-origin checks alone are insufficient.

## Decision

Guard both HTTP path-creation routes and explicit DLP-creation intents on HTTP
Conversation with the existing `context_owner(request, mutation=True)` helper.
That helper requires a loopback Host, an exact Origin in
`LOCAL_AI_PROJECT_EXECUTION_ALLOWED_ORIGINS`, a valid existing
`friday_project_session`, and its matching `X-Friday-CSRF` token. Reject before
calling the DLP service or model. Do not grant a Gateway action scope or accept
arbitrary Origins. Learn uses the existing restore/unlock endpoints, keeps the
CSRF token in memory, and requires the Owner to select Create after
authentication; authentication never creates a path. Unauthorized requests do
not write DLP state or invoke the model.

Trusted in-process services remain direct service callers. No supported
unauthenticated CLI creation route exists. Other DLP operations on an existing
path retain their current route contracts and are outside this bounded change.
This decision does not claim that all DLP mutations are Owner-authenticated.

## Consequences and rollout

The Stage 29 Learn client is compatible with the older API because the older
generation route ignores the additional CSRF header, but that pair remains
vulnerable until the hardened API is installed. Code publication does not
activate this boundary. The hardened API rejects the
Stage 28 Learn generation request, which sends no Owner CSRF proof. The new UI
and API therefore require a coordinated rollout after the protected live API
source, task clearance, service state, and rollback path are independently
qualified. This accepted decision does not authorize deployment.

The DLP architecture document records the exact boundary and the remaining
route scope.
