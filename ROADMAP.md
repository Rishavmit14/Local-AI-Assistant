# Roadmap

Status legend: **Done** means evidenced in the imported Stage 0 code; **Partial** means a proven baseline exists; **Planned** means later work. No capability from `CODEX_HANDOFF.md` is omitted.

## Stage 0 — Repository bootstrap (**Done**)

Actual live files inventoried and imported; working behavior organized into a package; service units sanitized; documentation, dependency groups, bootstrap/install scripts, ignore rules, demo fixture, and tests added. Original deployments remain untouched. Bootstrap provenance and discrepancies are recorded under `docs/history/`.

## Stage 1 — Stabilize and package (**Done**)

Typed environment configuration, structured JSON/text logging, explicit errors/transaction models, dependency-injected package boundaries, canonical console commands, compatibility wrappers, dependency groups, and broad unit/integration/regression tests are implemented. The transactional Git foundation now has final success/failure verification and summaries, deterministic rollback/cleanup, `--keep-failed-branch`, `--human-review`, and approval-gated `--auto-merge`. Worktrees/checkpoints remain correctly scheduled for Stage 8.

## Stage 2 — Code intelligence (**Planned**)

Tree-sitter parsers and exact ranges for functions, classes, methods, structs, traits, interfaces, contracts, modules, imports, and exports. Add symbol embeddings, definition/reference/caller/implementation lookup, repository maps, dependency/call graphs, and incremental updates. Priority: Python, Rust, Solidity, TS/JS, SQL, C/C++, Java, Shell.

Current chunk-based code RAG is **Partial**: extensions, ignored directories, 120/20 line chunks, BGE embeddings, FAISS + BM25 + RRF, persistence, and full reindex exist; symbol awareness does not.

## Stage 3 — Planning and scope (**Planned**)

Task classification; affected files/symbols; ordered and revisable plans; existence/consistency validation; risk/scope estimates; dependency-change detection; approval policy. First-class multi-file diffs with summaries, file-count and symbol-scope guards, plan-vs-diff and unrelated-change checks, unaffected-code preservation, and safe create/delete/rename.

Add project instruction/memory support for root/nested `AGENTS.md`, `AGENTS.override.md`, conventions, commands, architecture/generated-file/dependency rules, persistent memory, local config, and ADRs. Gate requirements, `pyproject`, package/lock files, Cargo/Foundry files, and system packages.

## Stage 4 — Tool-driven loop (**Planned**)

Controlled `read_file`, `list_tree`, `search_code`, `find_symbol`, `find_references`, `find_callers`, `find_implementations`, `inspect_git`, `git_diff`, `run_tests`, `run_build`, `run_lint`, `run_typecheck`, `run_safe_command`, `create_patch`, `apply_patch`, and `rollback` tools. Loop: request → plan → inspect → act → observe → replan/repair → verify.

Controlled shell begins with an allowlist; approval/block rules cover sudo, destructive removal, force push, `curl|bash`, credentials, and destructive DB operations. Add timeouts, child cleanup, cancellation, audit logs, optional Docker/bubblewrap/firejail, and CPU/RAM/disk limits.

## Stage 5 — Validation, tests, review, security, confidence (**Planned**)

Static registry: untracked/new files; reliable undefined-name and import checks; Python AST/syntax, Ruff, mypy, optional Pyright; Rust `cargo check`/Clippy; Solidity Forge build/test; JS/TS ESLint and `tsc --noEmit`; ShellCheck. The existing AST syntax/duplicate-definition validator is **Partial**.

Test intelligence: regression-test generation, optional TDD, relevant/affected-test selection, targeted-first then full suite, flaky handling, failure classification, bounded 1/2/3 repairs, never infinite loops. Existing detected Python/Rust/Node tests and one repair are **Partial**.

Self-review: task satisfaction, unrelated changes, architecture, security, performance, test adequacy, confidence, and risk. Low risk includes docs/tests; medium includes business logic; high includes auth, migrations, payments, security, smart contracts, and deployment and always needs approval.

