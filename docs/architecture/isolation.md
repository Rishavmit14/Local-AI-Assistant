# Repository isolation and safer autonomous execution

## Trust boundary

```text
validated exact plan + approval
  → task/repository/commit/plan-bound worktree
  → baseline checkpoint
  → command allowlist AND sandbox policy
  → scoped mutation
  → actual diff / ScopeGuard
  → isolated validation and review
  → exact state identity
  → hook-free task-branch commit
  → promotion ready (never automatic merge)
```

Repository code, test hooks, build scripts, package scripts, Makefiles, Cargo `build.rs`, and Git hooks are untrusted. Sandboxing reduces risk; it does not prove arbitrary code safe.

## Worktrees and checkpoints

`WorktreeManager` stores worktrees only below `LOCAL_AI_WORKTREE_ROOT/<repo-id>/<task-id>`. A separate metadata record binds task, repository, branch, base commit, plan hash, current commit, lifecycle, and cleanup. Safe identifiers, resolved containment, branch collision checks, locks, and Git worktree metadata prevent cross-task attachment.

Checkpoints record HEAD, staged and unstaged binary patches, untracked inventory/archive, modes, symlinks, and hashes. Restore performs a task-worktree-only reset/clean and recreates the exact checkpoint state. It never cleans the canonical repository.

## Sandbox and resources

`SandboxBackend` supports capability-aware Bubblewrap and native implementations. Bubblewrap is selected only if its actual namespace probe works. The native backend provides task HOME/TMP/cache, an allowlisted environment, process sessions, tree termination, bounded output, wall/CPU/process/open-file/file-size/address-space limits, but only partial filesystem isolation and no network isolation.

Strong isolation is required by default. If mount/network namespace isolation is unavailable, autonomous repository execution blocks. Explicit lower-trust policy can permit native execution with `network=allowed`, but it must not be described as contained untrusted execution.

## Promotion and recovery

Reviewed, validated, current, and committed states are bound by a deterministic temporary-index tree identity. Any later file, mode, symlink, untracked, branch, or canonical-HEAD change invalidates promotion. Stage 8 produces a task-branch commit and never merges main.

Interrupted `creating`, `executing`, `validating`, or cleanup states become `recovery_required`. Recovery inspection never auto-resumes. Task-local advisory locks prevent duplicate ownership and cleanup/execution races. Stage 7 timeline events record isolation backend/capability, network policy, checkpoint, cleanup, cancellation, rollback, and promotion readiness without exposing user-facing absolute worktree paths.

## Limitations

- The current host denies the Bubblewrap user-namespace probe despite having the binary.
- Native fallback cannot restrict filesystem reads or networking and therefore fails strong policy.
- cgroup v2 is visible but delegated controllers are not assumed; rlimits are enforced without root.
- Disk-directory quotas and seccomp filters are not implemented.
- No automatic merge, conflict resolution, package installation, submodule fetch, scheduler, or Stage 9 interface exists.
