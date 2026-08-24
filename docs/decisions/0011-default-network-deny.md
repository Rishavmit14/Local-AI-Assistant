# ADR 0011: Autonomous repository code defaults to network denied

- Status: accepted for Stage 8
- Date: 2026-08-24

## Decision

Sandbox policy has `deny`, `loopback_only`, and `allowed` states. Repository tests and build scripts default to `deny`. Friday orchestration may contact llama-server, but repository subprocesses do not automatically receive localhost or external network access. Network permission must be explicit, risk-classified, and auditable.

If the selected backend cannot enforce the requested policy, execution fails. Native process limits cannot enforce network denial; therefore they cannot satisfy strong-isolation policy. Loopback-only also fails unless a trusted backend can configure that namespace precisely.

## Consequences

Network-dependent tests need an explicitly reviewed policy. Friday does not install dependencies or initialize submodules as a side effect of validation. Local service credentials and database connection variables are absent from the child environment.
