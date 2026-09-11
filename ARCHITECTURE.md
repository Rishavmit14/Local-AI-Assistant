# Architecture

## Current accepted Friday system

```text
Qwen GGUF
   |
TurboQuant llama-server (127.0.0.1:8080)
   | OpenAI-compatible API
   |
   +-- LocalLLM / local chat / private document RAG + OCR
   +-- deterministic code intelligence
   |    +-- multi-language Tree-sitter index / repository RAG
   |    +-- planning / scope / approval / controlled tools
   |    +-- validation / review / repair / Git isolation
   +-- Friday-native integration gateway
   |    +-- authenticated localhost API
   |    +-- GitHub transport boundary
   |    +-- MCP-compatible stdio boundary
   +-- FridayInterfaceService / native presentation boundary
        +-- React/Vite Friday frontend
        +-- conversational voice
             +-- always-on microphone capture
             +-- Silero VAD segmentation
             +-- Parakeet Full wake ASR
             +-- Moonshine Medium fallback ASR
             +-- strict `Hey Friday` matcher
             +-- Whisper conversational STT
             +-- streaming local LLM response
             +-- Piper TTS / PipeWire playback
```

`local_ai_assistant.common.config` remains the typed configuration boundary. `local_ai_assistant.llm` is the model-client boundary. Deterministic code intelligence, planning, execution, validation, isolation, history, and the Friday-native gateway remain the authority-bearing backend layers.

Stage 8 worktree/checkpoint/isolation controls are accepted in the current branch. Stage 9's authenticated gateway, GitHub transport, MCP-compatible stdio, provenance/idempotency, bounded events, and delegation into existing safety services are implemented; real external-integration hardening remains. Stage 10 repository onboarding is partially implemented and broader benchmark/tuning work remains.

Stage 11 replaces Streamlit with Friday's native presentation/event architecture and conversational voice stack. The accepted wake path is:

```text
microphone -> Silero VAD -> Parakeet Full -> strict `Hey Friday`
                              | miss
                              v
                       Moonshine Medium
                              |
                              v
pause wake -> Whisper -> local LLM -> Piper -> PipeWire -> resume wake
```

Parakeet and Moonshine run as persistent fail-closed workers. Request/protocol failures invalidate a worker before reuse so stale responses cannot contaminate later requests.

Production Friday runs as the logged-in user's `systemd --user` service `friday-local-ai.service`. It has passed cold restart, controlled shutdown, live wake qualification, and full conversational turn qualification.

Production natural-language barge-in is accepted. Friday owns an ephemeral PipeWire WebRTC AEC graph using `monitor.mode=true`; the default physical speaker monitor is the echo reference, while the published `friday_aec_source` is captured explicitly by `FridayBargeInMonitor`. The wake path remains on the normal raw microphone and is paused during a conversational turn. The AEC session is created by the production wake bootstrap, owned by `FridayManagedWakeVoice`, and closed with the other managed voice resources.

The accepted interruption path is:

```text
Piper -> default physical sink -> sink monitor ----+
                                                    |
raw physical microphone ----------------------> WebRTC AEC
                                                    |
                                                    v
                                          friday_aec_source
                                                    |
                                                    v
                                         FridayBargeInMonitor
                                                    |
                                       trusted human speech
                                                    |
                                                    v
                                      stop playback + continue
                                      with interruption utterance
```

Live production qualification proved normal wake conversation and natural interruption without repeating the wake phrase.

Wake microphone ownership is also lifecycle-safe under concurrent pause/stop. `FridayAlwaysOnWakeCapture` reads from a stream-local handle while the shared current-stream reference is protected by its state lock. `pause()` and `stop()` retire the shared stream before closing it; therefore EOF or `VoiceCaptureError` produced while a retired stream is unwinding is treated as intentional cancellation. A failure from the still-current stream remains a real capture failure and fails closed. Pause keeps the wake loop alive and quiescent, resume reacquires a fresh stream, and stop terminates the loop cleanly.

