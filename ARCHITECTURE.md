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

Phase 15A hardens the internal task-checkpoint restore kernel: exact task/plan
identity, per-task serialization, a private pre-restore safety checkpoint,
verification and one compensating restore, plus recovery-scanner-visible
in-progress/double-failure state. Phase 15B now implements a separate owner
unlock and rollback-only server bridge, strict Origin/CSRF checks, exact
expiring reviews in TaskHistory, and History review/execute controls. Disposable
native-Astra review/execute and full regression qualify bounded authenticated
isolated-task checkpoint rollback only. General undo,
publication/canonical repository reversal, and interruption recovery remain
outside this qualification.

Stage 11 replaces Streamlit with Friday's native presentation/event architecture and conversational voice stack. The accepted wake path is:

```text
microphone -> Silero VAD -> Parakeet Full -> strict `Hey Friday`
                              | miss
                              v
                       Moonshine Medium
                              |
                              v
pause wake -> bounded active session -> Whisper -> local LLM -> Piper -> PipeWire
                                        | exact stop / bounded idle
                                        v
                                  clear session -> resume wake
```

Parakeet and Moonshine run as persistent fail-closed workers. Request/protocol failures invalidate a worker before reuse so stale responses cannot contaminate later requests.

Production Friday runs as the logged-in user's `systemd --user` service `friday-local-ai.service`. It has passed cold restart, controlled shutdown, live wake qualification, and full conversational turn qualification.

### Stage 22 Slice 1 — conversational coherence foundation

The presentation composition owns one typed, descriptive capability registry. It projects installed/integrated status, configuration, permission and live health without granting execution authority; conversation receives that projection as grounding, so it cannot truthfully invent or deny Friday's product surface.

An active voice session owns a bounded in-process conversation record (at most 16 turns and 12,000 characters). Following a successful wake turn it keeps raw wake capture paused, permits sequential fresh follow-up captures for up to the configured 60-second idle period, and returns to wake only on exact explicit stop, deliberate close, error, or idle expiry. The session record is cleared on close/restart; it is not persistent memory. The existing interaction lease keeps one microphone owner, and Stage 12's strict wake, exact stop, barge-in, and recovery paths remain authoritative.

Persistent memory remains a separately governed SQLite service. Conversation may read bounded retrieved records as labelled untrusted reference context, but model output and active-session turns cannot silently create or mutate durable memory.

Conversation grounding explicitly prioritizes the current owner request and
active-session history for references to the current discussion. Durable memory
is a distinct long-term source: its absence cannot override relevant active
history, and active history is never represented as persistent recall.

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

### Stage 22 Slice 6 — Qwen/conversation time-to-first-token optimization

The bounded local latency projection now distinguishes conversation routing,
Career Forge projection, memory retrieval, capability projection, prompt
assembly, Qwen request dispatch/acceptance/first token, returned token usage,
first speakable chunk, TTS, and first PipeWire PCM. It records only monotonic
timings and numeric size/token/cache metrics; no prompt, transcript, audio, or
memory content is retained.

The installed `llama-server` already had one slot and prompt caching enabled.
Profiling established that the slow path was prefill, not request transport or
generation: the previous prompt order put volatile active-session/retrieval
material before the large capability projection, so consecutive requests had
only 0.240–0.413 LCP similarity and evaluated 639–1,394 prompt tokens at
95–127 tokens/s (5.60–11.88 s). Friday now puts its immutable identity,
evidence policy, and descriptive capability projection first, followed by the
same labelled cognitive, active-session, durable-memory, Career Forge, and
route context. Source priority and all authority semantics are unchanged.
Warm normal/follow-up requests reached 0.902–0.970 slot similarity, evaluated
260–305 tokens at 98–126 tokens/s, and reached Qwen first token in about
2.06–3.09 s. The same Qwen model, quantization, offload, 32K configured runtime
context, memory, Career Forge grounding, Piper, AEC/barge-in, and exact-stop
boundaries remain in force. A grounded Career Forge teaching turn legitimately
remains heavier (988 newly evaluated tokens; about 11.13 s prefill).

### Stage 22 Slice 7 — first-speakable PCM handoff

The same bounded content-free trace now marks speech-queue admission, worker
start, Piper worker/request/first-audio boundaries, `pw-play` process start, and
first PCM write. Profiling isolated the post-Qwen delay to a single oversized
first `pw-play` stdin write: Piper and process startup were fast, but flushing a
whole sentence-sized PCM chunk could block for 0.85–10.83 s before the previous
first-PCM marker. The player now flushes an unchanged 8 KiB 16-bit PCM prefix
(about 186 ms at 22.05 kHz) before streaming the remainder contiguously. This
does not change text, synthesis, the audio bytes, Qwen configuration, AEC,
barge-in, or stop behavior. Physical qualification measured first-speakable to
first PCM at 54–619 ms (median 388 ms), removing the multi-second handoff wait.

