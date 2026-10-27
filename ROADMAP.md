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

The accepted Stage 4 coding-agent shell begins with an allowlist and its
historical policy blocks sudo, destructive removal, force push, `curl|bash`,
credentials, and destructive DB operations. That bounded coding-tool surface is
distinct from the cross-cutting Owner Sovereign Mode administrator capability
now specified for row 59; see ADR 0033. Add timeouts, child cleanup,
cancellation, audit logs, optional Docker/bubblewrap/firejail, and CPU/RAM/disk
limits.

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

Remaining: richer visual listening/thinking/speaking/interruption states;
streaming speech/initial-response latency; and longer-running voice stability
qualification. Capture/worker health recovery is accepted in Stage 12E and
wake/HTTP interaction ownership in Stage 12F.

## Stage 12 — Production Voice Lifecycle (**Accepted**)

Production AEC-backed natural interruption, blocked wake-read pause/stop
hardening, Stage 12D exact explicit-stop semantics, and Stage 12E supervised
capture/worker recovery are accepted. Wake capture
treats EOF/capture errors from an intentionally retired microphone stream as
lifecycle cancellation while genuine failures on the current stream fail closed.

Stage 12D accepts only normalized exact `stop`, `friday stop`, and
`hey friday stop`; these return the voice turn to IDLE without LLM or spoken
acknowledgement. The same classifier handles trusted AEC interruption transcripts
after immediate playback stop. Nonexact phrases remain conversational. Final
physical qualification passed inline stop, active-speech stop, and stop-loss
negative control on the clean runtime without diagnostic readers. Clipped host
audio was corrected and the rejected ASR alias was removed. Continue barge-in
observability, streaming speech latency, and long-running voice stability.

Stage 12O closes the remaining bounded real-microphone stability/observability
qualification. It records bounded last-error detail alongside type, allowing an
operator to distinguish worker/capture recovery causes without exposing voice
content. A primary wake-worker failure recovered in-process during qualification;
the old PID was replaced, and four later physical inline turns completed. After a
controlled reload, a clean 12-minute listening interval plus two physical turns
completed with zero recovery count, null error type/detail, stable worker PIDs,
and each full wake → LLM → Piper → resume lifecycle. Stage 13 is now next.

## Stage 12E — capture/worker health recovery (**Accepted**)

Accepted: capped recovery backoff after microphone or wake-worker failures,
bounded raw PCM reads, retired partial-frame/late-ASR cancellation, terminal
shutdown, old worker pipe cleanup, and a read-only voice-health endpoint.
Qualification passed deterministic failure/cancellation/backoff coverage and
683-test repository verification. Actual recorder death and stall recovered in
1.23/5.19 seconds on the same service PID. After the idle primary wake worker was
stopped, a fresh physical inline wake recreated it, recognized the command,
spoke the expected response, and returned to listening. Final acceptance gates
and remote recovery are recorded in the current handoff and Git history.

## Stage 12F — wake/HTTP interaction concurrency (**Accepted**)

Accepted: one deterministic interaction owner across physical voice and
presentation HTTP streams. Admission occurs before runtime mutation: active
voice rejects HTTP with 409; active HTTP pauses raw wake ownership and suppresses
wake dispatch; second HTTP requests reject without phantom events; completion,
disconnect, error and shutdown restore wake and release ownership. A read-only
owner projection and cancellation-safe synchronous streaming keep microphone
ownership fail-closed until a started model read reaches a safe stop.

Physical qualification passed both directions: voice ownership rejected the live
HTTP probe with 409 while a `Hey Friday` counting request completed, and a spoken
wake phrase during presentation ownership received no reply with zero accepted
wakes. The following stream completion returned Friday to listening. A trusted
barge-in that stops playback without a completed utterance now returns safely to
IDLE without partial-ASR replay or a false runtime error.

At that checkpoint, bare `Hey Friday` entered fresh-command capture without a
dependable audible ready cue. Stage 12H subsequently accepted the local “I'm
listening” acknowledgement; a missing cue is no longer an open Stage 12 item.

## Stage 12G — barge-in observability and long-playback stability (**Accepted**)

Accepted: bounded 30-second Piper first-audio arming, playback-lifetime barge
monitor passes after explicit monitor timeouts, and privacy-safe outcome, pass,
elapsed, and maximum VAD-probability event metadata. Stop failures remain hard
failures. Physical requalification proved a delayed start and late `Friday,
stop` interruption: playback stopped in 3.3 ms and the exact-stop path returned
to IDLE without a runtime error.

## Stage 13 — Persistent Friday Memory (**Accepted**)

Add local-first semantic long-term memory, episodic memory, bounded working memory, preferences, project/goal/person relationships, provenance/confidence, supersession/conflict resolution, and retention/deletion policy. Deterministic repository/project instructions remain a separate engineering authority.

The accepted foundation is a separate local SQLite memory boundary with typed
episodic, preference, fact, and working records; provenance/confidence,
active/superseded/conflicted/expired/deleted lifecycle, deterministic recall,
and explicit forgetting. It now has bounded per-subject working retention,
provenance-bearing subject relationships, owner CLI controls, and bounded hybrid
lexical/local-BGE retrieval. Production conversation can consume only labelled
untrusted read-only memory context. It deliberately does not overload task
history or grant memory mutation authority to model output. Owner/session capture
requires a complete direct owner API/CLI request; conflicted records stay
excluded until an explicit owner keep/discard resolution. Full deterministic
coverage, 729-test regression, repository verification, and live local service
qualification prove explicit capture, read-back, and deletion with healthy
resident voice workers. Stage 14 is now next.

The later Astra Phase 13 product integration qualifies a separate bounded
owner-declared preference application path: a canonical default-off memory
setting controls whether active preference records are supplied as untrusted
style context to normal text Conversation. This does not infer habits, mutate
memory, or affect capability-routed work; see the product integration matrix
and `docs/architecture/memory.md`.

## Stage 14 — Friday Career Forge Core V1 (**Accepted**)

Build Friday's first flagship specialization: a persistent, local-first ML/AI
Engineer apprenticeship on top of Stage 13 memory. Its versioned competency
graph, Learner Twin, evidence/mistake/assistance records, resume point,
mission/tutoring loop, evolving hardware-aware projects, and private/public
GitHub-evidence boundary are specified in
`docs/architecture/career-forge.md`. This is neither a generic quiz/course/JD
matcher nor a resume/streak generator. The owner controls pace; Friday controls
dependency-aware pedagogy. No Career Forge implementation begins before Stage 13
has its accepted foundation. The active foundation supplies the versioned
dependency graph and local Learner Twin persistence: every competency starts
UNVERIFIED, missions retain exact resume state and assistance-bearing evidence,
and mastery advances only one evidence-backed rung at a time. The tutoring-loop
checkpoint persists the canonical mission sequence, practical tutor modes, and
minimum progressive assistance. Friday's local presentation API now exposes the
read-only journey and dependency-gated mission-start boundary. Mission content,
now begins with deterministic why/verification/mental-model/attempt/teach-back
briefs and only later uses adaptation after evidence. Project/public-evidence
gates reject fake, unvalidated, secret-bearing, private/proprietary,
undocumented, or low-quality artifacts and never publish automatically. Further
presentation controls now include local mission resume, assistance and evidence
submission, plus one-rung matching-evidence mastery advancement. The accepted
V1 stops at bounded local project linkage; project execution integration belongs
to the later perception, desktop-control, autonomy, and advanced-integration
stages.

The current tutor checkpoint uses Friday's existing local Qwen conversation
boundary with mission-specific context. It records generated assistance only when
the caller deliberately selects an assistance level; it never lets model output
mutate mastery or bypass the learning/publication boundaries.

Career Forge is canonically part of Friday's existing cinematic UI and its one
natural text/voice interface. Its enduring surface model is LEARN (mission and
work), MAP (competencies/prerequisites/mastery), PROJECTS (the four evolving
engineering projects), and PROGRESS (evidence-backed growth). Stage 14 V1 adds
only bounded projections and controls needed by its core loop; rich workspaces,
perception, and desktop assistance remain later-stage enhancements to these same
surfaces.

The active V1 projection reads the local journey and begins only the API-selected
dependency-ready mission. It shows the four surfaces without fabricating
independence, retention, or public-evidence status; mastery advancement and all
other Learner Twin mutation remain in the existing bounded local API.

The core loop now also persists a mission's link to its canonical evolving
project family and projects those links in the cinematic UI. This is local
learning context only: it neither proves mastery nor grants project execution,
Git, or publication authority.

Acceptance: deterministic Career Forge/API coverage, complete Python regression,
repository verification, frontend lint/tests/production build, and a controlled
local-service restart passed. The live service returned the 16-competency journey
and the project-link projection while resident voice remained running. Stage 15
Visual Perception / Screen Awareness is next.

## Stage 15 — Visual Perception / Screen Awareness (**Accepted**)

Add safe read-only screen capture, active-window/application context, vision-model interpretation, OCR where appropriate, UI-state understanding, provenance, and privacy controls. Visual perception initially has no mutation authority.

The active foundation is an explicit local GNOME Shell capture endpoint. It
persists private pixels only under `var/perception` and returns bounded metadata;
it has no control, OCR, interpretation, network, or shell authority.
Capture metadata is local and bounded; expired pixels and metadata are purged
together, and the API exposes no image paths or raw pixels.
An explicit retained-capture OCR route reuses local Tesseract with bounded output
and no persistence of OCR text in perception state.
The same retained capture can receive deterministic OCR-derived UI-state hints;
these are not general vision inference and retain no control authority.
The active-window projection is a fixed read-only query and fails closed as
unavailable on desktops that disable it; it has no focus or enumeration fallback.
Owner-selected screenshots from the native desktop UI can be explicitly copied
into private perception retention with source provenance, allowing consent-safe
local OCR and UI-state qualification where portal parenting is unavailable. An
explicit retained capture can receive up to ten labels from a pre-cached,
CPU-only local ViT specialist; it never downloads, uploads, persists labels, or
uses Qwen, and is not a second general-purpose model.
The existing cinematic UI now projects local perception status and presents an
explicit capture request; it does not receive pixels, paths, OCR text, or control
authority.
The current GNOME desktop denies direct session capture; Friday exposes this as a
bounded privacy-permission outcome and does not bypass it. An owner-selected
native screenshot has qualified OCR, deterministic UI-state, and local visual
labels through private retention; direct GNOME capture remains subject to desktop
consent.

Acceptance: focused and complete Python regressions, repository verification,
frontend lint/tests/production build, and a controlled live-service restart
passed. The live local endpoint classified the owner-selected retained capture
with three bounded labels while voice remained running. Stage 16 Safe Desktop
Control is next and must remain an independent policy-governed mutation boundary.

## Stage 16 — Safe Desktop Control (**Accepted**)

Add policy-governed application launch/focus, bounded keyboard/mouse/UI actions, browser interaction, local file/application operations, permission classes, audit, and approval for destructive/high-risk actions.

The active foundation is a separate local action lifecycle: an exact
empty-by-default app allowlist, SQLite audit records, proposal, explicit
approval, and one-time fixed-vector GNOME focus/GIO launch execution. It has no
arbitrary shell, keyboard, mouse, browser, file, or perception authority.
The browser foundation is an approval-gated `gio open` request for an exact
HTTPS origin from an empty-by-default local allowlist; it is not generic browser
automation or web-content access.
The local-file foundation is approval-gated opening of an existing regular file
below an exact empty-by-default root allowlist. It is not file management or
mutation authority.
The semantic UI foundation uses exact preconfigured AT-SPI
`application::control::action` entries under the same approval/audit lifecycle;
it is not raw keyboard/mouse injection or screen-derived automation.

Acceptance checkpoint: complete Python/repository verification and frontend
lint/tests/build passed. A controlled Friday restart proved the live endpoint
returns an empty audit and rejects a non-allowlisted action while voice remains
running. Continue the remaining Stage 16 action classes only through independent
policy and audit extensions.

## Stage 17 — Autonomous Assistant Execution (**Accepted**)

The active foundation persists bounded local objectives with explicit
create/resume/cancel lifecycle state. After an explicit resume, an objective may
reserve exactly one plan-only canonical task for a configured repository ID and
ask Friday's existing native gateway/planner to generate its plan. A planner
failure preserves the same linked task for retry. An objective can bind only to
that plan-ready canonical task-history record (or another existing canonical
record) by task ID and exact token; the native API never supplies an arbitrary
plan hash. It does not execute tools or grant authority outside Friday's existing
guarded execution stack. Cancelling a bound objective asks that canonical task to
cancel first and leaves the objective nonterminal if task cancellation fails.
Objective reads project the linked task's canonical current state without copying
it into a parallel lifecycle. The existing cinematic UI receives a bounded
objective projection with create/resume/guarded-plan/cancel controls and a
read-only task-token-verified plan-review summary only.

Planning uses a worker thread with process-local admission so its synchronous
model call does not block health/status/cancellation requests. Concurrent plan
requests are rejected while that worker is active. Task identity/repository
reservation is durable across processes; gateway materialization, cancellation,
and ready-plan binding recover the same identity after interruption. Durable
cross-process planning and execution admission now protect local model and
code-agent dispatch; authenticated owner interaction, live execution
qualification, and the remaining guarded observe/validate/repair loop are pending.
Lifecycle and binding updates now reject stale observed state/task/token values
at the database write, preserving cancellation and competing canonical bindings.
Discovery of execution integration found the gateway adapter regenerated a plan
under an existing approval token. It now loads the exact canonical approved
artifact with state/digest/identity checks instead. Native objective dispatch
delegates that exact approved binding through existing gateway authentication,
scope/rate policy, and executor. Earlier checkpoints provisioned no credentials;
the durable owner policy now permits Codex to securely configure protected
local-only, least-privilege runtime credentials for this qualification. No
unguarded presentation dispatch is allowed. Authenticated owner interaction,
live execution qualification, and bounded observe/validate/repair remain
pending.
Executor-local admission now serializes duplicate submissions with shutdown and
reports cancelled queued handles without status exceptions.
The cinematic console now keeps the newest terminal canonical task state visible
as outcome evidence while treating it as non-active; polling remains read-only.
Terminal evidence can include the bounded canonical outcome/failure/decision;
nonterminal execution detail remains absent. Schema v6 adds durable cross-process
planning admission: only one local gateway can generate a task plan at a time;
normal failure releases the claim and an interrupted holder recovers after its
one-hour lease.
Schema v7 adds durable cross-process execution dispatch admission held through
executor completion, with 24-hour interrupted-dispatch recovery. Isolation and
exact approval remain authoritative.

Cold-boot recovery of the controlled report-only qualification found a completed
rollback artifact and cleaned, identity-matching worktree but an `executing`
canonical task row. The repair finalizes every code-agent terminal path before
cleanup and accepts isolated execution evidence only when it matches the
existing task's exact plan hash and starting commit. The same task was
reconciled as `rolled_back`; no replacement plan, task, worktree, promotion, or
canonical-checkout mutation was created. The local model's quoted numeric tool
ordinal is normalized only in its unambiguous decimal form. A fresh authenticated
controlled report-only execution subsequently completed with the exact approved
task/token, isolated worktree, two audited read-only tool events, deterministic
validation/review artifacts, and a canonical successful terminal outcome.
Report-only plans now execute only approved inspections and read-only validation
commands deterministically; mutation-capable plans remain model-directed and
bound to the existing scope/approval/isolation chain. Complete Python
regression/repository verification (811 tests), frontend lint/26 tests/build,
and a controlled live restart with healthy voice workers passed. Stage 18 is next.

Generalize Friday into a bounded objective loop: objective -> plan -> inspect -> act -> observe -> validate -> repair/replan -> complete or request approval. Reuse the existing planner/execution/validation/isolation/Git/history/approval stack.

## Stage 18 — Proactive Event and Automation Engine (**Accepted**)

Add local service/system/repository/filesystem/task/external event watches, schedules, meaningful notifications, relevance policy, permission policy, and rate limiting.

The accepted local engine persists typed watches, events, and acknowledgeable
notifications in SQLite. It provides read-only/change-only filesystem and Git
observers plus deterministic local system/service/task snapshots, explicit
external provenance, schedules, relevance floors, payload idempotency, metadata
redaction/bounds, and hourly delivery rate limits. Its sole permission is
notification: it cannot create tasks, approve, execute, mutate, or control the
desktop. A low-frequency presentation worker projects delivered notifications
through bounded loopback read/ack APIs. Full Python/repository verification
(819 tests), frontend lint/26 tests/build, and a controlled live service restart
with scheduled delivery/acknowledgement passed. Stage 19 is next.

## Stage 19 — Agent / Role Orchestration (**Accepted**)

Keep one user-facing Friday while internally routing conversational, reasoning,
coding, vision, retrieval, planner, coder, reviewer, debugger, test, and security
roles. Roles use sequential invocations of the current sole general-purpose Qwen
model unless later evidence qualifies another model; specialized components gain
no implicit extra privileges.

Typed prompt-only role clients serialize use of one local Qwen model. Conversation,
planning, coding, debugging, test generation, and review retain their existing
authority boundaries. Full verification passed 822 tests; frontend gates and a
controlled live role-routed conversation passed. Stage 20 is next.

## Stage 20 — Self-Learning / Research Engine (**Accepted**)

Add trusted-source collection, provenance, domain indexing, knowledge-gap identification, research plans, synthesis, curriculum generation, teaching/evaluation, and refresh/versioning. This does not mean silently modifying model weights.

The accepted local research ledger stores owner-provided versioned sources with
provenance and content hashes, supports bounded source collection/synthesis,
domain gaps, transparent curriculum status, and evidence-term evaluation. It
does not fetch externally or modify model weights. Full Python/repository
verification passed 824 tests. Stage 21 is next.

## Deferred specialization — Market Intelligence & Adaptive Trading Research

**Outside the active roadmap.** The owner explicitly deferred this former Stage
20 on 2026-09-10. Retain this detail as a future specialization idea only; do
not allocate active engineering effort or infer trading authority unless the
owner explicitly restores it.

Build a research, forecasting, charting, empirical-evaluation, and adaptive
learning specialization over Stages 13–19. The initial boundary is knowledge,
analysis, historical replay/backtesting, paper/live-shadow evaluation, and useful
alerts. It does not authorize autonomous real-money trading.

### Knowledge and provenance

- Ingest owner-authorized playlists/videos, captions/transcripts, local audio and
  video, PDFs, notes, documents, screenshots, annotated examples, and later
  trusted research. Preserve source/publication date/video/playlist/timestamp,
  transcript segment, speaker, chart frame/OCR/annotations, instrument, timeframe,
  session, and concept relationships as durable structured knowledge.
- Build a versioned trading knowledge graph for structure, buy/sell-side and
  internal/external liquidity, FVG/inverse FVG, order blocks, breakers,
  mitigation, displacement, structure shift, dealing ranges, premium/discount/
  equilibrium, PD arrays, imbalance, sweeps, inducement, session ranges,
  London/New York/Asian timing, killzones/macros/opening ranges, profiles and
  opens/highs/lows, SMT/correlation, draw on liquidity, HTF narrative/LTF
  execution, event context, entries, targets, invalidation, and risk.
- Preserve provenance, confidence, competing definitions, ambiguity,
  contradictions, temporal evolution, supersession, examples, and counterexamples.
  Keep `SOURCE TEACHING -> FRIDAY INTERPRETATION -> FORMAL HYPOTHESIS -> TESTED
  RULE -> PRODUCTION-ELIGIBLE MARKET MODEL` as explicit, non-collapsible states.

### Data, state, detectors, and forecasts

- Build an authoritative numerical market-data boundary for permitted OHLC(V),
  timestamps, bid/ask, volume, open interest, volatility, liquidations, useful
  order book/L2 and funding, economic calendars, instrument/session metadata,
  revision provenance, and careful timezone normalization. Derive coherent
  Monthly/Weekly/Daily/4H/1H/15m/5m/1m views. TradingView pixels are context for
  educational or visible charts, not the primary numerical source.
- Represent multi-timeframe bias/narrative, draw and liquidity, dealing range,
  premium/discount, imbalance/displacement/structure, session/event state,
  candidate arrays, targets and invalidation, with explainable HTF-to-LTF links.
- Add small versioned detectors rather than an opaque mega-algorithm. Each emits
  timeframe/timestamp, structure/evidence, confidence when supported, rule/model
  version, lineage, and ambiguity; prefer deterministic raw-data rules.
- Generate structured point-in-time scenarios before outcomes: instrument,
  creation time/price, horizon/timeframe, HTF context, expected direction/path,
  retracement/watch/entry zones, liquidity objectives/targets, invalidation,
  setup, reasoning, evidence/rule versions, calibrated confidence, and alternatives.
  Lock meaningful forecasts immutably; corrections create new versions.
- Enforce and test non-bypassable anti-leakage. At historical time T, prompts,
  higher-timeframe closes, events, revisions, annotations, and outcomes contain
  only information available at T. Post-outcome edits cannot rewrite forecasts.

### Visual analysis, evaluation, and improvement

- Annotate charts with liquidity, imbalance/FVG, blocks, structure/ranges,
  premium/discount, sessions/highs/lows, expected paths, watch/entry/target/
  invalidation zones, confidence, and explanation. Visually distinguish observed,
  detected, hypothesis, active forecast, invalidated, and completed state.
- Provide deterministic market replay that runs narrative, detectors, forecasting,
  chart annotations, alerts, and trade-plan reasoning exactly as if live.
- Evaluate individual concepts, combinations, setups, sessions, timeframes,
  instruments, and regimes. Record explicit execution/fill assumptions and sample
  count, direction/target/invalidation/timing accuracy, expectancy, MAE/MFE,
  profit factor/drawdown when appropriate, and confidence calibration.
- Separate research/training, validation, final out-of-sample, walk-forward, paper,
  and live-shadow phases. Live-shadow watches and locks real-time predictions but
  places no trades. Backtest success is not live evidence.
- Score locked forecasts across path, target, invalidation, timing, zones, HTF/LTF
  reasoning, and confidence. Retain successes and failures. Classify bias/draw/
  entry/structure/FVG/session/HTF/event/regime/timing/target/risk/data/detector/
  hallucination/insufficient-evidence mistakes as research evidence.
- Improve only through versioned production-model -> weakness -> hypothesis ->
  challenger -> historical/validation/out-of-sample/walk-forward -> paper/live-
  shadow -> compare -> promote/reject. Retain rejected hypotheses; one loss cannot
  rewrite strategy. Specialize evidence by approved market (initially NQ, ES,
  Gold, BTC), session, timeframe, volatility, regime, and events.

### Product surfaces and boundaries

- Integrate Stage 17 for low-noise `SETUP FORMING -> CONDITIONS STRENGTHENING ->
  CONFIRMATION -> INVALIDATION -> TARGET` monitoring and pre-market/session/
  multi-timeframe/post-session/performance briefings, including “Friday, market
  briefing.”
- Explain bias, conflicts, invalidation, targets, dominating timeframe, contributing
  concepts, empirical evidence, source lineage, and uncertainty. Sequential Market
  Director, HTF/LTF, Liquidity, Session, SMT/Correlation, Macro/Event, Statistical,
  Risk, and Skeptic roles use the same current general-purpose LLM.
- Provide a dashboard by forecast, timeframe, instrument, session, setup,
  confidence bucket and version, with target/invalidation/MAE/MFE/calibration/
  expectancy/drawdown views and a `KNOWN -> PREDICTED -> OUTCOME -> SCORE` audit.
- New curriculum follows source -> extract -> compare -> duplicate/extension/
  contradiction/revision -> hypothesis -> experiment without erasing provenance.
  Keep teacher claim, interpretation, hypothesis, historical, out-of-sample, and
  live-shadow evidence separate.
- Real-money execution requires a separately scoped high-risk stage and explicit
  owner authorization, risk/position/daily-loss controls, kill switch, order and
  partial-fill reconciliation, deduplication, disconnect recovery, broker security,
  audit, and live qualification. It is outside Stage 20.

Definition of done: demonstrate the full provenance-preserving curriculum flow,
chart understanding, formal hypotheses, authoritative multi-timeframe data/state,
versioned detectors and locked pre-outcome forecasts, leakage-safe replay and
evaluation splits, backtest/walk-forward/paper/live-shadow measurement, outcome
and mistake learning, evidence-gated challengers, domain specialization, useful
alerts/briefings/explanations, and transparent performance views.

## Stage 21 — Cognitive Architecture & Local Intelligence Amplification (**Done / accepted**)

Make the same current local general-purpose model materially more effective via
memory, retrieval, structured knowledge, planning, decomposition, tools, skills,
observation, critique, verification, repair, and experience. Do not imply that
architecture changes pretrained weights. Benchmark raw current model versus the
same model plus Friday's cognitive system.

- A cognitive controller classifies task type, complexity, ambiguity, information,
  memory/research/tool needs, risk, verification, and duration. Select bounded
  `TRIVIAL/ROUTINE/MODERATE/COMPLEX/DEEP` strategies so easy work stays fast and
  difficult work earns context, decomposition, iterations, tools, and critique.
- Complex work follows objective -> unknowns/subgoals/dependencies -> solve ->
  validate -> integrate -> review and Stage 16's bounded inspect/act/observe/
  evaluate/revise/verify loop rather than one giant prompt.
- Retrieve relevant conversational/working/episodic/semantic/project/preference/
  attempt/failure/research memory and document/repository/knowledge/database/local
  manual/permitted-internet evidence on demand. Filter, summarize, compress,
  evict stale context, and preserve authority; do not indiscriminately retrieve.
- Represent useful entities, relationships, time, provenance, confidence and
  contradiction structurally. Inspect before inference and use filesystem, Git,
  tests, calculators, APIs, databases, market data, indexes, and validators for
  measurable facts.
- Turn repeatedly proven workflows into versioned procedural skills with triggers,
  inputs, steps, tools, evidence, validation, failure handling, permissions,
  provenance, and version. One successful attempt is insufficient for promotion.
- Scale self-critique to task significance: objective satisfaction, assumptions,
  contradictions, dependencies, security, tests, unsupported conclusions and
  simplification. For significant work support sequential `PRIMARY -> CRITIC ->
  RECONCILIATION` roles using the same model and verify before claiming success.
- Track evidence-based confidence without fake precision. Classify reasoning,
  retrieval, data, tool, environment, dependency, permission, model limitation,
  ambiguity, product, test and harness failures, then perform bounded minimum
  repair and retest rather than random retry.
- Retain useful experience abstractions (task, strategy, evidence, outcome,
  failure, correction, lesson), not hidden reasoning tokens. Learn which strategies
  work by task class and compare prompt/context/decomposition/retrieval/review/tool
  policy versions. Reject complexity that harms correctness, reliability, latency,
  resource cost, completion, or verification rates.
- Budget VRAM/RAM/CPU, latency, context, iterations, retrieval, and tools. Provide
  FAST and DEEP paths using the same model. Preserve offline chat, voice, memory,
  documents, code/repository intelligence, local tools/desktop/skills/knowledge,
  local market history, reasoning, and validation when internet is unavailable.
- Keep the model client replaceable; a future open model can plug into memory,
  skills, knowledge, tools, cognition, market/creator specializations, autonomy,
  and evaluation without adding another general model now.

Definition of done: a durable suite spanning reasoning, coding/debugging,
repository understanding, planning/tools, memory/research, long tasks, and later
market/creator tasks compares `RAW CURRENT MODEL` with `SAME MODEL + FRIDAY` on
correctness, reliability, latency/resource cost, completion, and verification.
Only evidence-positive, versioned cognitive changes are promoted.

Accepted implementation: deterministic bounded strategy selection and complex
phase decomposition; provenance/contradiction-aware bounded evidence selection;
local SQLite experience and versioned skill records; qualitative failure and
confidence handling; same-model raw-versus-Friday benchmark contracts across all
required areas; and read-only conversation guidance. Existing tool, execution,
approval, validation, isolation, audit, and Git authorities remain unchanged.
The suite defines durable comparison artifacts but does not claim an unmeasured
model-quality gain or pretrained-weight change.

## Deferred specialization — Creator Studio & Digital Media Intelligence

**Outside the active roadmap.** The owner explicitly deferred this former Stage
22 on 2026-09-10. Retain its detailed ideas for possible future restoration; do
not implement or infer publication authority from them.

Build one owner-controlled local creator studio for original, valuable, accurate,
high-retention, trustworthy content and sustainable monetization across YouTube,
Shorts, Instagram/Reels/carousels/posts, X, and later approved platforms. Avoid
mass-generated spam, plagiarism, engagement bait, and dependence on expensive
neural text-to-video generation.

