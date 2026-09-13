# ADR 0026: Practice Lab uses fail-closed Bubblewrap execution

- Status: accepted
- Date: 2026-09-13

## Decision

Career Forge Practice Lab runs learner Python only with the existing
`BubblewrapSandbox`, a fresh temporary exercise directory, the system Python in
isolated mode, a denied network namespace, and explicit small process, CPU,
wall-time, memory, output, file, and descriptor bounds. The Lab probes the
backend's process, filesystem, and network guarantees and is unavailable rather
than falling back to the native backend when any guarantee is absent.

Drafts, bounded run metadata, and submitted attempts are stored beside the
existing Learner Twin in the same Career Forge SQLite authority. Submitted code
uses the existing governed attempt/evaluation/evidence contract; test success
never advances mastery.

## Consequences

The Lab has no shell endpoint, source-repository mount, production-database
mount, inherited credential environment, or default network. Python is the
initial exercise language; the typed assignment contract admits later runtimes
without treating this first workspace as a generic IDE or unrestricted executor.