Production qualification on Stage 12B proved two controlled restarts with no systemd stop timeout (patched shutdown ~0.18 seconds) and a full live `WAKE_ACCEPTED -> WAKE_PAUSED -> VOICE_THREAD_BEGIN -> VOICE_THREAD_COMPLETE -> WAKE_RESUMED` sequence on the patched process. Stage 12D adds exact explicit-stop semantics: normalized `stop`, `friday stop`, and `hey friday stop` end the active voice turn in IDLE before conversation, LLM, or acknowledgement speech. The same rule applies to trusted AEC interruption transcripts after the existing playback stop primitive has fired. Nonexact phrases remain conversational.

See [voice and wake architecture](docs/architecture/voice-and-wake.md).

## Deployment compatibility

Stages 0 through 8 did not mutate `/AI/projects/local-ai`, `/AI/projects/code-assistant`, llama.cpp, or model storage. The packaged code uses `LOCAL_AI_*` environment variables so reviewed deployments can point to existing paths or new state directories. Stage 11 removed the obsolete Streamlit product service and introduced the persistent user-session Friday presentation/wake service. A sanitized example is tracked at `config/services/friday-local-ai.service.example`; machine-local installed units remain external deployment state.

## Target architecture

The target is **Friday — Local Personal Cognitive Operating System**, one coherent
owner-controlled platform around the current Qwen llama-server and specialized
local components. It combines chat, private RAG/OCR, deterministic code
intelligence, role-based planning/coding/review/debug/test/security, controlled
tools, validation/policy, Git transactions/worktrees, history/metrics, native
integrations, voice/UI, durable memory, visual perception, desktop control,
autonomy, proactive events, research/self-learning, cognitive amplification, and
Career Forge learning intelligence. Market/trading and creator/media work are
deferred specializations, not active architecture scope. Git diffs remain
mutation truth; deterministic inspection precedes inference; risk and confidence
gates constrain automation.

Local Intelligence Sovereignty governs the system: current external information
may arrive through provenance-bearing adapters, while reasoning, planning,
memory, knowledge integration, evaluation, learning, orchestration, decisions,
and execution remain local and owner-controlled. Core cognition cannot require
paid/proprietary AI inference or cloud GPUs. The accepted Qwen model remains the
sole general-purpose LLM; multiple roles are sequential uses of it. Whisper,
Piper, wake/VAD, embeddings, OCR, and later vision/image models are specialized
components. ADR 0014 defines evidence required for any future general-model
addition or replacement.

Career Forge's durable boundary is a local Learner Twin and versioned ML/AI
Engineer competency graph above the Stage 13 memory foundation. It reuses
Friday's code intelligence, controlled tools, validation, Git isolation, history,
voice, and presentation surfaces, while keeping private learning evidence
separate from review-gated public career artifacts. Its detailed contract is in
`docs/architecture/career-forge.md`; ADR 0015 freezes its roadmap priority.
Career Forge is a mode of the existing cinematic Friday UI, not a separate
learning product: LEARN, MAP, PROJECTS, and PROGRESS are projections of the
same local Learner Twin and conversation/voice session. Later perception and
desktop-control capabilities extend that presentation boundary rather than
creating a parallel frontend or voice path.
The first Stage 14 cinematic projection calls only the existing local journey and
dependency-gated mission-start endpoints. It renders unknown progress honestly;
the frontend has no Learner Twin advancement, publishing, tool, or desktop
authority.

Stage 15 is an owner-initiated, read-only perception boundary. Captures remain
under configured `var/perception` state; the presentation API exposes bounded
metadata, explicit local OCR/UI-state results, and at most ten labels from an
offline cached specialist. The specialist is not a general-purpose model and
does not download or transmit pixels. Perception has no desktop-control, shell,
network, or mutation authority. See `docs/architecture/perception.md`.

