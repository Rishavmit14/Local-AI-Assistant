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
- A capability is not accepted merely because an experiment worked. Acceptance requires the selected implementation, relevant tests, canonical architecture/roadmap/history updates, a clean commit, push to the configured GitHub remote, and remote-HEAD verification.
- Remove rejected prototypes, obsolete helpers, abandoned configuration, and competing inactive implementations before capability acceptance unless an explicit documented architecture reason requires more than one implementation.
- Treat Git history and tests as implementation truth, `ARCHITECTURE.md` as current/target design, `ROADMAP.md` as capability/status truth, `HISTORY.md` as accepted chronology, ADRs as durable decisions, and `CODEX_HANDOFF.md` as bootstrap/vision context.

## Change workflow

1. Inspect relevant source and current Git status.
2. Keep generated state under `var/` or an environment-configured external path.
3. Add or update tests for behavior changes.
4. Run `python -m pytest` and `scripts/maintenance/verify-repository.sh` when dependencies are available.
5. Review `git diff --check`, tracked files, and Git status for prohibited or unrelated content.
6. Before completing a capability, update the canonical documentation that changed: roadmap status, current architecture, project history, relevant operations docs, and an ADR when a durable design decision was made.
7. Remove rejected experimental implementations before the final acceptance commit.
8. Require explicit human review for high-risk auth, payment, smart-contract, security, destructive migration, or deployment changes.
9. After an accepted capability is committed, push it and verify the configured remote branch resolves to the exact accepted commit before beginning the next major capability.

Do not perform destructive cleanup of external working directories. Do not install or enable systemd units without explicit approval; render and review templates first.

<!-- FRIDAY_GOVERNANCE_START -->

## Friday session bootstrap and repository governance

These rules are repository policy and are authoritative for Codex, ChatGPT,
coding agents, and human-assisted sessions working on Friday.

### Mandatory session bootstrap

Before planning or changing Friday:

1. Read the nearest applicable `AGENTS.md` / `AGENTS.override.md`.
2. Read `CODEX_HANDOFF.md`, `ARCHITECTURE.md`, `ROADMAP.md`, and `HISTORY.md`.
3. Read the relevant files under `docs/architecture/` and `docs/decisions/`
   for the subsystem being changed.
4. Verify the current Git branch, HEAD, configured `origin`, worktree
   cleanliness, and relevant runtime/service state.
5. Treat committed repository documentation and accepted recovery commits as
   the source of truth when chat history, agent memory, or older handoffs
   disagree.

Do not require the user to reconstruct previously accepted architecture or
workflow decisions when the repository already records them.

### Stage branch and `main` policy

- Each major roadmap stage has its own `stage-N/<capability>` branch.
- Never begin work belonging to a new stage on the previous stage's branch.
- Every accepted subtask/capability must have an explicit commit message that
  identifies the stage/subtask or clearly identifies the accepted capability.
- After a subtask passes its complete acceptance gate:
  1. commit it on its owning stage branch;
  2. push that stage branch to GitHub;
  3. fast-forward `main` to the exact same accepted commit;
  4. push `main`;
  5. fetch/verify that the stage branch and `main` both point to the intended
     accepted recovery commit.
- `main` therefore represents the most recent fully qualified, known-good
  Friday state, even when the surrounding major stage remains active.
- Do not merge rejected, experimental, unqualified, or dirty work into `main`.
- Do not force-push accepted history. A force-with-lease is permitted only for
  an explicitly proven branch-pointer repair, after the preserved branch/main
  recovery path is verified.
- Preserve completed stage branches on GitHub so the branch structure mirrors
  the roadmap and remains auditable.

### Documentation is part of the acceptance gate

No feature, capability, architecture change, runtime/deployment change, or
meaningful behavioral change is considered accepted until the canonical docs
are updated in the same accepted change.

At minimum:

- **New feature/capability:** update `ROADMAP.md`, `HISTORY.md`, and
  `CODEX_HANDOFF.md`; update architecture docs when the feature changes system
  structure, boundaries, data flow, runtime behavior, or ownership.
- **Architecture/design change:** update `ARCHITECTURE.md`, the relevant
  `docs/architecture/*.md`, and an existing/new ADR under `docs/decisions/`
  when a durable design decision is made; also reconcile roadmap/history/
  handoff status.
- **Runtime/deployment/service change:** update the relevant architecture or
  operations documentation, tracked sanitized config/service examples, known
  deployment requirements, `HISTORY.md`, and `CODEX_HANDOFF.md`.
- **New limitation, risk, deferred item, or known defect:** record it in the
  appropriate roadmap/handoff/history location instead of leaving it only in
  chat or test logs.
- **Acceptance/qualification:** record what was proven, important limitations,
  and the accepted recovery commit where practical.
- **Removed/rejected approach:** remove stale canonical claims and record the
  accepted replacement when the distinction matters for future maintenance.

Do not create parallel ledgers when an existing canonical document already owns
the information. Keep the existing canonical docs reconciled.

A commit/push/main-integration gate must fail if the implementation changed but
the relevant canonical documentation is stale.

### Execution / recovery discipline

- Prefer deterministic tests before fixes.
- Use rollback snapshots before production modifications.
- Do not commit/push until the implementation, qualification, docs, and required
  regression gates pass.
- Do not start the next major capability until the previous accepted checkpoint
  is remotely recoverable.
- Keep failed/abandoned competing approaches out of the final accepted tree
  unless intentionally retained and documented.
- For user-run terminal work, provide self-contained downloadable `.sh` scripts
  that log complete stdout/stderr to `/AI/tools/friday-chatgpt-logs/`, show live
  output, print the final log path and preserve exit status.
- Do not stop/restart Friday unless the stage explicitly requires it; when no
  restart occurs, state that Friday remains running/listening.
<!-- FRIDAY_GOVERNANCE_END -->
