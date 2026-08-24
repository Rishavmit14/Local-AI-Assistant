# Isolation operations

Inspect capabilities before enabling autonomous mutation:

```bash
local-ai-isolation capabilities
local-ai-isolation recovery
```

Create a worktree only for an already validated exact plan:

```bash
local-ai-isolation create REPOSITORY TASK STARTING_COMMIT PLAN_HASH \
  --approval-token PLAN_HASH
local-ai-isolation status REPOSITORY TASK
local-ai-isolation checkpoint REPOSITORY TASK PLAN_HASH before-risk
local-ai-isolation rollback REPOSITORY TASK PLAN_HASH before-risk
local-ai-isolation cleanup REPOSITORY TASK --delete-branch
```

`smoke` executes only a fixed no-op; the CLI intentionally has no arbitrary-command subcommand. With default network denial, smoke fails if the active backend cannot enforce that policy.

Worktrees, metadata, locks, checkpoints, task HOME/TMP/cache, and reports belong under the ignored configured runtime roots. Cleanup is explicit and path-contained. Successful task branches remain for review. Do not manually remove a live task directory; inspect locks, Git's worktree list, task history, and recovery findings first.

The child environment starts empty except for a trusted system `PATH`, locale/terminal/timezone fields, task HOME/TMP/XDG/cache settings, Git non-interactive safeguards, and explicitly approved variables. It does not inherit interpreter startup variables, proxies, Git overrides, SSH/cloud/package-manager credentials, database URLs, tokens, or the user's real HOME. Package installation, submodule update, network access, service commands, and arbitrary shell remain disallowed.

Repositories using Git clean/smudge filters or Git LFS fail closed before isolated checkout or promotion. Checkpoint creation also fails explicitly when its configured file-count or byte ceilings would be exceeded. These failures require operator review; do not bypass them by manually staging or copying files.
