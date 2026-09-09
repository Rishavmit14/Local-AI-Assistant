# Project History

This chronology records the working system that existed before this repository was bootstrapped.

Stage 11 began by retiring the legacy Streamlit product UI and extracting reusable behavior into `FridayInterfaceService`. It then delivered the native presentation/API/event foundation, React/Vite frontend state, Whisper conversational STT, Piper TTS, PipeWire playback, voice lifecycle telemetry, Silero/VAD primitives, AEC/barge-in primitives, and conversational barge-in tests.

The accepted always-on wake integration uses exact `Hey Friday`, Silero utterance segmentation, Parakeet Full primary ASR, Moonshine Medium fallback, persistent fail-closed wake workers, pause/resume orchestration, and managed startup/shutdown. Live qualification passed the accepted strict wake gate, a complete production voice turn, worker reuse, cold restart, and clean shutdown.

The persistent Friday runtime is deployed as the enabled user-session `friday-local-ai.service`. The original accepted wake integration was committed as `6e7de1263ecfe154e573aedd32eeb375d5e2b47f` after full Python/frontend/build/lifecycle gates and then pushed with remote HEAD verified.

Stage 12A subsequently identified the installed PipeWire 1.6.2 WebRTC echo-cancel support, proved that no active AEC graph previously existed, qualified an ephemeral `monitor.mode=true` topology against the real default microphone and speaker monitor, and promoted that topology into the production wake bootstrap. Acoustic qualification measured 23.75 dB speaker-only reduction and preserved human speech with a 1.0000 maximum Silero probability and a 1410 ms continuous run above the existing 0.85 trusted-interruption threshold. After deterministic regression, a controlled production restart published `friday_aec_source`; a normal wake turn passed and the user directly verified that natural speech interrupted Friday's active playback and continued the conversation without repeating `Hey Friday`.

Stage 8 added task-bound Git worktrees, exact checkpoints and rollback, capability-aware sandbox backends, clean task environments, resource/process limits, explicit network policy, crash recovery, promotion integrity, and history/UI visibility. The current Ubuntu host exposes Bubblewrap but denies its user-namespace probe, so strong untrusted-code execution fails closed and the native backend is reported as degraded rather than overstated.

Stage 7 added a versioned local SQLite task-history service, legacy artifact indexing, lifecycle/audit/search/metrics/export CLI, and read-mostly Streamlit coding/history/metrics/system workspaces. The UI invokes existing planner and exact-plan approval services; it does not bypass execution or Git safety.

Stage 6 generalized the deterministic Stage 2 index into one capability-aware language platform. It preserved Python and added narrow Tree-sitter adapters for Rust, Solidity, TypeScript/JavaScript, SQL, C/C++, Java, and Shell; shared multi-language relationships, parser-version invalidation, filters, maps, planner/scope/test evidence, and line-chunk fallback remain under the same deterministic authority.

Stage 5 introduced typed validation plans, deterministic validator and targeted-test selection, bounded scope-enforced test generation and repair, failure/flaky classification, validation caching, deterministic/security/model review, and a final commit-or-rollback decision. The execution order now separates targeted feedback from required final validation, while Stage 3/4 plan, approval, scope, command, and Git policies remain authoritative.

The Stage 5 self-review then bound validator commands to regenerated policy/configuration, strengthened cache/environment identity, restored exact Git-visible and sensitive-file state after validator side effects, activated optional scope-enforced test-generation/TDD flow, blocked repair/test weakening, expanded redaction/security heuristics, and bound automatic commit to the exact reviewed diff before and after staging.

Stage 4 activated `ScopeGuardPolicy` against generated and post-apply Git diffs, then added typed plan-bound tools, structured multi-file edits, parsed command allowlists, bounded execution/repair, human review, timeouts, and auditable rollback-integrated execution.

The Stage 4 security review then hardened quoted/binary patch handling, stale-symbol rejection, symlink and command-argument boundaries, dry-run isolation, bounded output capture, validation-side-effect rollback, and staged-diff coverage.