### Strategy, audience, and editorial intelligence

- Persist owner-authoritative brand/niche/audience/tone/style/visual identity,
  pillars/formats/lengths, topic history, wins/losses, objectives, offers, and
  preferences. Learn audience interests/questions/pain points/sophistication,
  engagement/retention/platform behavior only from legitimate provenance-bearing
  data; avoid unsupported demographic or psychological inference.
- Research public/permitted emerging and evergreen opportunities, unanswered
  questions, information gaps, stale explanations, and worthwhile contrarian
  angles. Analyze public creator/channel topics, formats, packaging, engagement,
  questions and gaps without cloning scripts, thumbnails, identity, art, or
  protected expression.
- Rank ideas by topic/audience/problem/angle/platform/format, novelty/timeliness,
  research/production cost, pillar alignment and series potential. Maintain
  daily/weekly/monthly campaigns, recurring series without repetitive duplication,
  and master-content trees from long video to native Shorts/Reels/carousels/X.

### Research, writing, production, and packaging

- For factual content use topic -> research questions/sources/evidence/claim map ->
  outline/script -> claim verification. Mark fact, interpretation, opinion,
  prediction and anecdote. Editorial review catches unsupported/stale/contradictory
  claims, misinformation risk, excessive similarity, and logical gaps.
- Support long video, Shorts/Reels, tutorials, explainers, demonstrations,
  educational/documentary/commentary storytelling. Generate meaningfully different,
  accurate hooks and titles; evaluate clarity, curiosity, audience/platform fit
  and promise fulfillment without deceptive clickbait or rigid universal formulas.
- Storyboard scene duration, narration, visual/overlay/motion/transition and asset
  source. Analyze owner footage through transcription, topic/segment/pause/cut/
  retake/strong-moment detection, chapters, captions, editorial notes and suitable
  self-contained clips.
- Use efficient local image tools for thumbnails, illustrations, diagrams,
  backgrounds, cards, carousels and infographics. Build thumbnail variants around
  hierarchy, focus, mobile readability, truthfulness, and available analytics.
- Reuse local TTS for chunked normalized narration/pronunciation/silence/loudness;
  treat owner-authorized voice personalization separately. Add local noise
  processing, trim/fade/mix/duck/loudness and licensed music/SFX handling.
- Compose locally with script + narration + owner footage + owned/generated
  visuals/diagrams/screen recordings/licensed B-roll + captions/transitions using
  FFmpeg/renderers. Support deterministic motion text/titles/lower-thirds/charts/
  highlights/pan-zoom/callouts and aligned SRT/VTT/burned/styled captions. Do not
  synthesize every video frame with AI.
- Extract Shorts/Reels for self-contained context, hook, payoff, duration, clarity
  and platform fit. Adapt each derivative natively. Package YouTube titles,
  description/chapters/thumbnail/subtitles/metadata/CTA; Instagram Reel/cover/
  caption/carousel/posts; and X posts/threads/visuals/clips without engagement bait.
  Support quality-appropriate localization beyond literal translation.

### Assets, publication, analytics, and learning

- Index local footage, B-roll, images, thumbnails, logos, diagrams, audio/music/
  SFX, templates and prior content with source, license, date, usage and derivatives.
  Classify `OWNER-CREATED/GENERATED/PUBLIC DOMAIN/LICENSED/ATTRIBUTION REQUIRED/
  UNKNOWN`; unknown external licensing fails closed for automated production.
- Detect excessive similarity to owner archives, templates, sources and competitors.
  The owner supplies expertise, opinions, experience, demonstrations, personality
  and ideas; Friday amplifies that identity through research, structure, production,
  repurposing, analytics and experiments.
- Initial publication is `PRODUCTION READY -> OWNER REVIEW -> OWNER APPROVAL ->
  PUBLISH`. Later policy-governed APIs remain optional. Protect credentials and
  track dated platform monetization/reuse/AI-disclosure/copyright/spam/synthetic-
  media/music rules as changing external facts.
- With authorization, ingest YouTube impressions/CTR/views/retention/watch-time/
  subscribers/traffic, Instagram reach/watch/shares/saves/comments/follows, and X
  impressions/engagement/reposts/replies/bookmarks/profile actions. Journal every
  item, platform/brand/topic/format/time, hook/title/thumbnail/script/assets/CTA,
  experiment, metrics and lessons.
- Analyze performance by topic/format/length/hook/title/thumbnail/timing/series/
  platform without false causality. Link opening drops/spikes/replays/weak segments/
  intro/payoffs to script structure. Preserve A/B experiments for hooks, titles,
  thumbnails, lengths, formats, CTAs and stories; one viral item cannot redefine
  strategy. Version `content -> performance -> hypothesis -> experiment -> compare
  -> accept/reject` learning.
- Add reusable versioned creator skills, low-noise Stage 17 topic/deadline/
  performance/question/draft/series alerts, and a command center for pipeline,
  performance, experiments, and learning. Analyze real revenue/RPM/sponsorship/
  affiliate/product/funnel/audience/cost/time/ROI data without promising earnings;
  connect only legitimate owner-defined products, services, newsletters, courses,
  communities, consulting, affiliates and sponsorships without deceptive marketing.
- Post-publication review explains hook, retention, thumbnail, audience fit, weak
  sections, CTA, effort versus result and next experiment, optimizing trust,
  originality, accuracy, audience value, brand, and sustainable monetization.

Hardware target remains i7-7700HQ, 32 GB RAM, GTX 1070 8 GB. Prefer the current
single local LLM, existing STT/TTS, FFmpeg, deterministic rendering, efficient
image generation, CPU/RAM offload and offline/batch work. Do not require cloud
GPUs, paid generation APIs, multiple large LLMs, or long photoreal neural video.

Definition of done: prove brand/audience memory, sourced opportunity research,
original idea/calendar/series and verified scripts, owner-footage understanding,
local visual/audio/video/caption/repurposing pipelines, provenance-safe assets,
review-gated packaging/publication, authorized cross-platform analytics, durable
performance/experiment journals, evidence-driven learning, useful proactive views,
business-value analysis, and versioned creator skills as one Friday capability.

## Post-Stage-21 — Friday Product Integration & Career Forge Advanced Integration (**Slice 8 prompt-assembly investigation accepted; owner review pending**)

Stages 0–21 remain accepted historical engineering evidence. Their accepted
backend/security/recovery scope is not rewritten because owner-facing product
integration remains incomplete. The owner-authoritative
`FRIDAY_PRODUCT_BASELINE.md` now governs the target release behavior and
qualification bar; `docs/qualification/PRODUCT_INTEGRATION_MATRIX.md` is the
evidence-led integration audit and dependency plan.

Work proceeds in this dependency order:

1. **Foundational Friday coherence:** continuous conversational session and
   working context, behavioral memory, truthful capability awareness, basic
   low-risk laptop agency, perception/shared context, and history/undo/recovery.
2. **Career Forge Advanced Product Integration:** the highest-priority
   specialization; connect the mature tutor loop, Practice Lab, selected-code
   and screen-aware tutoring, evidence/retention/progress, projects, interview
   mode, and approval-gated GitHub evidence.
3. **Product UI integration:** retain the cinematic identity while adding only
   connected, truthful workspaces and owner actions.
4. **Product reality qualification:** execute baseline E2E flows, repair
   evidence-backed failures, run the stable full regression, and freeze a
   release candidate before any independent Astra qualification.

Slice 1 accepted the narrow foundation only: a truthful typed capability
projection, bounded active voice-session continuity, bounded active-session
context, and governed persistent-memory recall through normal conversation. It
does not accept desktop expansion, Practice Lab, advanced Career Forge tutoring,
or broad workspace redesign. Further owner-facing qualification remains required
before the product is generally qualified.

Slice 2 adds one typed, deterministic conversation-to-capability router. Its
registry remains descriptive; only explicitly composed adapters may invoke
existing authority. The first adapter connects Career Forge information,
canonical mission start/resume, and bounded TutorMode handoff to Friday's active
conversation without creating a second agent or allowing model-driven Learner
Twin mutation. A narrow explicit owner memory form may persist through the
existing governed memory service; ambiguity makes no change. Practice Lab,
screen-aware tutoring, broad desktop routing, and frontend expansion remain out
of this slice. Focused/affected tests, repository verification, frontend gates,
real text memory restart, and physical wake/alias/stop qualification passed.

Slice 3 makes the bounded Career Forge learning loop owner-facing through the
same Friday conversation: lesson framing, explicit attempts, automatic minimum
progressive assistance, bounded Qwen assessment, feedback, teach-back, and
durable mission/attempt/evidence resume state. Only explicit lesson-question or
teach-back contexts create attempts. Correct quiz/teach-back assessments may
record assistance-bearing evidence but never auto-advance mastery; uncertain or
incorrect assessment records retry truthfully. Real voice qualification exposed
and repaired long tutor speech/Piper failure and bounded wake-ASR variants for
hints/evaluation. Practice Lab, screen-aware tutoring, broad desktop/UI work,
interview integration, retention automation, and model expansion remain out of
scope.

Slice 4 exposes the existing governed Learner Twin records as one bounded,
truthful progress/history projection through normal Friday conversation and the
existing PROGRESS panel. It reports active mission, ordered attempts/retries,
recorded assistance, evidence, recorded mastery state, and the deterministic
next action without a second progress store, percentage, fabricated mastery, or
ordinary voice-transcript retention. Real local text qualification and a
controlled service restart recovered the same durable mission/evidence state.
Practice Lab, retention automation, screen-aware tutoring, broad desktop/UI
work, interview integration, model expansion, and Astra remain out of scope.

Slice 5 adds privacy-safe bounded latency evidence to the accepted voice path.
Kokoro CPU was evaluated locally but rejected after owner listening because its
response delay and long speech pauses degraded Friday; Piper remains production.
The evidence identifies Qwen time-to-first-token, not Piper, as the next bounded
latency target. No new voice model, Practice Lab, or UI scope was accepted.

Slice 6 profiled and optimized the accepted Qwen/conversation path without
changing the model, quantization, GPU offload, context capability, grounding,
memory, Career Forge, voice lifecycle, Piper, AEC, barge-in, or exact stop.
The measured root cause was avoidable prompt-cache loss: volatile session and
retrieval material preceded the static capability projection. Stable ordering
raised warm slot similarity from 0.240–0.413 to 0.902–0.970, reducing normal
warm prefill from 5.60–11.88 s across the bounded baseline to 2.06–3.09 s Qwen
TTFT for 260–305 newly evaluated tokens. Grounded Career Forge teaching remains
longer where its real context requires it. Physical qualification exercised
wake, follow-up, Career Forge, teaching, barge-in/stop, and wake recovery; the
service remained healthy. The remaining owner-perceived first-PCM variability
is a separately measured voice handoff concern, not a reason to weaken Qwen
grounding or restart TTS experimentation in this slice.

Slice 7 measured that handoff rather than altering Qwen or replacing Piper.
The post-Qwen bottleneck was an oversized initial write to the newly started
`pw-play` stdin pipe: first-speakable to the old first-PCM callback ranged from
54 ms to 10.83 s (median 4.88 s), while Piper first audio and process startup
were fast. Friday now flushes an 8 KiB PCM prefix before the contiguous
unchanged remainder. Qualified turns measured first-speakable to first PCM at
54–619 ms (median 388 ms), with no multi-second handoff stall. The observed
speech-end to first-PCM range was 3.29–31.44 s (median 6.01 s); the 31.44 s
teaching-path outlier was pre-Qwen prompt assembly, outside this bounded
post-Qwen scope. Qwen, grounding, memory, Career Forge, Piper, AEC, barge-in,
exact stop, and wake recovery remain unchanged and qualified.

Slice 8 investigated the one 27.5-second pre-Qwen prompt-assembly outlier with
additional content-free substage timing. A controlled-restart, eight-turn
representative corpus did not reproduce it: cold assembly was 16.9 ms, and
warm/mixed median/p95/max was 2.23/128.4/128.4 ms. The slowest turn's 127.2 ms
was Career Forge projection; no route, active-session, memory, SQLite,
capability, policy, or serialization work reached seconds. Isolated first-use
local embedding initialization took 5.15 s but cannot explain the historical
empty-memory turn, so no speculative warmup or behavior change was made. Normal
warm Qwen TTFT remained 1.93–2.92 s; grounded Career Forge resume was 7.28 s.
Practice Lab and all other product scope remain out of this accepted slice.

Practice Lab is qualified: the active Career Forge mission supplies a typed Python exercise,
persisted draft, bounded Run/Test/Submit flow, progressive Tutor hint, governed
attempt/evidence projection, and deterministic submitted-code diffs. Learner
code runs only through fail-closed Bubblewrap with denied networking and strict
resource bounds; it has no shell, repository, credential, or production-store
access. Test success remains evidence rather than automatic mastery. The first
Lab is intentionally Python-only. Its owner editor now uses the existing
CodeMirror Python language stack for real syntax highlighting, editing history,
and arbitrary selected-code context while execution remains exclusively behind
the same sandboxed service. The real Friday voice route,
owner visual workspace/CLOSE review, and live Run/Test/Hint/Submit/restart-resume
flow passed. A Career Forge SQLite descriptor leak exposed during live Lab
projection was repaired by deterministic short-lived connection closure.

The Astra integration candidate on localhost:5191 now projects canonical Career
Forge state through typed presentation adapters: LEARN and Practice Lab use
their existing governed command boundaries, while MAP and PROGRESS render the
same Learner Twin competency, mastery, attempt/retry, assistance, evidence, and
history records returned by `/api/v1/career-forge/journey`. It has no browser
authority or fallback progress fixtures. Retention/review, adaptive progression,
PROJECTS, Interview Mode, screen-aware tutoring, and governed desktop assistance
remain the next product work rather than a parallel Career Forge implementation.

The first retention slice creates a single evidence-linked scheduled review when
an explicit one-rung mastery advancement succeeds. Its progressive interval is
deterministic. A due review can now be explicitly delivered through the
canonical service/API/Progress surface, recording only `delivered` and a
deterministic verification prompt; it does not claim completion, retention,
evidence, or a mastery change. The current candidate adds governed local-Qwen
review evaluation and a read-only weak-area projection
from failed/uncertain retention plus latest unresolved attempts. Private answers
remain local and unprojected; mastery never decreases automatically. The
canonical next action prioritizes due/delivered reviews and evidence-backed weak
areas. Adaptive reinforcement mission construction remains next.

Adaptive reinforcement is now connected through the canonical service, API,
typed presentation adapter, and PROGRESS surface. Only a currently derived weak
competency can start reinforcement. Friday preserves any interrupted advanced
mission, teaches the weak competency through the existing mission/tutor/evidence
loop, and resumes the preserved mission after an explicit evidence-backed rung
advancement completes reinforcement. The action never lowers or advances
mastery by itself, and a newer correct retention outcome clears historical
retention weakness.

The canonical PROJECTS workspace is now connected to those same Learner Twin
records. It renders the four evolving hardware-aware families, recorded mission
and competency links, and an explicit connect action only for the active
mission's declared family. Linking remains learning context and grants no
mastery, execution, repository, GitHub, or publication authority.

Interview Mode is now connected as a persistent, two-question no-help flow over
the active canonical mission. Explicit answers become assistance-free interview
attempts; the existing local-Qwen assessment boundary returns governed feedback
and creates typed evidence only for correct responses. Pending evaluation is
restart-resumable, while completion never changes mastery or claims readiness.
Selected-code and screen-aware tutoring are now connected to the active mission.
Practice Lab sends only an explicit text selection; LEARN can explicitly reuse
the latest already-retained capture through bounded local OCR, without taking a
new screenshot. Context is labelled untrusted and one-shot; explanation creates
no attempt, evidence, mastery, retention copy, or desktop authority.

Governed desktop assistance now composes Career Forge with Friday's accepted
desktop-control boundary. The active mission can prepare an allowlisted exact
action and retain an audit link; proposal, owner approval, and execution remain
separate transitions, and local Qwen has none of those authorities. Desktop
activity never becomes mastery or learning evidence.

The project-evidence review lifecycle is now durable and interactive. Only a
project-linked mission with existing evidence can be reviewed; deterministic
genuine-work, validation, secret, privacy/proprietary, documentation, and quality
checks yield blocked or qualified state, and explicit owner approval is a
separate transition. Approval still performs no publication. A second bearer-
authenticated `GITHUB_WRITE` request now binds that approved candidate to an
eligible promotion-ready Friday task and explicit onboarded GitHub mapping, then
delegates publication to the existing reconciled gateway publisher. The Learner
Twin retains the exact task/repository/base binding, published pull-request URL,
or bounded failure for safe retry. PROJECTS now recovers and displays those
durable review/publication outcomes and the published link after refresh without
receiving publication credentials or authority. Bounded mission autonomy now lets one active
project-linked mission prepare and recover one explicit Friday objective while
the existing objective/task path exclusively owns repository selection, planning,
approval, isolated execution, cancellation, and outcome. No task state becomes
learning evidence or mastery automatically. If that mission later publishes an
approved artifact, the publication binding must use the linked objective's exact
canonical task and repository in successful terminal state; an unrelated task
cannot be substituted. Retention/progress automation now
registers a notify-only proactive watch for the oldest due scheduled review;
stable event identity deduplicates repeat polls, while delivery, evaluation,
evidence, mastery, reinforcement, and mission changes remain explicit. The next
Career Forge now maps Teacher, Coach, Pair Programmer, Reviewer, Debugger,
Interviewer, and Curriculum Designer tutor modes onto sequential prompt-only
clients of the same local Qwen. LEARN exposes the explicit choice, all calls keep
the shared interaction lease, and only explicitly selected assistance is
recorded; roles gain no tool, Learner Twin, or mastery authority. The next Career
Forge now projects trusted curriculum research through the existing local
research ledger: MAP displays provenance-bearing source and canonical-topic
coverage for the active domain without exposing source content or granting graph,
mission, evidence, or mastery mutation. Evidence-positive cognitive-improvement
evaluation now reconstructs the governed loop from persisted provenance: a
failed objective retention baseline, evidence-backed weakness, reinforcement
mission, assessed intervention evidence, explicit mastery advancement, and a
fresh retention reassessment. Only a higher canonical mastery rung plus a
correct fresh reassessment that clears the original weak area is positive; an
incorrect reassessment is a deterministic negative control. The projection is
read-only and restart-safe. The next dependency is the final authoritative
Career Forge gap audit across MAP, PROGRESS, product baseline, tests, and
retained scope.

That audit closed the explicit `CF-E2E-004` shared-code-attention gap: Friday can
select a bounded function from the canonical saved Practice Lab draft, ask why
the owner wrote it that way, recover the exact question after restart, and turn
only a correct assessed explanation into typed evidence without automatic
mastery. The next retained gap is evidence-backed confidence and stale-retention
projection in the Learner Twin/PROGRESS boundary; no automatic mastery demotion
is implied. That projection is now integrated: PROGRESS shows categorical
confidence, retention state, evidence count, and independent correct attempts;
due reviews become stale and failed objective evidence becomes weak without
automatic mastery demotion. The next retained gap is interleaving older concepts
into newer missions and requiring repeated independent performance where the
canonical policy supports it.

Governed interleaving is now integrated. Eligibility is limited to evidenced
curriculum prerequisites and prioritizes weak/stale confidence or fewer than two
independent demonstrations. Cross-context attempts/evidence retain the older
competency identity inside the newer mission. Direct-prerequisite failure blocks
that mission until fresh repair evidence; transitive retention failure does not
block unrelated progression. PROGRESS exposes the complete provenance chain.
The next retained gap is an evidence-backed interview/job-readiness and portfolio
readiness projection; current evidence must not be converted into invented
percentages or resume claims.

That readiness projection is now integrated. PROGRESS derives categorical
career, interview, and portfolio states from the existing mastery, confidence,
interview, project, and governed-publication authorities. Interview support
requires both correct no-help responses from one completed bounded interview;
career readiness additionally requires all competencies at independent
application, no weak/stale confidence, and a published governed artifact. The
projection lists its evidence counts and blockers without a synthetic score,
automatic learner-state mutation, or generated resume claim. The next
dependency is a final retained-scope and owner-path acceptance audit across the
Career Forge product baseline, architecture, roadmap, and deterministic E2E
coverage.

Market/trading, creator/media, multiple heavyweight general-purpose models,
parallel LLM orchestration, paid inference, cloud-GPU core cognition, and
advanced organization-hierarchy visualization remain deferred unless the owner
explicitly changes priority. The current Qwen remains the sole general-purpose
local model and role contexts remain sequential.

## Stage 22 — Friday Career Forge Advanced Integration (**Engineering qualified; owner/external E2E remains**)

Integrate the accepted Stage 15–21 general capabilities into the mature Career
Forge: screen-aware tutoring, policy-governed desktop assistance, bounded
mission autonomy, retention/progress automation, sequential Teacher/Coach/Pair
Programmer/Reviewer/Debugger/Interviewer/Curriculum-Designer roles, trusted
ML/AI curriculum research, and evidence-positive cognitive improvements. This
stage extends—not replaces—the bounded Stage 14 core loop and must preserve local
sovereignty, learner-evidence provenance, owner pace, and review-gated public
artifacts.

The final bounded project lifecycle qualification uses the production Learner
Twin, Practice Lab, project/objective link, canonical plan/approval/execution/
validation/review history, evidence gates, authenticated publication boundary,
and restart recovery. Objective reservations now use their deterministic
`friday/task/...` branch, so the exact successful mission task is publication-
eligible without bypassing isolation. Wrong-task and pre-evidence controls never
reach publication, repeated publication creates no duplicate pull request, and
reconstructed services recover the same objective, evidence, readiness, task,
and published URL. No autonomous Career Forge engineering gap remains. Exact
owner/external qualification remains for physical selected-code, retention and
interview flows, plus a real GitHub publication using the owner's configured
credential and onboarded repository. The qualified engineering checkpoint is
published at `9aaef7460cd6c7fa22425f488ab8a9ab858b2073`.

## Astra Canonical Product Integration — Phase 1 (**Qualified and published**)

Career Forge autonomous engineering scope is closed; the due owner retention
review remains a genuine external boundary and does not block independent
whole-Friday product integration. Astra surface reality is audited in
`docs/qualification/PRODUCT_INTEGRATION_MATRIX.md` (2026-09-27). Existing LEARN,
MAP, Practice Lab, PROJECTS, Interview, and PROGRESS components use canonical
Career Forge adapters. Memory, Research/Knowledge, and Objectives / Activity
are qualified on the Astra integration branch. Notifications / Watch status is
qualified on the Astra integration branch; owner-configurable watch and schedule
management, Perception, System/Capabilities, History/Recovery, and
approval/action remain prototype or missing as classified there.

Phase 1 connects Astra Home and Conversation text input to Friday's existing
typed runtime client/store and canonical conversation stream plus runtime event
projection. It introduces no conversation engine, browser model call, transcript
local storage, or new authority. Deterministic tests, full repository validation,
and owner qualification passed on 2026-09-27. The owner sent a normal typed
message and received a real Friday/local-Qwen response, proved immediate
follow-up context with ephemeral marker `ORBIT-2719` (not present in durable
memory), asked for Career Forge capability state and received a registry-grounded
answer, and navigated Home -> Conversation with the canonical transcript intact.
The learner retention boundary and Pocket/Anna production voice state were
unchanged. The qualified candidate was committed as
`1fb8db70a572dc16014be8e94c0d3ca9db6bc496` and pushed to
`origin/integration/astra-friday`; fetched remote HEAD matched that commit and
the worktree was clean at verification. A documentation-only reconciliation
checkpoint records the final owner evidence and exact continuation state.

Real owner qualification has now accepted arbitrary selected-code tutoring, a
truthful incorrect due-review outcome with weak-area/reinforcement projection,
and a truthful two-answer no-help interview with zero earned interview evidence.
The interview passed mid-session recovery; completed-session recovery exposed a
UI omission and is repaired at `5cd3d87ca2161a80f88d20fcadc75575508bc806`.
Real publication remains
blocked before authorization because current owner state contains no project-
linked mission/task/artifact candidate, the onboarded repository lacks a GitHub
owner/name mapping, and no protected GitHub publication credential or
`GITHUB_WRITE` scope is configured. These are owner/project/external state
dependencies, not permission to fabricate a portfolio artifact.

## Astra Canonical Product Integration — Phase 2: Memory (**Qualified and published**)

Astra Memory now uses the typed Friday runtime client and governed memory
presentation routes backed by `FridayMemoryService` and canonical SQLite. The
workspace has no seeded records or browser-local durable-memory authority. It
supports truthful list/search/lifecycle projection, explicit remember,
correction by canonical supersession, conflict resolution, and confirmed
forgetting through the existing tombstone lifecycle. Durable memory remains
distinct from active-session context, and model output cannot write memory.

Deterministic backend/frontend validation and the real Astra owner flow passed:
explicit save, reload/navigation reconstruction, governed conversational
recall, correction/supersession, candidate service restart and recovery,
confirmed forgetting, visible deleted lifecycle, and a natural governed query
proving no active durable match. A frontend runtime-session restart cursor bug
was found during qualification, repaired, covered by regression, and the exact
read-only recall step then passed. The qualified checkpoint is
`be731f97fecc61b03d507986f3ebf4fccf2c01c4`, pushed and fetched from
`origin/integration/astra-friday`; remote HEAD matched and the integration
worktree was clean.

## Astra Canonical Product Integration — Phase 3: Research / Knowledge (**Qualified and published**)

Astra Research now uses a typed `FridayRuntimeClient` projection over the
existing `ResearchService`. Owner-entered source registration records canonical
domain, title, text, provenance, version, content hash, and creation time in
Friday's research SQLite. Source lists omit source text; content is retrieved
only for an explicitly selected source. No browser-local seeded sources or
notes remain authoritative. The backend has no source update/delete lifecycle,
so Astra exposes neither operation.

Evidence synthesis is truthfully presented as the current service's bounded,
deterministic source assembly, not model-generated narrative. The endpoint
returns its question and explicitly reports that the question is not applied to
retrieval. Astra distinguishes source metadata/text from assembled evidence.
The Knowledge tab accurately reports private document RAG as internal/CLI-only
and repository/code knowledge as guarded/internal with no general Astra query
route; no ingestion or retrieval system was invented for this phase.

Real Astra qualification on 2026-09-27 registered the benign synthetic source
`astra-qual-20260927`, verified its canonical metadata and content, navigated
away/back to confirm persistence, assembled evidence containing the source's
owner provenance, and inspected the truthful Knowledge limitations. The
candidate API at 8766 intentionally used the isolated
`var/astra-memory-phase2-qualification` state root; its fresh Career Forge DB
reports `unverified` and lacks the owner's records. Preservation was instead
verified read-only against the existing Friday API at 8765 and its authoritative
production Learner Twin SQLite: `se.python=explain`, the specified reinforcement
mission is completed, the review remains scheduled for
`2026-09-29T17:43:38.237311+00:00`, and its evidence and attempt are present.
No Career Forge state was changed. Qualification runtime isolation is an
explicit limitation of the candidate, not a learner-state discrepancy.
The qualified capability commit is
`afc69260beae96fe41056c4fea0f9543be604d22`; it was pushed to
`origin/integration/astra-friday` and fetched remote HEAD matched exactly.
The next whole-Friday dependency is Astra Objectives / Activity.

## Astra Canonical Product Integration — Phase 4: Objectives / Activity (**Qualified and published**)

The recovered Terra candidate replaces the seeded and simulated Astra Objectives
workflow with the existing `ObjectiveService` and canonical task-history paths.
Objective create/list/resume/plan/review/cancel remain backend-owned; the
frontend can inspect a canonical plan but cannot approve or execute it. A bounded
read-only `/api/v1/activity` projection joins objective records with persisted
task timeline entries and exposes no repository paths or artifact access.
Deterministic API/UI coverage and full repository verification pass. The owner
created synthetic objectives through Astra, navigated away and back, observed
canonical Activity, and intentionally cancelled the first objective. The owner
then generated and inspected a real canonical plan in the isolated qualification
runtime. Its task remains `awaiting_approval` with no execution outcome; no
approval or execution action was taken. The plan/objective/task survive backend
reconstruction and appear in Activity. The isolated evidence is recorded in
`HISTORY.md` and `CODEX_HANDOFF.md`. Capability commit
`e867bd4114cce6b40440a0362f72c04565154093` is remotely recoverable from
`origin/integration/astra-friday`. No next product slice was started in this
session.

