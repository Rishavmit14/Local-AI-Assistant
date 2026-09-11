# Friday autonomous execution

## Stage 17 foundation

`ObjectiveService` persists an owner objective locally before any planning or
execution begins. Objectives are bounded, resumable into `planning`, and
explicitly cancellable. This record is not a tool runner: it has no shell,
desktop, network, planner, validation, or Git authority.

An objective may bind once to a canonical task-history record that is already
`awaiting_approval` or `approved` and has an exact plan token. It stores both
that task ID and the token before moving to `planned`. The native API accepts
only the task ID; it cannot inject a free-form hash. This provenance is still
not authority: Friday does not load, invoke, mutate, or trust a plan merely
because it is attached to an objective.

Cancelling a bound objective first delegates cancellation to that same canonical
task-history record. If the task cannot be cancelled, the objective remains
nonterminal; Friday never reports a cancelled objective while leaving its linked
task runnable.

Later Stage 17 work may connect an objective only to Friday's existing validated
planner, isolated execution loop, approval, cancellation, validation, rollback,
and task-history boundaries. It must not create a parallel execution path.