### Stage 22 Slice 8 — pre-Qwen prompt-assembly investigation

The content-free latency trace now attributes total prompt assembly to route
classification, Career Forge projection, active-session projection,
SQLite/lexical/semantic durable-memory retrieval, capability projection,
cognitive policy, and prompt serialization. It retains only monotonic timing
and existing numeric sizes, never prompts, transcripts, memory contents, or
embedding vectors.

The historical 27.5-second class was not reproduced after one controlled service
restart and a bounded eight-turn normal/follow-up/current-discussion/memory/
Career Forge/long-session corpus. Cold assembly was 16.9 ms; warm/mixed median
was 2.23 ms and p95/max 128.4 ms. The slowest turn was a 127.2 ms Career Forge
projection; no serialization, memory, SQLite, capability, or model-service wait
approached tens of seconds. An isolated record-bearing memory store took 5.15 s
to initialize local BGE and 34.2 ms warm, but the historical outlier had empty
durable-memory context, so it is non-causal and no speculative warmup was added.
Normal warm Qwen TTFT remained 1.93–2.92 s; grounded Career Forge resume was
7.28 s. Slice 8 keeps diagnostics only and changes no product behavior.

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

Owner Sovereign Mode is the owner-authorized local administrator path. It uses a
root-owned systemd credential broker with systemd host-key encrypted storage;
the owner-session Secret Service is not a sufficient process-identity boundary.
The broker exposes no raw-secret retrieval API, authenticates the configured
Friday runtime process over private Unix IPC, and runs general local
administrative operations only within an already-authorized owner task. Root
privilege alone is not a confirmation trigger; consequence and ambiguity still
govern the existing risk policy. Normal executor pathways do not propagate the
secret into model/API/history/log surfaces or untrusted sandbox processes.
Unrestricted trusted root may recover or disclose it; compromise can expose
owner data, change security configuration, and compromise the full machine, a
risk the owner knowingly accepts. The accepted design and current qualification
state are in ADR 0033 and
`docs/architecture/owner-sovereign-mode.md`.

Phase 19 qualified the bounded candidate local administrative boundary and an
integrated synthetic local-Qwen sovereignty scenario. Production
`friday-local-ai.service` is not trusted by the candidate broker; this evidence
does not qualify production administrative UI/API integration, expand the
trusted-root threat model, or qualify every product capability. See
`docs/qualification/owner-sovereign-mode.md`.

Phase 17 qualifies a restart-based configuration boundary without changing the
one-general-model policy. `LocalLLM` is the only OpenAI-compatible chat client
for general-purpose cognition; its base URL must be loopback, its HTTP transport
ignores proxy environment settings, and failures do not retry or fall back to a
remote or second model. `LOCAL_AI_BASE_URL`, `LOCAL_AI_MODEL`,
`LOCAL_AI_CONTEXT_SIZE`, and `LOCAL_AI_LLM_TIMEOUT` select the backend at process
startup. Conversation, roles, Research, and code/planning paths continue through
the same client contract. Model identity stays configuration, not product
authority or persisted state. See ADR 0032 and the model-swap qualification
procedure.

Phase 18B qualifies one bounded offline owner-path scenario without changing
the installed runtime architecture. The disposable candidate API ran as the
normal owner UID/GID in a transient systemd `PrivateNetwork=yes` namespace and
listened only on AF_UNIX. A loopback presentation proxy connected the host Astra
page to that socket. A separate fixed-operation AF_UNIX relay connected only
the candidate's loopback chat-completions adapter to the already-local Qwen at
`127.0.0.1:8080`; it offered no general proxy or network tunnel. Candidate
processes could not reach external DNS/IPs or host loopback services. Existing
Practice Lab `NetworkPolicy.DENY` Bubblewrap remained unchanged and its actual
learner process was separately shown unable to reach external, host, or
candidate loopback services. This topology is qualification-only: it installs
no persistent unit, service, route, firewall rule, or host network change. It
does not isolate the host browser process or establish that online-only
capabilities or first-time installation work offline. See the Phase 18B
qualification record and `docs/architecture/isolation.md`.

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
The owner-facing lesson loop is also inside that same conversation boundary:
only an explicit canonical lesson question or teach-back context can create an
attempt; assistance is recorded at the minimum deterministic level; local Qwen
may return a bounded semantic assessment but cannot promote mastery; and a
correct assessment creates provenance-bearing evidence without automatic
advancement. Lesson wording/session history clears on stop or restart while the
mission, attempts, assistance, feedback, evidence, and resume point remain in
the local Learner Twin.

