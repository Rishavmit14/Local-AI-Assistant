# ADR 0001: Typed environment configuration

Status: Accepted for Stage 1

## Context

The imported applications used module globals and absolute project paths. That preserved the original machine but made isolated testing and alternate deployments difficult.

## Decision

Use frozen standard-library dataclasses collected by `AppConfig`. Load values from `LOCAL_AI_*` environment variables at process startup and inject the resulting snapshot into LLM, RAG, indexing, agent, and UI boundaries. Keep Stage 0 constants and entry-point files as documented compatibility aliases.

## Consequences

No additional configuration dependency is required. Tests can use temporary paths and fake model dependencies. Environment changes after component construction do not mutate a running component. YAML model profiles remain deployment documentation; environment-backed `AppConfig` is the Python runtime authority.