Stage 16 starts at a separate local desktop-control boundary. It accepts only
exact app identifiers from an empty-by-default local allowlist and records a
proposal, explicit approval, and one-time execution in SQLite before invoking a
fixed GNOME focus or GIO launch vector. It has no arbitrary shell, keyboard,
mouse, browser, file, or perception shortcut. The cinematic UI can display a
pending action and requires a local confirmation dialog before the explicit
approval/execution click; it cannot bypass policy.

Stage 17 begins with a durable local objective lifecycle. It records bounded
create/resume/cancel state and may bind exactly one already plan-ready canonical
task-history record by task ID and exact plan token. It delegates no authority
itself; cancellation of a bound objective delegates to that task's existing
history cancellation boundary. Objective reads project the current task-history
state without becoming a second lifecycle authority. Any future objective
execution must pass through the existing plan, approval, isolation, validation,
rollback, and audit chain.

Stage 14 begins with a local Career Forge SQLite Learner Twin boundary: canonical
competencies are versioned and dependency ordered, every state is initialized as
UNVERIFIED, and a mission retains exact resume and assistance-bearing evidence.
No self-report or a working solution automatically advances mastery; an explicit,
matching evidence-backed one-rung decision is required.

Stage 13 uses `local_ai_assistant.memory.FridayMemoryService`, a separate local
SQLite boundary rather than a reinterpretation of task-history audit data. It
stores typed episodic/preference/fact/working records, provenance/confidence,
expiry/supersession/conflict/deletion lifecycle, bounded working-memory retention,
and typed project/goal/person-capable relationships. Bounded hybrid retrieval
uses deterministic lexical evidence plus lazy local BGE embeddings; the SQLite
embedding cache is rebuildable and offline-only. Production conversation receives
retrieved text only as labelled untrusted reference context, while deterministic
service operations retain all memory mutation authority. See
`docs/architecture/memory.md`.

The compounding architecture is:

```text
current local LLM
  + memory + structured knowledge + retrieval
  + skills + tools + planning
  + observation + verification + experience
  + voice + vision + desktop + proactive automation
  + Career Forge specialization
  = Friday
```

The permanent authority direction is `voice/UI/external adapters -> Friday native API/event/policy boundary -> planning/approval/execution/validation/isolation/audit`. Later stages extend perception, memory, and autonomy without granting presentation, voice, vision, or external adapters a privileged shortcut. The CLI remains the recovery/power-user surface.

## Trust boundaries

- Model output, uploaded documents, indexed repositories, and shell output are untrusted.
- localhost binding is the default network boundary; remote exposure needs authentication and TLS.
- private/generated data never enters Git.
- high-risk production, security, payment, smart-contract, migration, and deployment changes always require explicit human review.
- real-money trade execution and content publication require their separately
  defined authorization/review boundaries; planned analysis or production does
  not imply permission to transact or publish.

## Stage 12C-A — inline wake command semantics

Accepted on 2026-08-30.

Friday now distinguishes an inline wake command from a bare wake phrase. When the
strict wake matcher accepts `Hey Friday, <command>`, the normalized wake remainder
is routed directly into the existing conversation boundary instead of sending the
original wake audio through Whisper a second time.

Accepted production flow:

```text
raw wake microphone
  -> wake VAD
  -> Parakeet Full / Moonshine strict wake detection
  -> strict `Hey Friday` matcher
  -> non-empty wake remainder
  -> Friday voice runtime LISTENING
  -> synthetic TRANSCRIBING boundary using wake-ASR text
  -> conversation / LLM
  -> Piper playback
  -> wake capture resumes
```

The runtime state contract remains authoritative:
`LISTENING -> TRANSCRIBING -> THINKING -> COMPLETED`.

Stage 12C-B below completes bare-wake semantics with a fresh follow-up capture; the original bare-wake audio is never reused as the command.

Qualification evidence:
- deterministic regression proves inline wake remainder bypasses original wake audio;
- direct-text voice regression proves no Whisper transcriber call is made;
- repository verification passed with 614 tests before production qualification;
- controlled production restart loaded the patch successfully;
- live `Hey Friday, what time is it?` reached the LLM with no `WHISPER_BEGIN`;
- live `Hey Friday, what is two plus two?` was accepted on the first retry-tolerant
  qualification attempt, reached the LLM with no Whisper retranscription, played
  speech, resumed wake capture, and the user confirmed the semantic answer was 4.