### Stage 22 Slice 4 — truthful Career Forge progress and learning history

`CareerForgeService.progress()` is the one bounded, read-only projection of the
canonical Learner Twin. It derives active mission/resume state, ordered attempts
and retry truth, recorded assistance, evidence, recorded mastery rungs, and a
dependency-aware next action directly from SQLite. It contains no percentage,
no independent progress store, and no inferred mastery. The presentation journey
and existing PROGRESS surface consume that same contract; conversation routes
progress/history questions deterministically rather than asking Qwen to invent
learning state. Current-session questions remain temporary conversation context;
only governed Career Forge records are durable learning history.

The canonical PROJECTS workspace is another projection of this same journey.
It always shows the four hardware-aware project families and their recorded
mission/competency links. Only the active mission may be explicitly connected,
and only to the project family declared by its competency. The action records
learning context; it grants no execution, repository, GitHub, publication, or
mastery authority.

Evidence-backed mastery advancement also schedules one bounded local retention
review. The due interval is deterministic by the newly recorded mastery rung;
the review stays scheduled until the owner explicitly delivers it through the
canonical local service/API/Progress surface. Delivery returns the deterministic
competency verification prompt and records only `delivered`. Queue and delivery
state have no authority to create evidence, complete a review, or advance
mastery; evaluation and weak-area detection use the separate governed boundary
below.

Governed review evaluation reuses Friday's existing local conversation model
and interaction lease. The evaluator must return a bounded correct/incorrect/
uncertain result; the private owner answer remains in local SQLite and is not
projected by the journey API. Incorrect or uncertain completed reviews plus the
latest still-failing attempt per mission question derive a read-only weak-area
projection. Assistance is supporting context, never enough by itself to label a
weakness. The canonical next action prioritizes due/delivered reviews and then
the strongest evidence-backed weak area without automatically lowering mastery.
The owner may explicitly start reinforcement only from that current weak-area
projection. Friday creates a canonical mission for the selected competency,
records its evidence reasons and any interrupted mission in the resume point,
and teaches it through the existing mission brief/tutor loop. A newer-topic
mission remains active but is no longer the newest resume target; after an
explicit evidence-backed mastery rung completes the reinforcement, resume falls
back to the preserved mission. No weakness, reinforcement start, or correct
answer mutates mastery automatically, and a later correct retention outcome
clears historical retention weakness from the current projection.
Friday's existing proactive engine observes the oldest due `scheduled` review
and emits one deduplicated local notification keyed by review identity and due
time. The watch is notify-only: it cannot deliver or evaluate the review, create
evidence, change mastery, start reinforcement, or alter mission state.

Interview Mode is a persistent two-question, no-help state machine attached to
one active canonical mission. The first question uses the mission verification
criterion and the follow-up uses its teach-back criterion. Each explicit owner
answer is stored as a normal `TutorMode.INTERVIEW` attempt with no assistance;
evaluation reuses the existing local-Qwen interaction lease and bounded
correct/incorrect/uncertain parser. Correct answers may create typed
`interview_response` evidence, but neither completion nor model feedback changes
mastery or claims job readiness. Pending evaluation survives restart and can be
resumed without resubmitting the private answer.

Selected-code and screen-aware tutoring are one-shot extensions of the same
active-mission tutor boundary. Practice Lab sends only the owner's current text
selection; LEARN may explicitly reuse the newest retained capture but never
creates a capture implicitly. Screen pixels remain under the perception
retention policy and only bounded local OCR text enters the prompt. Both sources
are labelled as untrusted owner context so displayed instructions cannot grant
authority. The response creates no attempt, evidence, mastery, desktop action,
or durable context copy; optional progressive assistance remains the only
governed learning-state write.

Career Forge desktop assistance composes, but does not weaken, the existing
desktop-control state machine. An explicit owner action for the active mission
may create one allowlisted `proposed` record and a Learner Twin audit link.
Proposal, exact-action approval, and execution remain three separate API/UI
transitions; local Qwen has none of those authorities. The link never becomes
attempt evidence or mastery, and desktop failure changes only the audited action
state.