1. `Qwen3.6-35B-A3B-UD-Q4_K_M` was selected as the strongest practical local coding/reasoning model for the MSI GT62VR hardware.
2. llama.cpp/TurboQuant profiles were benchmarked. The selected profile uses GPU layers 999, 34 CPU MoE layers, 262,144 context, 128/32 batch sizes, four threads, Turbo4/Turbo3 KV, and reasoning disabled. `--mlock` was rejected and full 242K prefill was deferred due cost.
3. A persistent localhost `llama-server` exposed the OpenAI-compatible API and was reboot-tested through systemd.
4. `LocalLLM` added normal and streaming Python clients against that API.
5. A second systemd service made the Streamlit interface persistent.
6. Document RAG added TXT, Markdown, PDF, and DOCX ingestion, token-aware chunks, SHA-256 change detection, persistent FAISS storage, then BM25 and reciprocal-rank fusion.
7. Selective Tesseract OCR was added for low-text PDF pages, retaining extraction metadata.
8. Streamlit added uploads, reindex controls, source display, chat history, and index/OCR statistics.
9. Code RAG added multi-language file discovery, overlapping line chunks, FAISS/BM25 retrieval, and repository-grounded questions.
10. The patch agent added unified-diff generation, path normalization, `git apply --check --recount`, explicit application, and detected test commands.
11. One bounded repair attempt was added after test failure. Exact failing-file contents, the current diff, test output, and retrieved context grounded repairs after hallucinated helpers and fake stubs were observed.
12. Python AST checks caught duplicate top-level definitions that syntax and tests had missed.
13. Fresh indexing before proposals and after edits addressed stale-patch failures.
14. Isolated `agent/*` branches, success auto-commit, deterministic rollback, return to the original branch, and failed-branch cleanup completed the proven Git transaction flow.
15. On 2026-08-23, Stage 0 imported the live source into this repository, introduced environment-configurable data paths, sanitized service templates, tests, documentation, and explicit generated-data exclusions. The original working directories and installed services were left unchanged for review.
16. Stage 1 stabilized the import as an injectable Python package: typed settings, structured logs, explicit errors and transaction summaries, canonical console commands, compatibility wrappers, configurable directories/retrieval/OCR/UI/runtime values, and comprehensive regression tests were added without changing the live external deployment.
17. Stage 2 added official Tree-sitter Python parsing, typed symbol/reference/call records, persistent incremental symbol embeddings and graphs, repository maps, deterministic queries, provenance, and symbol-first code RAG while retaining line chunks as fallback.
18. Stage 3 added deterministic affected-scope analysis, bounded structured Qwen planning, typed plan validation and persistence, dependency/migration/security awareness, explainable risk/confidence/approval policy, a future scope guard, planning CLI, and a mandatory planning gate before patch generation.
# Stage 9

The Friday-native integration gateway is present in the current branch with authenticated API/service boundaries, typed external provenance/idempotency, bounded events, GitHub transport/publication components, and controlled MCP-compatible interfaces. Targeted gateway/MCP tests pass; real external workflow hardening remains.

# Stage 10

Real-repository onboarding is partially implemented through onboarding services/CLI and integration coverage. Broader benchmark/context/runtime/model tuning remains active roadmap work.

# Stage 11

The current accepted Stage 11 baseline is the persistent Friday conversational/wake platform with production WebRTC AEC-backed natural-language barge-in. Stage 12B hardened the always-on wake microphone lifecycle: deterministic concurrency tests proved that intentional pause/stop could previously surface blocked-read EOF/errors as false microphone failures; the accepted fix retires the shared stream before close, treats retired-stream unwind as cancellation, preserves fail-closed handling for genuine current-stream capture failures, keeps pause quiescent rather than terminating the loop, and reacquires a fresh stream on resume. Production qualification then completed two controlled restarts without systemd stop timeout and a live wake/pause/voice/resume turn on the patched process. Stage 12C added inline wake commands and fresh bare-wake follow-up capture; Stage 12D adds exact explicit stop semantics. Stage 12 remains active for capture health/recovery, concurrency policy, observability, streaming speech latency, and longer-running voice stability.

## Stage 12C-A — inline wake command semantics

2026-08-30 — Accepted inline wake-command semantics.

- Added direct text entry to `FridayVoiceConversationService`.
- Routed non-empty `WakeSupervisorResult.remainder` through that direct-text entry.
- Preserved authoritative `LISTENING -> TRANSCRIBING -> THINKING -> COMPLETED`
  runtime transitions without invoking Whisper for the wake utterance.
- Replaced the obsolete test contract that required inline wake audio reuse.
- Live production qualification proved wake acceptance, LLM execution, playback,
  wake resume, and no `WHISPER_BEGIN` for inline wake commands.
- Deterministic live command `Hey Friday, what is two plus two?` produced the
  semantically correct answer 4.
- Recorded the then-remaining Piper Markdown-verbalization limitation; Stage
  12J later replaced it with deterministic TTS normalization.

## Stage 12C-B — bare wake fresh follow-up command

2026-08-30 — Accepted bare-wake fresh follow-up semantics.

- Added bounded one-shot raw-microphone follow-up capture using the accepted
  wake PCM/VAD primitives and a fresh segmenter per turn.
- Bare `Hey Friday` now waits for a new command utterance instead of reusing
  wake audio; only the fresh utterance enters main Whisper.
- Timeout/capture error closes pending LISTENING back to IDLE before wake resumes.
- Removed the obsolete no-boundary wake-audio reuse fallback; missing wiring
  now fails closed.
