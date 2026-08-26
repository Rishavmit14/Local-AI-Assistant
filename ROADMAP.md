# Roadmap

Status legend: **Done** means evidenced in the imported Stage 0 code; **Partial** means a proven baseline exists; **Planned** means later work. No capability from `CODEX_HANDOFF.md` is omitted.

## Stage 0 — Repository bootstrap (**Done**)

Actual live files inventoried and imported; working behavior organized into a package; service units sanitized; documentation, dependency groups, bootstrap/install scripts, ignore rules, demo fixture, and tests added. Original deployments remain untouched. Bootstrap provenance and discrepancies are recorded under `docs/history/`.

## Stage 1 — Stabilize and package (**Done**)

Typed environment configuration, structured JSON/text logging, explicit errors/transaction models, dependency-injected package boundaries, canonical console commands, compatibility wrappers, dependency groups, and broad unit/integration/regression tests are implemented. The transactional Git foundation now has final success/failure verification and summaries, deterministic rollback/cleanup, `--keep-failed-branch`, `--human-review`, and approval-gated `--auto-merge`. Worktrees/checkpoints remain correctly scheduled for Stage 8.

## Stage 2 — Code intelligence (**Done**)

Official Tree-sitter Python parsing now provides exact modules, functions, async functions, classes, methods, nested definitions, signatures, decorators, docstrings, imports, ranges, references, and conservative calls. Typed persistent symbols/graphs, content-hash incremental updates, changed-only embeddings, exact/name/semantic/lexical/hybrid queries, dependency/call queries, generated maps, provenance, CLI operations, failures, benchmarks, and deterministic fixtures are implemented.

The schema is extensible for structs, traits, interfaces, contracts, enums, implementations, namespaces, and additional languages, but their grammars/extraction remain scheduled for Stage 6. Dynamic Python dispatch and reflective imports remain explicitly unresolved.

The existing multi-extension 120/20 line-chunk BGE + FAISS/BM25/RRF index remains the compatibility fallback beneath exact, graph-related, and hybrid symbol retrieval.

## Stage 3 — Planning and scope (**Done**)

Typed task classification, deterministic affected-file/symbol/test candidates, bounded structured Qwen plans, existence/consistency validation, risk/confidence/approval decisions, dependency/migration/security awareness, instruction precedence, JSON persistence, CLI inspection, and the pre-patch coding-agent planning gate are implemented.

The plan-vs-diff `ScopeGuardPolicy` foundation defines file/symbol/new/delete/rename/count/protected/dependency/generated/security constraints. Actual first-class multi-file editing, diff enforcement, unrelated-change checks, and unaffected-code enforcement remain explicitly scheduled for Stage 4 rather than being silently performed in Stage 3.

Root/nested `AGENTS.md` and `AGENTS.override.md`, relevant architecture, conventions, commands, generated/protected paths, and dependency rules feed planning with defined precedence. Full persistent project memory remains a later product capability; Stage 3 persists scoped plan artifacts only.

## Stage 4 — Tool-driven loop (**Done**)

Controlled `read_file`, `list_tree`, `search_code`, `find_symbol`, `find_references`, `find_callers`, `find_implementations`, `inspect_git`, `git_diff`, `run_tests`, `run_build`, `run_lint`, `run_typecheck`, `run_safe_command`, `create_patch`, `apply_patch`, and `rollback` tools. Loop: request → plan → inspect → act → observe → replan/repair → verify.

Typed registry metadata, permission classes, strict tool-choice/observation records, plan-token/repository/HEAD binding, multi-file patch parsing, symbol effects, inspect-only/new/delete/rename/dependency/protected scope enforcement, structured file/symbol edits, pre/post-apply Git-diff checks, bounded loop/repair/reapproval stops, planned plus final tests, human review, timeouts/process cleanup, redacted atomic JSON audit history, execution CLI, and coding-agent integration are implemented. Scope increases require a separately validated plan and renewed approval; they are never silently accepted.

Controlled shell begins with an allowlist; approval/block rules cover sudo, destructive removal, force push, `curl|bash`, credentials, and destructive DB operations. Add timeouts, child cleanup, cancellation, audit logs, optional Docker/bubblewrap/firejail, and CPU/RAM/disk limits.

## Stage 5 — Validation, tests, review, security, confidence (**Done**)