## Astra Canonical Product Integration — Phase 5: Notifications / Watch status (**Qualified and published**)

The candidate replaces browser-local routine and notification state with the
canonical proactive notification journal. Astra reads a bounded list joined to
safe event kind/source and watch-label provenance, acknowledges through the
existing canonical route, and reconstructs acknowledgement timestamps from
SQLite. A read-only registry reports persisted watch enabled state, attached
observer availability, and whether the local polling worker is running. Astra
does not create or edit watches/schedules, change enabled state, or execute
actions. The engine supports internal interval polling/schedules and has no
owner-configurable calendar schedule or arbitrary automation engine. Notification
relevance is shown as the engine's score, not severity or urgency. Focused and
full deterministic checks pass. Owner UI qualification on 2026-09-27 confirmed
the genuine empty state, configured read-only watches, a real canonical
`task.changed` notification, persisted acknowledgement after navigating away and
back, and no approval or task execution. The isolated candidate objective remains
`planned`; its linked task remains `awaiting_approval` with no outcome. No
proactive trigger-injection route was added. Capability commit
`4cd83fc7bca9d4c70239321a442c74019476ef65` is published to
`origin/integration/astra-friday`; the current recovery handoff records the
final recovery SHA and clean worktree.

## Astra Canonical Product Integration — Phase 6: Perception (**Qualified and published**)

Astra Perception now projects Friday's canonical retained-capture metadata and
explicit read-only processing routes through the typed runtime client. Capture
metadata includes provenance, size, and expiry; pixels and filesystem paths are
not exposed. Capture listing, OCR, deterministic OCR-derived UI-state hints,
optional offline CPU ViT labels, and fixed active-window status all come from
Friday services. Processing outputs remain ephemeral in the view. Owner-selected
image ingestion remains an explicit local CLI path; Astra does not upload or
scan files. Direct GNOME capture and active-window awareness were physically
unavailable on the qualification host, and Astra reported both truthfully. No
Perception route gains desktop/action, conversation attachment, Memory,
Research, Objective, or learner mutation authority.

On 2026-09-27 the owner selected and saved a synthetic text-only screenshot,
ingested it through the CLI into the isolated candidate, then observed its
canonical capture metadata in Astra. OCR returned bounded Tesseract text as an
untrusted observation; UI-state returned the literal `text present` hint; the
cached local ViT returned model-estimated labels. Navigation reconstructed the
capture while view-only results cleared. Direct capture returned the desktop
privacy permission denial and created no capture. Active-window status remained
unavailable. Focused and full deterministic validation passed; evidence and
limits are recorded in the product matrix and handoff. Capability commit
`cbd2246f72e028b7347cdfc6fcb31017abd1db0a` was pushed to
`origin/integration/astra-friday` and fetched as the exact remote branch head.

At the end of Phase 6, the next dependency was System / Capabilities; Phase 7
is qualified below. The next missing surface is History / Recovery. Approval /
Action remains a later distinct surface.

## Astra Canonical Product Integration — Phase 7: System / Capabilities (**Qualified and published**)

Astra Local intelligence now projects Friday's `FridayCapabilityRegistry` and
existing read-only service endpoints through the typed runtime client. The
capability list is the same registry used to ground Conversation. The UI keeps
integration maturity separate from registry configuration, permission, and
health fields; those fields are not treated as universal live service probes
or execution grants. API health states only the presentation API response.
Voice, latency, bounded runtime/session metadata, interaction ownership,
proactive watch state, and active-window availability are independently loaded
from their actual routes. Unknown and failed data remain unknown/errors; no
fixture fallback, local capability/health persistence, diagnostic simulation,
restart, permission mutation, approval, or execution control is present. The
development server proxies both `/api` and `/health` to the configured Friday
candidate API.

Owner qualification on 2026-09-27 observed all 13 canonical capability rows,
the presentation API `ok` response, candidate voice disabled with no speech
backend reported, empty bounded session state, idle interaction state,
unavailable active-window query, and the live proactive worker with two
notify-only watches. The owner navigated away and back and reloaded the page;
the registry and runtime values reconstructed. The isolated API used
`var/astra-objectives-phase4-qualification`; production Friday on 8765 was not
restarted. Its existing Pocket/Anna runtime was not changed. The two Astra
qualification tasks remained `awaiting_approval` with no outcome; Career Forge
remained paused and unchanged. No Memory, Research, Objective, learner, or
desktop/action state was mutated.

Validation passed: focused capability/voice API coverage, four focused System
UI tests, 82 frontend tests, frontend lint, TypeScript and production builds,
920 Python tests, repository verification, and `git diff --check`. Existing
Vite bundle-size and Starlette/AnyIO deprecation warnings remain. System /
Capabilities is qualified; History / Recovery is the next missing Astra owner
surface identified by the product matrix. Approval / Action remains separate
and has not started.

## Astra Canonical Product Integration — Phase 8: History / Recovery (**Qualified and published**)

Astra History / Recovery is a read-only view over existing canonical sources,
not a new unified store. It projects ObjectiveService state and TaskHistoryService
timeline through the existing bounded Activity/objective routes, persisted
proactive notification and acknowledgement state, and the desktop action audit
ledger. Each source reports its own empty or unavailable state. Timestamps are
shown as recorded and do not imply cross-store causality. Desktop target IDs and
private paths are omitted. Checkpoint/recovery inspection remains internal/CLI-
only, and bounded conversation runtime events remain session-only. No approve,
execute, cancel, retry, rollback, or restore control is added.

Owner qualification on 2026-09-27 observed both existing Astra qualification
tasks (`task_290e6c92cefe4902b62b` and
`task_90be0b53d357423885aa`) as `awaiting_approval` with no outcome, the real
acknowledged and unacknowledged task notifications with event/watch provenance,
and the truthful internal-only recovery/session-only runtime limits. The owner
navigated away and back and refreshed; canonical records reconstructed. The
candidate showed no desktop action records. Neither task was approved or
executed. The candidate used the isolated
`var/astra-objectives-phase4-qualification` state root; production Friday at
8765 and the protected production checkout were not modified.

Focused History UI tests (3) and focused activity/desktop/proactive API tests
(3) pass. The full frontend suite (85), lint, TypeScript and production builds,
Python suite (920), repository verification, and `git diff --check` pass. The
existing Vite bundle advisory and Starlette/AnyIO deprecation warning remain.
This bounded History / Recovery surface is qualified. Approval / Action remains
a separate subsequent phase and is recorded below.

## Astra Canonical Product Integration — Phase 9: Approval / Action (**Qualified and published**)

Astra Attention now projects the canonical `DesktopControlService` action
ledger. Review is read-only; owner approval and one-time execution are separate
actions through the existing endpoints, with canonical state re-fetched after
each transition. Notifications remain separate. There is no browser-local
approval authority, fake decline state, retry, optimistic success, or free-form
proposal creation. Desktop proposal creation remains backend/internal until an
owner-safe target-discovery contract exists.

Desktop action approval is distinct from task exact-plan approval. Astra has
no secure owner credential/session adapter for the authenticated Gateway task
approval or native objective execution boundaries; neither is exposed as an
active browser action. Recovery/checkpoint mutation remains unavailable.

Physical owner qualification on the isolated candidate used the exact
`launch_app -> org.gnome.Calculator.desktop` proposal. Review left it proposed;
owner approval changed it to approved without launching Calculator; the
separate owner execution launched Calculator and canonical state became
`executed`. Navigation, page refresh, and History reconstructed the same
lifecycle. The older stale action remains `expired` and the first physical
attempt remains `failed`, both preserved as audit evidence. No other desktop
action class is claimed qualified. Both task sentinels remained
`awaiting_approval` with null outcome; Career Forge, production Friday, and
Pocket/Anna were unchanged.

Focused desktop/API tests (52) and frontend suite (90) pass; frontend lint,
TypeScript and production builds, repository verification (924 Python tests),
and `git diff --check` pass. Existing Vite bundle advisory and
Starlette/AnyIO deprecation warning remain. Phase 9 capability commit
`076f6fa0c1ce2c584be24096d8baeb22ff6de799` was pushed to and fetched from
`origin/integration/astra-friday` as the exact branch head. The next dependency
in the product matrix was long-running objective progress (row 49, PARTIAL),
completed by Phase 10 below.

## Astra Canonical Product Integration — Phase 10: Long-running Objective Progress (**Qualified and published**)

Friday now exposes a read-only `GET /api/v1/objectives/{objective_id}/progress`
projection that keeps objective state distinct from canonical task lifecycle,
uses deterministic narratives for every task status, bounds the event timeline,
and reports recovery as unknown when no isolation record exists. Recovery
inspection is scoped to the linked task and does not expose worktree paths,
credentials, approval, execution, rollback, or restore authority. The typed
Astra Objectives panel renders objective/task identities, status, owner
attention, latest event, bounded lifecycle, outcome fields when present, and
recovery summary. It makes no ETA or percentage claim.

Codex-performed local candidate UI qualification used the native Codex in-app
browser against API `127.0.0.1:8766`, Vite `127.0.0.1:5191`, and existing state
root `var/astra-objectives-phase4-qualification`. Rendered text and the
canonical API agreed for objective `76403f1080c949efb09e4aa1a3b1351e`, linked
task `task_90be0b53d357423885aa`, `awaiting_approval`, null outcome, approval
required, latest plan-ready event, bounded timeline, and unknown recovery.
Navigation from History to Objectives and a page reload reconstructed the same
canonical state. History retained both pending task sentinels and desktop
action states `expired`, `failed`, and `executed`. No task was approved or
executed and no desktop action was changed. The UI tool exposed accessibility
state and screenshots; browser console/network capture and raw storage
inspection were not available through that native tool. Candidate API responses
were queried directly and compared with the rendered UI.

The isolated candidate snapshot does not contain the authoritative Career
Forge baseline (`se.python=unverified`; expected mission/review absent), so
Career Forge data preservation cannot be demonstrated from this candidate.
Phase 10 changed no Career Forge implementation or state. The production API
on 8765 and protected production checkout were not touched. No owner physically
observed Phase 10; qualification is Codex-performed and deterministic.

Focused backend and frontend regressions, full frontend tests, lint, TypeScript
and production builds, and repository verification pass. Existing Vite bundle
size advisory and Starlette/AnyIO deprecation warning remain. The next product
matrix dependency is proactive watches/notifications (row 50, PARTIAL); it is
not started in this checkpoint.

## Cross-stage product capabilities (**Planned unless noted**)

- Explicit ask/explain, repo overview, architecture trace, review, bug investigation, traceback/log debugging, feature, test generation, refactor, security, docs, migration, and PR-review modes.
- Router plus planner, coder, reviewer, debugger, test engineer, and security reviewer roles; optional small local helpers for routing, ranking, classification, and summarization.
- Documentation automation for README/API docs/docstrings/changelog/architecture/config/diagrams/data flows/release notes.
- Architecture understanding for components, dependencies, request/DB/auth/security/runtime flows, and graph-generated diagrams.
- Large-refactor mode: plan → dependency analysis → staged edits → checkpoint → relevant/full tests → next stage; no opaque giant patches.
- Unified final platform: llama-server and specialized local models feeding local chat, document/repository RAG, code intelligence, planner/coder/reviewer/debugger/test/security roles, Git transaction manager, task history, Friday-native interface/event services, persistent conversational voice, deep memory, visual perception, safe desktop control, proactive automation, orchestrated agents/models, and the cinematic Friday desktop UI.
- Local Intelligence Sovereignty: core cognition stays on owner-controlled
  hardware; external services supply optional information rather than mandatory
  intelligence. Cognitive roles share the current general-purpose local Qwen.
- Career Forge is the active specialization: Stage 14 establishes its core and
  Stage 22 integrates mature Friday capabilities. Market/trading and creator
  ideas are explicitly deferred outside the active roadmap.

The product definition of done is **Friday — Local Personal Cognitive Operating
System**: local chat and voice; cinematic interface; private RAG/OCR; repository/
code intelligence; planning/tools/validation; safe autonomous execution; Git/
isolation/recovery; persistent personal memory; vision/screen awareness; safe
desktop control; proactive automation; role orchestration; research/self-learning;
Career Forge learning intelligence and cognitive amplification. The unifying
system is `CURRENT LOCAL LLM +
MEMORY + KNOWLEDGE + RETRIEVAL + SKILLS + TOOLS + PLANNING + OBSERVATION +
VERIFICATION + EXPERIENCE + SPECIALIZED CAPABILITIES = FRIDAY`. High-risk work
retains explicit review. Deferred specializations do not imply transaction or
publication authority.

## Stage 12C-A — inline wake command semantics

**Status: ACCEPTED**

Completed:
- inline `Hey Friday, <command>` remainder routing;
- no duplicate Whisper transcription for inline commands;
- authoritative runtime-state preservation;
- deterministic unit/regression coverage;
- live production qualification with wake pause/resume and AEC preserved.

At that checkpoint, remaining Stage 12 work included:
- bare `Hey Friday` acknowledgement UX;
- barge-in observability and long-running voice stability;
- TTS text normalization (accepted later as Stage 12J).

## Stage 12C-B — bare wake fresh follow-up command (**Accepted**)

Accepted:
- bare `Hey Friday` opens a fresh one-shot raw-mic command capture;
- the original wake utterance is never sent to main Whisper;
- fresh capture reuses 16 kHz mono S16_LE 32 ms wake audio configuration;
- each follow-up uses a fresh Silero/UtteranceSegmenter instance;
- no-speech wait is bounded to 8 seconds;
- timeout/capture error closes LISTENING to IDLE before wake resumes;
- a later bare wake works immediately after timeout;
- inline wake remainder remains direct-to-text and bypasses main Whisper;
- AEC remains barge-in-only.

At that checkpoint, remaining Stage 12 work included richer cinematic voice
states, long-running stability qualification, acknowledgement UX, streaming
speech latency (accepted later as Stage 12I), and Markdown-to-TTS normalization
(accepted later as Stage 12J).

## Stage 12D — exact explicit stop semantics (**Accepted**)

Accepted:
- exact normalized `stop`, `friday stop`, and `hey friday stop` classification;
- direct TRANSCRIBING-to-IDLE completion with no LLM or spoken acknowledgement;
- the same narrow classifier after trusted AEC barge-in stops active playback;
- nonexact stop-like phrases remain normal conversation;
- deterministic full-path tests and live inline/AEC/stop-loss qualification;
- removal of the rejected context-specific ASR alias;
- operational documentation for the undistorted MSI microphone/speaker levels.

At that checkpoint, the voice path buffered the complete LLM response before
TTS. The final counting trial took about 10.7 seconds for full generation before
synthesis began; Stage 12I later replaced that behavior with sentence-gated
incremental speech.

<!-- FRIDAY_DELIVERY_POLICY_START -->

## Repository delivery and documentation policy

Friday uses stage-owned Git branches (`stage-N/<capability>`) for roadmap
traceability. Each fully qualified subtask is committed and pushed to its owning
stage branch, then `main` is fast-forwarded to that same accepted commit so
`main` always represents the newest known-good Friday.

Stage branches must remain stage-accurate; work for a new stage begins on a new
stage branch rather than being accumulated on the prior stage branch.

Documentation is part of definition-of-done. Every accepted feature,
capability, architecture/runtime/deployment change, known limitation, or
meaningful behavioral change must reconcile the relevant canonical docs before
the acceptance commit is pushed. `AGENTS.md` defines the mandatory mapping and
acceptance gate; `CODEX_HANDOFF.md` records the current operational handoff.

The durable owner policy in `AGENTS.md` requires continuous autonomous execution:
accepted and remotely recoverable capabilities are checkpoints, not approval
pauses. Verify recovery/clean state and immediately begin the next capability.
After accepted Stage 12H, the next Stage 12 capability is streaming speech and
initial-response latency; all other Stage 12 scope above remains scheduled. Human involvement is reserved
for unavoidable physical input or genuine capability boundaries.
<!-- FRIDAY_DELIVERY_POLICY_END -->

## Stage 12I — streaming speech / initial-response latency (**Accepted**)

Accepted: deterministic sentence chunking and a bounded ordered speech queue let
the first completed sentence enter the existing persistent Piper/player path while
the Qwen response continues streaming. The conversation lifecycle now preserves
SPEAKING at model completion, then finishes playback to IDLE without duplicate or
dropped model text. Focused concurrency/error tests cover sentence order,
backpressure, queue close and the lifecycle race. Physical qualification on
2026-09-10 spoke the requested sky explanation: Piper began at 00:56:36 and LLM
completion followed at 00:56:38; three ordered Piper requests completed and wake
capture returned to healthy listening. Barge-in, exact stop, single-player
ownership and bounded memory remain intact.

## Stage 12J — Markdown-to-TTS normalization (**Accepted**)

Accepted: deterministic presentation-only text normalization runs immediately
before Piper, leaving model streaming and completed conversation text unchanged.
It removes common headings/list markers, emphasis, strikeout, inline-code,
link/image syntax and makes underscore-separated identifiers readable. Focused
unit tests prove the display/speech separation and common Markdown handling.
Physical qualification on 2026-09-10 asked Friday for a bold Markdown arithmetic
answer; Friday spoke the answer naturally as “4”, with healthy wake capture.

## Stage 12K — cinematic voice outcome signals (**Accepted**)

Accepted: the frontend now renders distinct event-derived speaking, completion,
and interruption signals beside its authoritative runtime-state projection. A
barge-in interruption remains visible through its listening handoff without
creating a client-owned lifecycle state, then clears at the next user turn.
Deterministic frontend-store coverage proves the state/outcome separation;
frontend tests, lint, and production build passed.

## Stage 12L — bounded voice-stage telemetry (**Accepted**)

Accepted: always-on production voice telemetry now uses a thread-safe rolling
buffer limited to 2,048 ordered stage records, preventing normal operation from
accumulating unbounded in-process diagnostic memory. Service-journal output
remains the durable evidence path. Deterministic capacity/order and validation
tests cover the boundary.

## Stage 12M — bounded Piper protocol handoff (**Accepted**)

Accepted: the persistent Piper worker reader now hands decoded protocol events
through a bounded 128-record queue. Backpressure is cancellation-aware, so an
event flood cannot grow Friday's memory indefinitely and a full queue cannot
trap the reader during shutdown. Deterministic capacity and retirement tests
preserve ordered single-worker delivery.

## Stage 12N — resident worker health projection (**Accepted**)

Accepted: read-only voice health now reports liveness and local PIDs for the
resident primary wake ASR, fallback wake ASR, and Piper workers, in addition to
capture health. A live restart confirmed all workers healthy; deterministic
coverage verifies the projection without transferring lifecycle authority.

Remaining Stage 12 work includes long-running stability qualification and
observability.


## Astra Canonical Product Integration — Phase 11: Proactive Watches / Notifications (**Qualified and published**)

The existing `NotificationsWorkspace` is qualified as a bounded owner-facing
view over canonical proactive notifications and configured watch status. It
shows notification acknowledgement separately from approval or resolution,
keeps event-occurrence time distinct from notification creation time (including
an explicit unavailable value), and distinguishes enabled watches, observer
attachment/availability, and polling-worker liveness without claiming observer
health. The schedule-source retention observer is described as due-item based;
`Watch.schedule` is an interval-triggered event flag, not a calendar lifecycle.

Qualification used the isolated candidate state root
`var/astra-objectives-phase4-qualification`, the native Codex in-app browser,
and direct canonical API comparison. One already-existing unacknowledged
candidate notification was acknowledged through the UI and re-fetched; no event,
watch, task, objective, desktop, or Career Forge state besides its
`acknowledged_at` changed. History reconstructed that timestamp after
navigation/reload, and System showed the same two enabled notify-only watches
and stopped worker. Watch authoring, schedule mutation, calendar semantics, and
action authority remain excluded pending a separate owner-safe policy.

## Astra Canonical Product Integration — Phase 12: Research / Self-Learning (**Qualified and published**)

Astra Research now distinguishes deterministic evidence assembly from an
explicit, user-triggered question-specific interpretation. The answer route
loads bounded canonical source evidence on the backend and uses Friday's
existing local Qwen reasoning role. It returns the canonical source identity
and hash with the interpretation, labels generated prose as unverified, and
does not claim citation validation. No-evidence requests skip model inference.
The path does not fetch the web, alter model weights, persist generated prose,
write memory, update learning state, or use normal conversation history/tools.
Live Astra UI qualification retrieved the synthetic beacon `ORBIT-7319` from
its registered source while ignoring embedded instruction-like source text.
The deterministic evidence-assembly route and its `question_applied: false`
semantics remain unchanged. Citation verification, browsing, and autonomous
learning from research remain outside this qualified capability.

## Astra Canonical Product Integration — Phase 14: Explain what Friday did (**Qualified candidate**)

A deterministic, read-only task explanation capability projects one exact
canonical task or explicitly linked objective through allowlisted facts,
source labels, up to 20 task events, and bounded isolation recovery evidence.
Astra History and Objectives expose explicit explanation actions, and the
conversation route answers exact task/objective identities without Qwen
interpretation. It preserves objective/task lifecycle distinctions and does
not infer causality from timestamps or treat plan, approval, execution, or
artifact presence as success. Qualification covers candidate API, native Astra
UI, reload/navigation reconstruction, exact-ID conversation routing, and
focused/full validation; see matrix row 54 and ADR 0028. The capability grants
no task, objective, desktop, shell, Git, approval, execution, rollback, or
restore authority.

## Astra Canonical Product Integration — Phase 15A: Transactional rollback safety (**Accepted kernel; product row remains partial**)

The internal checkpoint restore kernel captures a unique pre-restore schema-2
safety checkpoint, serializes task lifecycle/cleanup/promotion through the task
advisory lock, verifies target fidelity, compensates once on failure, and marks
double failure or process interruption for read-only recovery inspection.
Ignored task-local files are preserved because they are outside the checkpoint
model; default storage limits cap each checkpoint at 2 GiB and each task at 16
checkpoints. Task history records bounded isolation events without changing
`TaskStatus`. The CLI is routed through the kernel. This does not add owner
rollback authentication, an Astra action, or publication reversal; matrix row
55 remained PARTIAL at the Phase 15A checkpoint. Phase 15B below now qualifies
the bounded owner-authenticated isolated-task rollback path. Do not start row
56 as part of this capability.

## Astra Canonical Product Integration — Phase 15B: Authenticated owner rollback (**Qualified bounded checkpoint rollback; row 55 remains scoped**)

Adds a distinct `request_rollback` server bridge, separate owner-token unlock,
short-lived volatile session, strict configured Origin and CSRF checks,
TaskHistory-backed exact one-time reviews, stale-state rejection, idempotent
completion recovery, and a gated History review/execute surface. Disposable
native-Astra qualification on 2026-09-28 proved review left the worktree
unchanged; separately executing the reviewed task/checkpoint restored the exact
checkpoint while preserving the synthetic canonical source repository. The
canonical operation ledger, timeline, History navigation/reload, and deterministic
Phase 14 explanation reconstructed the result. Stale fingerprint rejection,
same-key idempotent replay, interrupted-result reconstruction, and different-key
conflict passed focused regressions without a second destructive rollback.
Full repository and frontend acceptance gates passed. This qualifies only the
bounded owner-authenticated rollback of an eligible checkpoint in an isolated
task worktree. It does not provide universal undo or reverse publication,
canonical repositories, desktop actions, or other Friday stores. Do not start
row 56 within Phase 15B.

Phase 15B accepted capability commit: `b03da82f1a37510971f0f84a19a2176d009584db`, published to `origin/integration/astra-friday` and `origin/main`.

## Astra Canonical Product Integration — Phase 16: Unified interruption recovery (**Qualified and published**)

Row 56 adds a typed, exact-task, read-only projection over existing TaskHistory,
admission claims, rollback operations, isolation metadata, execution artifact
records, and exact linked objectives. History is the primary recovery surface;
Objectives progress and Phase 14 explanation consume the same projection.
Current-process worker observation is reported separately from persisted task
state. An active/expired claim describes only its bounded admission lease.
Missing, corrupt, mismatched, and path-rejected isolation metadata fail closed;
cleanup, interrupted rollback, `failed_recovered`, `recovery_required`, and
terminal evidence awaiting explicit reconciliation retain distinct states.

The read model creates no persistence authority and performs no resume,
execution or rollback retry, cleanup, objective mutation, or reconciliation.
Application startup does not reconcile artifacts. The already accepted
explicit ArtifactImporter remains the only exact-identity and digest-idempotent
terminal import/finalization path. Phase 16 candidate qualification uses one
synthetic executing task with interrupted isolation metadata and an isolated
API restart; the canonical task, event, artifact, claim, rollback, objective,
and metadata projection must remain unchanged across restart.

The intended acceptance is bounded owner-visible interruption recovery, not a
universal repair engine. No rows 57–60 are started by Phase 16.

## Astra Canonical Product Integration — Phase 17: Model replaceability (row 57)

Row 57 qualifies configuration-driven replacement of Friday's local
general-purpose model through the existing `LocalLLM` OpenAI-compatible
boundary and sequential role clients. The endpoint is loopback-only; model ID,
context size, endpoint, and timeout are deployment configuration read at
startup. A compatible local backend change takes effect after restart. No
browser switch, hot swap, cloud fallback, database migration, or model-granted
authority is introduced. ADR 0014 continues to select Qwen as Friday's sole
current general-purpose model.

Qualification uses two deterministic loopback HTTP fixture backends with
different ports and model IDs, the same Friday Conversation API path, unchanged
source across restart, prompt-only roles, synthetic Memory/Research evidence,
and isolated candidate SQLite sentinels. A separate bounded smoke verifies the
currently configured Qwen endpoint. Fixture compatibility is not real-model
quality or permanent replacement approval. No safe concurrent alternate model
was loaded. See ADR 0032 and `docs/qualification/model-swap.md`.

Phase 17 qualifies only this bounded configuration and restart contract.


## Astra Product Integration — Phase 18A: Private document Knowledge (row 24)

Row 24 qualifies the bounded owner-selected private-document retrieval path.
The local CLI remains the only ingestion/indexing operation. Astra Knowledge
projects metadata from the existing local index, requires explicit indexed
source selection, constrains retrieval to those sources, and presents generated
answer prose separately from bounded canonical evidence. Embeddings are loaded
from the local cache; generation uses the existing loopback `Role.RETRIEVAL`
client. No answer/query persistence, upload, autoscan, reindex, general
Conversation route, or authority from document text is introduced.

Phase 18A native Astra qualification used one synthetic TXT file and isolated
candidate state. A grounded Qwen answer returned normalized source evidence; an
unrelated question abstained without model generation; navigation/reload
reconstructed the index inventory; and document instructions caused no
authority mutation. Unsupported extensions and absence of fact validation remain
limitations. This did not prove integrated offline operation. Row 58 remained
PARTIAL at the Phase 18A checkpoint; rows 59–60 were not started.

## Astra Product Integration — Phase 18B: Offline operation (row 58)

Row 58 is **QUALIFIED (bounded integrated normal-use offline operation, Phase
18B)**. E2E-018 exercised the existing Astra owner path against a disposable
Friday API running in a transient systemd `PrivateNetwork=yes` network namespace
as the normal owner UID/GID. The host network and production services were not
changed. Candidate Friday exposed only a private AF_UNIX API socket; local
presentation and model bridges used fixed local endpoints. The candidate had no
external IP/DNS access and could not reach host loopback services.

Conversation completed through the configured production local Qwen model by a
fixed chat-completions-only bridge to `127.0.0.1:8080`; the bridge accepted no
destination values, DNS, CONNECT, or generic TCP. Astra showed a real Qwen
answer. Candidate Memory, an active Career Forge mission, and the synthetic
private Knowledge index reconstructed after candidate restart. Local cached
embeddings and a synthetic CodeRAG repository remained usable. The real Astra
Practice Lab Run and Test paths invoked the existing Bubblewrap
`NetworkPolicy.DENY` sandbox and denied external, host-service, and candidate
adapter connections without policy changes. External DNS, direct IP, GitHub,
Hugging Face, and OpenAI negative controls failed inside the candidate.

The Astra browser itself remained in the normal host session: it loaded only
the locally built frontend and contacted a loopback presentation proxy, which
reached the candidate API over its fixed AF_UNIX socket. The browser process was
not placed in the candidate namespace; this qualification proves the integrated
owner flow does not require internet resources, not browser-process egress
containment. The Qwen model, embeddings, runtime assets, and indexes were
already local. Web research, GitHub, external APIs, package/model acquisition,
and first-install operation remain internet-dependent or outside this proof.
See `docs/qualification/offline-operation.md` for topology and evidence.