The TTS boundary deterministically normalizes common Markdown and readable
identifier separators before Piper without changing the streamed/model-completed
text used by the conversation. Headings and list markers, emphasis, strikeout,
inline code, links, images, and underscore-separated identifiers therefore reach
Piper as ordinary spoken prose. This is presentation-only normalization, not a
wake-command routing or model-text mutation.

The cinematic client keeps the runtime state as its authoritative activity
projection, and separately retains the latest voice outcome signal from runtime
events. `voice.speech.started`, `voice.speech.completed`, and
`voice.speech.interrupted` drive distinct speaking, completion, and interruption
visual treatment without introducing a presentation-owned runtime state.

Production voice-stage telemetry is a thread-safe rolling trace capped at 2,048
records. It retains recent diagnostic order for in-process consumers without
allowing an always-on service to accumulate unbounded stage history; operational
journal output remains the durable external diagnostic stream.

The persistent Piper worker protocol also has a bounded event handoff (128
records). Reader backpressure is cancellation-aware, so shutdown retires a
reader blocked by a saturated queue instead of leaving a worker thread behind.

Voice health exposes read-only liveness and local PIDs for the resident primary
wake ASR, fallback wake ASR, and Piper processes alongside capture health. This
detects an idle dead worker without granting the presentation layer control over
its lifecycle.

## Stage 12C-B — bare wake fresh follow-up command

Accepted production behavior:

```text
raw physical microphone
  -> strict Hey Friday wake utterance
  -> wake capture pauses
  -> runtime enters LISTENING
  -> new one-shot raw-microphone stream opens
  -> fresh Silero + UtteranceSegmenter
  -> first completed follow-up utterance
  -> main Whisper
  -> local LLM
  -> Piper
  -> wake capture resumes
```

The follow-up path reuses the accepted wake audio format (16 kHz, mono,
S16_LE, 32 ms chunks) while creating a fresh Silero/VAD segmenter for every
bare-wake turn. Waiting is bounded to 8 seconds. Always-on wake capture remains
paused while the one-shot recorder owns the raw physical microphone. AEC
remains barge-in-only and is not used for this capture.

The original bare-wake VoiceUtterance is never passed to main Whisper. If the
follow-up boundary is unavailable, the orchestrator fails closed rather than
restoring the obsolete wake-audio reuse behavior. Timeout or capture error
closes LISTENING back to IDLE before wake resumes.

Inline `Hey Friday, <command>` remains separate: the strict wake remainder
enters stream_text directly and bypasses main Whisper. Production qualification
proved fresh follow-up capture, Whisper, LLM/Piper response, clean 8-second
timeout, a second bare wake after timeout, and unchanged inline behavior.

At that checkpoint there was no acknowledgement chime or spoken "Yes?"; Stage
12H later accepted the local bare-wake “I'm listening” cue. Deployment remains
the logged-in user's `friday-local-ai.service`. The pre-Stage-12C-B recovery point is
`3ae5292bbd1b0042e01211a657dad0fd5e9078d6`; the accepted Stage 12C-B recovery
commit is the commit containing this section.

## Stage 12D — explicit stop semantics

Friday recognizes only normalized exact `stop`, `friday stop`, and
`hey friday stop` as explicit voice stop commands. Classification occurs after
the existing TRANSCRIBING event boundary and transitions directly to IDLE. The
command is not added to conversation history, sent to the LLM, or acknowledged
by TTS.

For active speech, trusted WebRTC AEC and Silero detection remain responsible for
stopping playback and returning the completed interruption utterance. Main
Whisper transcribes that utterance, then the same exact-command classifier ends
the turn. Nonexact phrases such as `stop loss`, `I didn't stop`, and longer
sentences continue through the ordinary conversation path. No fuzzy, suffix, or
ASR-error aliases are accepted.

