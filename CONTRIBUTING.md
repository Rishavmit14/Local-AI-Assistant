# Contributing

Start by reading `AGENTS.md`, `CODEX_HANDOFF.md`, `ARCHITECTURE.md`, and `ROADMAP.md`. Open focused changes against the current roadmap stage; do not combine unrelated milestones.

Use Python 3.11 or newer:

```bash
scripts/bootstrap/bootstrap.sh
source .venv/bin/activate
python -m pytest
scripts/maintenance/verify-repository.sh
python -m ruff check src tests app.py local_llm.py rag.py code_rag.py code_agent.py ui
```

Keep runtime files under `var/` or paths configured with `LOCAL_AI_*` environment variables. Never add private documents, model weights, indexes, secrets, caches, logs, or database state. Include tests, explain user-visible behavior and risk, and list validation performed in each pull request.
