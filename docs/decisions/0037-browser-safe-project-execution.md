# ADR 0037: Browser-safe Project approval and execution

- **Status:** Accepted
- **Date:** 2026-09-30

## Context

Career Forge Projects reached the canonical Objective plan boundary, but the
browser could not supply the Gateway bearer required by `SUBMIT_APPROVAL` and
`REQUEST_EXECUTION`. Giving that bearer to page JavaScript would make it
readable to scripts, browser storage, logs, and extensions. Calling Gateway or
execution services through an unauthenticated presentation route would instead
bypass the accepted authorization boundary.

## Decision

Use a same-origin Presentation API owner session for browser approval and
execution. A separately configured local owner unlock credential establishes a
short-lived volatile session. The browser carries a Secure-on-HTTPS,
HttpOnly, SameSite=Strict cookie and a CSRF header. Every mutation verifies the
loopback Host and exact configured Origin. The Gateway bearer remains
server-side.

At approval time, the backend loads the Objective and current TaskHistory plan,
requires `SUBMIT_APPROVAL` in the configured Gateway scope set, compares the
browser's task ID and plan hash with authoritative state, records exact-plan
approval, and transitions the task only after approval evidence exists. At
execution time, it independently requires `REQUEST_EXECUTION`, then delegates
through ObjectiveService and Gateway; canonical history verifies approval and
exact current plan again at admission. Duplicate dispatch remains governed by
Gateway execution claims. TaskHistory records approval and execution
authorization evidence without credentials.

The existing Objectives/Gateway routes retain their bearer-authenticated
contract for trusted clients. Browser sessions add no automatic approval,
localhost trust, test-only route, or execution exemption. The project session
is process-local and expires after ten minutes; restart revokes sessions.

## Consequences

- Browser execution requires explicit local owner session configuration and
  allowlisted same-origin loopback origins; missing configuration fails closed.
- Exact plan approval and Gateway execution scope are distinct gates.
- Approval is bound to the current TaskHistory hash, task, repository, and
  starting commit. A replaced plan must be approved again.
- Owner unlock material is submitted transiently to the same-origin backend;
  the Gateway bearer is never sent to or returned to page JavaScript.
- This bridge qualifies authorization and dispatch only. It does not by itself
  qualify artifact submission, assessment, or the complete owner product path.