- Retained lifecycle/error telemetry while removing qualification-only logging
  of complete wake ASR transcripts.
- Production qualification proved fresh capture -> Whisper -> LLM -> Piper,
  clean timeout, second bare wake after timeout, and unchanged inline routing.

## Stage 12D — explicit stop semantics

2026-09-09 — Accepted exact voice stop commands.

- Added normalized exact `stop`, `friday stop`, and `hey friday stop` handling
  at the existing voice TRANSCRIBING boundary.
- Exact stop now returns directly to IDLE without conversation history, LLM
  inference, TTS acknowledgement, or a second assistant turn.
- Reused the accepted WebRTC AEC/Silero playback interruption and main-Whisper
  path for stop commands spoken while Friday is audibly speaking.
- Kept stop-loss, negation, longer phrases, and ASR mistakes conversational;
  removed the rejected context-specific `go ahead and stop` alias.
- Diagnosed failed physical trials to clipped host audio. Reducing microphone
  volume from 1.0 / +30 dB to 0.5 / +11.25 dB and keeping speaker volume at or
  below 1.0 eliminated clipping in captured raw, AEC, and Whisper input.
- Final clean-runtime physical qualification passed silent inline stop, trusted
  active-speech stop, and the stop-loss negative control without diagnostic
  microphone readers. Active playback stopped about 3.2 ms after the trusted
  trigger, no stop acknowledgement followed, and wake capture resumed.
- Recorded complete-response buffering and initial speech latency as remaining
  Stage 12 work rather than expanding Stage 12D scope.

<!-- FRIDAY_GOVERNANCE_HISTORY_START -->

## 2026-08-30 — Repository governance and cross-session continuity

Codified the persistent Friday development/handoff rules in repository
documentation so new Codex/agent sessions do not depend on prior chat history.

The repository now explicitly requires:

- one stage-owned `stage-N/<capability>` branch per roadmap stage;
- every fully accepted subtask to be committed/pushed to its owning stage
  branch and then fast-forwarded into `main` at the same accepted commit;
- stage branches to remain stage-accurate;
- canonical documentation updates to be part of the acceptance gate for every
  feature, capability, architecture/runtime/deployment change, limitation, and
  accepted recovery point;
- new sessions to bootstrap from `AGENTS.md`, `CODEX_HANDOFF.md`,
  `ARCHITECTURE.md`, `ROADMAP.md`, `HISTORY.md`, and relevant ADR/architecture
  documents rather than requiring the user to restate accepted decisions.

The Stage 11/12 branch boundary was already repaired before this governance
entry: Stage 11 ends at `877cb1e6049eb6b0a6434d3eac835077be666c17`
and active Stage 12 is
`stage-12/production-voice-lifecycle`, accepted through
`70d368e49ad546d02b274c3e440f2178038a06d8` before this docs-only change.
<!-- FRIDAY_GOVERNANCE_HISTORY_END -->

## 2026-09-09 — Durable continuous-autonomy owner policy

Starting from accepted Stage 12D recovery
`2ce0686cf05c379280c6643a3e6aba82ac3a58b0`, the owner made autonomous roadmap
continuation durable. `AGENTS.md` now directs future sessions to own ordinary
engineering end-to-end and treat accepted checkpoints as the start of the next
capability's discovery. Human intervention is reserved for unavoidable physical
actions or true capability boundaries. Quality, documentation, isolation,
acceptance, and remote recovery gates remain mandatory. The canonical handoff
records recovery and active work; fresh sessions discover the policy through
the normal root AGENTS/bootstrap path without depending on conversation history.

## 2026-09-09 — Stage 12E capture and wake-worker recovery

Accepted recovery at the existing capture ownership boundary. Friday now bounds
raw PCM chunk reads, suppresses partial audio and late ASR results from retired
streams, retries microphone and wake-worker failures with capped backoff, closes
dead idle-worker pipes before replacement, and exposes voice readiness separately
from presentation HTTP liveness. Shutdown interrupts retry waits and cannot reopen
the microphone after stop.

Deterministic coverage exercised capture errors, recorder stalls, cancellation
races, late results, retry capping, worker replacement, and health reporting.
On PID 64096, terminating the actual recorder recovered in 1.23 seconds and a
SIGSTOP stall recovered in 5.19 seconds without restarting Friday. The owner then
physically said “Hey Friday, say recovery is working” after Parakeet PID 64118
had been stopped. Fresh Parakeet PID 64624 recognized the inline command; Friday
spoke “Recovery is working,” completed the turn, and resumed listening.

The final restart gate exposed and repaired a shutdown-order race: the old
launcher waited for Uvicorn to return before closing voice resources, so SIGTERM
could briefly look like recorder failure. Cleanup now begins at Uvicorn's first
exit signal and is idempotent. A repeat restart completed without capture-error
or retry telemetry.

