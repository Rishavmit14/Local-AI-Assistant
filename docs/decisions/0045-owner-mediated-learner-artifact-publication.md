# ADR 0045: Owner-mediated learner-artifact publication

- Status: Accepted design; one bounded real publication qualified; Stage 27 acceptance pending
- Date: 2026-10-05

## Context

Career Forge already has a deterministic review and explicit approval lifecycle
for public evidence. The existing gateway owns GitHub credentials and external
publication, but the Projects browser has no safe owner-session path to invoke
it. A successful API response must also prove the intended remote commit and
pull-request identity rather than trust a transport response alone.

Career Forge evidence must preserve assistance and task provenance. A Friday-
assisted artifact can be recorded as full-demonstration evidence only with its
exact successful task commit and blob identity; this record does not represent
independent learner assessment or advance mastery.

## Decision

Expose publication from the Projects UI only for an approved candidate bound to
a successful Friday task and explicitly configured repository. Browser
requests use the local Owner session, Origin/CSRF checks, and server-side
`GITHUB_WRITE` scope; no gateway bearer credential is sent to the browser.
Preserve the existing bearer gateway path for authorized non-browser clients.
The owner-reviewed publication plan binds the artifact path and Git blob, exact
promoted task commit, configured destination, base branch, and pull-request
operation. After publication, verify the remote branch SHA equals the task's
exact final commit, verify the remote artifact blob, and verify the pull
request's repository, head branch and SHA, base repository and branch, and
trusted web URL before persisting `published`. Any identity mismatch remains a
durable reconciliation condition, never success. Empty destinations may be
bootstrapped only after authenticated metadata confirms the exact repository is
empty and the promoted commit descends from the approved starting commit.

## Consequences

The server can resolve the owner-selected GitHub CLI OS-keyring credential by
reference and verifies its login and exact public writable repository at
startup. `GITHUB_WRITE`, the exact allowed repository, and the publication
purpose remain separately configured Gateway policy; the browser receives no
credential. One real publication to
`Rishavmit14/ML-AI-Engineering` was verified as PR #1 at the exact approved
commit and blob. The record reconstructed after candidate API restart and
browser reload. Deterministic fake transport remains the primary retry,
idempotency, and uncertain-side-effect recovery evidence; the real repository
was written only once. Full Stage 27 acceptance remains gated on final
regression/security checks and publication of the Stage 27 code recovery
commit.