Public project evidence now has a durable pre-publication lifecycle in the
Learner Twin. A candidate requires a canonical project-linked mission and at
least one existing mission evidence record. The deterministic genuine-work,
validation, secret-scan, privacy/proprietary, documentation, and quality checks
produce `blocked` or `qualified`; only a separate explicit owner transition can
produce `approved`. None of those states runs Git or GitHub. An authenticated
`GITHUB_WRITE` request may then bind that exact approved candidate to one
promotion-ready Friday task and explicit onboarded repository mapping. The
existing gateway publisher remains the sole external authority for repository
identity, final commit, `friday/task/` branch, remote reconciliation, push, and
pull-request creation; its URL/result is copied back into the Learner Twin. A
failed external attempt preserves approval and the exact binding for safe retry.

Bounded Career Forge mission autonomy is an audit link, not a second executor.
An active project-linked mission may prepare exactly one durable Friday
objective from explicit owner text. Career Forge records only the mission and
objective IDs; the existing objective/task services remain authoritative for
repository selection, planning, exact-plan approval, isolated execution,
cancellation, terminal outcome, and restart recovery. Task success never creates
learning evidence, advances mastery, completes a mission, or qualifies public
evidence automatically.

### Astra presentation integration foundation

UX-60A wraps these existing projections in one Friday product shell. Home mounts
the unchanged Astra Ultra `NeuralPresence` and the existing
`FridayRuntimeStore` Conversation together. Persistent navigation groups the
canonical projections as Home, Learn, Projects, Knowledge, Automate, History,
Notifications and Settings; previous hash routes remain valid. Learn's Overview,
Roadmap, Practice, Interview and Progress tabs use Career Forge read models and
action APIs without browser-owned mastery or Dynamic Learning Paths state.
Settings discloses Memory, Perception and Developer / Diagnostics without
removing any technical evidence. `docs/product/FRIDAY_PRODUCT_EXPERIENCE_SPEC_V1.md`
records the NeetCode-led visual reference and the protected brain identity.
No new frontend authority, model, remote asset dependency, or backend service
is introduced by this shell.

The Astra visual workspace consumes Friday only through `frontend/src/presentation`:
a typed presentation adapter maps the existing `CareerForgeJourney` read model
into Astra views, while explicit action methods retain the existing canonical
command boundary. LEARN renders the active/resumable mission, dependency-aware
next action, and evidence/assistance counts; Practice Lab uses the existing
draft, Run/Test/Submit, hint, and attempt endpoints; MAP renders the canonical
competency graph, prerequisites, and recorded mastery; and PROGRESS renders the
canonical next action, attempts/retries, assistance, evidence, and history.
PROJECTS renders canonical project families and exposes the existing bounded
active-mission link action. Interview Mode exposes the persistent no-help
question/evaluation flow through the same typed runtime and presentation seams.
Unavailable API state remains unavailable rather than becoming a fixture. There
is no second frontend store, session owner, or Career Forge persistence layer.
The first Stage 14 cinematic projection calls only the existing local journey and
dependency-gated mission-start endpoints. It renders unknown progress honestly;
the frontend has no Learner Twin advancement, publishing, tool, or desktop
authority.

The isolated Astra Phase 1 candidate also connects Home and Conversation text
through the existing `FridayRuntimeStore` / `FridayRuntimeClient` boundary:
`POST /api/v1/conversation/stream` starts the production conversation service,
and `/api/v1/runtime/events/stream` projects canonical user/assistant deltas.
The browser owns no transcript persistence, prompt context, capability state,
memory retrieval, or model client. The existing backend composes active-session
context, descriptive capability grounding, and governed read-only memory
retrieval. This candidate adds no voice path or action authority; existing
Pocket/Anna production voice ownership is unchanged. Owner-path qualification
passed on 2026-09-27: a real local-Qwen exchange, immediate active-context
follow-up, registry-grounded Career Forge capability answer, ephemeral-marker
absence from durable memory, and Home-to-Conversation transcript continuity
were observed. The Career Forge due review/mission/mastery and Pocket/Anna voice
service state remained unchanged. Phase 1 qualifies only this text/session
path; Astra voice, durable thread history, and other prototype or missing
surfaces remain outside this accepted boundary.

Astra Memory now projects only Friday's canonical durable-memory records through
the typed presentation client. Owner remember, correction/supersession,
conflict-resolution, and forget actions are explicit and pass through governed
API routes into the existing `FridayMemoryService`; forgetting preserves the
service's tombstone lifecycle. SQLite remains the persistence authority.
Browser state is limited to transient filters, selection, and form drafts. The
workspace distinguishes active, superseded, conflicted, and deleted records,
and surfaces service failure without demo fallback. Active conversation turns
remain a separate runtime context and never become durable records implicitly.
Physical Astra qualification covered save, reload, conversational recall,
correction, service restart/recovery, confirmed forget, and verified absence
from active recall. No memory database or authority was added to the frontend.

