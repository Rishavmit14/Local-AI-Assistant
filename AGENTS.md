# Local-AI-Assistant Engineering Instructions

These instructions apply to the entire repository. Read this file and `CODEX_HANDOFF.md` before changing code. A more deeply nested `AGENTS.md` or `AGENTS.override.md` may add stricter instructions for its subtree.

## Project invariants

- Keep the runtime local-first. The default is the local Qwen model through the localhost llama.cpp OpenAI-compatible API; paid inference and Codex must never become runtime requirements.
- Preserve working behavior before refactoring. Treat tests and actual machine files as implementation truth and document differences from historical prose.
- Never track GGUF or other model weights, virtual environments, FAISS indexes, embeddings, user documents, caches, secrets, generated logs, patches, or temporary/database state.
- Do not bypass Git isolation for coding-agent mutations. Patch preflight, structural/static validation, tests, bounded repair, auditability, and deterministic rollback are foundational requirements.
- Prefer parsers, Git, tests, linters, and build tools over model inference for deterministic facts.
- OpenClaw is not part of Friday's target architecture. Do not add OpenClaw dependencies, integrations, adapters, roadmap items, implementation work, or design assumptions unless the project owner explicitly reverses this decision.
- Never silently remove roadmap capabilities. Update status without deleting scope.
- Work one roadmap stage at a time. Stage 0 must be reviewed before Stage 1 begins.

## Change workflow

1. Inspect relevant source and current Git status.
2. Keep generated state under `var/` or an environment-configured external path.
3. Add or update tests for behavior changes.
4. Run `python -m pytest` and `scripts/maintenance/verify-repository.sh` when dependencies are available.
5. Review `git diff --check`, tracked files, and Git status for prohibited or unrelated content.
6. Require explicit human review for high-risk auth, payment, smart-contract, security, destructive migration, or deployment changes.

Do not perform destructive cleanup of external working directories. Do not install or enable systemd units without explicit approval; render and review templates first.
