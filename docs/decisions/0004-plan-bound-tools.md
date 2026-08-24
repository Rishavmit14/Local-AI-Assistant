# ADR 0004: Tool execution is plan-bound and deny-by-default

Status: Accepted for Stage 4

## Context

Stage 3 plans describe approved scope, but model-generated actions remain untrusted. More operational power is safe only after actual edits can be compared with deterministic policy.

## Decision

Tools are registered typed capabilities with permission, mutation, timeout, input, audit, and approval metadata. The model selects a named tool through strict JSON; it never receives a callable or raw shell. Mutations require the current repository/commit, exact plan approval when required, allowed paths/symbols, patch preflight, and pre/post Git-diff scope checks.

Commands are parsed into argv and matched against explicit families. Shell composition, redirects, substitution, environment injection, executable paths, package/service operations, and destructive commands are denied. Git diff remains mutation truth.

Executable approval does not imply arbitrary argument approval. Mutating formatter flags, alternate runners/plugins, external Git diff/output modes, symlink-following searches, Forge FFI/network forks, and repository-local wrappers are denied. Resolved path arguments must remain under the active repository.

## Consequences

Scope rejection cannot be overridden by Qwen. Replanning that would widen scope stops for a newly validated plan and renewed approval. Stage 4 uses lightweight JSON history; databases, worktrees, containers, multi-agent roles, and broad security review remain later stages.