Static registry: untracked/new files; reliable undefined-name and import checks; Python AST/syntax, Ruff, mypy, optional Pyright; Rust `cargo check`/Clippy; Solidity Forge build/test; JS/TS ESLint and `tsc --noEmit`; ShellCheck. The existing AST syntax/duplicate-definition validator is **Partial**.

Typed validation plans, repository-driven Python/Rust/Solidity/Node/Shell adapters, ranked targeted tests, targeted-first/full-final policy, scoped test generation and optional TDD primitives, deterministic test-validity checks, failure/flaky classification, validation caching, bounded evidence-driven repair, deterministic/security/model review, provenance, final decisions, CLI operations, and coding-agent quality gating are implemented. Repairs and generated tests cannot widen approved scope. External scanners and coverage are used only when already configured.

Self-review: task satisfaction, unrelated changes, architecture, security, performance, test adequacy, confidence, and risk. Low risk includes docs/tests; medium includes business logic; high includes auth, migrations, payments, security, smart contracts, and deployment and always needs approval.

Security foundation: secret/key/token/password/private-key scanning and optional configured gitleaks; conservative path traversal, SQL/command construction, unsafe deserialization, auth bypass, weak crypto, and Solidity external-call/access/upgrade/signature heuristics are implemented. SSRF, insecure-randomness depth, oracle/accounting analysis, and comprehensive language-aware security review remain later hardening rather than being overstated as complete.

Confidence/risk scoring covers retrieval, symbol/context coverage, tests, plan consistency, scope, static validation, results, security flags, and change risk, gating apply/commit. Database awareness detects schema/framework migrations, destructive SQL, ordering, validation, and rollback strategy. A policy engine combines risk, confidence, file/dependency/security/migration/deployment state, and user config.

## Stage 6 — Multi-language (**Done**)

A single typed language registry and capability-aware adapter architecture now preserves Python and adds Rust, Solidity, TS/JS, SQL, C/C++, Java, and Shell to the shared symbols, graph, persistence, incremental embeddings, repository map, CodeRAG, planner, ScopeGuard, and validation/test-impact evidence.

Rust has the strongest new coverage: nested modules, functions/async functions, structs, enums/variants, traits, impls/trait impls, methods/associated functions, aliases/constants/statics/macros, visibility, attributes/docs/generics/where clauses, imports/modules, test attributes, and conservative calls/references. Later adapters extract their roadmap declarations and explicit relationships while reporting partial/unavailable semantics rather than overstating runtime resolution. Legacy line chunks remain the fallback for unsupported/uncertain constructs.

## Stage 7 — UI, history, and metrics (**Done**)

Stage 7 originally delivered Streamlit Documents, Coding, History, Metrics, and System workspaces with an allowlisted repository selector, task creation, existing-planner invocation, exact-plan approval binding, scope/artifact/timeline detail, operational metrics, health visibility, and cooperative cancellation between tool steps. Those presentation components are retired in Stage 11; their reusable backend-facing capabilities are preserved through `FridayInterfaceService`. Mutating execution remains exclusively behind the existing Stage 4 coding-agent transaction rather than being reimplemented in presentation code.

A versioned SQLite history store normalizes tasks, lifecycle events, plans, executions, tools, validations, reviews, approvals, affected scope, imports, and metrics while retaining JSON evidence by path/hash. Deterministic search, timeline, audit, JSON/Markdown export, migration, storage/vacuum operations, redaction, concurrent readers, and synthetic multi-thousand-task benchmarking are implemented. Metrics never invent missing token/model timing data. Prompt versioning and benchmark-task quality comparisons remain Stage 10 hardening.

## Stage 8 — Isolation and bounded autonomy (**Implemented on Stage 8 branch**)

Task/plan/repository/commit-bound Git worktrees keep autonomous mutations away from the canonical checkout. Exact staged/unstaged/untracked/mode/symlink checkpoints, scoped rollback, deterministic task branches, local locks, crash-recovery classification, cleanup, exact promotion identities, task history, CLI, and UI visibility are implemented.