Security: secret/key/token/password/private-key scanning and gitleaks evaluation; path traversal, SQL/command injection, unsafe deserialization, SSRF, auth bypass, weak crypto/randomness; Solidity reentrancy, access control, unchecked calls, oracle/accounting, and upgradeability checks.

Confidence/risk scoring covers retrieval, symbol/context coverage, tests, plan consistency, scope, static validation, results, security flags, and change risk, gating apply/commit. Database awareness detects schema/framework migrations, destructive SQL, ordering, validation, and rollback strategy. A policy engine combines risk, confidence, file/dependency/security/migration/deployment state, and user config.

## Stage 6 — Multi-language (**Planned**)

Harden Python, then Rust, Solidity, TS/JS, SQL, C/C++, Java, and Shell across indexing, planning, editing, validation, tests, and review.

## Stage 7 — UI, history, and metrics (**Planned**)

Extend Streamlit with Chat/Documents/Coding tabs; repo selector; task/mode; plan/symbol/affected-file/diff views; Apply/Reject; test/repair/commit/rollback actions; branch, risk, confidence, dependency and security indicators; streaming progress.

Task history stores prompt/task, timestamps, repo/start commit/branch, plan/context/patch, validation/tests, repairs, result, and commit. Dashboard tracks tasks, first-pass/repair success, rejections, structural/test failures, files changed, latency, tokens/sec, and prompt/version performance. Version planner/coder/reviewer prompts; add benchmark tasks and a regression suite comparing failure modes.

## Stage 8 — Isolation and bounded autonomy (**Planned**)

Git worktree per task, isolated filesystems, checkpoint commits, staged rollback, concurrent-task safety. Evaluate Docker/bubblewrap/firejail, CPU/RAM/disk and command/generation limits, hung-child termination, and untrusted-repo mode. Only after single-task reliability: sequential priority queue, pause/cancel, per-task isolation, conflict prevention, and approvals.

## Stage 9 — Integrations (**Planned**)

GitHub issue → task → agent branch → validation/tests → commit → PR, plus PR review and CI; never force-push without approval. OpenClaw may expose only the safe coding-agent interface and cannot bypass Git transactions, validation, approvals, sandbox, or risk gates.

## Stage 10 — Real-repository hardening (**Planned**)

Onboarding detects languages, builds, tests, linters, typecheckers, frameworks, repo map, symbol index, candidate `AGENTS.md`, local config, and baseline health. Exercise real repositories and a benchmark suite; measure/tune retrieval, prompts, repairs, and local model adapters.

Context management becomes budget-aware: repo map first, exact symbols/dependencies/tests next, no blind 256K filling, cached summaries/symbols, incremental/changed-only embeddings, and provenance. Runtime work adds coding and deterministic/low-temperature profiles, generation config, health/startup checks, fallbacks, context profiles, benchmark harness, and alternative local model adapters.

## Cross-stage product capabilities (**Planned unless noted**)

- Explicit ask/explain, repo overview, architecture trace, review, bug investigation, traceback/log debugging, feature, test generation, refactor, security, docs, migration, and PR-review modes.
- Router plus planner, coder, reviewer, debugger, test engineer, and security reviewer roles; optional small local helpers for routing, ranking, classification, and summarization.
- Documentation automation for README/API docs/docstrings/changelog/architecture/config/diagrams/data flows/release notes.
- Architecture understanding for components, dependencies, request/DB/auth/security/runtime flows, and graph-generated diagrams.
- Large-refactor mode: plan → dependency analysis → staged edits → checkpoint → relevant/full tests → next stage; no opaque giant patches.
- Unified final platform: llama-server feeding local chat, document/repository RAG, code intelligence, planner/coder/reviewer/debugger/test/security roles, Git transaction manager, task history, and Streamlit UI.

The product definition of done includes local chat; private RAG/OCR; repo Q&A and symbol tracing; planning and multi-file safe edits; build/test/lint/typecheck; bounded repair; code/security review; instruction memory; risk/confidence gates; Git isolation/commit/rollback and optional worktrees; history/metrics/UI; multi-language work; optional GitHub/OpenClaw/queue integrations. High-risk changes retain explicit human review.
