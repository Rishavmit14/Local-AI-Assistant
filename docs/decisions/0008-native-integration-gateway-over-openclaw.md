# ADR 0008: Native integration gateway over OpenClaw

Status: Accepted

## Context

OpenClaw was previously considered as a possible future integration; that direction is superseded and abandoned. Friday already owns deterministic planning, approval, execution, validation, review, Git transactions, task history, and operational policy. Adding a second orchestration runtime would duplicate sessions, routing, configuration, lifecycle ownership, and runtime dependencies while making Friday's policy boundary less clear.

## Decision

Friday remains independently operable. External systems connect through Friday-native interfaces and narrowly scoped adapters rather than controlling or replacing Friday's orchestration.

- GitHub issue, branch, pull-request, and CI support will be implemented natively.
- MCP is preferred where a standard tool or interface protocol is useful.
- A WebSocket/event interface may be added where event delivery materially helps.
- Direct external adapters require a clear justification and must preserve Friday's deterministic safety policies.
- OpenClaw is intentionally excluded from the target architecture, dependencies, integrations, adapters, and roadmap unless the project owner explicitly reverses this decision.

## Consequences

Friday has one authoritative planner/executor/session model and one configuration and policy boundary. Integrations can evolve without adding a second orchestration dependency or duplicating routing and runtime state. Stage 9 becomes **Native Integration Gateway / GitHub / External Interfaces**.
