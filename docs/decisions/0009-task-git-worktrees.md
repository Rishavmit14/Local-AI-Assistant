# ADR 0009: Task-scoped Git worktrees isolate autonomous mutation

- Status: accepted for Stage 8
- Date: 2026-08-24

## Decision

Every Stage 8 autonomous mutating run receives a dedicated `friday/task/<task-id>` branch and a worktree beneath the configured Friday runtime root. Identity metadata binds the task ID, canonical repository identity, starting commit, exact plan hash, branch, worktree, and lifecycle. The canonical checkout is never the autonomous command working directory.

Worktree creation rejects dirty canonical repositories, stale commits, branch/path collisions, traversal, symlink escape, and mismatched persisted identity. Successful work remains on its isolated branch for explicit promotion; Stage 8 never automatically merges main. Git hooks are bypassed for internal checkout and automated commits because repository hooks are untrusted executable code. Submodules are not initialized, updated, or fetched automatically.

## Consequences

Worktrees share Git objects without copying complete repositories. Multiple tasks may use independent worktrees, but each remains bound to its original base. Canonical drift, branch divergence, or changed promotion evidence fails explicitly and is never silently rebased or conflict-resolved.

Execution reports identify the isolated worktree for auditability, while task
history retains the canonical repository identity. Such evidence is accepted
only when its task, exact plan hash, and starting commit match the existing
canonical task. Failed/cancelled executor paths finalize canonical task history
before cleanup; a cleaned worktree is recovery evidence, not a terminal result.