Row 59 Local Intelligence Sovereignty is **QUALIFIED (bounded Phase 19 local
reasoning plus candidate Owner Sovereign boundary)**. The owner-enrolled
credential broker passed candidate-only native root-file, transient-systemd,
broker-restart, and private-network qualification with sudo timestamps
invalidated. Practice Lab and untrusted model/document inputs cannot retrieve
the credential. The integrated local-Qwen E2E exercised Conversation,
Research, Memory, Career Forge cognition/evaluation, CodeRAG/planning, and
Reviewer/Security, including an optional external-adapter denial followed by
local Conversation recovery. All state in that E2E was synthetic and
disposable. Production `friday-local-ai.service` is not trusted by the
candidate broker; no production admin UI/API integration is qualified. This
also does not qualify every Friday capability, all privileged operations,
browser-process containment, or first-time installation offline; trusted root
remains in the trust base. See
`docs/qualification/owner-sovereign-mode.md` and ADR 0033.

UX-60A rescues the interrupted frontend shell from the accepted `aae600a`
baseline. It keeps the exact Astra Ultra `NeuralPresence` implementation and
its supporting `Vision.css` presentation, then places it beside canonical
Conversation on Home. The persistent Home, Learn, Projects, Knowledge,
Automate, History, Notifications and Settings navigation preserves older hash
routes. Learn presents the existing Career Forge Overview, Roadmap, Practice,
Interview and Progress with a NeetCode-led dark, scannable visual system; all
mastery and next-action content remains canonical. Settings discloses Memory,
Perception and Developer / Diagnostics. `docs/product/` records the product
contract and the observed public NeetCode reference. UX-60A adds no Dynamic
Learning Paths backend, owner mastery mutation, second conversation store, or
required network asset. **Row 60 remains PARTIAL**: it tracks whole-product
owner qualification, including remaining Dynamic Learning Paths capability and integrated
owner flows. At the UX-60A recovery boundary, DLP-1 was the next engineering
step. DLP-1 through DLP-4 are now accepted and published. DLP-4 generalized
arbitrary-domain teaching, assessment, evidence, mastery, retention and
sequencing. The Owner's Stage 28 visual approval and UI publication are
qualified as of 2026-10-14; broader integrated owner flows and rows 60/61 remain
PARTIAL. The final NeetCode-led UX now implements a responsive shared shell,
keeps every existing destination discoverable, preserves `NeuralPresence`, and
adds a canonical read-only Home continuation dashboard. Read-only inspection
found the production API running from a separate General Computer Agency
worktree. A final runtime audit listed 136 OpenAPI paths; the read-only list
endpoints for learning paths, Projects, and watches returned HTTP 200, so the
previously observed 404s were not reproduced and no current missing route is
confirmed. Progress retains available attempts/evidence/history and marks
missing projections unavailable. Owner
decisions preserves the existing execution approval boundary. Stage 28's
responsive matrix passed for all 16 routes at five viewport targets, and the
current live Home and local Qwen conversation were qualified. The host browser
does not expose native reduced-motion emulation, so no reduced-mode screenshot
is claimed. Populated owner-state visuals and broader integrated Career Forge
flows remain open; no whole-product qualification is claimed. See the current
evidence in `docs/product/FINAL_NEETCODE_PARITY_AND_PRODUCT_AUDIT.md` and
`CODEX_HANDOFF.md`.

A final read-only owner-facing route review found no saved dynamic learning
paths or assigned projects in the live owner state. Projects lists four
canonical pathways; opening the FraudShield "Explore the learning path" action
lands on generic Learn without carrying the selected project's identity or
focus. The path-creation form was left empty and no learner state was written.
This project-template-to-learning handoff is the next concrete Row 60/61
integration slice; do not auto-create paths, projects, evidence, or mastery.

### Stage 28 responsive visual candidate — 2026-10-11

The candidate adds the four-item mobile primary navigation, keeps the remaining
destinations available through the existing Ask Friday finder, and stacks
Settings appearance choices and links at narrow widths. A live local preview
checked all 16 hash routes at 1440 × 900, 1280 × 800, 768 × 1024, 390 × 844,
and 320 × 740 CSS-pixel targets: every route rendered a visible heading and
document width fit the viewport. The finder exposed all 16 unique destinations.
Representative desktop Home, mobile Home, and 320 px Settings views were
visually inspected. The candidate preview intentionally had no Qwen connection
and showed “Local connection unavailable”; no owner progress was seeded.

Frontend acceptance passed 159 tests across 31 files plus two Owner-bridge
checks, ESLint, TypeScript, and production build. The repository verifier passed
1,839 tests with 6 skipped, compilation/CLI checks, and dependency consistency
using a disposable Python 3.11 environment whose editable package metadata
points at this exact worktree. The initial fallback Python 3.14 environment had
15 environment-specific failures (missing bubblewrap interpreter path,
different editable checkout, and subprocess timeouts); the corrected targeted
tests and full gate passed. The production bundle still has Vite's existing
large-chunk advisory (~1.29 MB).

This is a responsive candidate checkpoint, not whole-product qualification.
Owner visual review remains open, as do broader integrated product evidence and
the rest of Row 61 scope. Rows 60 and 61 remain PARTIAL. See
`docs/product/FINAL_NEETCODE_PARITY_AND_PRODUCT_AUDIT.md` and the current
`CODEX_HANDOFF.md` for exact candidate identity, protected state, and next step.

### Stage 28 owner-approved Astra UI — qualified and published (2026-10-15)

The Owner approved the exact responsive Astra UI on 2026-10-14 and authorized
its qualification, publication on 2026-10-15 to
`stage-28/final-product-visual-acceptance` and
`main`, and activation as the normal UI at `http://127.0.0.1:5193`. The built
frontend is served by the user-level `friday-ui.service`; same-origin `/api`
and `/health` traffic reaches the existing local API. The service binds only to
loopback and does not supervise or restart the API, Qwen, Pocket/Anna, voice, or
computer-control services. The previous GCA UI and rollback unit are preserved.

All 16 routes passed at 1440×900, 1280×800, 768×1024, 390×844, and 320×740
(80 route/viewport checks). Keyboard, focus, accessible-label, responsive,
modal, tabs, and reduced-motion regression coverage passed. The live UI and
proxied health endpoint returned HTTP 200. The shared local conversation was
confirmed inactive and empty before a bounded Qwen smoke exchange, which
returned `READY`; no physical voice, computer action, restore, or learner-state
write was exercised. Frontend qualification passed 168 tests across 35 files
and four Node Owner-bridge/local-server checks; lint, TypeScript, production
build, and the Python 3.11 repository verifier (1,839 passed, 6 skipped) also
passed. The lockfile then patched two vulnerable development-only transitive
packages; full and production npm audits now report zero vulnerabilities.
`docs/operations/friday-ui.md` records service and rollback operations
and the host systemd namespace limitation.

The accepted implementation and dependency-audit checkpoint is
`018dc4bb7b609d23111060b0112e630cfa852b3d`. At that checkpoint,
`stage-28/final-product-visual-acceptance` and `main` were fetched and verified
against direct `git ls-remote` output at the exact same remote SHA. The final
handoff reconciliation is documentation-only and follows that checkpoint.

This qualifies the approved Stage 28 UI and its live local Qwen path. It does
not qualify the broader Career Forge product or close roadmap rows 60 and 61;
both remain **PARTIAL**. Populated owner-state visuals and native browser
reduced-motion capture remain limitations. See
`docs/product/FINAL_NEETCODE_PARITY_AND_PRODUCT_AUDIT.md`, the integration
matrix, and `CODEX_HANDOFF.md`.

### Stage 29 Project-to-Learn, Owner creation security, and SSE — code qualified and published (2026-10-15; deployed afterward)

Published from Stage 28 baseline
989b98b1b22d6e031a1fcc5f09a84601a88a47d9 on
stage-29/project-to-learn-security-sse and canonical main. The release commit
is the current shared branch tip; resolve the exact SHA from Git HEAD.

Projects carries a canonical project-template ID into Learn. Learn resolves the
registry name/focus, keeps the proposed goal editable, and preserves route
context across reload, Back/Forward, and return to Projects. Stale or malformed
context fails safely. Navigation and Owner-session restore do not create a
learning path, project, evidence, review, assessment, or mastery record. Path
creation still requires an explicit Owner Create action; no template-to-path
lifecycle or schema was added.

Direct curriculum-create, local-model generate, and explicit DLP creation
intents through HTTP Conversation now use
context_owner(request, mutation=True). A valid Owner session, loopback Host,
exact configured Origin, and matching X-Friday-CSRF proof are required before
model or DLP writes. Existing trusted
in-process calls and the route contracts for other DLP mutations are unchanged.
The approved Stage 28 visual and existing assessment/review/mastery rules are
unchanged. See ADR 0052 and
docs/architecture/dynamic-learning-paths.md.

The former synchronous SSE subscriber blocked an AnyIO worker during server
shutdown. The API now uses bounded async subscriber queues, rejects new
subscriptions during shutdown, prioritizes a close marker, cleans up
disconnects, and after a one-second drain aborts only remaining SSE transports.
It does not cancel model work, tasks, project generation, or computer actions.
Three real FastAPI/Uvicorn stop cycles on the live dependency versions completed
in 0.265, 0.264, and 1.268 seconds; ASGI lifespan completed, no blocked reader
or child remained, and SIGKILL was not used. Uvicorn re-raised SIGTERM after
cleanup (return code -15). This is idle SSE evidence, not production task-drain
or restart qualification.

The exact source passed the full repository verifier (1,864 passed, 6 skipped),
frontend tests (182 across 37 files), four bridge/local-server checks, ESLint,
TypeScript, production build, dependency checks, changed-file Ruff, Python
compilation, and diff checks. The isolated browser/FastAPI/SQLite Owner journey
passed with a temporary store: unauthorized attempts made no writes, explicit
authorized Create persisted a draft, and a fresh API process plus browser
reload recovered it. Mastery/evidence and Project records remained unchanged.

Known limitations: two historical MCP stdio EOF timeouts remain unexplained;
whole-tree Ruff reports 11 findings in unchanged files; one cold isolated test
start missed its 10-second readiness window before an instrumented pass. The
live API remains on the protected GCA checkout and does not yet enforce the
Stage 29 creation boundary. No production service, Qwen process, Owner session,
learner/project data, or task was modified; no deployment occurred. API-first
deployment remains blocked until task clearance and atomic new-work admission
are implemented and qualified. Rows 60 and 61 remain PARTIAL; this release does
not qualify the full Career Forge product. See CODEX_HANDOFF.md and
docs/operations/stage29-release-plan.md.

### Stage 30 connected Project → Learning Journey — bounded slice deployed and qualified (2026-10-16)

Stage 30 adds one connected FraudShield journey using the existing Projects,
Dynamic Learning Paths, Career Forge, Reviewer, and Owner-session authorities.
Opening the project pathway is read-only. In an isolated real-browser flow, an
unauthenticated Create returned 401 without writes; Owner unlock alone created
nothing; explicit CSRF-authenticated Create persisted one DLP draft; explicit
Start activated it; and an authenticated milestone assignment created exactly
one canonical FraudShield project. Replaying the same assignment returned the
same project instance.

Learn presented the assigned milestone's prerequisites, objectives, evidence
requirements, and a contextual Career Forge lesson. The Owner submitted an
unexecuted source artifact and explanation to the existing local Reviewer. An
incorrect result persisted the attempt, created no project evidence, set
`needs_revision`, and recommended revision. A correct result created one
milestone evidence record, completed this one-competency project, and updated
the recommendation to continue from the DLP sequence. Career Forge mastery
remained unchanged; no task execution, computer action, or GitHub publication
occurred. Browser reload and a separate isolated API process recovered the
same path, project, review, evidence, and progress from temporary SQLite stores.

The isolated Chrome/FastAPI/SQLite journey also proved navigation-only reads,
rejected unauthenticated path creation and project assignment, CSRF persistence
across Learn/Projects navigation, and no duplicate project after assignment
replay or reload. The deterministic fixture Reviewer and Teacher made no Qwen
call. The test did not use production credentials, learner data, services, or
computer actions.

Qualification passed: frontend 184 tests across 37 files and four Node
bridge/local-server checks, full ESLint, TypeScript, and production build; the
Python 3.11 repository verifier passed 1,866 tests with 6 skipped, compilation,
CLI checks, and package consistency. The first fallback verifier attempt used
Python 3.14 with an editable package pointing at another checkout and failed
21 cases; its log also exposed the API exact-route assertion that needed the
new endpoint. Rebinding a disposable Python 3.11 environment to this exact
worktree and correcting that endpoint expectation produced the passing final
gate. The Python verifier used 1.71 GiB peak process-tree RSS, with 22.29 GiB
minimum host-available RAM; its memory-pressure stop guard did not trigger.
TypeScript, lint, build, browser, and full Python phases were run sequentially.

MicroTurn remains research-only and NO-GO for the live 600 ms voice target:
the supplied benchmark records 28 ticks, 18 deadline misses (about 64.3%),
uneven response quality, and runner exit 120 during Python shutdown. Cleanup was
corrected afterward, but the full model benchmark was not rerun and no audio,
microphone, barge-in, or physical Stop qualification was performed. Stage 30
did not load or run Qwen, change voice/vision configuration, or add MicroTurn
integration.

This bounded slice does not qualify the full Career Forge learner journey or
Friday V1. Roadmap rows 60 and 61 remain PARTIAL; broader multi-topic learning,
retention/adaptive progression, voice operation, validated project execution,
approval-gated publication, and final visual acceptance remain open.

The owner-approved release source `2c200bf798e195f2fff4908b147304d46a49d795`
is deployed on `main` and `stage-30/career-forge-connected-journey`. The
immutable runtime pointer resolves to that exact release. API and UI health,
same-origin Learn/Projects routes, all 13 frontend asset hashes, fail-closed
unauthenticated Owner checks, voice readiness, and healthy computer agency were
verified after cutover. Projects is schema v3; Learning Paths remains v2. All
15 production databases pass integrity checks and their table counts match the
post-stop backup. No production project or learner record was created, the
pre-existing mission and Practice Lab draft remain intact, and all 12
historical `in_doubt` actions remain untouched. See the deployment record in
`docs/operations/stage30-release-plan.md` and the current `CODEX_HANDOFF.md`.

### Stage 31 qualified, published, and deployed — Multi-topic ML Engineering Learner Journey

Stage 31 adds one connected three-node fraud-detection learning journey on the
existing DLP, Career Forge, Projects, Owner-session, and Reviewer authorities.
The versioned curriculum teaches data preparation/evaluation, logistic
regression, and trees/model comparison with explicit sequential prerequisites,
substantive lesson content, and fixed conceptual/practical question contracts.
Career Forge retains the answer and feedback history and applies its existing
mastery ladder; independent application requires two distinct correct,
unassisted question IDs. Failed answers remain recorded and recommend existing
reinforcement. The Astra Learn path restores across page and API restart.

Project artifact/explanation review preserves its own assessment-contract
fingerprint and remains durable in Project/Career Forge evidence. It neither
becomes a fixed DLP question answer nor directly changes DLP mastery. Unknown
question IDs and unauthenticated assessment, path, and project mutations fail
closed. The isolated real-Chrome/FastAPI/SQLite browser journey passed with
deterministic Teacher, Assessor, and Reviewer fixtures; it does not claim live
Qwen pedagogical quality or whole-product Career Forge qualification. All three
nodes reached `apply_independently`; Node 1's failed answer recommended
`REINFORCE_FIRST`; rejected and corrected project artifacts produced two
durable reviews and one accepted project evidence record; browser reload and
isolated API restart recovered the path and project. No task, computer action,
or task execution occurred in the qualification run.

The qualified application commit is
`c1b1fee95e9d651d4caf3cd5184296170636f450`. Release source
`075645a3198a37a9ff101a18614065ff8cc5c9e9` (tree
`a0337a2b277e57c046e5eba45fc3a2a661cd3e04`) is deployed through the immutable
`/home/kumar-rishav/.local/share/friday/api/current` pointer. The approved
fast-forward advanced `main` from `b939874e89fb695360425bfe8ca4dd82dee05769`
to the exact release source; the post-deployment documentation checkpoint is
published on both `main` and `stage-31/ml-engineering-learning-journey`.
Release manifest SHA-256 is
`874abb7f4a5b1d170cf0338fcd1d9d47877a0b7f6fbb81bc9505a92a9293f5d1`.

The release adds no database migration: Learning Paths remains schema v2 and
Projects schema v3. All 15 production stores pass integrity checks and table
counts match the verified post-stop backup. The pre-existing active mission
and Practice Lab draft remain intact; no production learner attempt, evidence,
path version, or project was created. The Stage 30 contract can read Stage 31
stored mastery rows but does not project the new Stage 31 progression in its
owner-facing DLP view. Preserve Stage 31 data and recover forward after any
Stage 31 learning writes; Stage 30 is not a semantically safe rollback after
such writes. Backup manifests, service configuration snapshots, checks, and
recovery details are recorded in `docs/operations/stage31-release-plan.md` and
under the owner-only Stage 31 maintenance directory.

Post-cutover checks passed: API and UI health, Projects/Learn/Progress routes,
all 13 frontend asset hashes, mission and draft recovery, unauthenticated
Owner rejection (401), wrong-Origin rejection (403), and integrity/count checks
for all 15 stores. Pocket/Anna, capture, wake path, and computer-agency health
are ready; there is no active voice turn. Qwen and vision were not restarted.
The UI interruption was about 6 minutes and 2 seconds; API and voice were
unavailable for about 1 minute and 56 seconds. The longer UI window included
sequential local voice-worker startup and correction of a release-checker
symlink predicate; no application or data fault occurred. Rows 60 and 61 remain
PARTIAL; this three-node journey does not establish Senior ML/AI Engineer
readiness or complete Career Forge. Stage 32 was not started in this session.

### Stage 32 — Voice-first learning and reliable interruption (**QUALIFIED AND DEPLOYED — physical acceptance and full regressions passed; production release verified 2026-10-27**)

#### Latest physical acceptance — all gates passed (2026-10-27 local, physical PASS)

Candidate `a99591b3183d45bb83ce30b46372e7c1` used the current source-bound
manifest. Its immutable evidence is under
`/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-physical-operator-ready-20261027T125146Z-f61afc463909/`.
The manifest source revision matches the tested worktree snapshot
`uncommitted:277253b8bd17c4f2c72919399a50eee6cc146fe4:worktree-content-sha256:4d58847ff0851cf2176c8b2b06cfdc3a71f0f1d90edb3c31c3dc9a2e1c065ec4`.

All ten physical gate results passed: wake; learning continuation and learner
path retrieval; Qwen explanation; Owner-confirmed Pocket/Anna output; physical
barge-in; repeat intent and correlated response; spoken Stop; five-second
no-stale-playback confirmation; next-wake recovery; read-only learning
progress; isolated spoken assessment; and Owner-confirmed Astra voice
synchronization. Resource qualification passed before capture handoff and the
guard did not abort. The assessment was isolated to candidate state, was
marked incorrect, and awarded no mastery or production write.

The complete acceptance ledger is PASS:

| Gate | Result | Evidence |
|---|---|---|
| A. Physical wake | PASS | Accepted wake count increased once; listening acknowledgement completed. |
| B. Finalized ASR | PASS | Gate-eligible finalized transcripts with accepted model or inline-wake provenance were recorded for learning, repeat, Stop, progress, and assessment flows. |
| C. Machine-learning continuation | PASS | Spoken continuation routed to the current ML lesson. |
| D. Learner-path retrieval | PASS | Path `48790ea5da65411483284246bc32b670`, node `data-evaluation`, version 1 retrieved. |
| E. Qwen lesson generation | PASS | Local Qwen response and assistant completion were recorded. |
| F. Pocket/Anna playback | PASS | Candidate voice health selected Pocket/Anna and playback events were recorded. |
| G. Owner audibility | PASS | Typed Owner confirmation was bound to playback ID `a99591b3183d45bb83ce30b46372e7c1:1590e274bddb4926b8059ba260822bd3:31`. |
| H. Physical barge-in | PASS | VAD interrupted verified active playback; finalized ASR and follow-up route were recorded. |
| I. Repeat-lesson intent | PASS | `Please explain the lesson again.` was accepted by the production repeat intent classifier. |
| J. Correlated repeat response | PASS | The same learning path/node was retrieved and a correlated Qwen/Pocket/Anna follow-up began. |
| K. Spoken Stop recognition | PASS | Final ASR was `Friday, stop.` at event sequence 359. |
| L. Active Stop cancellation | PASS | Active playback was interrupted; candidate logs record `TTS_CANCELLED` and `PLAYBACK_COMPLETE`. Qwen had completed generation before interruption, so active LLM cancellation was not applicable. |
| M. No stale queued speech | PASS | The formal five-second quiet gate and typed Owner confirmation passed; no stale speech event appeared before recovery wake. The source sets the speech-cancel event and closes the producer queue; no separate queue-invalidation event is emitted. |
| N. Wake recovery | PASS | A subsequent accepted wake and listening lifecycle completed. |
| O. Read-only progress | PASS | `progress_read` event marked `read_only=true` and returned the current path/node projection. |
| P. Isolated spoken assessment | PASS | Exactly one candidate attempt was recorded, marked incorrect, with no mastery and no production write. |
| Q. Astra UI synchronization | PASS | Owner confirmed candidate UI/voice synchronization through the typed operator action. |
| R. Resource safety | PASS | Resource preflight qualified; the independent guard did not trigger during the physical session. |
| S. Stage 31 restoration and data preservation | PASS | Independent report is `RESTORED_VERIFIED`; release pointer and production database fingerprints were unchanged, health and capture recovery checks passed, candidate workers stopped, and timer cleanup verified. |

Final verification on the same code snapshot: `scripts/maintenance/verify-repository.sh`
passed, including **2,039 Python tests passed and 6 skipped**; Ruff and Python
compilation passed; the frontend suite passed **189 tests**, ESLint, TypeScript,
production build, and dependency checks passed; all 101 installed Python
packages are compatible. The frontend build reported the existing large-chunk
advisory. `git diff --check` passed before the final documentation-only
reconciliation and is rerun for source closure. No frontend source or approved
Astra UI change is included.

For Stop, repeated playback turn `a11c4c59a8f04ce8b3f3c97c4ad91550` started at
12:55:40.455605Z (runtime session `99c79c1de4a0448097c4b6235569d2b6`, sequence
222). The Owner reports speaking while playback was active; the recording does
not separately timestamp physical speech onset. VAD interruption sequence
353 occurred at 12:55:56.998292Z, 16.543 seconds after playback start, with
514,560 PCM bytes written. The same runtime session finalized `Friday, stop.` at sequence 359 at 12:55:57.415961Z, then entered `voice_explicit_stop` at
sequence 360 at 12:55:57.416027Z. Detection-to-ASR-finalization was 417.669
ms; interruption-to-Stop state was 417.735 ms. Onset-to-stop latency cannot be
calculated because physical onset was not recorded. Candidate logs record
`TTS_CANCELLED` followed by `PLAYBACK_COMPLETE`; Qwen generation had completed
before the interruption, so active model cancellation was not applicable. The
listener-start event at sequence 356 carries the interrupted playback's
`voice_turn_id`; that listener stopped at sequence 357 and its finalized
transcript was sequence 359 in the same runtime session. This ordered capture
chain correlates the Stop transcript to the interrupted turn even though the
transcript event itself does not repeat the turn ID.

The separate `no_stale_playback` gate passed its five-second quiet window and
typed Owner confirmation. No stale speech event appeared before the subsequent
recovery wake. The formal operator result for `spoken_stop` and the quiet gate
is PASS; this resolves the earlier capture-drain failure without changing the
acceptance threshold.

Independent restoration reached `RESTORED_VERIFIED`: the immutable Stage 31
release pointer remained `075645a3198a37a9ff101a18614065ff8cc5c9e9`, production
database fingerprints matched before/after, API/UI/Qwen/Qwen-Vision health
checks returned 200, the microphone returned to listening with advancing PCM,
AEC cleanup passed, candidate processes stopped, and the recovery timer was
inactive. Stage 32 is physically accepted and source-closed. The 51-path implementation
commit `af0ec81ed60ab5c888771b8c543850e60f51dfb6` is published on
`stage-32/voice-first-learning-reliability`; remote verification resolved to
the same SHA. The source-acceptance checkpoint itself did not yet include a
production release. The controlled production release and following
documentation checkpoint are recorded immediately below. Stage 33 remains
handoff-only with no implementation in this worktree.

#### Controlled production release — DEPLOYED AND VERIFIED (2026-10-27)

The accepted runtime source `512d1d521b44b853d7ffebd62222e087b199c3a3`
(tree `2fc80bf43cefac48ca175d4e927adcea6c29b55b`) is installed at the immutable
release directory and selected by `/home/kumar-rishav/.local/share/friday/api/current`.
Main was fast-forwarded from `67a44833844787c7fe5e81603e160aaa92a0a07f` to
this exact runtime source; Stage 32 and main were remotely verified there before
cutover. The subsequent docs-only release checkpoint is published on both refs.
Stage 31's immutable release is retained. The release manifest SHA-256 is
`3552d1d08e470555bbe14cf5b9c239e597f86bd4d2290edd318034d759a7c0fa`; all 686
SHA256SUMS entries verify. There is no migration, lock change, or service
configuration change.

API/UI, Qwen, and vision returned 200 after cutover; Pocket/Anna, wake, AEC,
capture, and workers were ready. Exact-release isolated smoke and live release
checks passed, including all 13 frontend assets, protected-route denial,
restoration of the existing mission/attempt/draft, and all 15 database integrity
and fingerprint checks. A 55.4-second/12-sample stability watcher found no
health, voice, memory, PSI, database, or timer fault. Qwen and vision were not
restarted. No owner data or task/action history was changed; the 12 historical
`in_doubt` and three `result_present` actions were not replayed. No new
post-deployment speech cue or authenticated screen observation was performed;
the physical A–S PASS is source-bound pre-deployment evidence, and protected
screen routes correctly required an Owner session that was not present. Full
checks, backup/config manifest digests, and recovery boundaries are in
`docs/operations/stage32-release-plan.md`. Product rows 60 and 61 remain
PARTIAL. Stage 33 was not started; see the current `CODEX_HANDOFF.md` for its
recommended first owner-facing slice.

#### Earlier physical barge-in result and correction in progress (2026-10-27 local, PARTIAL)

Physical candidate `9c039bb8599248908b13a9ef8652e805` passed guarded startup,
ALC898/AEC capture handoff, real wake, learning continuation, local Qwen lesson
generation, and Owner-confirmed Pocket/Anna audibility. Lesson playback began
at 10:19:10.073 UTC. The barge-in cue appeared while it was still speaking;
the runtime emitted `voice.speech.interrupted` at 10:19:45.211 UTC after 35.138
seconds, then entered LISTENING. The 1.6-second finalized ASR transcript at
10:19:48.010 was `Can I have a beat that?`; the runtime routed that text into a
new conversation turn. The gate failed immediately because it required exact
transcript equality with `Can I repeat that?`, before a repeat lesson route
could complete. The physical audio was not retained, so the transcript cannot
be acoustically replayed. Event and capture evidence prove microphone/VAD
activity, duplex interruption, and an interrupted playback event; they do not
prove correct repeat-intent recognition.

The candidate health reported Pocket/Anna as the selected output; Piper was
present in the worker inventory but was not the selected backend. The
independent restore reached `RESTORED_VERIFIED`, cleaned up candidate and
resource-guard units and the automatic timer, restored Stage 31 listening with
advancing PCM, and verified unchanged production data and release pointer.
Evidence is under
`/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-physical-operator-ready-20261027T101527Z-aa0f8961e56f/`.

The source fix adds only the observed, fully anchored ASR homophone as a
learning `REPEAT` intent, changes the spoken qualification cue to
`Please explain the lesson again.`, and has the operator gate use Friday's
production repeat-intent classifier followed by correlated lesson-context,
Qwen-delta and speech-start evidence. The gate still fails for unrelated
transcripts or generic assistant routing; wake, VAD, AEC and resource
thresholds are unchanged. The regression passes 120 focused tests, including
an integration test from the recorded ASR phrase through the existing router
and `VoiceLearningCoordinator`; report:
`/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-engineering-qualification-20261026/stage32-barge-in-intent-fix-final-20261027.xml`.
This result was superseded by the later physical retest below.

