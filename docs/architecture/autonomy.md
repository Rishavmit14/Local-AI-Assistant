# Friday autonomous execution

## Stage 17 foundation

`ObjectiveService` persists an owner objective locally before any planning or
execution begins. Objectives are bounded, resumable into `planning`, and
explicitly cancellable. This record is not a tool runner: it has no shell,
desktop, network, planner, validation, or Git authority.

An objective may record one exact validated plan hash and move to `planned`.
The hash is provenance only: Friday does not load, invoke, mutate, or trust a
plan merely because it is attached to an objective.

Later Stage 17 work may connect an objective only to Friday's existing validated
planner, isolated execution loop, approval, cancellation, validation, rollback,
and task-history boundaries. It must not create a parallel execution path.
