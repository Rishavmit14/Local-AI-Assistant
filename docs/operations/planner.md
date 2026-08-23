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
local-ai-code-agent demo "Fix login_user" --approve-risk
```

The coding agent always refreshes deterministic indexes, generates/persists/validates a plan, classifies risk, and makes an approval decision before asking Qwen for a patch. `--plan-only` stops before patch generation. Validation errors always stop. High/critical plans require explicit `--approve-risk`; this does not bypass branch, patch-check, structural validation, tests, rollback, or merge approval.

Dependency and migration detection is planning-only and never installs packages or runs migrations. Planning artifacts are lightweight JSON, not the Stage 7 history database. Treat plans as potentially sensitive repository metadata and keep them in ignored runtime storage.