#### Previous physical retest — Stop evaluator false positive corrected (2026-10-27 local, PARTIAL)

Physical session `db4543abee204dc8a5f5550a1d2c4b36` ran from
`2026-10-27T10:40:51.707Z` through independent restoration at
`2026-10-27T10:48:52.393Z`. Its evidence is under
`/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-physical-operator-ready-20261027T104034Z-2e0b35f31718/`.
The operator marked all ten gates passed; event review found its Stop gate
incorrectly joined separate events. The repeat response began at sequence 218
(`10:43:16.772Z`). Sequence 353 (`10:43:35.915Z`) interrupted that playback,
but the finalized transcript at sequence 359 was `Very good, stop.`; Friday
then generated and completed a normal response at sequence 421
(`10:43:56.508Z`). The exact `Friday stop.` transcript and
`voice_explicit_stop` transition occurred at sequences 427–428
(`10:44:16.213Z`), after playback was already complete. Spoken Stop was
recognized, but it did not cancel active generation/playback: Gate L FAILS.
Gate M remains PENDING because the quiet period followed a Stop issued after
the playback ended, not a verified active-playback cancellation.

The physical barge-in path passed: playback interruption was recorded at
sequence 179 with 1,244,160 PCM bytes after 32.133 seconds; ASR finalized the
requested `Please explain the lesson again.` at sequence 185; the existing
`data-evaluation` path/node was retrieved at sequence 186; Qwen produced the
repeat explanation; Pocket/Anna playback began at sequence 218. The Owner
confirmed audibility. Read-only progress, an explicitly confirmed isolated
assessment, and Owner-confirmed Astra synchronization passed. The assessment
was marked incorrect in candidate data, made no production write, and awarded
no mastery. ALC898/AEC capture, wake recovery, resource qualification, and
Stage 31 restoration/data fingerprints were verified.

The acceptance harness now binds Stop interruption to the active playback
turn and ordered matching transcript/state transition, and fails if a normal
assistant response starts first. The ambiguous `Can I have a beat that?`
homophone alias was removed because no recording exists to establish those
words as a repeat request. One hundred twenty-one focused voice-intent,
operator, and integration tests pass. These fixes require a fresh physical
Stop retest; the candidate must be refreshed from current source and left
PREPARED before the Owner provides new START authorization. Stage 32 remains
PARTIAL.

#### Previous physical Stop audit — playback stopped; Stop transcript missing (2026-10-27 local, PARTIAL)

Candidate session `217ae63a2d6347d58fe69200058d53b1` used the corrected
same-turn Stop evaluator and source-bound physical workflow. Evidence is under
`/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-physical-operator-ready-20261027T113522Z-3d61d8b5eac9/`.
The Owner reports clearly saying `Friday, stop.` during the repeated lesson and
hearing Friday stop immediately with no later speech. The runtime confirms a
playback interruption on the active repeat turn but does not preserve a
separate physical speech-onset timestamp or finalized Stop transcript.

Playback sequence 208 (`voice.speech.started`, `11:38:14.275Z`) belongs to
voice turn `78a94614739f4616b237b8cbdb6a9d8c` in runtime session
`f7fc4e9f05c04a7aa051d1be2b7f8412`. At `11:38:27.168Z`, sequence 349 emitted
`voice.speech.interrupted` for that same turn after 12.893 seconds of playback
and 583,680 PCM bytes. The runtime transitioned to idle at sequence 350 and
resumed listening at 351–352. Candidate logs record TTS cancellation, playback
completion and LLM cancellation, followed by a follow-up capture timeout. No
ASR transcript or explicit Stop transition followed; the listener idled out at
sequence 353 (`11:41:27.482Z`). The Owner confirms no further audible speech;
the event log also contains no later speech-start or speech-completion event.

The operator marked `spoken_stop` failed with `physical_gate_timed_out` after
240.496 seconds because the gate never received a finalized Stop transcript.
The playback cancellation is supported by the interruption event and TTS
cancellation, but exact command recognition and its causal link to cancellation
are not established in software. The formal no-stale-playback gate did not run,
so it remains pending despite the Owner's direct silence observation.

The first incorrect software transition was monitor shutdown: after VAD had
confirmed speech and playback stopped, `capture_interruption` honored the
turn-cleanup stop event before the segmenter completed the same utterance. The
follow-up capture then opened after the physical utterance and timed out. The
monitor now drains a confirmed utterance through its bounded end before
shutdown, turn cleanup waits up to 35 seconds for that drain, and the evaluator
requires the interruption and transcript to match the active playback session
and turn. An idle-timeout event now gives the precise failure
`interrupted_utterance_missing_finalized_stop_transcript`.

The saved event timeline was replayed through the corrected evaluator. The old
result remains FAIL (`physical_gate_timed_out` at 240.496 seconds); the new
result is FAIL (`interrupted_utterance_missing_finalized_stop_transcript` at
the listener idle timeout). No physical evidence was fabricated and no pass
was inferred. The 134-test focused suite passed with zero failures or skips;
Ruff, compilation and `git diff --check` passed. The independent restoration
report is `RESTORED_VERIFIED`; Stage 31 release pointer, learner data, API/UI,
Qwen and vision remained healthy, and candidate/timer cleanup completed.

Stage 32 remains PARTIAL until the fixed monitor physically captures and
finalizes `Friday, stop.`, the active cancellation is correlated, the formal
quiet check passes, and the remaining acceptance ledger is reconciled.

#### Latest resource-guard root cause and correction (2026-10-27 local, PARTIAL)

Replay of the 2026-10-26 trigger shows the candidate orchestrator applied its
10-second sustain timer to rolling PSI `avg10`. Candidate avg10 remained above
2% for 10.544 seconds (5.16% at abort), while actual cumulative full-PSI
intervals above 2% lasted at most 6.017 seconds system-wide and 4.010 seconds
in the candidate cgroup. The short burst was real; MemAvailable was 23.79 GiB,
SwapFree 3.56 GiB, candidate memory current/peak 6.27/6.58 GiB, and cgroup
high/max/OOM events were zero. A detailed sample just after the trigger records
9,144 major faults/22.96 GB reads for Qwen and 4,001 major faults/525 MB reads
for the candidate API. Cold page-ins are supported as contributors, while the
full kernel reclaim path remains unproven.

Both candidate and independent enforcement now use cumulative PSI deltas and
the unchanged 2%/10-second thresholds. The runtime parser retains the system
`total` counter; a delayed candidate-loop sample is rebased only when the
independent same-session guard is active with a fresh sample. Missing counters,
counter resets, an unhealthy external guard, and invalid intervals in the
independent guard still fail closed. Thirty-five focused resource-guard and
candidate-orchestrator tests pass. The 15-file Stage 32/voice/agency focused
suite passes 209 tests; its report is
`/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-engineering-qualification-20261026/stage32-focused-resource-guard-fix-20261027.xml`.
Targeted Ruff, compilation, and diff checks pass. The corrected candidate code
has now completed the Owner-started bounded no-speech resource requalification.
Session `ecf2fca8919b493e9f6f5efe20ed49c9` reached READY in 81.48 seconds and
remained READY for 180.23 seconds, with 177 orchestrator samples and 359
independent guard samples. Candidate peak memory was 5.82 GiB; minimum
MemAvailable and SwapFree were 22.82 GiB and 5.23 GiB. Candidate cumulative
full PSI did not increase; system full PSI exceeded 2% for at most 2.017
seconds in total, with no interval longer than 1.009 seconds. Existing
thresholds were unchanged, candidate cgroup high/max/OOM counters stayed zero,
and no resource trigger was recorded. Host reclaim and swap-in were observed,
but the candidate cgroup had no swap-in/out increase. The bounded-completion
path stopped the independent watchdog and restoration reached
`RESTORED_VERIFIED`, including unchanged Stage 31 release and learner
databases, healthy API/UI/Qwen/vision, ALC898/AEC cleanup, wake-armed listening
capture with advancing PCM, and candidate/timer cleanup. The five-run
deterministic resource report is
`/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-operator-control-root/resource-qualification-after-no-speech-20261027.json`.
The operator is now prepared for the physical workflow. Stage 32 remains
PARTIAL until the physical speech, learning, audibility, interruption, stop,
recovery, assessment, Astra synchronization and final restoration gates pass.

#### Latest guarded candidate — Vite owner-capability bootstrap dependency (2026-10-27 local, PARTIAL)

Candidate `aaf4f51968574c84a47fdc97ef58c7ae` received exact typed `START` and
stopped Stage 31 capture. Vite exited immediately because its local-owner
bridge could not find the private `<session>/owner/owner-capability.json` file.
The candidate API normally creates this file when it starts, so launching
Vite before the API exposed a startup dependency. Candidate voice workers did
not launch; no speaking cue or physical speech gate was reached.

Independent restoration reached `RESTORED_VERIFIED`, confirmed Stage 31
listening and unchanged learner data, and stopped candidate processes; the
automatic restoration timer remains the safety fallback. Evidence is under
`/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-physical-operator-ready-20261026T192407Z-913165b550e0/`.

The orchestrator now provisions this session-scoped capability through the
existing `LocalOwnerTrust` implementation before launching Vite. It must keep
the existing owner-only directory/file permissions, installation binding,
no-overwrite behavior, and API reuse of the same capability. Targeted tests and
regressions verify the owner-only directory/file permissions, installation
binding, and no-overwrite reuse; 29 orchestrator/resource tests and targeted
Ruff pass. The next guarded run must verify the live Vite-first handoff before
any speech. Resource thresholds remain unchanged; Stage 32 remains PARTIAL.

#### Latest physical candidate — host PSI abort during candidate voice-worker startup (2026-10-27 local, PARTIAL)

Candidate `195123a133b54ef2b5ee6b0fc1a813ea` passed fresh preflight and
received one exact typed `START`. Stage 31 capture handoff began. Candidate
logs show Parakeet, Moonshine, and Pocket/Anna workers started and the ALC898/AEC
capture check reported ready, but the 15-second resource-stability gate did not
complete and no speaking cue or physical speech gate was recorded.

The independent guard aborted at 19:01:41.741 UTC because host full-memory
PSI avg10 remained above the unchanged 2% limit for 10.024 seconds; the trigger
sample was 2.38%, and the sampled peak was 5.98%. Candidate cgroup memory peaked
at 5.46 GiB; candidate full PSI peaked at 2.89% but was 1.42% at the trigger.
During the final detailed 10-second interval, candidate cgroup major faults
rose by about 603 of the host's 634 total. Per-process samples attribute 490
major faults to the newly launched Vite/Node process, 81 to Piper, and 18 to
the candidate API. Vite became ready immediately before the pressure trigger.
This makes overlapping cold Vite and voice-worker loading the strongest
identified contributor, but does not prove it was the only contributor or the
complete kernel reclaim path. MemAvailable stayed above 23.37 GiB, SwapFree
above 4.29 GiB, and OOM counters stayed at zero.

The candidate now starts Vite and warms `/src/main.tsx` after exact `START`
and Stage 31 capture shutdown, then requires 15 seconds within the existing
resource limits before launching candidate voice workers. The independent
restore timer and resource guard remain active, and all thresholds are
unchanged. Targeted regression must pass; the next guarded candidate run must
still prove stable live startup before any speaking cue is released.

No speech cue, wake, transcript, or physical voice gate passed. The independent
restore report reached `RESTORED_VERIFIED`, verified Stage 31 listening and
unchanged production learner data, stopped the candidate, and confirmed timer
cleanup. Evidence is under
`/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-physical-operator-ready-20261026T190037Z-9c9fd5233ade/`.
Stage 32 remains PARTIAL. The next guarded candidate run can verify the
serialized startup path; do not speak until the page displays `START SPEAKING NOW`
and the exact phrase. The previous barge-in attempt's next exact cue remains
`Can I repeat that?`.

#### Latest physical candidate — barge-in transcript mismatch and safe restoration (2026-10-27 local, PARTIAL)

Candidate `b4c24cfe7a6647b992fd41baccd2547e` completed guarded resource
preflight, ALC898/AEC capture handoff, physical `Friday` wake, learning
continuation, a live Qwen response, and owner-confirmed Pocket/Anna audibility.
During active playback, the runtime recorded `voice.speech.interrupted`
(sequence 183). The finalized 1,472 ms interruption transcript (sequence 189)
was `Can I repeat that?`; the Owner reported speaking the displayed
`Friday, repeat that.` cue. The exact transcript gate failed, so no learning
repeat route or later Stop, recovery, progress, assessment, or Astra UI gate
was credited.

The resource guard did not trigger during this candidate. Its samples show
system full-memory PSI avg10 peaking at 1.99%, candidate full PSI at 0%, minimum
MemAvailable of 23.15 GiB, and minimum SwapFree of 4.10 GiB, all under the
unchanged thresholds. The live Qwen response completed safely; following the
earlier PSI abort, this is consistent with Qwen already being resident but does
not prove a general warm-up mitigation. Keep the guard unchanged. Independent
restoration and timer cleanup reached `RESTORED_VERIFIED`; Stage 31 listening
was verified. Evidence is preserved under
`/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-physical-operator-ready-20261026T184026Z-be08deb5bed0/`.

At this checkpoint, the planned cue was `Can I repeat that?`, based on a
previous Whisper transcript. The later physical candidate and resulting
source correction are recorded in the latest barge-in section above.
Stage 32 remains PARTIAL and unpublished.

#### Previous physical candidate — PSI guard abort during Qwen learning inference (2026-10-27, PARTIAL)

Candidate `48b9fc5932924907b55a67bda81f15d2` passed guarded preflight,
ALC898/AEC capture, and the physical `Friday` wake. The Owner then reported
saying the learning continuation. Runtime evidence shows endpoint finalization,
the local Qwen request, `LOCAL_LLM_FIRST_TOKEN`, and the beginning of speech
chunks; the continuation gate was not credited because the independent memory
guard aborted before the response completed. No later physical gate passed.

The full repository regression had completed before this run. At 18:33:36Z,
the host `llama-server` process (PID 1823) accumulated 5,980 major faults in
ten seconds; host full-memory PSI avg10 reached 6.45% and candidate-cgroup full
PSI reached 6.02%. The server's RSS grew from about 0.13 GiB at 18:33:26Z to
17.25 GiB at 18:33:46Z during the first live Qwen inference. At the 18:33:43Z
abort, candidate-cgroup full PSI was 2.70% against the unchanged 2%/10-second
limit, MemAvailable was 23.14 GiB, SwapFree 4.07 GiB, candidate memory 5.34
GiB, GPU memory 7,502/8,192 MiB, and cgroup OOM counters were zero. This is
strong evidence that Qwen model-page residency/reloading during live inference
is the leading pressure source, but the exact kernel reclaim path is not proven.
Do not relax the guard. A later live candidate completed Qwen inference safely
without a resource trigger after the model had already been exercised. This
supports, but does not prove, a warm-residency explanation; no general
mitigation is claimed.

The resource guard stopped the candidate and independent restoration reached
`RESTORED_VERIFIED`; Stage 31 listening and automatic timer cleanup were
verified. Evidence is preserved under
`/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-physical-operator-ready-20261026T183202Z-62eec9aa8d34/`.

#### Latest physical candidate — resource guard abort during concurrent full regression (2026-10-26, PARTIAL)

Candidate `4becbee05de2422fba6ecf96c2bc7364` passed guarded startup and capture
checks. Before any user speech gate, the independent guard observed system
full-memory PSI at 2.82% for 10.209 seconds, exceeding the unchanged
2%/10-second threshold. At the trigger, MemAvailable was 24.63 GiB, SwapFree
3.89 GiB, candidate memory was 5.56 GiB, GPU memory was 7,515/8,192 MiB, and
cgroup OOM counters were zero. The full repository regression was running at the
same time; this overlap is a confounder but is not proven to be the pressure
cause. The guard stopped the candidate and independent restore reached
`RESTORED_VERIFIED`, with Stage 31 listening and timer cleanup complete. No
speech gate passed. Evidence is under
`/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-physical-operator-ready-20261026T171101Z-991273537eb1/`.

The full repository verifier has since passed 2,011 tests with 6 skipped and
all installed-package checks compatible. Keep full regressions separate from
physical candidate runs; do not alter the guard threshold.

#### Previous physical candidate — interruption transcript mismatch and safe restoration (2026-10-26, PARTIAL)

Candidate `e71742e7e2a24e3e82a13280c871cd1c` passed resource preflight, wake,
learning continuation, Qwen response, and owner-confirmed Pocket/Anna playback.
The runtime recorded a genuine `voice.speech.interrupted` event. Finalized ASR
then produced only `Dallas and again.` from 1,472 ms of audio; the Owner reported
speaking `Friday, explain the lesson again.` The exact-transcript barge-in gate
failed with `finalized_barge_in_transcript_did_not_match_learning_repeat_prompt`,
and no learning-repeat follow-up was credited. Independent restoration reached
`RESTORED_VERIFIED`; Stage 31 listening capture and timer cleanup were verified.
Stop/no-stale-playback, recovery wake, read-only progress, isolated assessment,
and Astra UI synchronization remain unqualified. Evidence is under
`/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-physical-operator-ready-20261026T170149Z-881a2f9b6834/`.

At that checkpoint, the planned cue was `Friday, repeat that.` The later run
transcribed it as `Can I repeat that?`; the next exact cue is updated to match
those observed words while preserving exact finalized transcript, single-turn
routing, Qwen, and Pocket/Anna playback requirements. Stage 32 remains PARTIAL
and unpublished.

#### Previous physical candidate — barge-in not performed before playback ended (2026-10-26, PARTIAL)

Candidate `e5ddc1278f1b4d7a808749b79a475ad5` passed resource preflight, wake,
learning continuation, Qwen, and owner-confirmed Pocket/Anna playback. No
interruption occurred before speech ended; the gate failed with
`Pocket_Anna_playback_finished_before_barge_in`. Independent restoration
reached `RESTORED_VERIFIED`. Evidence is under
`/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-physical-operator-ready-20261026T165625Z-69687d4fad8e/`.

#### Postboot physical candidate — inline-wake gate mismatch and safe restoration (2026-10-26, PARTIAL)

Candidate `41cd5e23c1a146549dbc75ce6b52ec90` completed resource preflight and
passed the physical wake gate. The Owner spoke the exact machine-learning
continuation phrase; Stage 31 emitted the documented inline-wake remainder,
created a learning context, routed the turn through Qwen, and completed
Pocket/Anna speech. The Stage 32 controller stayed on gate 2 because it
required a model-backed transcript and rejected
`source=wake_remainder`/`transcriber=wake_asr`. It never displayed the
contemporaneous audibility gate. The controller also had an unreachable
per-gate timeout after early returns. The candidate was aborted without
claiming continuation or later gates; no audibility, barge-in, Stop, recovery,
progress, assessment, or Astra synchronization gate passed.

The independent report reached `RESTORED_VERIFIED`, retained the Stage 31
release pointer and production databases, and verified listening ALC898/AEC,
wake, and advancing PCM. The actual resource guard recorded 1,806 samples over
904.288 seconds, with 0.518-second maximum gaps, no cumulative counter resets,
and final `STOPPED`; no sustained PSI threshold was crossed. The harness now
accepts only the explicit inline-wake provenance and checks timeouts before
gate dispatch. The 19-test operator-orchestrator file and targeted Ruff pass.
Full repository verification passes 2,010 tests with 6 skipped and all 101
installed packages compatible; a fresh Owner-present physical run remains
required. Candidate evidence is preserved under
`/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-physical-operator-ready-20261026T161719Z-ecf03eebebc5/`.

#### Session #12 — resource abort, controller outage, and recovery repair (2026-10-26, PARTIAL)

The Owner entered one valid `START` for session
`8c952603ed4449d99d307fd32069f74e`. Capture handoff began, then the resource
guard aborted before a speaking cue. No speech event, transcript, turn, or
physical gate was recorded. The preserved session directory is
`/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-physical-operator-ready-20261026-12/`.
Its restoration report verified the immutable Stage 31 release, unchanged
learner database, API/Astra UI/Qwen/vision health, ALC898/AEC listening capture,
wake, fresh PCM, candidate cleanup, and recovery timer cleanup.

The trigger was a real PSI/reclaim event without host hard-memory exhaustion or
OOM: MemAvailable was 23.43 GiB, SwapFree 4.58 GiB, candidate memory peaked
near 6.37 GiB, and host/candidate PSI avg10 peaked at 5.42%/3.8% before
decaying. The monitor applied its 10-second sustain timer to a rolling `avg10`
window, which could count the same trailing interval twice. The guard now uses
cumulative full-stall `total` deltas across successive samples no more than
2.5 seconds apart. Existing 2%/10-second limits remain; missing PSI telemetry
aborts safely, and the live avg10 readiness check still withholds the speaking
cue above 2%. The cause of the underlying pressure remains unresolved, so a
candidate run must exercise this guard before resource safety is requalified.

The `CONTROL UNAVAILABLE` page followed the abort because the controller
process shared the candidate orchestrator's systemd cgroup. A new session
created by `start_new_session=True` did not escape that cgroup; the independent
restore correctly stopped it and killed the controller. The loopback
controller now runs in its own `friday-stage32-operator-control.service` with
`Restart=on-failure`. The restore verifier checks that independent unit,
process identity, and current session projection. A live crash/restart test
recovered under a new PID while preserving the restored session.

The stable page at `http://127.0.0.1:8768/` now shows `PREPARED` and a
`Begin physical test` action only after the prior report proves
`RESTORED_VERIFIED`. Begin creates a private fresh session and starts its
orchestrator preflight in an independent unit; it does not authorize microphone
handoff. The page's fresh exact `START` remains required after recovery,
resource, and owner-control checks pass. The current page still displays
session #12's resource abort alongside verified Stage 31 restoration. Codex
has not launched the next session.

#### Session #11 lease expiry and prepared operator page — 2026-10-26 (PARTIAL)

Session #11 reached `AWAITING_OWNER_START` but its 300-second lease expired
without an Owner START. The event history records zero typed STARTs, no capture
handoff, and no physical speech gate. Automatic recovery reached
`RESTORED_VERIFIED`; it verified Stage 31 API/Astra UI/Qwen/vision, listening
ALC898/AEC capture, wake armed, advancing PCM, unchanged production learner
data and release pointer, candidate shutdown, and timer cleanup. The preserved
evidence is in the #11 operator qualification state directory.

A 15-second host-only resource window after restoration observed maximum full
memory PSI avg10 of 0.00%, minimum MemAvailable of 23.42 GiB, and minimum
SwapFree of 4.71 GiB. Candidate resource safety remains subject to the existing
guard on the next run. At that checkpoint the operator page could remain in a
safe `PREPARED` state with no START lease or capture handoff. The later
persistent page-driven workflow supersedes the conversational `ARM` step: the
Owner can select Begin when physically ready, then type the new session's exact
`START` on the page. Stage 31 retains microphone ownership until that fresh
authorization and verified handoff.

The no-session operator page change is covered by the 14-test control-server
module. Stage 32 remains PARTIAL pending new Owner START and genuine physical
voice evidence for the outstanding gates.

#### Integrated operator, restoration, and resource qualification — 2026-10-26 (PARTIAL)

The typed-START page now drives the real temporary candidate orchestrator. It
shows the exact physical-ready message only after resource, operator,
automatic-restore, and independent manual-restore gates pass. START is bound to
the active session and expires after 300 seconds. Before acknowledgement, the
candidate voice stack is not warmed, production capture remains under Stage 31,
and no speech gate runs. After START, capture handoff must prove ALC898/AEC
input, PCM progression, listener readiness, and candidate capture ownership
before showing the speaking cue. This loopback page does not change the
approved Astra UI.

Live restoration passed through the actual independent user service for manual
abort, automatic timeout with an active candidate unit, and automatic fallback
after candidate-unit death. Each report reached `RESTORED_VERIFIED`, verified
the separate service cgroup, and checked Stage 31 release/API/UI/Qwen/vision,
AEC/wake/PCM, production learner databases, candidate cleanup, and timer cleanup
after verification. A real integrated pre-START abort also completed manual
restoration with Stage 31 healthy.

Session #04 expired before typed START and did not start candidate capture.
Its overlapping manual/guard restoration services raced on fixed temporary
report names, producing a rename error and contradictory status/report files.
The source now serializes restore-service invocations per session and gives
state writers unique private temporary files. The 78-test Stage 32 suite passed,
and a live duplicate-restoration qualification with a harmless sleep-only
candidate, an armed recovery timer, and two concurrent restore services reached
`RESTORED_VERIFIED`; it verified separate cgroups, candidate shutdown, timer
cleanup, Stage 31 health and unchanged learner databases. The failure report
and the new passing evidence are both preserved. A fresh physical-ready session
must still receive a new Owner START before any speech gate.

Two comparable no-speech resource windows each remained READY for 180 seconds
without a guard trigger. In the first, startup took 47.55 seconds, candidate
peak memory was 6.23 GiB, candidate PSI was zero, system PSI avg10 peaked at
2.12%, MemAvailable stayed above 23.39 GiB, SwapFree above 4.85 GiB, and
candidate major faults increased by 81 with no file refaults. In the second,
startup took 30.85 seconds, peak memory was 5.15 GiB, candidate PSI was zero,
system PSI avg10 peaked at 0.18%, MemAvailable stayed above 23.43 GiB, SwapFree
above 4.83 GiB, and candidate major faults increased by one with no refaults.
The earlier 14.79% PSI event remains unexplained residual risk. No threshold or
resource setting changed. This supersedes the earlier interim instruction to
block solely on reconstructing that historical event; current guarded
qualification passes under the tested conditions.

The first live READY page exposed a multiline JavaScript serialization defect
before START. The page now emits the prompt as a JSON-escaped JavaScript string.
In a later run the Owner typed START once; live ALC898/AEC input, listener, PCM
progression and capture ownership checks passed. At 06:51:34.854 UTC the
speaking cue was displayed while system full-memory PSI avg10 was already
3.92%; candidate PSI was 0.60%. The unchanged guard restored Stage 31 at
06:51:38.430 UTC after system PSI exceeded 2% for 10.277 seconds (trigger
sample 2.77%). Candidate memory peaked at 6.54 GiB; candidate swap and
OOM/high/max events stayed zero. No physical gate or finalized transcript was
captured. The first measurable correlation was Pocket/Anna worker initialization
reading 82.9 MiB and adding 27 major faults in one sample while host reclaim and
swap activity rose; sole root cause remains unproven. Trigger and restoration
evidence are preserved in `live-handoff-resource-outcome.json` beside the run
state.

The control page now clears/hides prior speaking-cue, READY and START content
when status polling fails. The orchestrator now keeps capture quiet and requires
15 consecutive seconds within the unchanged resource limits before displaying
the speaking cue. Focused tests cover this snapshot gate and unavailable-page
behavior. The new live gate has now passed a 16.003-second observation across
16 samples; system full PSI avg10 peaked at 1.25%, candidate PSI at 0.18%.

A separate session-bound `resource_requalification_no_speech` mode now lets the
Owner start a bounded live recheck without presenting a physical speech gate.
The mode waits for typed START, performs the real capture handoff and 15-second
stability gate, observes for 180 seconds without speech, then restores Stage 31.
Its first preflight attempt exited before candidate startup because the copied
operator page did not receive `STAGE32_WORKTREE`; independent restoration
completed and cleaned up the timer. A corrected session later failed a generic
pre-START safety check with no candidate startup; its 59 samples showed zero
system PSI, and it also restored cleanly. Per-check diagnostics now capture the
failed condition on a future attempt. The focused Stage 32/operator suite passes
74 tests.

The fresh resource-only session
`/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-resource-only-requalification-20261026-03/`
completed one typed START for a no-speech recheck. After the actual live capture
handoff and the 16.003-second gate, it remained READY for 180.402 seconds with
177 samples, zero wakes/VAD/utterances, and no cue or physical gate. Candidate
peak memory was 5.95 GiB; orchestrator-window system/candidate PSI avg10 peaked
at 0.25%/0.03%; MemAvailable stayed above 23.28 GiB and SwapFree above 5.17
GiB. No guard trigger occurred. The combined report for all three bounded
windows is PASS with thresholds unchanged and the historical PSI cause
explicitly unresolved. Restoration reached `RESTORED_VERIFIED`, including
unchanged production learner data and timer cleanup. Stage 32 remains PARTIAL
pending physical Gates A–J, retained per-turn evidence, and final Stage 31
restoration. The physical-ready run now persists the detailed live capture
predicates separately in `capture-readiness.json`.

