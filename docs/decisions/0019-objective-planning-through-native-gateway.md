# ADR 0019: Objectives request plans through the native gateway

## Status

Accepted

## Context

Stage 17 adds a durable objective loop to Friday's cinematic interface. The
objective journal needs to request planning without introducing a presentation
planner, accepting a filesystem path, or duplicating task-history authority.

## Decision

After an owner explicitly resumes an objective, Friday reserves one task ID and
configured repository ID atomically on the objective. The native gateway
materializes that plan-only task through the existing history idempotency
transaction before asking `IntegrationGatewayService` to plan it. The
gateway continues to own repository mapping, task creation, and delegation to
the validated local planner. Task history remains the source of plan tokens,
approval, execution, validation, rollback, and audit state.

If local planning fails, the objective remains `planning` with its canonical task
ID. A later retry plans the same task; it cannot create a duplicate task or bind
a replacement task. The presentation API accepts either a pre-existing canonical
task ID for compatibility or a configured repository ID for this guarded flow;
it never accepts a path or a plan hash.

Lifecycle and binding writes compare the observed state, task ID, and token in
the database update itself. Stale writers fail closed; an earlier read check
alone must not allow a late resume/bind to overwrite cancellation or another
binding. The two journals do not share a transaction: a persisted reservation
is materialized idempotently under source `friday-objective` and its task ID.
Retry and cancellation recover that exact reservation, including after a crash
between journal writes. A ready persisted plan is rebound without regeneration.
Single-inference admission remains process-local, not a distributed lease.

## Consequences

The cinematic UI gains a bounded plan-request control but no approval or
execution control. The presentation runtime has an in-process native gateway
adapter and closes its event bridge on shutdown. This deliberately reuses the
existing local Qwen planner and does not add a second general-purpose model or
remote runtime dependency.
