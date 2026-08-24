# ADR 0012: Friday-native integration gateway

## Status

Accepted for Stage 9 implementation.

## Decision

External systems connect through a small, authenticated Friday-native gateway. It exposes typed task/history/status capabilities and delegates to existing services. GitHub uses explicit repository mappings and injectable clients. A controlled MCP-compatible boundary may expose the same typed capabilities, but MCP is not execution authority.

The default API binds to localhost and privileged actions require scoped bearer authentication. External issue/comment content is untrusted data. Stage 3–8 approval, ScopeGuard, validation, review, worktree/sandbox, and Git promotion rules remain authoritative.

## Consequences

Friday remains independently operable offline. Duplicate orchestration, sessions, routing, and security state are avoided. Public exposure, live webhook ingress, and broad external automation remain deployment concerns outside this stage.
