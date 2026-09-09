# ADR 0013: Strict persistent wake cascade and user-session voice deployment

- Status: accepted for Stage 11

## Context

Friday needs low-latency always-on wake recognition compatible with the logged-in PipeWire session. Energy-only segmentation proved unreliable, repeated ASR startup was wasteful, and unqualified barge-in could mistake Piper echo for a human interruption.

## Decision

Use exact `Hey Friday`, strict normalized matching, Silero VAD, Parakeet Full primary wake ASR, Moonshine Medium fallback only on primary miss, persistent fail-closed workers, one always-on wake stream, pause/resume around conversational turns, and `systemd --user` for persistent deployment. Production natural-language barge-in uses Friday-owned ephemeral PipeWire WebRTC AEC with `monitor.mode=true`: the default physical speaker monitor is the echo reference and `friday_aec_source` is explicitly captured by the trusted interruption monitor. Do not change global PipeWire defaults or move wake recognition away from the normal raw microphone path.

## Consequences

Wake latency avoids repeated model startup, fallback can recover primary misses without weakening phrase policy, Silero produces reliable completed utterances, stale worker responses cannot contaminate later requests, and Friday remains persistent in the user's audio session. Qualified WebRTC AEC now suppresses speaker/Piper echo sufficiently for natural interruption while preserving trusted human speech, so production natural-language barge-in is accepted.

For always-on wake capture, pause/stop now use stream retirement as the cancellation boundary: the lock-protected current-stream reference is cleared before close wakes any blocked read. EOF/capture errors from the retired stream are cancellation; failures from the still-current stream remain errors and fail closed. Pause keeps the loop alive and quiescent, resume reacquires a fresh stream, and stop terminates cleanly. This behavior is deterministic-test qualified and production restart/live-turn qualified. Stage 12 continues with the remaining microphone/runtime lifecycle hardening.

## Stage 12C-A — inline wake command semantics

Decision: a non-empty strict wake remainder is treated as already-recognized user
text and must not be retranscribed from the same wake audio.

Rationale:
- wake ASR has already recognized the inline command;
- repeating Whisper adds latency and can change the command;
- the wake remainder can enter the existing conversation path while retaining
  the authoritative runtime state machine by passing through a synthetic
  `TRANSCRIBING` state/event boundary.

Non-goals for this decision:
- bare-wake follow-up capture;
- generic current-time/tool access;
- Markdown-to-speech normalization.

Production qualification confirmed the inline path executes without
`WHISPER_BEGIN`, completes speech playback, and returns microphone ownership to
the always-on wake capture.

## Stage 12C-B — fresh follow-up capture decision

Decision: a bare accepted wake and its command are distinct utterances. The wake
utterance authorizes the turn but is never reused as main-Whisper conversation
input. Friday pauses always-on wake ownership and captures at most one fresh
raw-microphone utterance through a bounded one-shot boundary.

The boundary uses the existing wake PCM configuration and a fresh Silero/VAD
segmenter per call. Timeout is 8 seconds. Timeout or capture failure closes the
pending LISTENING state to IDLE before wake resumes. Missing follow-up wiring
fails closed rather than restoring the rejected wake-audio reuse path.

This preserves strict wake semantics, prevents duplicate transcription, keeps
AEC isolated to barge-in, and makes repeated bare-wake turns lifecycle-safe.

## Stage 12D — exact stop-command decision

Decision: recognize only normalized exact `stop`, `friday stop`, and
`hey friday stop` at the voice conversation boundary. Once text reaches the
existing TRANSCRIBING state, an exact stop transitions directly to IDLE and
bypasses conversation history, LLM inference, and acknowledgement speech.

For trusted AEC barge-in, the established AEC/Silero path remains authoritative
for stopping playback and capturing speech. Whisper then supplies text to the
same exact classifier. Do not introduce fuzzy matching, suffix matching,
context-specific ASR-error aliases, or treat negated/longer phrases as stop.

This keeps stop semantics narrow and deterministic while preserving natural
conversation for `stop loss`, `I didn't stop`, and other noncommands. Physical
qualification passed inline stop, active-speech stop, and the stop-loss negative
control after clipped host audio levels were corrected. Machine audio gain is an
operational prerequisite, not an application policy or semantic workaround.

## Stage 12E decision — recover at the capture ownership boundary