## Dynamic Learning Paths — DLP-1/2 authority

DLP is the curriculum sequencing authority above Career Forge. Its local
`LearningPathService` stores path metadata and immutable version snapshots in
`LOCAL_AI_LEARNING_PATHS_DB` (default `var/learning-paths/paths.sqlite3`). Each
snapshot contains modules, learning nodes, prerequisite edges, project
milestone references, target metadata, provenance, and a stable topological
order. Create and revision validate the complete graph before one SQLite
transaction writes the version and current-version pointer. See
`docs/architecture/dynamic-learning-paths.md` for bounds and route contracts.

Curricula supplied directly or proposed by the existing local
`Role.CURRICULUM_DESIGNER` are untrusted until deterministic schema/reference/
DAG validation succeeds. Local model failure has no fabricated or cloud
fallback. DLP owns no mastery, attempts, evidence, mission, retention, readiness,
project execution, browser state, or next-learner-node authority. Career Forge
remains their canonical owner and is not mutated by path generation or reads.
The API provides create, local generation, list, detail, version history,
validated revision, evidence-aware sequencing, and versioned low-impact
adaptation. Sequencing reuses a bounded read-only Career Forge projection:
independent-application mastery with current/reinforced confidence supports a
node, while stale/weak/unverified evidence leads to review, reinforcement, or
diagnostic recommendations. Direct unsupported prerequisites block dependent
nodes while unrelated branches remain candidates. Adaptation records decision
provenance in a new immutable version and never writes Career Forge learner
state. Learn now provides functional path selection, review delivery and answer
submission, and reinforcement handoff over these canonical services. Explicit
owner-authored equivalence keys may resolve arbitrary DLP nodes across paths
only when assessment fingerprints match and Career Forge evidence satisfies
the target mastery rung. Sequencing projects source provenance read-only; it
does not copy learner records or create relationships. Project/capstone
milestones are excluded. The browser never calculates mastery or sequencing.
Learn remains a functional integration shell; final visual acceptance is
explicitly deferred. Matrix rows 60 and 61 remain PARTIAL for broader product
qualification and remaining DLP capabilities. See ADR 0036 and
`docs/architecture/dynamic-learning-paths.md`.

### Astra Research / Knowledge presentation boundary

Astra's Research workspace uses the typed Friday runtime client and existing
`ResearchService`/SQLite. Source-list responses project canonical metadata
without content; content is read only for an explicitly selected source.
Explicit owner registration carries owner-provided provenance and text through
the governed presentation API. Deterministic synthesis remains bounded source
evidence and does not apply the question to retrieval or produce generated
prose. These Research ledger paths remain separate from private-document RAG.

The Knowledge tab reads a bounded metadata projection of the existing local
document index and submits a query only with explicit indexed-source IDs.
`PrivateDocumentKnowledgeService` constrains backend vector and lexical
retrieval to those selected IDs before ranking. It uses cached local embeddings
and the existing loopback `Role.RETRIEVAL` model client, and returns generated
prose separately from bounded canonical source excerpts. It does not scan,
ingest, upload, or reindex files; indexing remains an explicit local CLI
operation. Document text is untrusted and has no memory, learning, task, or
action authority. No answer/query is persisted and no general CodeRAG or
Conversation route is added. Phase 18A's disposable synthetic-corpus Astra
qualification verified navigation/reload, grounded evidence, no-evidence
abstention, and lack of authority effects; the integrated offline scenario
remains separate.

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
create/resume/cancel state and may bind exactly one canonical task-history record
by task ID and exact plan token. After explicit resume, it may reserve one
plan-only task for a configured repository ID and delegate plan generation to the
existing native gateway/planner; planner failure preserves that task linkage for
retry. It delegates no execution authority itself; cancellation of a bound
objective delegates to that task's existing history cancellation boundary.
Objective reads project the current task-history state, and the cinematic UI
receives only a bounded objective projection with create/resume/guarded-plan/
cancel controls, without becoming a second lifecycle authority. Any objective
execution must pass through the existing plan, approval, isolation, validation,
rollback, and audit chain.

Executor terminal handling is also task-history authority: after a result is
persisted, code-agent records `rolled_back`, `cancelled`, or successful
review/finalization before a failed isolated worktree can be cleaned. Execution
artifacts may name their bound isolated worktree, while the canonical task stays
bound to its canonical checkout; import accepts this only when task ID, exact
plan hash, and starting commit match the existing task. A cleaned worktree or
artifact alone never implies completion.

For a task awaiting approval, the projection includes a bounded, task-token-
verified review summary. It is strictly read-only and does not expose artifact
paths, write APIs, approval, or execution.