#### Runtime event-to-gate integration — 2026-10-26 (PARTIAL)

The latest physical session above reached live capture, displayed the first
wake cue, and restored Stage 31 after two accepted wake counters and listening
acknowledgements but no finalized transcript or gate result. The candidate
event loop now drains its startup event cursor before the cue, then sends only
new sequenced runtime events and live voice-health snapshots to the operator
controller. The operator page displays finalized transcript, assistant
response, gate index/result, and a link to the isolated Learn view. Its
session-bound Origin/CSRF route accepts only the current gate's owner
observation.

The default physical plan now follows the requested A–J order. It requires a
finalized Whisper transcript and learning-path evidence for continuation,
Qwen and Pocket/Anna evidence, and a typed owner confirmation that Anna is
audible while playback is active before showing the barge-in cue. Spoken Stop
must interrupt active playback; a five-second quiet interval and owner
confirmation cover stale playback. Progress emits explicit read-only routing
evidence. Assessment answers use the `My answer is` route prefix, require a
separate spoken `Yes`, and pass only when exactly one new attempt appears in
the isolated candidate database. Per-gate runtime events, voice-health
snapshots, typed owner observations, database fingerprints, and available
latency snapshots are retained with private file permissions.

The focused Stage 32, voice-learning, voice-intent, and runtime-event tests
pass (119 tests, no failures); Ruff, Python compilation, operator-page
JavaScript syntax, and `git diff --check` pass. These tests qualify the event
controller path in code only. The prior physical run did not produce a
transcript or gate result, so none of Gates A–J is physically qualified. A
fresh session with this implementation and a new typed Owner START is still
required before physical results can be claimed.

The #05 physical learning response recorded actual Qwen and Pocket/Anna
playback-start/completion events, but the Owner did not submit the required
audibility confirmation during playback. This is unconfirmed acoustic output,
not evidence of TTS failure. Session #06 then expired with zero typed STARTs
and no capture handoff; its independent restoration reached
`RESTORED_VERIFIED` and cleaned up the recovery timer. The operator page now
shows an explicit `FRIDAY IS SPEAKING` cue and binds an Owner confirmation to
the current session, voice turn, playback-start event and timestamp. Two
focused operator test files pass with Ruff, compilation and diff checks. A new
Owner START and all outstanding physical gates remain pending; Stage 32 stays
PARTIAL.

Session #07 then received one valid START; capture handoff and the physical
wake gate passed. The finalized learning request matched, retrieved the
`data-evaluation` node, and produced a Qwen response with Pocket/Anna playback
start. The assistant turn was interrupted before the Owner audibility
confirmation and before the continuation gate completed. A later Whisper
`[BLANK_AUDIO]` event had incorrectly triggered a command-mismatch failure.
The harness now ignores that explicit blank sentinel and records a matching
cancelled response as the actual failed transition. The 25 affected unit tests
pass. Session #07 restoration reached `RESTORED_VERIFIED`, including listening
capture, wake, unchanged production learner data and timer cleanup. A fresh
session and Owner START are required to retry the affected physical gate; no
audibility or barge-in pass is claimed.

Session #08 subsequently passed physical wake and learning continuation, then
the Owner confirmed Pocket/Anna audibility during active playback with a
session/turn/start-sequence timestamp binding. The barge-in produced a real
playback interruption but finalized ASR as `for how to cancel my answer.`
The generic follow-up response did not satisfy correct learning routing. A
later interruption was not attributable to a spoken Stop gate. The candidate
was manually aborted; Stage 31 restoration reached `RESTORED_VERIFIED`, including
timer cleanup. The barge-in gate and all later physical gates remain pending.

