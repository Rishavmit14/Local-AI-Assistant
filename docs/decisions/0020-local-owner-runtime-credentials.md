# ADR 0020: Local owner runtime credentials are operational configuration

## Status

Accepted

## Context

Stage 17's native objective dispatch is intentionally disabled unless a
localhost gateway has a bearer-token digest and `request_execution` scope. The
previous default-deny qualification correctly proved that an unconfigured
runtime cannot dispatch work, but treating local credential provisioning itself
as a repeated human-approval stop prevented authorized roadmap qualification.

## Decision

The owner authorizes Codex to generate and configure Friday's local-only runtime
credentials, authentication material, least-privilege scopes, and local service
configuration when needed for canonical roadmap implementation, testing,
operation, or qualification. Plaintext credentials remain protected local state
outside the repository and never appear in Git, logs, API/UI projections, or
documentation. The configuration grants only the scope required by the current
capability and has a clear revoke path: remove the protected credential or
disable gateway enablement, then reload the local service.

This is operational authority, not a security exception. Bearer authentication
and authorization, exact approved-plan identity, isolated worktree ownership,
validation, rollback, audit/task history, and Git authority remain mandatory.
The runtime remains localhost-bound and fail-closed without its configuration.
It does not authorize external credentials, paid services, public exposure,
authentication bypasses, destructive security changes, or unrelated high-risk
actions.

## Consequences

Stage 17 can perform controlled authenticated live execution through its
existing canonical route while preserving the separation between Codex's local
engineering authority and Friday's runtime authorization boundary. The
cinematic UI remains a bounded review/observation surface and receives no
credential-management or privileged execution control.