Objective planning runs outside the presentation event loop with one active
operation per process. Health, status, and cooperative task cancellation remain
responsive during inference; competing plan requests receive 409.
Objective lifecycle and plan-binding writes compare the observed state/task/token
atomically in SQLite, rejecting stale transitions instead of reviving
cancellation or replacing another binding.
Objective task IDs and repositories are reserved before canonical task creation;
the gateway reuses history's transactional idempotency claims to materialize the
same plan-only task after interruption. Retry/cancel recover the reservation,
and a ready canonical plan can bind without regenerating it. This does not add
cross-process inference scheduling or execution authority.
The existing gateway execution adapter now selects exact approved-plan reuse:
history validates canonical state and artifact bytes/identity, and code-agent
checks repository HEAD before entering its unchanged isolated execution stack.
It does not regenerate a new plan under an earlier approval token.
The native objective dispatch route delegates only an exact approved binding to
that adapter, guarded by gateway enablement/bearer digest, execution scope, and
rate policy. Absent configuration fails closed; the cinematic panel does not yet
expose execution or credential management. Task history owns execution/outcomes.
For roadmap implementation and controlled local qualification, Codex may
provision a securely generated local-only bearer credential and the least scope
needed in protected non-repository service state. That operational authority is
not a runtime shortcut: the credential is never logged or committed, is
revocable by disabling gateway configuration/removing the local secret, and
still traverses bearer checks, exact-plan approval, isolation, validation,
rollback, audit, and Git controls.
The cinematic objective surface separately shows the newest active objective and
the newest terminal canonical task result. Polling refreshes this bounded
projection without copying or changing task lifecycle state; cancellation never
claims a different canonical task outcome.
Terminal evidence may include a bounded canonical outcome/failure/final-decision
string, while nonterminal details stay absent.
Task-history schema v6 makes planning admission durable across gateway processes:
one task has one model-generation claim, released on normal completion/failure
or recoverable after a one-hour interruption lease. It does not add planning or
execution authority.
Task-history schema v7 also makes execution dispatch admission durable across
gateway processes. The claim follows the executor future until completion;
isolation remains the final mutation owner and exact approval is unchanged.
Executor admission serializes duplicate submissions and shutdown per process,
reusing in-flight handles and reporting queued cancellation explicitly. This
does not replace isolation's cross-process worktree ownership controls.

Task-history SQLite schema v5 keeps plan-attachment metrics additive and checks
their physical columns at initialization. A stale schema therefore fails before
planning rather than after a local model has generated an artifact.

Stage 18 adds a separate local proactive event journal, not a second gateway or
executor. Typed watches observe local system, service, repository, filesystem,
task, schedule, and explicitly configured external sources. They are
read-only/change-only where applicable, durable, relevance-filtered,
deduplicated, rate-limited, and acknowledgeable. The sole Stage 18 permission
is notification: no watch can plan, approve, execute, mutate Git/files, drive
the desktop, or grant authority. See `docs/architecture/proactive-events.md`
and ADR 0021.

Astra Phase 5 adds a typed Notifications projection over that same journal:
notification rows are joined to safe event kind/source and watch-label fields;
the owner can acknowledge through the canonical timestamp transition. A
read-only watch projection separates persisted enabled state, observer
availability, and live worker state. It exposes no watch authoring, schedule
management, action proposal, approval, or execution route. Arbitrary event
metadata stays backend-only. The runtime notification event remains ephemeral
session telemetry, separate from durable Memory and conversational history.

Astra Phase 6 adds a typed, read-only Perception projection over the existing
Perception services. Capture rows expose bounded metadata, provenance, and
expiry only; pixels and local paths stay private. Capture, OCR, deterministic
OCR-derived UI-state hints, optional cached local visual labels, and active
window status are explicit backend requests. OCR and inference results remain
ephemeral in the view and are not written to Memory, Research, or normal
Conversation context. Owner-selected image ingestion remains CLI-only. GNOME
capture privacy denial and unavailable active-window status are presented as
such; no fallback or desktop/action authority is added. Perception stays
independent from the governed Stage 16 desktop-control service.

Stage 19 adds a typed, prompt-only local role router over the existing sole Qwen
client. Conversation, planning, coding, debugging, testing, review, retrieval,
vision, reasoning, and security roles are sequential contexts, never privileged
agents. They cannot select another model or bypass task, tool, approval,
validation, isolation, Git, desktop, or audit policy. See
`docs/architecture/role-orchestration.md` and ADR 0022.