A typed sandbox boundary probes Bubblewrap and otherwise reports a constrained native backend honestly. Task HOME/TMP/cache, allowlisted environments, process-tree cancellation, bounded output, wall/CPU/process/open-file/file-size/address-space limits, and explicit network policy are implemented. On the current host Bubblewrap user namespaces are unavailable; strong isolation therefore fails closed rather than silently downgrading to native process limits. Disk quotas, seccomp, delegated cgroups, automatic conflict resolution, and task scheduling remain limitations/later work. Stage 8 never auto-merges main.

## Stage 9 — Native Integration Gateway / GitHub / External Interfaces (**In progress on review branch**)

Build a Friday-native internal integration/service API, then add native GitHub issue → task → branch → validation → commit → PR, PR-review, and CI-status integration. Prefer MCP-compatible external tool/interface integration where a standard protocol is useful, add a WebSocket/event interface where justified, and use direct external adapters only when justified. Friday remains independently operable and has no OpenClaw dependency. Every external action remains behind Friday's risk gates, exact plan approval, ScopeGuard, Git transaction safety, validation, Stage 8 sandbox/isolation policy, and audit/history.

## Stage 10 — Real-repository hardening (**Planned**)

Onboarding detects languages, builds, tests, linters, typecheckers, frameworks, repo map, symbol index, candidate `AGENTS.md`, local config, and baseline health. Exercise real repositories and a benchmark suite; measure/tune retrieval, prompts, repairs, and local model adapters.

Context management becomes budget-aware: repo map first, exact symbols/dependencies/tests next, no blind 256K filling, cached summaries/symbols, incremental/changed-only embeddings, and provenance. Runtime work adds coding and deterministic/low-temperature profiles, generation config, health/startup checks, fallbacks, context profiles, benchmark harness, and alternative local model adapters.

## Stage 11 — Conversational Voice & Cinematic UI (**Planned**)

Add local microphone input, wake-word activation, voice activity detection, local Whisper speech-to-text, streaming response text, sentence/chunk streaming TTS with an original Friday assistant voice, barge-in, and immediate speech stop. The project must not clone or impersonate an identifiable actor or public figure.

Expose deterministic assistant states—`SLEEPING`, `LISTENING`, `TRANSCRIBING`, `THINKING`, `PLANNING`, `WAITING_FOR_APPROVAL`, `EXECUTING`, `VALIDATING`, `REVIEWING`, `SPEAKING`, `COMPLETED`, `ERROR`, and `CANCELLED`—through Friday's native WebSocket/event boundary. Build the primary Friday interface fresh from scratch with a GPU-accelerated WebGL/Three.js/Canvas-style cinematic and audio-reactive neural core driven by real conversation, task, planner, executor, validation, review, approval, retrieval, voice, and system-health events. The legacy Streamlit UI is removed completely. The CLI remains the recovery and power-user interface.

The authority boundary is permanent: voice/UI → Friday native API/event boundary → existing planning, risk, approval, execution, validation, and audit systems. Voice and UI code receives no privileged direct path to shell execution, filesystem or Git mutation, model tool execution, or approval bypass.

## Cross-stage product capabilities (**Planned unless noted**)

- Explicit ask/explain, repo overview, architecture trace, review, bug investigation, traceback/log debugging, feature, test generation, refactor, security, docs, migration, and PR-review modes.
- Router plus planner, coder, reviewer, debugger, test engineer, and security reviewer roles; optional small local helpers for routing, ranking, classification, and summarization.
- Documentation automation for README/API docs/docstrings/changelog/architecture/config/diagrams/data flows/release notes.
- Architecture understanding for components, dependencies, request/DB/auth/security/runtime flows, and graph-generated diagrams.
- Large-refactor mode: plan → dependency analysis → staged edits → checkpoint → relevant/full tests → next stage; no opaque giant patches.
- Unified final platform: llama-server feeding local chat, document/repository RAG, code intelligence, planner/coder/reviewer/debugger/test/security roles, Git transaction manager, task history, Friday-native interface/event services, conversational voice, and the cinematic Friday desktop UI.

The product definition of done includes local chat; private RAG/OCR; repo Q&A and symbol tracing; planning and multi-file safe edits; build/test/lint/typecheck; bounded repair; code/security review; instruction memory; risk/confidence gates; Git isolation/commit/rollback and optional worktrees; history/metrics/UI; multi-language work; a Friday-native integration gateway with optional GitHub/MCP/external adapters; and optional queued autonomy. High-risk changes retain explicit human review.
