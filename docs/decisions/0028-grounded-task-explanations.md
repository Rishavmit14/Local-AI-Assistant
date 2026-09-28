# ADR 0028: Grounded task explanations are deterministic read-only projections

## Status

Accepted for bounded Astra product integration qualification.

## Context

Task history and objective progress already retain canonical lifecycle evidence,
but owner-facing surfaces do not combine those records into a bounded answer to
“what happened?” A general model prompt over broad task details would expose
unneeded request, artifact, repository, and event-summary fields and could
conflate evidence with inference.

## Decision

Add `TaskExplanationService` as a typed allowlist over one exact canonical task
identity and, only when explicitly linked, its objective. Reuse task history,
objective records, and isolation recovery inspection. Bound the timeline to 20
events and retain source labels and explicit limitations. Exclude raw requests,
arbitrary summaries, commands, artifact paths/content/metadata, affected-file
scope, and unrelated stores. Present event order without causal claims.

Expose only read-only GET routes and an exact-ID deterministic conversation
route. Do not call Qwen for these explanations. Keep objective/task states,
plan/approval/execution/outcome states, and recovery status distinct. No new
approval, execution, rollback, restore, desktop, shell, or Git authority is
introduced.

## Consequences

Answers are reproducible and auditable from canonical records, and unknown or
missing evidence remains explicit. The route explains one identity at a time;
it does not establish worker liveness, cross-store causality, or facts absent
from task/objective/isolation records. Future generated interpretation would
require a separate design and must remain clearly distinguished from records.