Career Forge now selects sequential prompt-only specialists on that same router:
Teacher, Coach, Pair Programmer, Reviewer, Debugger, Interviewer, and Curriculum
Designer map to the mission tutor mode chosen by the owner. Astra exposes the
choice in LEARN; the shared interaction lease still serializes local-Qwen use,
and generated help is recorded at the explicitly selected assistance level.
Roles gain no Learner Twin, tool, execution, desktop, or mastery authority.

Career Forge curriculum research is a read-only projection over Friday's
existing local provenance ledger. MAP compares canonical competency titles with
explicit owner-collected, versioned sources and shows evidence/gap counts; source
content remains in the research boundary. Coverage is advisory and cannot edit
the competency graph, reorder missions, create evidence, or change mastery.

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
service operations retain all memory mutation authority. The canonical memory
SQLite also stores an explicit default-off owner setting for bounded,
owner-declared preference adaptation in normal text Conversation only. Applied
records remain untrusted style guidance below the current turn and all system,
safety, capability, and approval policy; no passive habit inference or memory
write occurs. See `docs/architecture/memory.md` and ADR 0027.

Astra Phase 14 adds a deterministic, read-only explanation projection over
`TaskHistoryService` and explicitly linked `ObjectiveService` records. Exact-ID
GET routes and the conversation adapter share typed allowlisted explanation
DTOs; no Qwen generation or action authority is involved. Plan, approval,
execution, outcome, objective state, and recovery remain distinct facts, and
timeline order does not imply causality. See
`docs/architecture/task-history.md` and ADR 0028.

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

### Astra Phase 7 — System / capability projection

Astra's Local intelligence view is a read-only presentation of the composition-
owned `FridayCapabilityRegistry` plus existing health/status routes. The typed
client preserves canonical capability maturity, configured, permissioned,
healthy, owner-route, and limitation fields. It does not infer host availability
or action authority from those descriptive fields. Conversation and Astra read
the same backend registry; no second frontend capability interpretation is
introduced.

Health remains endpoint-specific: `/health` reports the presentation API only;
voice health/latency, interaction ownership, bounded session metadata,
proactive worker/watch state, and active-window status retain their own
independent responses and failures. Astra omits session text/identity, window
title/application identity, worker PIDs, error details, and local paths. It has
no browser-persisted capability/health state and no diagnostic or service
mutation route. Development Vite proxies `/api` and `/health` to the selected
candidate API. Capability visibility never grants desktop control, objective
execution, approval, learner, Memory, or other action authority.

### Astra Phase 8 — History / Recovery projection

Astra History is a read-only composition over existing service-owned records,
not a new unified persistence authority. The typed client loads objective/task
activity, objective state/outcome, proactive notification history, and desktop
action audit independently. Failed sources remain distinct from genuinely
empty sources; records preserve their service provenance and timestamps do not
assert causality across stores. Desktop target identifiers are omitted because
the canonical field may contain a private path. Task-bound recovery/checkpoint
inspection remains internal/CLI-only; no owner-routable recovery projection is
claimed. Runtime conversation events remain bounded in-memory session state,
not a durable transcript. Astra adds no approval, execution, retry, rollback,
restore, desktop, shell, file, Git, or learner authority.

### Astra Phase 9 — Approval / Action

Astra Attention is a typed read/write presentation over the existing
`DesktopControlService` ledger. It loads `GET /api/v1/desktop/actions`, shows
canonical lifecycle states and bounded decision-safe application targets, and
uses only the existing per-action approve and execute routes. Review is
read-only; approval and execution are separate explicit owner transitions;
each successful transition is followed by a canonical re-fetch. Attention has
no local approval state, decline lifecycle, optimistic success, free-form
proposal creator, or retry behavior. Proposal creation remains backend/internal
until a safe target-discovery contract exists. History reads the same action
ledger and continues to omit target identifiers.

Task exact-plan approval remains a distinct Gateway boundary. Astra has no
secure owner credential/session adapter for task approval or objective
execution, so it exposes no active task approval or execution control. Desktop
approval grants only the exact persisted action and never causes execution or
grants other capability authority.

For `launch_app`, the persisted allowlisted desktop ID remains the reviewed and
audited identity. At execution, the service resolves only that exact basename
in configured system XDG `applications` directories for `gio launch`; it does
not inspect `XDG_DATA_HOME`, recurse, accept caller paths, choose between
duplicate matches, or follow an alias to a differently named entry. URI, file,
and accessibility command semantics are unchanged. Physical qualification
proved one isolated `launch_app` to
`org.gnome.Calculator.desktop` through proposal, review, approval, separate
execution, navigation/reload, and History reconstruction. The stale attempt
remains `expired` and the first physical attempt remains `failed` in canonical
audit history. Other desktop action classes are not thereby qualified.

