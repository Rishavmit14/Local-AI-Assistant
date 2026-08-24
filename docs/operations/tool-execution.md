# Controlled Tool Execution

Inspect tools and policies:

```bash
local-ai-execute show-tools
local-ai-execute show-policy /tmp/plan.json
local-ai-execute show-history /tmp/execution.json
```

Dry-run a persisted plan:

```bash
local-ai-execute execute demo /tmp/plan.json --dry-run --max-steps 8
```

The transaction-integrated mutation path is:

```bash
local-ai-code-agent demo "request" --tool-loop \
  --apply --branch --test --validate --rollback-on-fail \
  --auto-commit --approve-risk PRINTED_PLAN_TOKEN
```

Use the existing `--approve-risk PRINTED_PLAN_TOKEN` spelling with the coding agent. `--human-review` runs the proposed actions without mutation. High/critical plans require the exact hash printed for that plan.

Allowed command families cover pytest, Ruff, mypy/Pyright, Cargo, Forge, npm/pnpm/yarn tests, TypeScript, ESLint, read-only Git, and bounded search. Pipes, chaining, redirects, substitutions, environment injection, absolute/out-of-repository arguments, package installation, service control, force push, and destructive filesystem commands are rejected.

Timeouts and loop limits use `LOCAL_AI_*` execution settings documented in `.env.example`. Timed-out process groups receive termination and then forced termination if needed.