The previous cue, `Friday, cancel my answer.`, only selects the learning
cancellation action when an answer is pending. At this checkpoint, the physical
barge-in cue used Friday's existing lesson-repeat intent, `Friday, explain the lesson
again.` The gate requires the matching finalized transcript, one correlated
learning-context turn, Qwen output, and follow-up playback start before it
passes. It fails closed on a transcript mismatch, missing learning route, or
multiple follow-up turns. Focused operator, physical-control, and voice-intent
regressions pass. This is a qualification-harness correction; Stage 32 remains
PARTIAL pending a fresh Owner START and physical Gates A–J.

Physical-ready attempt #09 reused the unchanged resource report, which passed
its three guarded runs, then stopped before candidate-session creation because
the transient systemd-run environment omitted `PATH`; no START, capture
handoff, restoration timer, or speech gate occurred. The complete failed state
is preserved under `/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-physical-operator-ready-20261026-09/`.
This is a harness launch failure, not a new resource or production failure. The
next physical attempt uses a fresh state directory and forwards the allowlisted
host runtime environment.

Physical-ready attempt #10 received one valid typed START and then the existing
resource guard restored Stage 31 before capture readiness could show the
speaking cue. At 10:40:06 UTC the host full-memory PSI peaked at 12.86% and
candidate cgroup full PSI at 11.86%; sustained trigger samples were 5.54% host
and 5.33% candidate for 10.30/10.24 seconds, beyond the unchanged 2%/10-second
limits. Candidate cgroup memory was 5.89 GiB; cgroup swap-out and OOM counters
were zero and host MemAvailable was 23.48 GiB. The pressure source is not
isolated. No physical speech gate or capture-ready cue was recorded. Independent
restoration reached `RESTORED_VERIFIED`, verified listening/wake-armed Stage 31,
unchanged production learner databases, candidate cleanup, and timer cleanup.
Evidence is under `/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-physical-operator-ready-20261026-10/`.
The earlier three guarded resource runs remain PASS, but this new abort keeps
physical readiness PARTIAL. No threshold or resource setting changed.

The same inspection found the operator browser could retain prior-session
confirmation and START-submission UI state. The page now clears those values on
session change and status failure. Its resource-trigger context artifact also
uses an undated filename; #10's original filename remains in its evidence.
Focused tests cover the corrected gate, route, page, and trigger record.

Stage 32 binds finalized local voice turns to the selected active DLP path and
Career Forge's existing dynamic lesson, fixed assessment contract, Reviewer,
evidence, mastery, and prerequisite projections. Continue, explain, repeat,
progress, answer, correction, confirmation, and cancellation intents route
before generic capability adapters. Voice cannot create or select a path or
project. Local mutations require Friday's existing trusted `local-owner`
principal. Spoken answers remain bounded in-memory drafts until explicit
confirmation; retries use one interaction id, and incorrect or uncertain
reviews preserve canonical remediation without granting mastery.

The existing wake, ASR, Qwen, Pocket/Anna, AEC, and event-stream interfaces are
reused. AEC monitoring now starts before model/reviewer wait so speech can
cancel generation before first playback. Turn ids and cancellation events close
the active model or Reviewer stream; cancellation before the assessment commit
leaves a confirmed attempt pending, while a completed durable assessment is
never rolled back by Stop. The Learn workspace follows the runtime context
event, renders the same selected path/node, shows only an unsubmitted voice
draft, and refreshes canonical feedback/progress events. No voice database,
daemon, model, wake engine, or production service change was added.

#### Fresh 2026-10-25 bounded physical candidate — PARTIAL / resource-guard abort

A fresh candidate used a new isolated state directory. The 20-minute restore
timer, direct manual-restore control, and independent resource guard were armed
before handing off Stage 31 capture. Qwen and vision remained active. The
candidate's sequential Parakeet, Moonshine, and Pocket/Anna startup reached
READY with the ALC898-backed candidate AEC source, live Qwen endpoint, isolated
learning-path fixture, and connected UI. The unchanged resource guard then
aborted before owner speech: system full-memory PSI avg10 exceeded 2% for about
10.2 seconds, with a 7.74% trigger sample and a 14.79% peak sample. Candidate
cgroup current/peak memory was 6.42/6.53 GiB, cgroup full PSI was 3.57%, and
the candidate accumulated 5,964 major faults and about 0.64 GiB swap-out.
MemAvailable remained 24.33 GiB and OOM counters were zero. The trigger is a
resource-safety failure for candidate readiness; do not repeat this startup
unchanged or weaken the guard.

No owner speech was requested and no physical gate ran. Final event and latency
snapshots contain zero events/turns; exact transcripts, retrieval, Qwen
teaching, audible output, barge-in, spoken Stop, progress, assessment, and UI
state transitions are therefore unavailable. The isolated learner fixture
remained at zero lesson attempts, and read-only integrity checks passed.
Automatic restoration returned to the original Stage 31 release and verified
API/UI/Qwen/vision health, listening and wake-armed capture with PCM advancing,
one healthy Pocket/Anna and wake-worker stack, and unchanged production
database fingerprints. No Qwen/vision restart, commit, push, deployment, main
advancement, or Stage 33 work occurred. Evidence is under
`/home/kumar-rishav/.local/state/friday-stage32-physical-20261025t155427z/physical-candidate/`.
A later no-speech run reached READY and remained under the unchanged guard for 180 seconds, but the earlier sustained-PSI abort still has no cause-specific correction. The resource gate remains PARTIAL; do not repeat the previous startup unchanged or treat one quiet run as proof that the intermittent cause is fixed.

Follow-up reconstruction found 3.13 GiB file-backed and 3.26 GiB anonymous
candidate-cgroup pages at the abort, plus 48,887 file workingset refaults,
391,927 pages scanned (369,335 by kswapd), 223,961 pages stolen, 0.64 GiB
swap-out, and 32 MiB swap-in. The leaf cgroup had unbounded `memory.high` and
`memory.max` and no high/max/OOM events; historical cgroup swap settings and
ancestor limits were not captured. A same-day full-stack startup with the same
Parakeet → Moonshine → Pocket/Anna order reached capture at 5.23 GiB with
8,719 cgroup major faults and 33,110 reclaim scans, but only 0.18% system PSI
and no swap movement. Worker duplication or startup-order change is not
established.

The selected Parakeet (2.4 GiB), Moonshine (257 MiB), and Pocket cache
(272 MiB) files are under `/AI` on rotational HGST `/dev/sdb`. The sysstat
ten-minute interval containing the abort recorded 44.48 major faults/s,
19,335 kswapd scans/s, 4,353 steals/s, and `pswpout/s=338.16`. The matching
`sar -d` row shows `/dev/sdb` read throughput 6,431 KiB/s, average request
size 385.11 KiB, await 19.88 ms, average queue 0.33, and utilization 6.18%.
This confirms model-file reads but does not show disk saturation. Candidate
file refaults support cold model-file loading as part of the reclaim activity;
historical per-PID faults, mapping identity, external process contribution,
and swap-limit ancestry were not retained. No single process or file can be
named as the exact fault source. This is not evidence of physical RAM
exhaustion, and no storage or startup mitigation is justified by this capture.

The October 25 temporary control page did not require a typed `START` and did
not expose all requested states; it must not be used to prompt speech. A future
bounded physical run will use the visible Codex operator flow with explicit
`PREPARING`, `RESOURCE CHECK`, `CANDIDATE READY`, and `AWAITING OWNER START`
states, then show one exact gate phrase after `START`, followed by the actual
transcript and gate result, with abort/restoration visible. The approved Astra
UI is unchanged. The resource sampler now records per-process faults, I/O and
PSS, system vmstat, cgroup swap/io controls and ancestor limits, plus process
identity and mapping snapshots at triggers and READY; its 13 focused tests
pass. These changes improve future diagnosis and do not qualify a resource fix
or physical gate.

#### No-speech resource attribution follow-up — 2026-10-25 UTC / 2026-10-26 local (PARTIAL)

The production-only baseline remained quiet: zero system and service PSI, no
reclaim/swap movement, 23.22–23.25 GiB MemAvailable, and no /dev/sdb I/O. A
fresh candidate run after 30 seconds of stable quiescence reached READY in
46.5 seconds and held 180 seconds without speech or a guard trigger. Candidate
cgroup memory.current peaked at 6.22 GiB and memory.peak at 6.26 GiB. At the
peak sample, memory.stat showed 3.86 GiB anonymous and 2.29 GiB file-backed
pages; file-backed memory reached 2.58 GiB at a different sample. Candidate
cgroup PSI and swap stayed zero, with no OOM/high/max events.
System PSI avg10 peaked at 2.6% but did not remain above 2% for 10 seconds.
MemAvailable stayed above 23.39 GiB. Candidate cgroup major faults totaled
8,531 and reclaim scans 284,016 pages. /dev/sdb read about 2.87 GB during
startup, with 25.1 seconds of device busy time; saturation was not established.

The candidate API process contributed about 7,180 major faults; Parakeet
primary 64, Moonshine fallback 1, Pocket/Anna synthesizer 203. During the
stable READY window, a process named ChatGPT accounted for about 10,206 host
major faults outside the candidate cgroup; Qwen had about 116 and received no
candidate inference request. The candidate caused material reclaim but had no
cgroup PSI stalls or swap. The earlier failed run has no PID/mapping attribution
and the first no-trigger run did not save mapping names, so the root cause
remains inconclusive. No model, storage, kernel, swap, or guard-threshold
change is justified.

Stage 31 restoration verified the release pointer, API/UI/Qwen/vision, active
ALC898/AEC capture, advancing PCM, wake, one worker per voice role, candidate
cleanup, and unchanged production databases. During controller teardown the
resource monitor lost its orchestrator cgroup PID and invoked the idempotent
restore fallback; restoration passed, but monitor lifecycle should be corrected
before another run. No physical gate or START prompt ran.

The tracked operator flow now requires resource_safe, auto_restore_armed, and
independent_abort_armed before showing the exact READY message or accepting
typed START. It rejects duplicate/expired START and withholds the speaking cue
until capture is verified. Its 39 focused tests, Ruff, and compilation pass.
The page is not yet integrated with the temporary candidate orchestrator.
Stage 32 remains PARTIAL; next work is to capture cgroup/mapping identity at
resource milestones, fix the controller teardown race, and integrate the page
before any physical attempt.

#### Second no-speech READY attribution and restoration follow-up — 2026-10-25 UTC / 2026-10-26 local (PARTIAL)

A second isolated no-speech run is preserved at
`/home/kumar-rishav/.local/state/friday-stage32-physical-20261025t155427z/physical-candidate-attribution-20261025t185049z/`.
After stable production preflight it reached READY and remained there for 180
seconds without a guard trigger. In that exact window system PSI avg10 peaked
at 0.14%, MemAvailable stayed above 23.43 GiB, SwapFree stayed at 4.83 GiB,
candidate cgroup memory.current peaked at 5.15 GiB and memory.peak at 5.16 GiB,
and candidate PSI stayed at zero. Cgroup major faults increased by one and
reclaim counters did not move; system vmstat recorded 73 major faults, 90
swap-in pages, and 74 swap-out pages.

The READY snapshot records executable, parent PID, cgroup, PSS, and top
resident mappings. Parakeet was 2.11 GiB PSS, candidate API 845 MiB,
Pocket/Anna 799 MiB, Moonshine 685 MiB, and candidate UI 219 MiB. The snapshot
included Moonshine's 140 MiB decoder KV and 90 MiB encoder ORT mappings. API
and Parakeet had 260 and 58 cumulative major faults at READY. This run followed
a recent full model load; it does not establish cold-start residency or explain
the earlier sustained PSI event. No resource mitigation or threshold change is
justified.

The manual watchdog ran inside the candidate systemd service cgroup. When it
stopped the orchestrator service, systemd terminated the watchdog before its
final cleanup record and timer cancellation. A separate watchdog invocation
completed the final report, verified candidate/AEC/controller cleanup, and
stopped the timer. The release pointer and production database fingerprints
were unchanged; Stage 31 API/UI/Qwen/vision, listening capture, fresh PCM, wake,
and single-worker counts passed. The tracked operator server now launches
manual restoration in a uniquely named user service outside the candidate
cgroup, returns RESTORATION_STARTED, and rejects duplicates. A failed launch
leaves the automatic timer armed. A temporary no-op watchdog verified the
separate service cgroup; its live restore path still requires integration with
the candidate orchestrator and end-to-end verification before physical use.
The earlier pressure cause remains unknown, and no physical gate ran. The
focused Stage 32 suite passed 50 tests across four files; Ruff,
compilation, and diff checks passed.

#### Post-reboot recovery of the READY physical candidate — 2026-10-24

The later 2026-10-18 isolated physical candidate did reach READY with wake
phrase `Friday`, the ALC898-backed Stage 32 AEC source, live Qwen, and an
isolated ML path. Its candidate log records one `WAKE_ACCEPTED`, five
`ASR_FINAL` events, four local-LLM request starts, six first-playback PCM
writes, and six playback completions. The saved owner control request has all
six physical observations checked. The candidate did not persist its event
stream or a valid latency snapshot, so the exact ASR transcript, per-turn
latencies, and assessment confirmation cannot be independently reported. The
isolated learner fixture had zero attempts; no production learner mutation was
evidenced. Physical qualification remains **PARTIAL**.

Root cause was in the test controller, not demonstrated wake recognition: its
manual-stop check looked for the Stage 32 worktree path, while the candidate
process command line contained the isolated state path to `run_candidate.py`.
The request was saved but did not invoke restoration. The independent
20-minute watchdog restored and verified the Stage 31 release before the
October 24 reboot. No OOM or kernel pressure event was recorded. The physical
log's missing transcript/event files are therefore a harness evidence gap; do
not change wake thresholds or replace the detector based on that run.

The uncommitted qualification repair uses exact script-path process matching,
makes manual control invoke the locked restore verifier directly, captures
final candidate events/transcripts/latency before shutdown, and adds an
independent systemd resource monitor for host/candidate memory, PSI, swap,
worker RSS, major faults, and GPU memory. The 2026-10-25 attempt exercised the
fresh candidate and automatic restoration; the result and resource trigger are
recorded above. Do not begin another owner-present physical run until the
single-stack startup's resource-pressure cause has a concrete safe remedy.

Code-only evidence: synthetic final ASR, deterministic Qwen/Reviewer fixtures,
and a test playback sink traverse the actual voice and conversation services,
isolated FastAPI endpoints, and temporary Career Forge/DLP SQLite stores. The
journey proves lesson selection and spoken delivery, draft-only behavior,
explicit one-attempt confirmation, unauthorized browser-write rejection,
non-mastery after one correct question, API reconstruction, and runtime/UI
projection tests. Final code-only gates passed: repository verification
reported 1,897 Python tests passed and 6 skipped; the frontend reported 189
tests across 38 files, four Node checks, ESLint, TypeScript, and production
build passed. The isolated real-Chrome Stage 31 regression also passed its
three-topic Learn journey, authorization negatives, browser reload, and API
restart recovery (`/tmp/friday-stage32-stage31-browser-regression-20261016`).
That regression does not constitute a Stage 32 physical voice test. A
2026-10-17 hardware-free isolated readiness run passed: the candidate API read
its active learning path, actual Pocket/Anna synthesis delivered 157,440 bytes
to a memory sink, and CPU Whisper.cpp transcribed the 3.28s synthetic utterance
as “Friday, continue my machine learning course.” The Stage 32 intent router
classified it as `continue`; Pocket started in 15.67s and Whisper completed in
2.69s. Candidate services shut down cleanly. No mic, speaker, AEC, wake model,
Qwen request, or production learner mutation occurred.

The readiness cgroup peaked at 2.38 GB, system full PSI avg10 peaked at 1.81%
against the unchanged 2%/10s guard, candidate-cgroup full PSI remained 0%,
MemAvailable stayed above 23 GiB, SwapFree above 3.0 GiB, and OOM/high/max
counters remained zero. This run did not load Parakeet or Moonshine, so wake
worker startup is still unqualified. In the separate 2026-10-17 startup attempt,
a duplicate Parakeet reached about 1.19 GB RSS while reading about 1.88 GB; system
full PSI avg10 reached 14.12% for 10.33s and candidate-cgroup full PSI reached
9.24%, triggering the guard. MemAvailable was still 23.2 GiB, SwapFree 3.09
GiB, and cgroup OOM counters were zero. The controller grew from about 28 MiB
RSS to 840 MiB during ASR/intent imports, so this evidence implicates duplicate
worker startup plus observer overhead without proving either one alone caused
the PSI spike. The exact
trigger sample is preserved at
`/home/kumar-rishav/.local/state/friday-stage32-physical-qualification-20261016/resource-pressure-trigger-20261017.json`.

The owner-approved 2026-10-18 physical retest did not reach candidate READY and
no owner speech occurred. Its first harness launch failed before candidate
startup because the watchdog unit name did not match the checked name; the
temporary timer and control page were stopped. The corrected attempt used a
dedicated cgroup, preserved a pre-cleanup trigger sample, and aborted after 37s
during `PARAKEET_START_BEGIN`: system full-memory PSI avg10 was 6.65% for 10.23s
against the unchanged 2%/10s threshold. At trigger, MemAvailable was 23.2 GiB,
SwapFree 3.52 GiB, candidate cgroup memory.current/peak was 3.61 GiB,
candidate-cgroup full PSI was 1.88%, and OOM counters were zero. The CPU
Parakeet worker reached 1.25 GiB RSS/HWM; the candidate API reached about
373/844 MiB RSS/HWM and 473 MiB swap. Candidate cgroup `memory.stat` showed
2.30 GiB file pages, 1.29 GiB anonymous memory, and 8,005 major faults. Aggregate
GPU use was 6,816/8,192 MiB; no candidate Qwen instance or request was used.
The preserved trigger and 1-second resource timeline are in
`/home/kumar-rishav/.local/state/friday-stage32-physical-qualification-20261018-retry-01/`.

The retry stopped before Parakeet READY, so Moonshine, Pocket/Anna playback,
candidate ASR, candidate UI, live-Qwen teaching, transcript confirmation,
read-only progress, barge-in, Stop, recovery, and physical latency measurements
remain untested. The candidate briefly created its isolated AEC graph on the
shared PipeWire source; watchdog cleanup removed it. Production capture was
never paused. Production API PID 7729 and capture node 83/PID 7836 remained
unchanged, PCM advanced from 13,742 to 14,906, wake stayed armed, API/UI/Qwen/
vision remained healthy, and production learner/wake counts were unchanged.

The failure repeats the Parakeet-startup PSI event, so do not retry the same
startup unchanged or relax the resource guard. Each current
`PersistentWakeDetector` owns a subprocess with private stdin/stdout pipes;
sharing a production worker through that interface is unsafe. This blocks a
candidate-native wake test, but not the separate microphone/Whisper,
Pocket/Anna, or voice-learning gates. A supported resource-safe candidate wake
path remains deferred; if it requires changing or restarting the protected
Stage 31 service, obtain separate owner approval before that production change.
No Stage 32 deployment, `main` advancement, or Stage 33 work occurred.

Physical wake, microphone/ASR, audible Pocket/Anna, physical transcript
confirmation, physical teaching quality, barge-in, spoken Stop, and recovery
remain **not qualified**. Synthetic Qwen routing and candidate read-only
progress passed, but the capped teaching response was incomplete. The
2026-10-17 readiness snapshot used production API PID
5174 and showed a historical `WakeRuntimeError`, recovery count 1. The
2026-10-18 retest supersedes it: production API PID 7729 remained unchanged,
capture stayed listening and wake-armed with advancing PCM, and health showed
no current voice error and recovery count 0. The release pointer, production
learner counts, and wake count were unchanged. Do not repeat the per-node
production Pause. Private readiness evidence is in
`/home/kumar-rishav/.local/state/friday-stage32-physical-qualification-20261016/staged-readiness-synthetic-result-20261017.json`.
No deployment, `main` advancement, or Stage 33 work occurred. Career Forge rows
60 and 61 remain PARTIAL. The scoped branch is
`stage-32/voice-first-learning-reliability`; no deployment or `main`
fast-forward is permitted for this stage. The source checkpoint
`807432a662f09294a78fd79aa5dfafa06394214c` is published on the scoped remote
branch; Stage 31 remains the current `main` and deployed runtime state.

The readiness gate that caused the duplicate worker startup was in the
qualification harness: `cli.main()` starts the managed wake service before the
candidate API, `FridayManagedWakeVoice` starts Parakeet then Moonshine, and the
old harness waited for candidate `wake_path_armed` before declaring READY.
Basic audio/learning gates do not need that candidate wake stack. A
test-only runner now starts the isolated API with `LOCAL_AI_WAKE_ENABLED=false`
and a temporary bearer-protected loopback route limited to the `continue`
learning intent. Production wake policy and the Stage 31 worker are unchanged.

The 2026-10-18 synthetic run passed isolated API readiness, active path
retrieval, Pocket/Anna synthesis to a memory sink, and CPU Whisper ASR: the
2.96-second generated utterance was transcribed as “Friday, continue my machine
learning course.” in 3.02 seconds and classified as `continue`. The isolated
voice-origin route emitted `VOICE_LEARNING_CONTEXT` for eligible node
`data-evaluation` (“Data Preparation and Evaluation Foundations”), and one
existing-Qwen response returned lesson-specific teaching content with a
160-token cap. That response ended mid-sentence at the cap, so response
completeness is not qualified. Read-only progress retrieval succeeded; the
temporary candidate learner store had one dynamic subject and zero assessment
attempts. Production learner counts stayed unchanged. Candidate API and
workers shut down cleanly. No wake model, AEC graph, microphone, speaker, or
production capture pause occurred. The first harness-only retry, before the
temporary path seed step, is preserved separately.

The unchanged guard remained below its thresholds: system full-memory PSI
avg10 peaked at 1.42%, MemAvailable stayed above 23.1 GiB, SwapFree above
3.8 GiB, and no OOM or guard event occurred. Process HWM was about 845 MiB for
the candidate API, 1,017 MiB for Pocket, and 390 MiB for Whisper. The sampled
cgroup is shared with the Codex app, so its PSI is not candidate-isolated. The
production API PID, capture identity, voice/wake state, learner counts, and
API/UI/Qwen/vision health were unchanged; PCM advanced and the candidate
process exited. Evidence is under
`/home/kumar-rishav/.local/state/friday-stage32-lightweight-audio-20261018/`.

The owner approved lightweight physical Gates A–C on 2026-10-18. The selected
HDA Intel PCH / Realtek ALC898 microphone (source 57), existing
`friday_aec_source` (node 78), its production AEC links, built-in analog output
(sink 56), and Pocket/Anna production speech backend were verified. A temporary
reader linked directly to the existing AEC source and captured two complete
12-second, 16 kHz mono samples (384,000 bytes each). CPU Whisper took 3.244s and
3.648s and returned `[BLANK_AUDIO]` both times (RMS 37.66 and 43.21); no actual
transcript was confirmed or routed to learning. The exit status was 1 after a
full sample, without stderr.

One bounded Qwen request reused the live production model service but supplied
“Continue my machine learning course.” as typed test text. It took 12.332s and
emitted the eligible `data-evaluation` lesson context. The response ended
mid-sentence at the 256-token cap. The isolated temporary DB added one dynamic
subject and one `unverified` competency, with zero lesson attempts; production
learner counts did not change. This result is synthetic input evidence, not
physical ASR, transcript confirmation, or read-only progress qualification.

The attempted Pocket/Anna analog-speaker check ended when the resource/audio
watchdog detected production PCM age 5,319ms while production voice was in
`detecting` with the wake path unarmed. It aborted the candidate before durable
speaker-route, stop-latency, or audibility evidence was written. No wake was
counted, no voice turn or interaction was active, and runtime was idle. At the
trigger, MemAvailable was 22.4 GiB, SwapFree 3.97 GiB, system full PSI avg10
was 0%, cgroup current/peak was about 3.40/3.96 GiB, and OOM counters were
zero. The watchdog fired within the 20-minute bound; the timer did not expire.

Production capture was never paused and no audio configuration or service was
changed. API PID 7729 and release pointer
`075645a3198a37a9ff101a18614065ff8cc5c9e9` remained unchanged. The production
capture returned to listening/armed and PCM advanced throughout a 12-second
post-abort check; API/UI/Qwen/vision returned HTTP 200, production learner
counts stayed unchanged, and all candidate processes stopped. No production
service was restarted. Physical microphone/ASR, audible playback, transcript
confirmation, response quality, barge-in, spoken Stop, wake, and recovery remain
unqualified. Candidate wake was disabled only in this test.

Evidence is under
`/home/kumar-rishav/.local/state/friday-stage32-lightweight-physical-20261018-03/`.
That earlier physical window closed after the safety abort. The later direct
root-cause retest is recorded below; Gate D remains unqualified.

The production API exposes no authenticated wake-event interface: voice health
has counters, while `/api/v1/runtime/events` is not an authenticated wake
contract and the current wake path emits no accepted-wake event there. Gate D
therefore remains separate. The smallest production proposal is a bounded,
redacted in-memory wake/Stop event record and local-Owner-authorized read-only
endpoint, without audio/transcript data or detector-policy changes. Do not
implement or deploy it under this qualification. Rollback would remove only
that telemetry/endpoint and restore the previous immutable Stage 31 release
using its existing recovery procedure.

The earlier lightweight physical run ended with an audio-age safety abort. The
later owner-authorized direct root-cause retest and its production restoration
are recorded below. Gate D's application-level wake and Stop evidence remains
unqualified; Stage 32 is not ready for release preparation.

### 2026-10-18 direct root-cause physical retest — PARTIAL; resource-guard abort

With Friday's production capture gracefully stopped, two supervised 15-second
captures were made from the selected HDA Intel PCH / Realtek ALC898 Internal
Mic. Raw input delivered 240,000 16 kHz mono frames (RMS 609.89, peak 15,081,
no clipped samples); CPU Whisper took 2.62 seconds and returned “Friday continue
my machine learning course.” The identical phrase through a temporary PipeWire
WebRTC AEC graph returned the same transcript in 2.656 seconds (RMS 451.20,
peak 7,929, no clipped samples). The graph linked the physical mic and the
built-in analog speaker monitor reference. PCM existed only in memory and was
wiped after transcription. Both full bounded reads ended with `pw-record`
status 1 after the harness's normal SIGINT, with no stderr; all expected frames
were present. This verifies the physical raw and AEC microphone/Whisper paths,
not Friday's application wake or conversation path.

The previous 5,319 ms abort was a watchdog classification defect. Its guard
allowed phase `detecting` in one condition but still unconditionally rejected
PCM age above 5 seconds. `FridayAlwaysOnWakeCapture` synchronously calls the
wake detector after VAD completes an utterance, before it reads another chunk;
therefore PCM age grows during that bounded inference even when no device-read
failure has been observed. New monotonic read-start/read-completion, VAD
inspection, ASR-handoff, and detector-duration fields distinguish those phases.
A focused blocking-detector regression verifies the health snapshot reports
`detecting`, a completed prior read, and no read currently in progress. This
explains the old guard trigger; it does not retroactively prove whether the
physical device stalled during that earlier attempt.

One isolated candidate stack was then started after production stopped. The
Parakeet, Moonshine, Pocket, and AEC processes were singular; Qwen and vision
were not restarted. The unchanged safety guard aborted during candidate worker
startup after system full-memory PSI avg10 stayed above 2% for 10 seconds and
peaked at 19.5%. At the trigger, MemAvailable was 24.25 GiB, SwapFree 4.30 GiB,
the shared user execution cgroup peaked at 7.30 GB, and OOM counters were zero.
Observed worker RSS included Parakeet 1.69 GiB, Moonshine 736 MiB, Pocket 781
MiB, and API 350 MiB. No owner speech, wake, candidate ASR, Qwen request, TTS
playback, learner mutation, assessment, or computer action occurred. Candidate
processes and its temporary AEC graph were stopped. Do not repeat this startup
unchanged or weaken the resource threshold.

The original Stage 31 unit was restored inside the 20-minute window. The
release pointer stayed at `075645a3198a37a9ff101a18614065ff8cc5c9e9`; API, UI,
Qwen, vision, voice listening, wake workers, Pocket/Anna, AEC speaker-reference
links, and computer-agency health verified healthy. Production PCM advanced
after restoration. Production learner and task databases matched their
pre-test snapshots exactly, including all 12 historical `in_doubt` actions.
Qwen and vision were not restarted, and `main` and Stage 33 were untouched.

The saved control request records positive owner observations for physical
wake, Pocket/Anna audibility, transcript confirmation, barge-in, spoken Stop,
and recovery/read-only progress. Candidate markers corroborate an accepted
wake, five finalized ASR turns, model requests, playback PCM completion, and
speech/model cancellations. The final runtime event/transcript and latency
snapshots were not retained, so the exact ASR words and measured per-turn
latencies are unavailable. The old control instructions excluded assessment;
the isolated spoken assessment confirmation remains untested. These are
positive physical observations, but Stage 32 remains PARTIAL and is not ready
for release preparation. Private evidence is under
`/home/kumar-rishav/.local/state/friday-stage32-root-cause-20261018T063217Z/`.

## Dynamic Learning Paths — DLP-1–4 accepted and published (row 61, PARTIAL)

DLP-1 establishes a separate local SQLite authority for versioned learning-path
curricula above Career Forge. It includes modules, nodes, explicit prerequisite
edges, project milestone references, goal/mode/target metadata, a deterministic
cycle-rejecting validator and stable topological ordering, local
`CURRICULUM_DESIGNER` proposal generation, and typed create/list/detail/history/
revision routes. Every candidate passes deterministic validation before
transactional persistence; invalid or failed model proposals create no state.
Career Forge owns all attempts, evidence and mastery. DLP-2 adds a read-only
Career Forge evidence adapter and deterministic sequencing: only current or
reinforced independent-application evidence supports a mapped node; stale,
weak, below-threshold, or unverified evidence yields review, reinforcement, or diagnostic
recommendations. Direct prerequisite failures block dependent nodes without
blocking unrelated branches. Sequence projections expose stable candidates,
reasons, and evidence-backed counts. Adaptive replanning now uses the current
evidence projection and deterministic policy on an explicit Learn request.
Exact owner-declared cross-path evidence can remove only unstarted redundant
future nodes; active-session nodes, project milestones, and their direct
prerequisite nodes remain. Weak evidence selects Career Forge reinforcement,
insufficient mastery selects diagnosis, and due or stale retention keeps review
first. Each meaningful decision records its trigger, source evidence, resulting
graph and decisions, planner provenance, and learner-facing reason in an
immutable DLP version. The canonical graph validator and SQLite expected-version
write remain authoritative. Unchanged or indecisive state creates no version,
and Career Forge attempts, evidence, reviews, or mastery are never written by
replanning.
Provider failure defers mapped nodes. DLP-3 added persistent owner path selection in the DLP SQLite boundary, draft-to-active lifecycle transitions, deterministic explicit Conversation creation/list/current/next intents, and Learn list/detail/sequence projection through typed APIs. DLP-4 added Career Forge-owned dynamic subjects and contract-bound evidence. Both DLP-4 and its publication recovery are accepted: capability commit `4a420217bcddca42aa2655c3379b196729a43432`; published recovery `7fcb926a2625cf9e30aad0037fd38a5df6d2afcc`. Learn now delivers/evaluates canonical Career Forge reviews and starts/resumes Career Forge reinforcement for supported fixed and dynamic subjects. Candidate browser qualification proved incorrect and correct review answers, dynamic reinforcement with assistance provenance, backend sequence refresh, and restart reconstruction. Review answer text remains within Career Forge's governed store; the browser holds only a transient draft. Project/capstone integration now adds exact direct-prerequisite gates, a versioned DLP-to-Projects relation, durable Projects instances and Objective/task artifact references, and explicit Career Forge explanation/evaluation evidence. Project work uses existing Objectives/Gateway approval, isolation, validation, review, and recovery. Task success and project completion do not grant mastery. Deterministic candidate backend/frontend coverage verifies assignment, idempotent retry, Objective resume, task-state gating, and durable projections; the successful browser/model Project assessment is qualified below. Row 61 remains PARTIAL for remaining product capabilities and broader owner qualification; final visual acceptance remains deferred. Row 60 remains PARTIAL. Learn is a FUNCTIONAL INTEGRATION SHELL; no final visual design acceptance is claimed. See `docs/architecture/dynamic-learning-paths.md`.

## Project / Capstone lifecycle integration — QUALIFIED bounded journey; row 61 remains PARTIAL

DLP project milestones now carry a typed project kind, assignment rationale,
competency keys, exact direct prerequisites, expected outcome, and bounded
evidence expectations. Assignment requires the selected active immutable path
version and current independent Career Forge support for every direct DAG
prerequisite. DLP schema v2 records the versioned milestone-to-Project link;
Projects owns durable instances, state, Objective/task references, artifact
references, review idempotency, and links to Career Forge evidence. Starting
work reserves and resumes one canonical Objective, so planning, exact-plan
approval, isolated execution, validation, review, cancellation, and recovery
remain under existing Friday controls.

A successful validated task is necessary but does not create learning evidence.
The learner must explain the work and receive a correct bounded local Career
Forge assessment. Only Career Forge stores project-derived evidence, linked to
the attempt, exact task/commit, and artifact IDs. Project completion requires
evidence for each assigned competency but does not advance mastery. Candidate
browser qualification with isolated synthetic state demonstrated rationale and
criteria, gated assignment, Projects/Objective projections, refresh and API
restart recovery, and return to Learn. The browser scenario stopped at the
canonical Objective planning boundary: the candidate had no configured
repository and no owner-approved task plan, so no task execution, artifact
submission, or UI-driven evidence review was claimed. Deterministic API fixtures
covered task-success gating, correct/incorrect/uncertain review, evidence
provenance, idempotent replay, and unchanged mastery. A separate single request
to local Qwen exercised the bounded Reviewer parser; it is not claimed as
end-to-end browser assessment. Adaptive replanning is now separately qualified
through deterministic backend/frontend regression and isolated browser journeys
for successful cross-path acceleration and weak-assessment remediation, including
reload reconstruction. Overall rows 60 and 61 remain PARTIAL. Remaining row-61
gaps after the later successful Project journey are broader owner product
qualification and final visual design acceptance.

### Browser-safe Project authorization — QUALIFIED (bounded authorization bridge)

The Presentation API implementation candidate establishes a volatile
same-origin owner session with an HttpOnly/SameSite=Strict cookie, CSRF header,
and exact loopback Origin/Host checks. It keeps Gateway bearer credentials
server-side and independently checks configured `SUBMIT_APPROVAL` and
`REQUEST_EXECUTION` scopes. Approval binds the authoritative Objective/task to
the current TaskHistory plan hash; execution re-enters ObjectiveService and
Gateway for canonical revalidation and isolated dispatch. Focused integration
coverage exercises denied and allowed paths. An isolated native-browser journey
also qualified successful approval, isolated task dispatch, artifact
production, and browser submission. A local Qwen-backed review correctly
rejected the thin qualification artifact; the project moved to `needs_revision`
and created no evidence or mastery change. This qualifies the authorization
bridge only. A successful project artifact/assessment lifecycle, broader owner
qualification, and final visual acceptance remain open; row 61 remains PARTIAL.
See ADR 0037 and `docs/architecture/integration-gateway.md`.

### Successful Project assessment — QUALIFIED (isolated Stage 22 owner path)

A fresh FraudShield capstone completed browser approval, exact-plan isolated
execution, full `unittest` validation, reviewed task commit, three artifact
submission, independent local-Qwen assessment, Career Forge evidence, and
return-to-Learn. Project `proj_3eb8f6dbe8de4f18a7067aac4c340b68` is
`completed`; task `task_c5df9f1ce54f4f14b6fb` is `succeeded` at commit
`9ebf0763cde42d0c903dda025a52c461359e4076`. The accepted explanation
generated one provenance-linked evidence record and no mastery transition;
the next DLP node recommends reinforcement. Browser reload and candidate API
restart reconstructed the completed state and restored the local Owner session.
Exact boundary/category and invalid-input audit checks passed against the
committed artifact. Earlier failed attempts and rejected assessments remain
immutable history, with no evidence awarded for them.

The candidate also qualifies bounded clean interruption and validation-failure
recovery. The historical failed artifactless retry
`cec6a3d29075496eb08cc3a2af7024b4` was reconciled to `rolled_back` /
`terminal_consistent` before the fresh Project was started. Exact-plan retry,
symbol/path authorization, sandboxed validation, and immutable attempt
artifacts remain required; see ADRs 0038–0040. This qualifies the specific
successful Project lifecycle. Row 61 remains PARTIAL for broader owner product
qualification and final visual design acceptance; row 60 remains PARTIAL.

### Stage 23 Career Forge evidence qualification — QUALIFIED (bounded owner path)

An isolated owner browser selected exact lines from a physical local Python
file under an allowed root, reloaded that question, and obtained a correct
local-Qwen explanation assessment. The resulting `code_explanation` evidence
retains canonical source path, file version, full and selected digests, line
range, question and criterion. Draft-backed code questions retain separate
provenance. Two no-help interview answers earned independent evidence. Neither
channel changed mastery automatically. One explicit matching-evidence
advancement moved `se.python` from `unverified` to `recognize` and scheduled a
review. A deterministic candidate-only time control made the review due; the
browser delivered it, submitted a correct local-Qwen answer, and showed
`reinforced` confidence with mastery still `recognize`.

Backend negative controls cover source/version/digest/range/symbol drift,
missing/out-of-scope files, changed source during inference, duplicate or weak
answers, interrupted and incomplete local-model output, stale interview
question/contract, stale/superseded reviews, and exact retry without evidence
inflation. Learn and Progress reconstruct a pending retention answer from the
Career Forge store. Browser reload and candidate API restart reconstructed
selected-code, review, interview, evidence, mastery, and automatic local Owner
trust without manual unlock. The existing `GITHUB_WRITE` publication gateway
now binds a candidate artifact to a regular blob in the exact promoted task
commit; authenticated fake-transport tests cover failure, retry, idempotency,
binding changes, and restart persistence. No real external publication was
performed for this qualification.

Row 61 remains **PARTIAL**. This bounded evidence slice does not qualify
contextual page attachment or final whole-product visual acceptance. Existing
cross-path equivalence and Project/capstone restrictions remain governed by
their own contract and milestone rules; no evidence channel automatically
grants mastery or public publication authority. See ADR 0041 and
`docs/architecture/career-forge.md`.


### Manual curriculum editing with prerequisite protection — QUALIFIED (bounded candidate path)

Learn now exposes bounded owner operations over the canonical DLP graph:
add a lesson, move it between existing modules, add prerequisite edges, and
remove eligible future nodes. Writes require an expected path version and
atomically validate the complete graph before creating a new immutable
revision. Dependency, milestone, supported-evidence, active-session, cycle,
reference, and stale-write protections are covered by deterministic backend
tests. Existing same-path dynamic Career Forge evidence remains applicable only
when the node's semantic assessment contract is unchanged, and historical
project references remain attached to their original canonical Project.

Native browser qualification on an isolated candidate path demonstrated opening
the editor, adding a lesson, adding a valid prerequisite and checking the new
sequence, rejecting a prerequisite cycle without a revision, moving a future
node between modules, removing an eligible future node, and recovering the
saved curriculum after browser refresh and candidate API restart. The path
remained active and resume candidates were coherent. API negatives separately
prove stale-write conflicts, dynamic-session continuation across unrelated
edits, invalidation after a material contract change, evidence preservation,
and project/capstone anchor protection. The browser candidate had no assigned
project, so browser task execution/artifact submission/assessment is not
claimed.

This sub-capability does not close row 61. Broader production owner qualification,
browser-driven project task execution/artifact submission/assessment, and final
visual acceptance remain open.


### Cross-path evidence equivalence — QUALIFIED (isolated owner journey)

Career Forge fixed competency IDs remain shared canonical identity. For
arbitrary-domain DLP subjects, an owner may assign the same stable
`equivalence_key` to nodes in separate immutable path versions. DLP considers a
source only when both current path versions explicitly declare the key, the
node assessment fingerprints match exactly, and the source Career Forge record
contains a correct assessed attempt/evidence. Model-generated paths leave the
key unset. The source path/version/node, attempt, evidence, evaluator,
timestamp, and artifact reference remain visible in the deterministic sequence
projection; no evidence record or mastery is copied.

Existing Career Forge independent-application mastery and current/reinforced
retention remain the default credit threshold. Owners may require a higher rung,
but not lower the independent-application floor. Lower or stale evidence
requests reassessment or review; mismatched scope is not credited even with an
identical key. Project/capstone milestone nodes remain path-specific, and the
prerequisite DAG is not altered. The Learn editor saves equivalence and required
proficiency as version-checked immutable revisions.

An isolated native browser candidate used real local Qwen assessments in a
source path, earned independent-application evidence, then opened a second
path and received an explained skip after exact-contract equivalence was
owner-declared on both paths. A refresh reconstructed the source relationship.
A same-key advanced-scope control remained diagnostic, and a matching-contract
control requiring transfer/debug mastery remained diagnostic at
`apply_independently`; evidence and mastery were unchanged. A first assessment
request exposed that the endpoint routed through general conversation and
returned unrelated task-routing text. The endpoint now uses Friday's existing
sequential Reviewer role over the same local Qwen model; subsequent browser
assessments returned valid labels. This does not close browser project
execution/assessment, broader production
qualification, or final visual acceptance. Row 61 remains PARTIAL. See ADR 0036
and `docs/architecture/dynamic-learning-paths.md`.

## Stage 24 — contextual page attachment (row 61, bounded qualification)

A shared, explicit attachment contract now connects current Learn paths and
Projects to ordinary local-Qwen Conversation. Owner-selected source IDs are
resolved on the server, snapshotted with full-state digests and versions, bound
to durable messages, and checked again for stale or unavailable state. A
candidate native browser attached both surfaces together, got a contextual
answer, reconstructed history after reload and API restart, and rejected a
stale Learn attachment after an owner-facing curriculum edit. Local Owner trust
restored automatically. The attachment never grants evidence, mastery,
execution, filesystem, Memory or publication authority. See ADR 0042.

Row 61 remains **PARTIAL**. Stage 23 selected-code, retention and interview
qualification remains intact. The bounded Learn-path and Project adapters do
not yet cover Practice Lab selected-code, Research or private-document page
attachments; those are future adapters only if owner workflows need them.
Broader cross-path owner integration and real authenticated external learner
artifact publication remain PARTIAL. Final whole-product visual acceptance
remains NOT STARTED. Do not infer whole-row completion from this slice.

Stage 24 acceptance gates: 1,347 Python passed, 6 expected skips; 127 frontend
tests across 20 files plus two Owner-bridge checks passed; repository verifier,
CLI/syntax, `pip check`, ESLint, TypeScript, production build, changed-file
Ruff, `git diff --check`, and private-capability/bundle secret audit passed.
The browser's second contextual question used the canonical saved Project
assignment at path version 1 while the attached current Learn path was version
2, preserving the distinction between historical assignment and live context.

## Stage 25 — broader cross-path owner integration (row 61)

Stage 25 connects Conversation/context attachments, Learn/DLP, Career Forge,
Projects, Practice Lab selected-code, retention and interview through one
canonical read-only relationship resolver. The owner can move from a Learn
item to assessed evidence, Project assignment and contribution, and back from
competency/evidence/review to the current Learn decision. Project contribution
requires the exact accepted task/artifact/assessment chain; an assignment alone
is labeled practice. Selected-file evidence retains Stage 23 source identity
and currentness. Review due status and mastery advancement are taken from the
exact Career Forge records. Factual provenance answers are deterministic;
other explicit attached discussion remains on local Qwen. Attachments grant no
Memory, evidence, mastery, Project, publication or execution authority.

The bounded candidate browser used the real Stage 22 Project/Stage 24 path
qualification records for Learn→evidence, Project→competency, competency→Project
and due review→origin journeys. A separate disposable copy of the qualified
Stage 23 selected-file/interview/review records was linked to a new validated
Learn path for the matching `se.python` competency, without modifying those
Career Forge records. The browser traced selected-file evidence and separate
interview evidence to that path and preserved the explicit `recognize` mastery
advance only for the matching selected-file evidence. Reload, candidate API
restart and local Owner restoration reconstructed the bound history. Research
retains stable source IDs but has no Stage 25 adapter; its private source
selection policy stays separate. Final acceptance totals and published recovery
identity are in `CODEX_HANDOFF.md` after the final gates.

Related-context Open actions for supported Learn paths/nodes and assigned
Projects carry stable IDs in the route. The target workspace fetches canonical
records, focuses the exact item after load and after reload, and reports a
missing, malformed, or stale target without selecting an unrelated item.
Review and Practice Lab relationships remain explicit attachment/provenance
actions; those surfaces do not expose stable deep item routes in Stage 25.

Row 61 remains **PARTIAL**: real authenticated external learner-artifact
publication is PARTIAL and final whole-product visual acceptance is NOT STARTED.
The next major dependency is determined by the final Row 61 audit; Stage 25
does not implement full screen/computer agency or the visual redesign.

## Stage 26 — Full Screen Understanding / Computer Agency (**QUALIFIED**)

Target: a governed owner-request → observe → understand → plan → act → observe
→ verify → correct/recover loop across real browser and native Linux apps.
Typed actions need fresh semantic/visual grounding, risk and approval checks,
bounded retries, durable audit, stop/cancel, and crash-safe recovery. Screen
content remains untrusted and grants no execution, Memory, Career Forge
evidence, Project, or external-publication authority.

Initial isolated candidate on the published Stage 25 baseline adds an
owner-authenticated, read-only AT-SPI/GDK observation with timed IDs/digests,
monitor geometry and bounded visible element metadata. It corrects AT-SPI
child traversal and uses the desktop Screenshot portal when direct GNOME
capture is denied; candidate pixel/metadata permissions are tightened.
Perception presentation routes require restored local Owner trust and canonical
Origin/CSRF on mutations.
An isolated private SQLite task ledger now records bounded action claims,
observation digests, cancellation and in-doubt crash recovery without granting
desktop authority. Consequential claims remain blocked pending canonical
approval integration.
The owner physically granted GNOME RemoteDesktop pointer/keyboard permission
once. A private persisted restore capability now opens a fresh worker/session
without another GNOME dialog. Two fresh candidate API processes restored it
and executed safe pointer/keyboard checks; this host returned the same token
on restore, while atomic replacement remains implemented for a changed token.
The controller now claims exact target/window/geometry fingerprints, not an
unrelated whole-desktop clock label, and verifies each result. Live disposable
GTK click/text/focus/shortcut, stale-geometry refusal and re-grounding,
Chrome local navigation and one-goal no-submit form fill, GNOME Text Editor
file focus, a visible error dialog, stop/cancel, worker restart, and two API
process restores passed as candidate proofs. Protected Owner task/action/run/
list/cancel routes, bounded permission status, an on-demand screen account and
minimal Perception controls exist. The deterministic runner accepts exact
Chrome navigation, named no-submit form fields, allowlisted Text Editor
file goals, and a native owner-named click with an expected visible result;
appended instructions fail closed. The native click goal changed a disposable
GTK label and recorded one verified action. It re-grounds one proven stale
pre-action target. A single-step local Qwen native proposal path exists, but
four live qualifications, including an owner-bound expected-result revision,
returned blocked with zero actions. An Owner-private route can re-observe an
in-doubt semantic action's persisted result and record it as present without
replay. Trusted legal native candidates, owner-object binding, and deterministic
selection for one unique legal control replaced the repeatedly blocked raw
Qwen proposal path. A live Owner UI request opened a menu and showed details
in two independently verified steps with no per-action approval and no model
call. Natural wording variants map to the same safe control; common browser
URL wording shares the existing navigation workflow. Exact interrupted results
are now bound to the original window. Explicit Owner Resume can skip a
re-observed effect or continue after a never-started actor, while uncertain
effects remain paused. A live GTK interruption completed after Owner
re-observation/Resume with one original action and no replay; browser and API
reload reconstructed the result. Stop intent is durable before waiting on the
process-shared task guard; a live two-step cancellation stopped after the first
verified action. The planner now exposes a typed, task-state-checked legal-action
catalog with target/window/geometry identity, source observation, owner-goal
match, risk, preconditions, trusted result class, and policy rationale. The
Owner recovery projection shows the original window and latest recovery
observation ID. The final deterministic suites qualify the legal-action
catalog, ambiguity refusal/fallback, recovery invariants, Owner API/UI, and
Stages 22–25 regression protections. The full repository gate passed 1,459
Python tests with 6 expected skips; the frontend passed 132 tests plus two
Owner bridge checks, lint, TypeScript and production build. Secret/security
audit, CLI/syntax, dependency check, Ruff and diff checks passed. Ambiguous
Qwen ranking itself remains unqualified: its live candidate returned blocked,
then trusted bounded resolution completed without widening authority.
Arbitrary browser pointer occlusion and canonical consequential-action
authorization remain outside the accepted boundary. Real reboot/login and
physical microphone qualification remain unproven; they were not simulated.
An isolated Owner browser recovery journey showed one action interrupted after
its real semantic effect, `recovery_required` reconstruction, a fresh
result-present observation, unchanged one-action count after browser and API
restart, and permission restoration without new consent. A live screen account
identified the active disposable app and visible "Details ready" label after
filtering GNOME's decorative active compositor frame; private screenshot
portal capture and local OCR were exercised.
Stage 26 is **QUALIFIED** for its bounded local workflows. Milestone C —
General Computer Agency owner-path integration is **QUALIFIED** as of
2026-10-11: all six physical journeys and the required full repository,
frontend, runtime-recovery, service-template, and remote-publication gates
passed. Accepted capability commit `cc386b2ff865d49a44a7ec939a05f5d74589129e` is based on `09842e7eefcdda6df34d5f4163078fb6cca29e06` and is published
on `stage-26/milestone-c-general-computer-agency` and `main`; the publication-recovery follow-up is recorded below
and in `docs/qualification/PRODUCT_INTEGRATION_MATRIX.md`.

Milestone C qualification covers the six bounded owner journeys. Full cold-boot
qualification remains pending, spoken-name fidelity remains unresolved, and
broader owner product qualification, latency work, and final visual acceptance
remain open under row 61 and Milestone F. Earlier candidate failures and physical
probe chronology remain in `HISTORY.md`, `docs/architecture/desktop-control.md`,
and `docs/architecture/voice-and-wake.md`.

The 2026-10-10 read-only Probe 5 follow-up found the built-in `Internal
Microphone` route active and Friday receiving PipeWire-converted S16LE,
16 kHz, mono frames from a S32LE, 48 kHz, stereo source. Silero is configured
at probability threshold 0.50, but per-frame level/probability is not exposed;
the earlier zero-speech event therefore remains unable to distinguish absent
speech from weak or misrouted input. The Owner confirmed the earlier 180-second window contained no qualifying command. Preserve its zero-speech telemetry as an unused request window, not evidence of a microphone, VAD, or ASR failure. No audio setting, threshold, or code was changed in that read-only follow-up. A later coordinated physical Probe 5 result is recorded below.

The subsequent coordinated window began after READY and GO at
`2026-10-10T08:03:56Z`. A real wake and expected-command ASR classification
were observed; Friday admitted task `3559b576c69145a1bdb296d2354573f6`, then
failed `execution_failed` after two verified Files location-bar actions. The
fixture stayed unchanged and no target bound. The actual `desktop.runner`
source and gate state in that process were not captured, so the earlier
attribution to `friday-live-vision` and conclusion that the candidate gate was
unavailable were unsupported. This attempt proves the exercised voice input
reached ASR but does not qualify stale-target recovery. The exact drop-in was
removed and Friday returned healthy/listening at PID 43816. The later physical
result below supersedes its next-step status.

A later coordinated physical attempt on 2026-10-10 accepted wake, completed
the spoken acknowledgment, and transcribed the expected folder command. Task
`5475cf80148e45dfadea6fdf75acd2c1` failed before an action was prepared; no
target was bound and the Amber/Birch/Cedar fixture did not change. The cause
was reproduced: after service restart, the no-context Files fallback scanned
the whole Nautilus tree without an active-window token and exceeded its
10-second observer limit. The candidate now scopes that scan to the already
verified active Files frame. The affected general-plan module passes, and a
real scoped observation returns all three folders. Private sanitized evidence
is under `probe-attempts/probe5-physical-20261010T072453Z/`. The gate was
unloaded and Friday returned to healthy listening. Probe 5 remains physically
unqualified; a later physical attempt was coordinated after the candidate-side
fix, but its actual imported service source was not captured. Probe 6 remains
unstarted.

A second physical attempt, initially described as using the loaded active-window
fix, accepted wake and transcribed the expected folder command. Friday safely completed two
verified read-only Files-location shortcuts and gathered fresh scoped
observations, but live OCR found Birch and Cedar without Amber; task
`6b8679008aaa4bf0a7da5d9f336ae567` failed before target binding. Its gate did
not release or change the fixture. The exact screenshot was removed after
local OCR metadata extraction. Because it followed a critical GO notification
and in-chat GO output, notification occlusion/focus remains a plausible but
unconfirmed harness cause. The next attempt will use a normal notification
with an 8-second expiry and suppress Codex output during the physical window.
Friday returned to healthy listening, the gate is unloaded, and Probe 5
remains physically unqualified. Probe 6 remains unstarted.

A subsequent physical window used a normal 8-second desktop notification and
no in-chat output. Its watcher ran 180.44 seconds while 5,640 PCM chunks
advanced, but VAD frames, utterances, wake checks, runtime events, transcripts,
and tasks remained zero. The gate stayed unbound and the fixture remained
unchanged; this does not determine whether speech was attempted or diagnose
the microphone/VAD/ASR path. Private evidence is under
`probe-attempts/probe5-physical-20261010T074419Z/`. The exact gate was unloaded
and Friday returned healthy/listening. No further physical window is armed;
await fresh Owner readiness before retrying. Probe 5 is still unqualified and
Probe 6 remains unstarted.

### Probe 5 physical stale-target recovery — PASSED (2026-10-10)

A corrected fail-closed preflight verified that Friday's actual service process
(PID 70598) loaded the candidate runner and qualification gate with matching
source identity. Fresh active-window OCR/geometry verified Amber, Birch, Cedar
and Birch as ordinal two. In the coordinated physical request, wake and the
expected command were observed (one utterance, 22 VAD speech frames). Task
`e5fdd97a87e24381ab2d536efd3580ff` bound Birch; the one-shot gate added Zephyr
after binding; the original action was rejected as `stale_collection_changed`
before dispatch; and Friday re-observed, re-grounded, opened Birch, and
verified its exact Files location. The durable task succeeded with four
verified actions and `spoken_result=true`; the Owner confirmed it worked.
The watcher reported `final_response_not_played` because final speech event 21
preceded task terminal event 23, while its classifier expected the opposite
order. The completed speech event and Owner confirmation establish playback;
this is a watcher false negative, not a product failure.

Private evidence is under
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe5-physical-final-20261010T090023Z-c9e2/preflight-rearm-1/`.
Cleanup evidence confirms Zephyr and the temporary drop-in were removed, the
original fixture inodes restored, the gate unloaded, and Friday healthy and
listening at PID 72204 with Pocket/Anna, Qwen, and vision healthy. Probe 5 is
physically passed. Milestone C remains PARTIAL; Probe 6 active Stop and final
acceptance gates remain outstanding. No commit or push was made.

