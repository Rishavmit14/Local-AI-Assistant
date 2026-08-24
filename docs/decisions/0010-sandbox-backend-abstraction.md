# ADR 0010: Capability-aware sandbox backend abstraction

- Status: accepted for Stage 8
- Date: 2026-08-24

## Decision

Repository commands execute through a typed `SandboxBackend`. Bubblewrap is preferred only after a real capability probe succeeds. Otherwise Friday exposes a constrained native backend with process groups, clean environment, task HOME/TMP/cache, bounded output, cancellation, timeouts, and POSIX resource limits.

Capability status is explicit: `supported`, `partial`, or `unavailable`. Native process isolation does not claim mount or network isolation. A policy requiring strong filesystem/network containment fails closed when bubblewrap/user namespaces are unavailable. Sandboxing never expands the Stage 4 command allowlist.

## Consequences

The current Ubuntu host has `/usr/bin/bwrap`, but its user-namespace probe is denied, so the active fallback is native and strong untrusted-code execution remains blocked by default. This is honest degraded operation, not a silent downgrade. A future container backend can implement the same interface without changing planner, ScopeGuard, validation, or approval authority.