### Astra Phase 10 — Long-running Objective Progress

`GET /api/v1/objectives/{objective_id}/progress` composes objective state from
`ObjectiveService`, task status/outcome and a bounded timeline from canonical
`TaskHistoryService`, and linked-task recovery classification from only that
task's isolation metadata and recovery inspection. Missing isolation metadata
is reported as unknown rather than healthy. Stable status mappings produce
fixed user-facing narratives; objective state never overwrites task state.
The typed Objectives panel renders those identities and facts and includes
only already-redacted task outcome fields. This route and panel are read-only:
they do not approve, execute, cancel, retry, rollback, restore, expose
credentials, or reveal recovery paths. Recovery and isolation stay owned by
their existing services. Codex-performed candidate navigation and reload
reconstructed the canonical pending-approval projection; terminal task UI
states remain deterministically tested but were not present in that candidate.


### Astra Phase 11 — Proactive Watches / Notifications

The existing typed `NotificationsWorkspace` is qualified as a read-only
notification and configured-watch surface, with the existing canonical
notification acknowledgement as its sole mutation. Event occurrence and
notification creation times render independently; absent event time is shown as
unavailable. The view reports enabled state, observer attachment/availability,
notify-only permission, configured interval/mechanism, and worker liveness
without inferring observer health from attachment. A `schedule` source denotes
the due-item observer; the separate watch `schedule` boolean means the engine
may emit an interval-triggered event and does not represent a calendar. No
watch-authoring, watch-mutation, calendar, or action routes are added.

### Astra Phase 12 — Research answer generation

The Research workspace has a separate explicit answer operation over
server-loaded canonical local source records. The backend bounds the evidence
context and invokes the existing local `Role.REASONING` client; browser input
cannot replace source text or prompts. Empty evidence skips inference. The
response labels generated prose as an interpretation, includes canonical
source identity/hash metadata, and makes no citation-validation claim. This
route bypasses normal conversation history, memory and learning hooks, web
fetching, and action tools; it does not persist generated prose.

### Astra Phase 16 — unified task recovery read model

`TaskRecoveryProjectionService` composes existing task history, admission claim
timestamps, Phase 15 rollback operations, exact objective links, isolation
metadata, execution artifact records, and trustworthy process-local worker
observation for an exact task. It is a presentation read model, not another
authority. History, Objectives progress, and deterministic Phase 14 explanation
share the same classification. API restart does not infer a still-running
worker or mutate an interrupted task. The existing exact-identity,
digest-idempotent explicit artifact-import path remains unchanged; startup and
recovery reads do not trigger reconciliation. Row 56 is bounded to truthful
owner-visible inspection and adds no universal resume, retry, cleanup, or
rollback authority.

## Dynamic Learning Paths owner integration (DLP-4 accepted and published)

DLP persists curriculum versions and the owner's selected path in its separate
local SQLite authority. Conversation recognition is deterministic for explicit
path operations; validated local `CURRICULUM_DESIGNER` output remains proposal
only. Learn renders typed DLP list/detail/sequence responses. Career Forge owns
all assessment, attempts, evidence, mastery, retention, review, and reinforcement
state. DLP-3's bounded owner integration is accepted at
`4cf22b1fc645f19ba5a64123b342a4f78442a49f`. DLP-4 adds Career Forge-owned
dynamic subjects bound to immutable path/node contracts; explicit sessions,
local assessment, evidence, mastery, retention, and sequence projection reuse
the existing Career Forge learner authority. Arbitrary nodes without a
registered dynamic subject remain unverified and cannot unlock dependents.
DLP-4 was accepted as `4a420217bcddca42aa2655c3379b196729a43432` and its final
published recovery pointer is `7fcb926a2625cf9e30aad0037fd38a5df6d2afcc`.
Learn review and reinforcement answer flows reuse Career Forge review, mission,
assessment, and evidence authority; dynamic DLP subjects retain their subject
binding across reinforcement and restart. Owner final visual acceptance remains
deferred, and rows 60/61 remain PARTIAL.

Project/capstone milestones now compose three existing authorities with a
dedicated Projects instance service. DLP's immutable version determines the
assignment rationale and exact prerequisite gate; Projects stores instance
state and references to Objectives/TaskHistory/Career Forge; Career Forge
stores explicit explanation attempts and project-derived evidence. Project
work starts through ObjectiveService and the existing exact-plan approval,
isolated execution, validation, review, and recovery flow. A validated task
alone creates no learning evidence, and project completion never advances
mastery. The durable data model and evaluator boundary are specified in
`docs/architecture/projects.md` and ADR 0034.