### Session 13 — Probe 6 physical active-task Stop passed (2026-10-11; candidate)

The Owner's confirmation that the previous 90-second Stop window was unused
remains accurate: “No, I did not say ‘Friday, stop’ during the 90-second Probe
6 hold.” That earlier task `3d81f020bb26444195414d7d73226d5` remains failed with
one verified create action, no Files navigation release, and no success event;
its directory and all earlier probe folders remain preserved.

After explicit READY, the first arm attempt hit a transient API startup race
after Friday restarted with the temporary gate drop-in. It sent no GO, created
no task, and requested no speech. The exact drop-in was removed, ordinary
service health was restored, and the private arm/cleanup watcher was corrected
to wait through startup. A fresh live preflight passed before the physical
retry.

The one physical retry passed. Task `a623b966f5094866b124e794ddf4fea0` created
and verified `/home/kumar-rishav/Downloads/copper groove`; the gate bound the
task and paused before Files `open_location` with exactly one verified create
action. Friday registered a real strict-wake Stop event for that task
(`voice_explicit_stop_active_computer_task` from `strict_wake_remainder`), and
live wake counters advanced. The task-bound gate recorded
`cancelled_before_dispatch` 3.94 ms after the Stop event. The durable task ended
`cancelled`, the pending Files action was never released, no task-success event
was emitted, and no API/harness cancellation was injected. The critical
STOP-NOW cue was closed after the window. Directory identity `[2050, 2514261,
1000]` is preserved. The persisted request/action use lowercase `copper groove`,
although GO specified `Copper Grove`; no audio or request text was copied into
probe evidence, and the normal task-history record retains its request field, so
the source is unknown. This is Stop-path evidence only, not folder-name fidelity.

Cleanup restored ordinary service at PID 47411 with capture listening, wake
armed, Pocket/Anna, healthy Qwen/vision, no active task or voice turn, and the
qualification gate unloaded. The exact temporary drop-in was removed and all
four previously preserved probe directories retained their identities.
Private correlation and cleanup evidence are under
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe6-owner-confirmed-retry-20261011T075932Z/`;
the setup-race recovery evidence is under
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe6-owner-confirmed-retry-20261011T074516Z/`.
Probe 6 physical active-task Stop is **PASSED** for this candidate. Milestone C
remains **PARTIAL** until the remaining full acceptance and recovery gates are
completed. Candidate remains uncommitted and unpublished.

### Final Milestone C closure audit — Outcome A recommended; Owner publication approval pending (2026-10-11)

The six physical General Computer Agency journeys remain accepted. The final
candidate passed the complete Python/repository verifier (1,839 passed, 6
skipped), frontend tests (133 plus two bridge checks), lint, TypeScript/build,
changed-file Ruff, diff whitespace, service-template verification, and
authenticated post-restart readiness. The service restart loaded the candidate
planner guard and returned Friday to normal voice/wake listening with healthy
Pocket/Anna, Qwen and vision, active Owner permission, no active task, and the
qualification gate disabled. Full cold-boot qualification remains PENDING.

Probe 6 task `a623b966f5094866b124e794ddf4fea0` retains its physical Stop
pass: one verified create, real strict-wake active-task Stop, 3.94 ms from
recorded Stop event processing to cancellation, `cancelled_before_dispatch`,
and no Files release or success event. That timing is not end-to-end speech
latency. GO specified `Copper Grove`; admitted request/action and created path
say `copper groove`. No raw audio or ASR transcript survives, so the
admission variance cannot be attributed to speech, ASR, or transcription.
Earlier GO `Friday Stop Canary` versus admitted `Friday Stop canry` has the
same evidence boundary. The filesystem preserves the admitted literal and
refuses existing destinations; the candidate planner now rejects any
create-directory target not present verbatim in the owner goal. Deterministic
tests cover exact planner/ledger target binding and name/collision cases.
Speech-to-name fidelity remains an unresolved, non-destructive limitation, not
a proven ASR defect.

The read-only task database passes `quick_check`; there are no active,
recovery-required, or awaiting-clarification tasks. Twelve historical
`in_doubt` actions remain unchanged and unreplayed. The five Owner folders
retain their original inode identities. No dedicated vulnerability/secret
scanner is installed; repository dependency consistency and a high-confidence
credential-pattern scan passed, but no vulnerability-database audit is claimed.
Repository Ruff reports 11 findings only on unchanged files; changed-file Ruff
is clean. The Vite large-chunk advisory remains Milestone F work.
Available timings have distinct boundaries: Probe 1 completed in about 58.53
s; Probe 3 spoken playback completed at about 29.34 s; Probe 6 measured 3.94
ms from recorded Stop-event processing to cancellation. The latest memory
snapshot showed 30 GiB total and 23 GiB available with no observed pressure;
broader per-stage latency/resource qualification remains Milestone F work.

**Outcome A is recommended:** Milestone C is ready for Owner publication
approval. The project capability status stays **PARTIAL** until the Owner
authorizes publication and the candidate passes its commit, push, fetch and
remote-HEAD recovery gates. The candidate remains 50 modified tracked paths
and 18 untracked paths on `stabilization/general-computer-agency` at
`09842e7eefcdda6df34d5f4163078fb6cca29e06`; no commit, merge, or push
occurred. See `CODEX_HANDOFF.md` for inventory, protected-checkout status,
and the exact next action.

At audit time, read-only `git ls-remote` showed `origin/main` at the
candidate base SHA and no remote candidate branch. The separate local main
checkout is owner-dirty at `47ae92bba1c3b50d9dd6f2264d95b6cfaf275e75`
(ahead 1 / behind 21). Preserve it; publication must re-fetch and verify the
remote base, push the accepted stage branch, and only advance remote main when
the update remains a fast-forward. Do not reset or repurpose that dirty
checkout.

### Historical Session 8 — Probe 6 dynamic controlled cancellation passed; physical recovery inconclusive (2026-10-11)

The candidate keeps strict wake capture available for the active voice computer
task, checks durable cancellation between planned steps and at the actor
boundary, and prevents delayed playback completion from reviving a cancelled
task. Its optional one-shot gate is scoped to the local Owner and
`downloads_create_open_files`; it binds a fresh task to its trusted plan rather
than requiring a preset utterance or destination name. The admitted plan must
create a fresh safe child in the resolved Downloads directory and open that
same child in the default Files application. After the first action, the gate
verifies the ledger result and filesystem identity, then waits for a task,
nonce, and action-count-bound watcher acknowledgment. Missing or mismatched
evidence and either timeout fail closed and preserve the new folder.

The previous controlled Probe 6 task
`9791e9a7e7894b95870a8b3d737f22d5` reached the verified one-action boundary;
authenticated API cancellation suppressed `open_location` and preserved the
verified directory. A second actual-service controlled task,
`c75149414ab74a84b45de5eb1f200a22`, bound to its actual `Silver Birch` child
under Downloads, passed all dynamic boundary checks, received the armed
acknowledgment, and was cancelled through the authenticated local Owner API.
Its action ledger retained exactly one verified create and no Files action;
the folder identity was preserved. This is controlled API cancellation, not
physical voice Stop evidence. An earlier controlled harness attempt reached the boundary with task
`0fa32e1177854f25ac5a37b1d9c431fc` and created `Teal Lantern`, but its task
response parsing failed before it could arm the watcher. Its cleanup issued
authenticated API cancellation; it is not counted as a controlled pass, and the
owner folder is preserved. A following capture-readiness preflight stopped
before task creation. The corrected controlled evidence is under
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe6-dynamic-controlled-20261011T042821Z/`; the earlier harness records are under `probe6-dynamic-20261011T042209Z/` and `probe6-dynamic-controlled-20261011T043000Z/`.

The earlier physical window remains **INCONCLUSIVE**. Task
`0f5c880dc510487f921467058a4fb1f5` recorded `Friday Stop canry`; it completed
three verified actions before reaching the old exact-name boundary. No Stop
event or cancellation was observed. Preserve
`/home/kumar-rishav/Downloads/Friday Stop canry`; private evidence is under
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe6-physical-20261010T142132Z/`.

The one authorized dynamic physical recovery window reached the actual armed
boundary for task `3d81f020bb26444195414d7d73226d5`. It verified the actual
created `/home/kumar-rishav/Downloads/blue lantern` directory and held the
pending Files navigation for the 90-second Stop window after STOP-NOW. No exact
voice Stop event was recorded and strict-wake counters did not advance during
that window. The gate timed out fail-closed; the task is `failed` with one
verified create action, no navigation release, and no success event. No
API/harness cancellation or raw audio/transcript was retained. The Owner later
confirmed: “No, I did not say ‘Friday, stop’ during the 90-second Probe 6
hold.” The Stop window was therefore unused; the missing event is consistent
with the test conditions and is not evidence of a microphone, wake,
recognition, barge-in, or cancellation defect. Physical qualification remains
**INCONCLUSIVE**; preserve the task record unchanged. Preserve this
folder and the earlier `Friday Stop canry`, `Teal Lantern`, and `Silver Birch`
folders. Private evidence is under
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe6-dynamic-physical-20261011T043242Z/`.

The temporary drop-in and gate were removed. Cleanup confirmed normal
candidate service PID 34757, listening and wake armed, healthy Qwen/vision,
active desktop permission, no gate or active task, and all four folders intact.
The Owner confirmed that Stop was not spoken during this hold and requested one
coordinated retry after explicit READY. This missing event is not a voice-path
failure; do not arm the retry before readiness. Probe 6 remains unqualified,
Milestone C remains **PARTIAL**, and final full-repository qualification and
closure gates remain outstanding. Candidate is uncommitted and unpublished.

The post-arm Stop-window timeout now has focused deterministic coverage; it
fails closed after acknowledgment, creates no release marker, and preserves
the folder. The gate module tests pass (17 tests); the earlier focused
24-module Probe 6 regression selection, Ruff, and compilation passed before
this added timeout case. Final full-repository acceptance, physical Probe 6,
and Milestone C closure gates remain outstanding. Milestone C is **PARTIAL**.
Keep the candidate uncommitted and unpublished for this request.

### Milestone C publication recovery — QUALIFIED (2026-10-11)

Capability commit `cc386b2ff865d49a44a7ec939a05f5d74589129e` (parent `09842e7eefcdda6df34d5f4163078fb6cca29e06`) was pushed to `stage-26/milestone-c-general-computer-agency` and
fast-forwarded to `main`; fetched refs and direct remote heads were verified at
the same recovery tip after the documentation-only publication follow-up. The
accepted commit contains the reviewed 67-path implementation, tests, service
configuration, ADRs, and canonical docs. The pre-existing unreferenced
`uv.lock` was excluded from the commit and preserved in the local recovery
snapshot; the original candidate worktree remains untouched. The canonical
`.git` snapshot and all dirty-worktree archives remain at
`/AI/tools/friday-recovery/repository-reconciliation-2026-10-11`.

The six physical journeys remain the owner-path qualification evidence. The
folder-name admission variance remains unattributed because no audio or ASR
transcript was retained; full cold-boot qualification and wider latency/product
qualification remain open. No historical `in_doubt` action was replayed.

## Stage 27 — Authenticated learner-artifact publication (**QUALIFIED**)

The isolated candidate adds an Owner-session/CSRF browser path to request
publication of an already approved Career Forge artifact through the existing
`GITHUB_WRITE` gateway. The browser receives no bearer credential. Gateway
publication now verifies the promoted remote branch SHA and the pull request's
repository, head branch/commit, base repository/branch, and trusted URL before
recording `published`; mismatches remain `reconciliation_required`. A disposable
real Friday browser journey qualified Owner unlock, explicit review/approval,
locked-session refusal, publication, reload, and candidate API restart against
a fake transport. Deterministic tests cover authorization, binding and
reconciliation.

The owner selected and the authenticated account verified the public empty
destination `Rishavmit14/ML-AI-Engineering`. The isolated candidate configured
the exact repository mapping, `GITHUB_WRITE` scope, and the keyring-backed
`Rishavmit14` credential reference server-side. One Owner-approved Friday task
created `artifacts/model_card.md`, passed its complete project suite, and was
promoted through the exact reviewed task-branch flow. The Career Forge record
links the artifact, task, commit, and blob digest as full-assistance evidence;
it explicitly is not an independent learner assessment and does not advance
mastery (`ml.classical` remains UNVERIFIED).

The canonical publisher made one real external publication and verified the
exact remote branch commit, artifact blob, repository, and open PR identity:
`https://github.com/Rishavmit14/ML-AI-Engineering/pull/1`. Candidate API restart
and browser reload reconstructed the record without another write. Deterministic
fake-transport tests cover idempotency and uncertain side-effect reconciliation.
This bounded external journey is qualified. Final Stage 27 and Stage 22–26
Python/repository gates pass (1,467 passed, 6 skipped), as do the 133-test
frontend suite, Owner bridge checks, lint, typecheck, build, dependency
consistency checks, changed-file Ruff, and secret-pattern audit pass. Capability
commit `672c9e9b8d562f868437e4518349c1ca3735ac43` is published to the Stage 27
branch and fast-forwarded to `origin/main`; fetched refs match and GitHub
attributes author and committer to `Rishavmit14`. Row 61 remains PARTIAL because
whole-product visual acceptance is NOT STARTED.

## Session 1 Milestone A — Voice to Action Spine (**QUALIFIED; published 2026-10-07**)

The direct low-risk open route is wired from the normal Friday voice path into
the accepted Stage 26 computer agency. `FridayVoiceConversationService` marks
voice-origin turns; a deterministic intent router sends direct open/focus
requests through a pre-Qwen path before memory retrieval or prompt assembly.
Typed chat does not execute actions. The route requires the private local Owner
grant and restored GNOME permission, creates a durable owner-bound task, and
speaks success only after a fresh desktop observation verifies the browser
destination or installed application. Apps resolve through XDG desktop
metadata to a canonical launch ID; `/usr/bin/gtk-launch` performs the fixed
launch, while executable, D-Bus, desktop-ID, and `StartupWMClass` identities
ground app-scoped AT-SPI verification. A registered app's active/focused
visible element or a newly visible matching element can verify an open; each
scoped observation is bounded at two seconds and the verification window at
twelve seconds. The action ledger records actor return code, a bounded
verification category/count, and result-observation ID without screen text or
stderr. URI dispatch uses fixed `gio open` arguments asynchronously so the
browser postcondition can be observed while the OS handler runs; unresolved
dispatch is `in_doubt` and is never replayed. Durable Stop is checked during
the wait and terminates only Friday's still-running `gio` dispatcher; any
uncertain effect remains `in_doubt`. Sites use generic host resolution rather
than per-site command allowlists. Friday UI and internal routes use the
single configured `LOCAL_AI_OWNER_UI_ORIGIN`, aligned with the Owner bridge
and `LOCAL_AI_PROJECT_EXECUTION_ALLOWED_ORIGINS`. Existing exact Stop, task
cancellation/recovery, and content-free latency telemetry remain in the path.

Resolved URI and installed-app claims bind the selected URI or exact desktop
entry and require a distinct fresh observation, without comparing the whole
accessibility tree; screen-element actions retain strict stale-target checks.
Physical evidence on 2026-10-07: the owner reports YouTube opened in Chrome,
but its older durable task remains `in_doubt`; do not claim verified completion
or repeat YouTube unless browser dispatch changes. The latest Files probe
opened and focused the file manager, Friday said “Files is open,” and its
action recorded `postcondition_verified`. The fresh Friday UI retest showed
Daybreak at `http://127.0.0.1:5193/#home`; task
`b8e62dfc42924ebaa9efff7368ff27e9` / action
`dc181f9c822b43cfb8e05eda42b51dde` succeeded with `browser_title_visible`,
match count 1. This is a unique page-title match scoped to the registered
default HTTP handler, not proof of the exact URL or `#home` fragment. The
earlier failed action `1fb5de11c9584a1287b7056eae463916` remains historical.
Calculator also opened visibly in the latest physical probe, but Friday later
said it could not verify it. Task `161059a9d06e4fc499bad4de54d3a91b` / action
`975369b9a54a4f7e859c0fc6e098a81c` resolved to
`org.gnome.Calculator.desktop` / `Calculator`; `gtk-launch` returned 0, while
the app-scoped result observation had zero elements and verification ended
`postcondition_failed` / `not_found`, count 0. The ledger does not retain
accessible identities, so the exact missing root label is unknown. The
candidate now adds the registered XDG display name only as an AT-SPI root
selection alias; the success predicate still requires a registered desktop ID,
executable, D-Bus ID, or `StartupWMClass` identity. A subsequent physical
retake showed Calculator visibly, but task
`fa304617c65c4bdba82a576bde2ec349` / action
`dc55de7154b8448281707584bfb2a4ab` is `recovery_required` / `in_doubt` with
outcome `interrupted`. Its `gtk-launch` process exceeded the synchronous
10-second subprocess timeout before the post-launch scan ran. Actor return
code, result observation, verification category, and match count are null; the
selected AT-SPI root was not persisted. The candidate now dispatches the
launcher as a child while polling the strict app-scoped predicate concurrently.
The repaired asynchronous dispatch was physically retested once. Task
10be3127fc0346ba9c71e1e50399dd2a succeeded; action
ea85eb47d73242deb6aca3eb07cc2aa8 is verified as postcondition_verified with
actor return code 0, verification result active, and match count 106. The
result observation contains 106 elements in the Calculator-scoped tree and no
monitor records. The count is matching accessible elements, not windows or
desktop-wide matches. The root selector includes registered Calculator
identities and the display name; the ledger does not retain the exact selected
AT-SPI root label. The success predicate still requires registered identities.
The previous in-doubt action fa304617c65c4bdba82a576bde2ec349 /
dc55de7154b8448281707584bfb2a4ab remains unchanged and unreplayed.
The candidate now observes registered app-specific AT-SPI roots, accepts an
active/focused or newly visible matching app element, bounds verification, and
stores a content-free actor/verification summary. URI dispatch is nonblocking
and observes the requested browser address while the OS handler runs; an
unresolved handler is recorded with its last observation as `in_doubt`. The
latest Friday UI latency row has one turn and starts at the VAD owner speech-end
boundary: transcript event ~374ms, route selection 436.5ms, first speakable
chunk 696.1ms, first PCM 1,704.6ms, durable actor start ~5,849ms, action
completion ~9,533ms, final response ready 10,193ms, and playback complete
12,920.8ms. The in-memory row has no task ID or timestamp, so the saved event
cursor and task/action timestamps supplied correlation. The owner then issued one physical “Hey Friday, stop” while capture was
listening and reported silence. Runtime sequence 26 transcribed “stop” and
sequence 27 recorded voice_explicit_stop to idle; post-probe health showed the
capture thread still listening, with no active turn or error. No task/action
or latency row is created for Stop. This qualifies the silent Stop/listening
path; the probe had no in-flight desktop action, so active launcher cancellation
remains covered by deterministic tests rather than this live attempt.
The Calculator row from the failed attempt was: transcript ~411.7ms, route
selection 451.3ms, first speakable chunk 621.3ms, first PCM 1,852.1ms, actor
start ~5,922.9ms, result observation/action completion ~24,364/24,365ms,
failure/final response ready ~24,785ms, and playback complete 28,684.3ms from
the VAD speech-end origin. The first visible Calculator time is owner-estimated;
the durable verifier did not find a scoped element. The final delay is thus
corroborated by runtime telemetry, though the owner's 8s + 10–15s estimates are
approximate.

The previous Calculator retry used the repaired root selector but never ran
post-launch verification because the launcher blocked. Its VAD speech-end row
was transcript event ~376.7ms, route selection 437.6ms, first speakable chunk
684.5ms, first TTS audio 2,138.2ms / first PCM 2,139.6ms, actor start
~6,186.7ms, action interruption ~16,352ms, failure response ready 16,525.7ms,
and playback completion 22,522.6ms. It has no result observation or verification
count and remains in_doubt.

The fresh verified Calculator row is correlated to VAD speech end: transcript
event 383.5ms, route complete 427.1ms, intent 427.7ms, route selected 427.8ms,
first speakable chunk 629.9ms, first TTS audio 1,648.2ms / first PCM 1,649.5ms,
actor start 6,234.9ms, result observation 8,178.7ms, action completion
8,182.6ms, final response ready 8,485.9ms, and playback complete 10,694.4ms.
The user-estimated six-second window appearance has no machine timestamp.

Focused deterministic runner/ledger/AT-SPI/Stop/wake tests pass (99). Final
repository verification passed 1,525 tests with 6 skips, compile/CLI checks,
and dependency validation for 101 packages. Frontend passed 133 tests across
20 files plus 2 Owner-bridge checks, ESLint, TypeScript, and production build
(with the existing large-chunk advisory); changed-file Ruff, diff check, and
secret-pattern scan with zero findings passed. SQLite integrity is ok with 26
tasks, 22 actions, and 57 observations. A private recovery snapshot is saved
outside Git. Regression, local secret/recovery/diff, and publication gates
passed; at capability publication, fetched branch and main matched the accepted
capability commit.
| Milestone item | Status | Remaining evidence |
|---|---|---|
| Voice intent to existing computer agency | INTEGRATED | Candidate is running through the normal voice service; focused routing and action tests pass. |
| YouTube browser action | PARTIAL | Owner reports Chrome opened YouTube; the durable task is `in_doubt` and has no verified-completion marker. The candidate changed URI dispatch earlier in this slice, but the latest instruction authorizes no more application probes; preserve the owner report and its in-doubt task without replay. |
| Friday UI destination | PARTIAL | Fresh physical retest succeeded: task `b8e62dfc42924ebaa9efff7368ff27e9` / action `dc181f9c822b43cfb8e05eda42b51dde` verified `browser_title_visible` with one unique title match in the registered browser; owner saw `http://127.0.0.1:5193/#home`. The predicate does not verify the exact URL/hash. |
| Generic native application | LIVE PROVEN | Files and the fresh Calculator task both reached postcondition_verified. The Calculator result was app-scoped (106 matching accessible elements, result active); its exact selected root label is not persisted. Earlier Calculator failures remain historical; the prior in-doubt action is preserved. |
| Owner trust, Stop, recovery, and latency path | PARTIAL | The physical Stop command was transcribed and caused voice_explicit_stop; capture remained listening and the owner reported silence. No desktop action was in flight, so live task cancellation was not exercised. The Calculator speech-end row is correlated to the durable action timestamps; latency remains in-memory without embedded task/time IDs. |
| Candidate service on the normal Friday microphone path | INTEGRATED | Isolated candidate serves :8765 with reversible private systemd override; Daybreak is served loopback at :5193; voice health is listening. The protected production source checkout remains outside this worktree; its observed dirty voice/TTS paths were preserved. |
| Physical spoken results | PARTIAL | Files, Friday UI, and Calculator have verified durable task/action outcomes with owner-reported spoken results. Friday UI verifies the root page title, not its exact URL/hash. The YouTube owner report remains physically successful but its older task is in_doubt. Stop was silent and returned capture to listening. |
| Milestone A product acceptance and publication | QUALIFIED | Physical Calculator, Daybreak UI, Files, and silent Stop/listening evidence; speech-end-relative latency; 1,525 Python tests (6 skipped); 133 frontend tests plus 2 bridge checks; lint/build, secret/recovery/diff checks; at capability publication, fetched refs matched accepted commit b647c4fb622dd5ee9568bebc7a732c0ebb0b17ff on stabilization/voice-action-spine and main. Preserve the YouTube owner success report with its old task in_doubt and the missing exact AT-SPI root label. |

This is a bounded voice integration through the accepted Stage 26 computer
agency; it does not redefine Stage 28 or rewrite Stage 26. The physical
microphone gate has Calculator and silent Stop/listening evidence. The accepted
capability is published and remotely recoverable. General screen-question
context and consequential actions remained outside Session 1 Milestone A. See
ADR 0046 and the Session 1 section of
`docs/qualification/PRODUCT_INTEGRATION_MATRIX.md`.

## Session 2 Milestone B — Live Vision (**PRODUCT QUALIFIED; published 2026-10-07**)

The candidate routes normal physical voice screen questions through the reused
Stage 26 `ScreenCaptureService` (GNOME Shell Screenshot D-Bus with desktop
Screenshot portal fallback) and fresh AT-SPI/window observer. A separate authenticated
loopback llama.cpp service runs Qwen2.5-VL-3B on CPU; primary Qwen remains
text-only and receives bounded untrusted visual/OCR/semantic text, never image
bytes. Visual turns require a new capture after the request, reject stale
semantic evidence, suppress OCR/VLM on detectable sign-in or verification
screens, and request no Owner screenshot or desktop action. Semantic
app/window/focus questions use the fast metadata path.

Physical voice evidence: Friday described a canvas-only revenue chart and,
after the screen changed, a distinct warehouse-inventory chart with new capture
and context identities. A third physical question correctly explained the
visible terminal `ZeroDivisionError`. The candidate voice service had been
restarted before these probes; persistent portal permission remained usable.
No upload or special vision page was used. On the final physical terminal turn,
visual inference took 39.9s, Qwen's first token arrived at 55.2s, and completed
playback took 102.3s from speech end. A tuned 1024px/512-token same-frame
benchmark took 29.2s and retained all chart cues; the earlier 768px/1024-token
minimum run took 73.7s and missed labels. Both image edge and token budget
changed, so the results compare configurations rather than isolating the
token-cap effect. Full-turn latency remains too slow to feel conversational.
The first successful chart turn took 103.96s end to end (63.44s VLM); the
changed-chart turn took 123.09s (72.17s VLM), both before final service tuning.
The initial timed-out probe failed safe and did not reuse old screen content.
The authoritative private evidence is in the owner-only
`/home/kumar-rishav/.local/state/friday-live-vision/` directory; no image, raw
OCR, or voice log is tracked. The full repository verifier passed 1,562 tests
(6 skipped), changed-file Ruff passed, both perception SQLite databases passed
`integrity_check`, the candidate secret scan found no credentials, and the
recovery snapshot permissions and installed visual-cortex unit were verified.
Capability commit `cc1c10ee47cdd2899161e7c2ba8d67ee03d39b05` is published on
`stabilization/live-vision` and `main`; fetch and `git ls-remote` confirmed both
refs matched. GitHub attributed the author and committer to `Rishavmit14`.
Milestone B is PRODUCT QUALIFIED, with the measured latency limitation retained
as a product follow-up.
