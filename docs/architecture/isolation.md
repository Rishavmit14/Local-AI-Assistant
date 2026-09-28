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

Checkpoints record HEAD, staged and unstaged binary patches, a bounded untracked inventory/archive, modes, symlinks, and hashes. Schema 2 checkpoints cover non-ignored untracked files; ignored task-local data is preserved by restore because it is outside the checkpoint model. Older schema 1 checkpoints remain readable by the CLI but are not eligible for transactional restore. Archives have file-count and per-file ceilings; patch-plus-archive content is capped at 2 GiB by default, with at most 16 checkpoints per task. Storage has private permissions, and member-by-member restoration refuses parent symlinks and non-file objects. Restore performs a task-worktree-only reset/clean and recreates the exact checkpoint state. It never cleans the canonical repository.

### Transactional task-checkpoint restore (Phase 15A)

`TransactionalRollbackService` is the only supported checkpoint mutation
kernel. It validates the canonical task, repository, task ID, plan hash,
worktree identity/lifecycle, and current checkpoint HEAD; rejects canonical,
protected, active, promoted, terminal, and recovery-required states; then holds
the same per-task advisory lock used by worktree lifecycle transitions and
cleanup. Under that lock it creates a uniquely named schema-2 safety checkpoint,
persists `rollback_in_progress`, restores the target, and verifies HEAD, staged
and unstaged patch identities, non-ignored untracked inventory/content/modes,
and symlink targets. Failure triggers one compensating restore and identical
verification. A verified compensation reports `failed_recovered`; double
failure persists `recovery_required`. A process crash leaves the durable
`rollback_in_progress` marker, which the recovery scanner reports for operator
inspection. The CLI and authenticated owner-review adapter use this kernel.
The adapter exposes only safe checkpoint projections, validates a separate
server-side `request_rollback` bridge authority, and never gives Astra the
Gateway bearer. Its exact review is bound to the task, plan, checkpoint
identity, current worktree fingerprint, owner principal, and expiry. Execute
atomically consumes the review before invoking the kernel; exact idempotency
keys recover completed results without a second restore. Checkpoint artifacts
and lifecycle metadata are fsynced before destructive work. TaskStatus is not
changed by this internal worktree operation. Phase 15B qualified this bounded
behavior through disposable native-Astra review/execute; the synthetic source
repository was preserved and canonical audit/explanation records reconstructed.
Row 55 is qualified only for authenticated isolated-task checkpoint rollback.
It does not imply general undo or row 56 interruption recovery.

### Unified interruption read model (Phase 16)

`TaskRecoveryProjectionService` is a task-scoped, read-only composition over
TaskHistory, its admission-claim and rollback ledgers, exact ObjectiveService
links, task isolation metadata, execution-artifact records, and the optional
current-process execution Future. It adds no persistence authority and performs
no lease pruning, reconciliation, cleanup, execution, or rollback. History,
Objectives progress, Phase 14 explanations, and the exact-ID recovery endpoint
share the same projection instance and deterministic classification.

An in-progress lifecycle with no currently observed Future is an interrupted
lifecycle requiring inspection. A claim is reported as active or expired by
its fixed one-hour planning or 24-hour execution lease; expiry permits later
admission but proves neither worker death nor task outcome. Process-local
`not_started` or absent worker observation is unknown, especially after API
restart. Missing isolation metadata is unknown rather than healthy. Missing
worktrees, corrupt or rejected metadata, `rollback_in_progress`,
`recovery_required`, `cleanup_pending`, objective-plan disagreement, terminal
execution evidence not reflected in TaskHistory, and successful or recovered
rollback results are each preserved as separate bounded facts. The DTO exposes
no paths, raw metadata, artifact content, environment, or credentials.

Startup does not reconcile terminal artifacts. The existing explicit
`ArtifactImporter` remains the only supported reconciliation path: it validates
the exact task, plan, starting commit, repository identity and artifact schema,
then uses digest idempotency before finalizing canonical history. An
unreconciled terminal artifact is shown for inspection; the read model never
invokes the importer. No universal resume, execution retry, rollback retry, or
automatic cleanup is authorized.

## Sandbox and resources

`SandboxBackend` supports capability-aware Bubblewrap and native implementations. Bubblewrap is selected only if its actual namespace probe works. The native backend provides task HOME/TMP/cache, a minimal environment and trusted system PATH, closed inherited descriptors, process sessions, tree termination, bounded output, wall/CPU/process/open-file/file-size/address-space limits, but only partial filesystem isolation and no network isolation.

Strong isolation is required by default. If mount/network namespace isolation is unavailable, autonomous repository execution blocks. Explicit lower-trust policy can permit native execution with `network=allowed`, but it must not be described as contained untrusted execution.

## Promotion and recovery

Reviewed, validated, current, and committed states are bound by a deterministic temporary-index tree identity. Any later file, mode, symlink, untracked, branch, or canonical-HEAD change invalidates promotion. Isolation-owned Git calls disable hooks, prompts, editors, pagers, signing, system/global configuration, and reject repository/shared Git filter or LFS attributes rather than executing clean/smudge programs. Stage 8 produces a task-branch commit and never merges main.

Interrupted `creating`, `executing`, `validating`, rollback-in-progress, or cleanup states become `recovery_required`. Recovery inspection never auto-resumes. Task-local advisory locks prevent duplicate ownership and cleanup/execution/rollback/promotion races. Stage 7 timeline events record isolation backend/capability, network policy, checkpoint, cleanup, cancellation, rollback, and promotion readiness without exposing user-facing absolute worktree paths.

## Limitations

- The current host denies the Bubblewrap user-namespace probe despite having the binary.
- Native fallback cannot restrict filesystem reads or networking and therefore fails strong policy.
- cgroup v2 is visible but delegated controllers are not assumed; rlimits are enforced without root.
- `RLIMIT_NPROC` is per real UID (and may not constrain privileged users), not a task cgroup PID quota. Native process groups cannot guarantee containment of a deliberately daemonized process that creates a new session.
- `RLIMIT_AS` limits virtual address space, not GPU memory; mmap-heavy runtimes may fail as resource/environment failures rather than ordinary code defects.
- Native mode can see host `/proc`, Unix sockets, shared Git administration paths, and devices. This is why the default strong-autonomy policy blocks it.
- Git LFS/filter repositories are rejected for isolated automated checkout/promotion; no filter process or network download is attempted.
- Disk-directory quotas and seccomp filters are not implemented.
- No automatic merge, conflict resolution, package installation, submodule fetch, scheduler, or Stage 9 interface exists.
