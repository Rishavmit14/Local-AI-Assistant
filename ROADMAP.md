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

## Stage 8 — Isolation and bounded autonomy (**Done / accepted**)

Task-bound Git worktrees, exact checkpoints/rollback, sandbox/resource/network policy, crash recovery, explicit promotion, task history, and fail-closed strong-isolation requirements are implemented. Main is never silently auto-merged. Remaining kernel-level isolation enhancements are hardening rather than a missing Stage 8 foundation.

## Stage 9 — Native Integration Gateway / GitHub / External Interfaces (**Implemented; integration hardening remains**)

Authenticated Friday-native gateway APIs, typed provenance/idempotency, bounded events, GitHub transport/publication components, repository mapping, and MCP-compatible stdio are implemented and tested. External inputs remain untrusted and cannot bypass planning, approval, validation, isolation, review, Git, or history controls. Remaining work is real end-to-end external workflow qualification and deployment hardening where required.

## Stage 10 — Real-repository hardening (**Partial / active**)

Repository onboarding code/CLI and integration coverage exist. Remaining work includes broader real-repository benchmark suites, retrieval/prompt/repair/model-adapter tuning, context-budget/runtime profiles, representative framework/build/test qualification, and regression evidence across real repositories.

## Stage 11 — Conversational Voice & Cinematic UI (**Advanced implementation; production voice + natural interruption accepted**)

Accepted: Streamlit removal; `FridayInterfaceService`; native presentation API/event/runtime boundary; React/Vite frontend foundation; local microphone input; Whisper STT; streaming LLM lifecycle; Piper TTS; PipeWire playback; VAD/Silero wake segmentation; strict `Hey Friday`; Parakeet primary + Moonshine fallback wake ASR; persistent fail-closed wake workers; always-on capture; wake pause/resume around conversation; user-session systemd deployment; cold restart/shutdown qualification; voice/wake telemetry; WebRTC PipeWire AEC; and production natural-language barge-in with immediate playback interruption.

Production barge-in uses an ephemeral Friday-owned PipeWire WebRTC AEC graph in `monitor.mode=true`. The physical/default speaker monitor supplies the echo reference while `friday_aec_source` supplies the cleaned microphone stream exclusively to `FridayBargeInMonitor`; wake capture remains on the normal raw microphone path. Live qualification proved strong speaker-echo suppression, preserved human speech above the existing trusted interruption gate, normal wake conversation, natural interruption without repeating the wake phrase, and stable service operation.

Remaining: deterministic blocked-read pause/stop hardening; explicit `Friday, stop` semantics; wake-then-separate-command semantics; capture-thread health supervision/restart; concurrent HTTP/presentation versus wake-turn policy; richer visual listening/thinking/speaking/interruption states; and longer-running voice stability qualification.

## Stage 12 — Production Voice Lifecycle (**Active**)

Production AEC-backed natural interruption is accepted. Continue the remaining microphone/runtime lifecycle hardening: explicit stop semantics, blocked-read pause/stop correctness, wake-then-command behavior, capture/worker recovery, concurrency policy, observability, and long-running voice stability.

## Stage 13 — Persistent Friday Memory (**Planned**)

Add local-first semantic long-term memory, episodic memory, bounded working memory, preferences, project/goal/person relationships, provenance/confidence, supersession/conflict resolution, and retention/deletion policy. Deterministic repository/project instructions remain a separate engineering authority.

## Stage 14 — Visual Perception / Screen Awareness (**Planned**)

Add safe read-only screen capture, active-window/application context, vision-model interpretation, OCR where appropriate, UI-state understanding, provenance, and privacy controls. Visual perception initially has no mutation authority.

## Stage 15 — Safe Desktop Control (**Planned**)

Add policy-governed application launch/focus, bounded keyboard/mouse/UI actions, browser interaction, local file/application operations, permission classes, audit, and approval for destructive/high-risk actions.

## Stage 16 — Autonomous Assistant Execution (**Planned**)

Generalize Friday into a bounded objective loop: objective -> plan -> inspect -> act -> observe -> validate -> repair/replan -> complete or request approval. Reuse the existing planner/execution/validation/isolation/Git/history/approval stack.

## Stage 17 — Proactive Event and Automation Engine (**Planned**)

Add local service/system/repository/filesystem/task/external event watches, schedules, meaningful notifications, relevance policy, permission policy, and rate limiting.

## Stage 18 — Multi-Agent / Multi-Model Friday (**Planned**)

Keep one user-facing Friday while internally routing to appropriate conversational, reasoning, coding, vision, retrieval, planner, coder, reviewer, debugger, test, and security capabilities. Specialized agents gain no implicit extra privileges.

## Stage 19 — Self-Learning / Research Engine (**Planned**)

Add trusted-source collection, provenance, domain indexing, knowledge-gap identification, research plans, synthesis, curriculum generation, teaching/evaluation, and refresh/versioning. This does not mean silently modifying model weights.

## Cross-stage product capabilities (**Planned unless noted**)

- Explicit ask/explain, repo overview, architecture trace, review, bug investigation, traceback/log debugging, feature, test generation, refactor, security, docs, migration, and PR-review modes.
- Router plus planner, coder, reviewer, debugger, test engineer, and security reviewer roles; optional small local helpers for routing, ranking, classification, and summarization.
- Documentation automation for README/API docs/docstrings/changelog/architecture/config/diagrams/data flows/release notes.
- Architecture understanding for components, dependencies, request/DB/auth/security/runtime flows, and graph-generated diagrams.
- Large-refactor mode: plan → dependency analysis → staged edits → checkpoint → relevant/full tests → next stage; no opaque giant patches.
- Unified final platform: llama-server and specialized local models feeding local chat, document/repository RAG, code intelligence, planner/coder/reviewer/debugger/test/security roles, Git transaction manager, task history, Friday-native interface/event services, persistent conversational voice, deep memory, visual perception, safe desktop control, proactive automation, orchestrated agents/models, and the cinematic Friday desktop UI.

The product definition of done includes local chat; private RAG/OCR; repo Q&A and symbol tracing; planning and multi-file safe edits; build/test/lint/typecheck; bounded repair; code/security review; deterministic project instructions; persistent Friday memory; risk/confidence gates; Git isolation/commit/rollback/worktrees; history/metrics/UI; multi-language work; a Friday-native integration gateway with optional GitHub/MCP/external adapters; production conversational voice with interruption; visual perception; safe desktop control; bounded autonomous execution; proactive automation; multi-agent/multi-model orchestration; and bounded research/self-learning workflows. High-risk changes retain explicit human review.