Physical qualification covered silent inline stop, trusted AEC stop during
audible counting, and a spoken stop-loss negative control. The clean runtime
stopped playback about 3.2 ms after the trusted trigger, transcribed
`Friday stop.`, produced no second assistant response, and resumed wake capture.
The stop-loss request completed through LLM and speech with no stop event.

The deployed MSI required undistorted host audio levels for reliable AEC ASR.
Qualification used microphone volume 0.5 (hardware capture +11.25 dB) and speaker
volume at or below 1.0 after higher levels produced clipping. These remain
machine-specific operational settings rather than application-enforced defaults.
Complete-response buffering still delays initial speech and remains later Stage
12 work.

## Stage 12E — capture/worker recovery

The managed wake loop supervises capture and wake-worker failures in
the existing capture thread, closes the failed stream, resets segmentation, and
retries with 1/2/4/8/16/30-second capped backoff. A run lasting 60 seconds resets
the delay. Failed utterances are discarded; no ASR request or voice action is
replayed. Existing fail-closed workers restart lazily on fresh input; dead idle
workers release old pipes before replacement. Unclassified failures remain
visible as failed rather than being blindly retried.

Production raw wake/follow-up capture has a two-second whole-PCM-chunk deadline.
Stream retirement suppresses incomplete PCM and late ASR results from cancelled
generations. Segmentation and reset are serialized, and shutdown is terminal and
interrupts recovery waits. `/api/v1/voice/health` exposes capture phase, managed
thread state, recovery count, and last error type separately from HTTP `/health`.
The API remains read-only. Host qualification proved actual recorder death and
stall recovery without a service restart, then a physical inline wake turn after
an idle Parakeet worker was stopped. The replacement worker recognized the fresh
speech, Friday replied, and capture resumed. Stage 12E is accepted.
Voice shutdown begins at Uvicorn's first exit signal, before HTTP teardown. This
removed the observed false recovery during service stop and a controlled restart
then completed without capture-error or retry telemetry.

## Stage 12F — interaction ownership

Friday now shares one `FridayInteractionCoordinator` between production wake
orchestration and the HTTP presentation API. It grants a nonblocking,
generation-bound lease to exactly one `voice` or `presentation` interaction
before runtime mutation. Voice ownership makes overlapping HTTP return 409;
presentation ownership pauses raw wake capture before streaming and resumes it
before releasing the lease. A wake that loses admission is discarded without a
voice thread or phantom runtime event. Completion, failure, thread-start error,
client disconnect, and shutdown cleanup release ownership idempotently.

Synchronous LLM streaming has an explicit cancellation boundary: an immediate
disconnect releases a never-started stream, while an in-flight synchronous read
keeps microphone ownership fail-closed until that read reaches a safe stop. A
closed started stream becomes `CANCELLED`, so it cannot poison the next voice
turn. `/api/v1/interaction/state` is the read-only busy/owner/generation
projection.

Live qualification on the user-session service proved both directions. During a
physical `Hey Friday, count slowly from one to one hundred` turn, the watcher
observed `owner=voice`, paused capture, and HTTP 409 with no presentation work.
During a long presentation stream, the owner spoke `Hey Friday, say this voice
request should be blocked`; Friday gave no reply, accepted zero wakes, and
resumed listening after the stream completed. Stage 12F is accepted.

Qualification also found a long trusted interruption may stop playback before a
bounded completed utterance is available. Friday now records the interruption and
returns to IDLE without sending partial audio to Whisper or incorrectly reporting
a voice failure. This remains fail-closed and does not claim a conversational
continuation without a completed utterance.

## Stage 12G — long-playback barge monitoring

Friday waits a bounded 30 seconds for Piper's first audible playback, then keeps
barge coverage alive through explicit bounded-monitor timeout passes while speech
continues. Speech events report only aggregate outcome/pass/elapsed/VAD metadata.
The live delayed-counting trial stopped on `Friday, stop` in 3.3 ms and completed
the exact-stop IDLE path without a runtime error.