Decision: supervise retryable microphone/wake-worker
failures in the existing managed capture thread. Reuse loaded models and the
accepted AEC graph instead of restarting the whole service. Retire and close
failed streams, reset VAD state, discard failed utterances, and retry at a capped
rate; worker protocol invalidation stays authoritative and no failed request is
replayed. Two-second raw chunk deadlines cover stopped recorder processes.
Shutdown is terminal and interrupts backoff; unclassified failures remain failed.
Keep voice health separate from HTTP liveness. This confines recovery ownership
and avoids introducing a second competing microphone supervisor or weakening
strict wake/stop policy. Deterministic, host recorder fault, worker replacement,
and physical wake qualification passed, so this decision is accepted.

Managed voice cleanup begins at Uvicorn's first exit signal, before HTTP server
shutdown. The outer `finally` remains as an idempotent guarantee. This prevents
recorder unwind from being retried between SIGTERM and application teardown.

## Stage 12F decision — one interaction owner

Use one fail-fast lease coordinator across wake voice turns and presentation HTTP
streams. Admit before any runtime event, keep the active interaction, and never
preempt or queue. Voice makes overlapping HTTP return 409. HTTP pauses wake for
its stream, so presentation ownership suppresses an in-flight wake. Resume
microphone ownership before release and expose read-only ownership state.

Disconnect cleanup distinguishes an unstarted stream from a synchronous model
read already in progress: the former releases immediately; the latter retains the
lease until the iterator reaches a safe cancellation boundary. This prevents
unsafe raw-microphone reuse and leaves the runtime `CANCELLED` rather than stuck
in `THINKING`. Physical bidirectional qualification passed.

If trusted barge-in has already stopped playback but cannot produce a completed
bounded utterance, do not replay or transcribe partial audio. Record the
interruption and return to IDLE. This is fail-closed recovery, not permission to
invent a conversational continuation.

## Stage 12G decision — bounded playback-lifetime barge monitoring

Do not use a short pre-playback arm deadline as an interruption failure. Piper
may need several seconds to produce first audio for a long response. Wait up to
30 seconds to arm, then retain the existing bounded capture pass and re-arm only
its explicit timeout while playback remains active. Preserve a failed playback
stop as an error. Emit only outcome/timing/pass/VAD summary metadata. Live late
exact-stop qualification passed with a 3.3 ms playback stop and no runtime error.

## Stage 12I decision — sentence-gated incremental Piper speech

Use model streaming as the only text producer. A deterministic chunker hands
complete sentences to a bounded ordered queue, consumed serially by the already
authoritative Piper/player path. This begins audible synthesis before completion
without parallel Piper workers, reordering, text loss, or unbounded buffering.
SPEAKING is a valid concurrent lifecycle state at model completion; cancellation,
barge-in and explicit stop retain their existing ownership and failure boundaries.

## Stage 12J decision — presentation-only TTS text normalization

Normalize speech text immediately before Piper synthesis, after model streaming
and conversation events have retained the original text. The deterministic local
normalizer removes common Markdown presentation syntax and makes underscore
separators readable, while retaining the meaningful written words in links,
images, and inline code. This avoids modifying the model transcript, conversation
history, streaming contract, or Piper/player ownership.

## Stage 12K decision — event-derived cinematic voice outcomes

Keep `FridayRuntimeState` authoritative for the client while deriving a separate
presentation-only voice outcome from existing runtime events. Speech start,
completion, and interruption must not mutate lifecycle state or ownership. Keep
the interruption outcome visible through the immediate barge-in listening
handoff, then clear it at the next user turn so a completed/old interruption is
not represented as current activity.

## Stage 12L decision — bounded voice-stage telemetry

Keep the production voice-stage trace in a bounded in-memory rolling buffer.
Recent ordered stages remain available for lifecycle diagnostics, while the
always-on service cannot grow memory indefinitely during normal operation.
Continue emitting the existing journal records; the bounded in-process trace is
not a replacement for durable operational logs.

## Stage 12M decision — bounded Piper protocol handoff

Bound the persistent Piper worker reader's in-process event queue and make its
backpressure cancellation-aware. A malformed/flooding worker must not accumulate
unbounded decoded audio/events, and a service shutdown must retire a reader
waiting on a saturated queue. Preserve ordered event delivery and the existing
single Piper-process ownership.
