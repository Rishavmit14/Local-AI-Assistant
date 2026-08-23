# Planner Operations

Planning is dry-run by default and stores JSON under the ignored code-index plan directory unless `--output` is supplied.

```bash
local-ai-plan analyze demo "Fix login_user"
local-ai-plan generate demo "Fix login_user" --output /tmp/login-plan.json
local-ai-plan validate demo /tmp/login-plan.json
local-ai-plan show-files /tmp/login-plan.json
local-ai-plan show-symbols /tmp/login-plan.json
local-ai-plan show-risk /tmp/login-plan.json
local-ai-plan show-approval /tmp/login-plan.json
local-ai-plan export /tmp/login-plan.json /tmp/login-plan-copy.json

local-ai-code-agent demo "Fix login_user" --plan-only
local-ai-code-agent demo "Fix login_user" --approve-risk PRINTED_PLAN_TOKEN
```

The coding agent always refreshes deterministic indexes, generates/persists/validates a plan, classifies risk, and makes an approval decision before asking Qwen for a patch. `--plan-only` stops before patch generation. Validation errors always stop. High/critical plans print a token derived from the exact validated plan; `--approve-risk` must repeat that token, so approval cannot silently transfer to changed plan content. This does not bypass branch, patch-check, structural validation, tests, rollback, or merge approval.

`validate` also checks the persisted repository identity and starting commit against the current target. A stale or cross-repository plan must be regenerated.

Dependency and migration detection is planning-only and never installs packages or runs migrations. Planning artifacts are lightweight JSON, not the Stage 7 history database. Treat plans as potentially sensitive repository metadata and keep them in ignored runtime storage.
