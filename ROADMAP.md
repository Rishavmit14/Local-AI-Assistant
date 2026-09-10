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

## Stage 14 — Friday Career Forge Core V1 (**Partial / active**)

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
minimum progressive assistance. Mission generation, project/public-evidence
gates, and presentation controls remain active Stage 14 work.

## Stage 15 — Visual Perception / Screen Awareness (**Planned**)

Add safe read-only screen capture, active-window/application context, vision-model interpretation, OCR where appropriate, UI-state understanding, provenance, and privacy controls. Visual perception initially has no mutation authority.

## Stage 16 — Safe Desktop Control (**Planned**)

Add policy-governed application launch/focus, bounded keyboard/mouse/UI actions, browser interaction, local file/application operations, permission classes, audit, and approval for destructive/high-risk actions.

## Stage 17 — Autonomous Assistant Execution (**Planned**)

Generalize Friday into a bounded objective loop: objective -> plan -> inspect -> act -> observe -> validate -> repair/replan -> complete or request approval. Reuse the existing planner/execution/validation/isolation/Git/history/approval stack.

## Stage 18 — Proactive Event and Automation Engine (**Planned**)

Add local service/system/repository/filesystem/task/external event watches, schedules, meaningful notifications, relevance policy, permission policy, and rate limiting.

## Stage 19 — Agent / Role Orchestration (**Planned**)

Keep one user-facing Friday while internally routing conversational, reasoning,
coding, vision, retrieval, planner, coder, reviewer, debugger, test, and security
roles. Roles use sequential invocations of the current sole general-purpose Qwen
model unless later evidence qualifies another model; specialized components gain
no implicit extra privileges.

## Stage 20 — Self-Learning / Research Engine (**Planned**)

Add trusted-source collection, provenance, domain indexing, knowledge-gap identification, research plans, synthesis, curriculum generation, teaching/evaluation, and refresh/versioning. This does not mean silently modifying model weights.

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

## Stage 21 — Cognitive Architecture & Local Intelligence Amplification (**Planned**)

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

## Stage 22 — Friday Career Forge Advanced Integration (**Planned**)

Integrate the accepted Stage 15–21 general capabilities into the mature Career
Forge: screen-aware tutoring, policy-governed desktop assistance, bounded
mission autonomy, retention/progress automation, sequential Teacher/Coach/Pair
Programmer/Reviewer/Debugger/Interviewer/Curriculum-Designer roles, trusted
ML/AI curriculum research, and evidence-positive cognitive improvements. This
stage extends—not replaces—the bounded Stage 14 core loop and must preserve local
sovereignty, learner-evidence provenance, owner pace, and review-gated public
artifacts.

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