## 2026-09-09 — Local sovereignty and durable Stages 20–22

Accepted the product architecture and roadmap scope, not implementations, for
Local Intelligence Sovereignty and Friday as a Local Personal Cognitive Operating
System. Core cognition remains owner-controlled and locally executable; external
services may supply information but not mandatory intelligence. The tuned Qwen
remains the sole current general-purpose model, while sequential roles and
specialized local components remain available. ADR 0014 records the decision.

The canonical roadmap now preserves detailed mandatory future Market Intelligence
& Adaptive Trading Research, Cognitive Architecture & Local Intelligence
Amplification, and Creator Studio & Digital Media Intelligence stages after their
existing prerequisites. The update grants no real-money trading or publishing
authority and does not mark any of those future capabilities implemented.

## 2026-09-09 — Stage 12F voice/presentation interaction ownership

Accepted a shared nonblocking interaction coordinator across physical voice and
presentation HTTP streams. Admission happens before runtime mutation. A live
physical `Hey Friday, count slowly from one to one hundred` turn held voice
ownership while the concurrent HTTP probe received 409; wake capture was paused
for the turn. Conversely, a physical wake phrase during a long presentation
stream produced no reply and zero accepted wakes, then normal stream completion
returned Friday to listening.

Deterministic coverage includes concurrent claims, no phantom prompts,
pause/resume and thread-start failures, immediate and in-flight HTTP disconnects,
and cancellation state recovery. A disconnect during an active synchronous model
read retains microphone ownership until the iterator reaches a safe stop.

The long voice qualification also exposed a trusted barge-in stop with no
completed utterance. Friday now records that incomplete interruption and returns
to IDLE without passing partial audio to Whisper or raising a false voice failure.

## 2026-09-09 — Stage 12G long-playback barge-in stability

Accepted playback-lifetime barge monitoring and privacy-safe interruption
outcomes. The former five-second first-audio deadline could expire while Piper
was still preparing a long response, silently disabling barge-in and later
reporting a false voice error. The bounded arm deadline is now 30 seconds, and
explicit monitor timeouts re-arm while playback continues. A live late stop
reached the exact-stop IDLE path with no runtime error.

## 2026-09-09 — Stage 12H bare-wake acknowledgement

Accepted a local “I'm listening” cue before fresh bare-wake capture. It keeps
wake paused, returns from SPEAKING to LISTENING, then opens the independent raw
follow-up stream. Physical qualification heard the cue, transcribed “What time
is it?”, completed the normal response, and returned to healthy listening.

## 2026-09-10 — Stage 12I incremental streaming speech

Accepted sentence-gated streaming speech through the persistent local Piper
process. The model remains the sole producer; a deterministic chunker and bounded
ordered queue begin ordered synthesis at the first complete sentence, while the
authoritative runtime can remain SPEAKING through model completion. Deterministic
tests cover chunks, queue closure/backpressure, lifecycle completion, incremental
start and speech failure. Physical `Hey Friday` qualification confirmed the sky
explanation, Piper start before LLM completion, orderly synthesis and healthy wake
resume.

## 2026-09-10 — Stage 12J Markdown-to-TTS normalization

Accepted deterministic presentation-only normalization at the Piper boundary.
Common Markdown formatting, links/images, and underscore-separated identifiers
now become readable speech while the model's streamed and completed text remains
exactly intact. Focused coverage and a live bold-Markdown arithmetic request
confirmed natural spoken “4” and healthy wake capture.

## 2026-09-10 — Stage 12K cinematic voice outcome signals

Accepted an event-derived frontend voice signal alongside the authoritative
runtime state. The cinematic client now distinguishes speech start, completion,
and barge-in interruption without claiming lifecycle ownership; interruption
remains visible through the listening handoff and clears with the next user turn.
Frontend tests, lint, and production build passed.

## 2026-09-10 — Stage 12L bounded voice-stage telemetry

Accepted a 2,048-record rolling telemetry trace for the always-on production
voice service. Recent ordering diagnostics remain available while normal uptime
can no longer grow the in-process trace indefinitely; journal output remains the
durable operations record. Focused capacity/order coverage passed.

## 2026-09-10 — Stage 12M bounded Piper protocol handoff

Accepted a bounded, cancellation-aware Piper worker event queue. Persistent
protocol output now has a 128-record in-process limit, and reader retirement
unblocks saturation during shutdown. Deterministic Piper capacity and lifecycle
tests passed.

## 2026-09-10 — Stage 12N resident worker health projection

Accepted read-only liveness/PID health projections for persistent primary wake,
fallback wake, and Piper workers. A live service restart confirmed all three
workers and wake capture healthy; deterministic projection coverage passed.
