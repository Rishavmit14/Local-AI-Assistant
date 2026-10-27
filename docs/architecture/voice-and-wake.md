# Friday Voice and Wake Architecture

## Boundary

Voice is an input/output surface and has no privileged path around Friday's native API/event/policy boundary.

## Accepted conversational path

`microphone -> Whisper STT -> local Qwen streaming -> selected local TTS -> PipeWire playback`


When whisper.cpp is configured for CUDA and returns a nonzero result whose
stderr explicitly identifies CUDA out-of-memory, Friday removes any partial
transcript output and retries that same utterance once with `--no-gpu`. Other
CLI errors, timeouts, and CPU fallback failures remain fail-closed. This keeps
Whisper local while allowing it to yield VRAM to the general-purpose model.

## Owner-machine TTS selection

Piper remains the fail-safe default. An explicit
`FRIDAY_TTS_BACKEND=pocket` selects Friday's persistent Pocket worker and its
Anna voice while retaining the same bounded framed-PCM interface and PipeWire
playback path. The Pocket worker runs from the owner-managed local virtual
environment, uses the existing local Hugging Face cache in offline mode, and
does not download models during service startup. The protected machine
configuration selects Pocket; the isolated voice-action candidate carries
that selector forward. The selected backend is reported by local voice health.

Interrupts propagate through the streaming text queue, TTS iterator, and
playback worker. When Stop or barge-in wins, Friday closes the active iterators
and prevents another model chunk from being requested, while retaining text
already produced. The exact stop classifier and wake ownership boundaries stay
unchanged.

Voice learning reuses the same deterministic intent router after a barge-in.
Clear requests such as `Can I repeat that?` and `Please explain the lesson
again.` map to the existing `REPEAT` action. The transcript `Can I have a beat
that?` is ambiguous without retained audio and is not treated as a repeat
alias. The Stage 32 operator validates the production repeat route and its
correlated lesson response rather than requiring Whisper to preserve the
displayed wording exactly. This does not alter wake matching, AEC, VAD
thresholds, or Stop handling.

The physical Stop qualification binds the finalized `Friday, stop.` transcript
and explicit stop transition to an interruption of the currently active
playback turn. A normal assistant response between that interruption and the
stop transition fails the gate; a later Stop transcript cannot be combined
with an unrelated earlier interruption. The listener-start event in the final
physical run carried the interrupted turn ID, then the same runtime session
recorded utterance completion, final `Friday, stop.` ASR, and the explicit Stop
transition in order. Candidate logs showed TTS cancellation and playback
completion; Qwen had already completed generation. The distinct five-second
quiet gate passed with Owner confirmation and no stale speech before recovery
wake. The evidence contains no separate queue-invalidation event, so the claim
is limited to source cancellation plus externally verified silence.

## Session 1 Milestone A — direct voice open actions (candidate)

The normal microphone path now marks voice-origin conversation turns. A
deterministic intent router can intercept a direct open/focus request before
memory retrieval, context assembly, or Qwen and send it through the existing
Stage 26 computer-agency runner. Non-voice conversation remains model-only.
The action returns an immediate spoken acknowledgement, then a spoken result
based on the durable task's verified terminal state.

This route requires the configured private local Owner grant and restored GNOME
permission. It handles exact installed-app names from XDG metadata, generic
website names or explicit safe URLs, and Friday's loopback UI/internal routes
from `LOCAL_AI_OWNER_UI_ORIGIN`. That setting is the canonical UI origin and
is aligned with the Daybreak server-only bridge and
`LOCAL_AI_PROJECT_EXECUTION_ALLOWED_ORIGINS`. Application launch uses the
canonical XDG desktop ID through fixed `/usr/bin/gtk-launch` arguments. The
verifier scopes AT-SPI traversal to registered desktop-ID, executable, D-Bus,
and `StartupWMClass` identities, then recognizes active/focused or newly
visible matching app elements. URI dispatch uses a fixed asynchronous `gio
open` child so the browser address can be checked during handoff. The route
does not ask Qwen to choose a URL or target. Stop still reaches the Stage 26
durable cancellation hook. Action latency stages distinguish intent selection,
dispatch, verification/failure, final response readiness, fast-path completion,
and completed voice playback. Inline wake commands use the completed captured
utterance boundary as their monotonic latency origin. These telemetry records
retain stage timings only, not transcripts or audio; they remain in-memory and
have no task ID or wall-clock timestamp for durable turn-to-action correlation.

Owner reports YouTube opened in Chrome, though its earlier task remains
`in_doubt`; the latest Files probe opened and its task verified. The first
Files retest lacked a structured latency row; a subsequent retest now records
one from the captured inline-wake utterance boundary. That trace remains
in-memory and does not carry a durable task ID. Friday UI
showed Daybreak at `:5193` and spoke “I'm opening Friday's User interface,” but
its old URI task is `in_doubt` because `gio open` timed out. Calculator opened
physically but its old task ended `postcondition_failed`; its three stored
observations each had 187 elements and did not retain identities or actor exit
status. The updated candidate stores actor return code and a content-free
verification category/count/result observation, but not stderr or accessible
screen text. The latest Stop was recognized silently at 16:06:08 IST; capture
health showed wake listening. There is no computer task/action or latency row
for explicit Stop. The app-scoped verifier, nonblocking URI dispatch, and
evidence fields pass focused tests; fresh Files, Daybreak, and Calculator
probes are required. The candidate remains unqualified.

## Stage 22 Slices 5–7 — measured latency attribution and handoff repair

At the Stage 22 decision, Piper was the accepted production TTS. The current
owner-machine selection is documented above. Kokoro CPU was evaluated locally with
the current Qwen configuration and three female candidates; the owner selected
Bella for a bounded comparison, then rejected Kokoro for production after a real
Friday trial because response start was materially slower and speech had
unnatural long pauses. GPU Kokoro was not attempted: Qwen already occupied about
7.18 of the GTX 1070's 8 GiB VRAM, leaving no safe whole-Friday headroom.

The runtime retains a bounded, in-memory, content-free latency trace and
read-only `/api/v1/voice/latency` projection. It records endpoint finalization,
ASR finalization, conversation routing, Career Forge/memory/capability work,
prompt assembly, Qwen request dispatch/acceptance/first token and returned
usage, first stable speakable chunk, TTS first audio, and first PCM written to
PipeWire. It retains only monotonic durations and numeric character/token/cache
metrics, never raw audio, a transcript, a prompt, or memory content.

Slice 6 confirmed that the installed one-slot llama.cpp runtime already enabled
prompt caching. The bottleneck was volatile material preceding the large static
capability projection, not a model-server queue or a new model requirement.
The immutable identity/evidence/capability prefix now comes first; cognitive,
session, memory, Career Forge, and route material remain present afterwards with
their existing labels and priority semantics. In bounded local comparisons,
warm normal/follow-up prefill fell from 639–1,394 newly evaluated tokens
(5.60–11.88 s) to 260–305 (2.06–3.09 s Qwen TTFT), with LCP similarity rising
from 0.240–0.413 to 0.902–0.970. The current Qwen configuration, Piper, AEC,
barge-in, and exact stop were unchanged. A fully grounded teaching turn remains
correctly heavier; it is not compacted away for latency.

Slice 7 extends the same privacy-safe trace through completed speech chunk,
queue/worker admission, Piper request and first audio, `pw-play` startup, and
first PCM write. It found no material queue, Piper, process-start, AEC, or
sentence-gating delay after the first completed speakable chunk. Instead, the
old player attempted to write a complete sentence-sized PCM buffer before its
first-PCM callback; pipe backpressure made that blocking operation take
0.85–10.83 s in four of five baseline turns (54 ms in the fifth). The player
now writes and flushes an 8 KiB 16-bit PCM prefix first, then writes the exact
unchanged remainder contiguously. Qualified post-change turns measured
first-speakable to first PCM at 54–619 ms (median 388 ms). This is a scheduling
repair, not a TTS/model change; Piper naturalness and every accepted AEC,
barge-in, exact-stop, and wake lifecycle boundary remain intact.

## Stage 22 Slice 8 — pre-Qwen prompt-assembly classification

The bounded trace now has content-free begin/complete boundaries for total
assembly, route classification, Career Forge and active-session projection,
SQLite/lexical/semantic durable-memory retrieval, capability projection,
cognitive policy, and serialization. The historical 27.5-second pre-Qwen event
was not reproduced: cold assembly was 16.9 ms; the eight-turn warm/mixed corpus
median was 2.23 ms and p95/max 128.4 ms, with a 127.2 ms Career Forge projection
as the slowest substage. Isolated first-use local BGE initialization took 5.15 s
(34.2 ms warm), but cannot explain the historical empty-memory event. Friday
therefore retains diagnostic boundaries without speculative warmup or context
omission. Qwen prefill and correctly grounded teaching remain the latency floor.

## Accepted always-on wake path

Canonical phrase: `Hey Friday`. Wake uses 16 kHz mono PCM, Silero VAD, Parakeet Full primary ASR, and Moonshine Medium only after a primary miss. Both use the same strict matcher.

The matcher uses Unicode NFKC, case folding, punctuation-to-space normalization, and collapsed whitespace. It accepts exact `hey friday` and transcripts beginning `hey friday ` while preserving the remainder; it does not intentionally accept fuzzy aliases.

Parakeet and Moonshine run as persistent fail-closed subprocess workers. Request/protocol failures invalidate the worker before reuse so stale results cannot satisfy later requests.

Stage 12 accepted a one-turn wake lifecycle. Stage 22 Slice 1 extends it without replacing its components: on wake, capture pauses; a bounded active session runs the initial and sequential fresh follow-up turns; exact explicit stop, a deliberate close, failure, or the configured idle deadline clears that session and resumes wake capture.

### Candidate Probe 5 capture/VAD boundary observation (2026-10-10)

The production wake bootstrap requests ALSA `default` PCM as S16LE, 16 kHz,
mono, in 32 ms (512-sample) chunks. On the current owner session, PipeWire's
built-in HDA Intel PCH / Realtek ALC898 `Internal Microphone` source runs at
S32LE, 48 kHz, stereo and converts to the negotiated Friday stream format. The
source is unmuted at 0.50 volume; the selected physical source is the built-in
mic, and whether it matches the Owner's intended mic is not yet confirmed.

Wake uses the local Silero ONNX VAD with a default probability threshold of
0.50. Each signed little-endian int16 frame is normalized to float32. The
segmenter requires 3 consecutive VAD-positive frames (96 ms) to start, 6
positive frames (192 ms) to retain an utterance, and 19 silent frames (608 ms)
to finish it. The energy thresholds in `VoiceVadConfig` apply to the alternate
`PcmEnergyVad`; they do not decide speech in the active Silero path. Capture
health exposes frame and VAD counts but not per-frame RMS or Silero probability.
The Owner later confirmed no required command was spoken during the 2026-10-09
window; preserve its zero-VAD counters as an unused request window, not evidence
of an audio defect. In a later coordinated 2026-10-10 attempt, a real wake was
accepted, an utterance reached Whisper, and ASR was classified as the expected
folder command. This demonstrates the live capture/VAD/wake/ASR path handled
that physical utterance. The task failed before target binding. Because that
process's runner source and gate state were not captured, the earlier claim
that the candidate gate was absent from the imported runtime was unsupported.
No audio or raw transcript is saved, and no audio settings or thresholds were
changed.

The later physical Probe 5 run accepted wake, recorded one utterance and 22
VAD speech frames, and recognized the expected folder-command class. Friday
completed the final speech segment (event sequence 21) before the durable
computer-task completion event (sequence 23). The watcher misclassified this
valid ordering as `final_response_not_played`; the Owner confirmed hearing the
successful result. No audio or raw transcript was retained.

## Stage 22 Slice 1 — bounded active voice session

`FridayWakeVoiceOrchestrator` remains the exclusive owner of wake/capture lifecycle. After a completed turn it opens one fresh raw-microphone follow-up capture at a time (default idle allowance: 60 seconds, configurable from 15 to 300 seconds). Wake remains paused throughout the active session, so the design does not introduce competing microphone readers. The session controller retains at most 16 turns / 12,000 characters for conversational grounding and clears them on close; it does not persist audio or a transcript.

Exact `stop`, `friday stop`, and `hey friday stop` retain their accepted meaning. Trusted barge-in still stops Piper before its utterance becomes the next turn. Only a classifier-confirmed explicit stop closes the session immediately; an ASR near miss remains ordinary conversation rather than weakening the stop boundary.

## Deployment

The accepted always-on runtime uses the user-session systemd unit `friday-local-ai.service` with `LOCAL_AI_WAKE_ENABLED=true` and `LOCAL_AI_WAKE_PHRASE=hey friday`. A sanitized example is tracked under `config/services/`. Both Friday user units are enabled for `default.target` login activation. The vision-cortex unit must not declare `After=default.target`, because it is itself wanted by that target and would create an ordering cycle through Friday. Friday declares `Wants=` and `After=friday-vision-cortex.service`; the cortex unit holds its start job until its loopback `/health` endpoint succeeds, bounded by `TimeoutStartSec=300s`. On 2026-10-08 both user services were stopped and only Friday was started. Systemd brought the cortex to HTTP-ready first; cortex and Friday health both returned `status: ok`, and voice capture reached `listening` with no active turn/error. Both units remained enabled for `default.target`, and `systemd-analyze --user verify` passed apart from an unrelated installed `spice-vdagent.service` warning. This exercises automatic dependency startup without manually starting the cortex. No fresh logout/login or reboot was performed, so activation after a new login remains unobserved.

## Barge-in

Production natural-language barge-in is accepted. The wake bootstrap owns an ephemeral `PipeWireAecSession` configured with PipeWire WebRTC AEC and `monitor.mode=true`. The physical/default speaker monitor becomes the echo reference, `friday_aec_source` is published as the cleaned microphone source, and `PipeWirePcmCapture` targets that exact source for `FridayBargeInMonitor`. No global default source/sink is changed and the normal always-on wake capture remains on the raw microphone.

The trusted interruption policy remains Silero >= 0.85 for at least 180 ms after the AEC arm delay. Temporary acoustic qualification measured 23.75 dB speaker-only reduction; human speech over speaker playback reached probability 1.0000 and remained above threshold for 1410 ms. A controlled production restart then proved the real graph, normal wake conversation, natural interruption while Piper was actively speaking, immediate playback stop, and continuation with the interruption utterance without another wake phrase.

The AEC session is lifecycle-owned by `FridayManagedWakeVoice` and closed with the other persistent voice resources. Exact explicit stop semantics were separately accepted in Stage 12D below.

## Wake capture pause/stop lifecycle

Blocked wake reads are now hardened. The loop keeps a stream-local handle for the active `read_chunk()` while `_stream` is the lock-protected ownership reference. `pause()`/`stop()` retire `_stream` before closing the underlying stream. When the blocked read wakes, EOF or `VoiceCaptureError` from a stream that is no longer current is treated as intentional cancellation rather than as microphone failure. Genuine failures from the still-current stream continue to raise `WakeCaptureError` and fail closed.

Pause semantics are deliberately quiescent rather than terminating: the wake loop stays alive while paused, releases microphone ownership, and resume reacquires a fresh stream. Stop releases the blocked stream and terminates the loop. Deterministic tests cover pause EOF, pause-induced capture error, stop EOF, stop-induced capture error, pause->immediate-resume fresh-stream reacquisition, and genuine unexpected failure. Production qualification completed two controlled restarts with no systemd stop timeout and a live wake/pause/voice/resume turn on the patched runtime.

## Stage 12O — bounded stability and actionable observability

The final Stage 12 qualification exercises actual wake/capture/workers rather
than adding a new voice path. Voice health projects a bounded `last_error_detail`
beside the existing error type; it is operational backend detail, never a voice
transcript. A real primary-worker failure demonstrated in-process recovery and
replacement. A controlled reload then completed a 12-minute clean listening
window and two full physical inline turns with no recovery/error state and stable
resident workers. Stage 12 is accepted; Stage 13 memory is next.

## Stage 12C-A — inline wake command semantics

For a wake transcript that strictly matches `Hey Friday` and has a non-empty
remainder, the wake detector's remainder is authoritative for the first
conversation turn. The orchestration layer pauses wake capture, calls the voice
service's direct-text boundary, and does **not** pass the original wake
`VoiceUtterance` through Whisper.

The direct-text boundary emits `VOICE_LISTENING_STOPPED`, enters
`TRANSCRIBING`, emits `VOICE_TRANSCRIPTION` with metadata identifying
`source=wake_remainder` and `transcriber=wake_asr`, then delegates to the normal
conversation service. This preserves existing runtime-state rules instead of
adding a direct `LISTENING -> THINKING` transition. The non-empty remainder is
the finalized command text used by that conversation turn; it has no separate
model path because the inline wake recognizer supplied it. Qualification may
accept this event only with its explicit source/transcriber pair, exact command
matching, and the gate's required downstream route evidence.

Bare-wake semantics are completed by Stage 12C-B below.

Before Piper synthesis, a deterministic presentation-only normalizer converts
common Markdown into spoken prose: headings/list markers, emphasis, strikeout,
inline code, links, images, and underscore separators. The original model text
continues unchanged through streamed and completed conversation events.

The presentation client separately projects the latest voice outcome from the
authoritative runtime event stream. Speech start/completion/interruption remain
event-derived visual signals, while runtime state remains the sole lifecycle
authority. An interrupted signal persists through the barge-in listening handoff
and clears when the next user turn begins.

`VoiceTurnTelemetry` retains a bounded rolling trace of the most recent 2,048
production stages. This preserves in-process ordering diagnostics without an
unbounded always-on memory cost; structured service-journal records remain the
external operational evidence.

The telemetry conversation wrapper forwards the inner conversation's
`last_voice_action_selected` flag and the post-playback success/failure
callbacks. A voice computer task becomes durably successful only after the
final result finishes playback; interrupted or failed playback keeps the task
incomplete. Each wrapper around the conversation must preserve these lifecycle
callbacks as well as the route-selection flag.

Piper's persistent worker reader uses a bounded 128-event protocol queue. It
applies backpressure during an abnormal event flood, while reader retirement
unblocks a full queue during shutdown so boundedness cannot create a lifecycle
leak.

The read-only voice-health endpoint includes liveness/PID projections for the
primary wake worker, fallback wake worker, and Piper worker. It remains an
operational observation boundary; worker start/stop ownership stays managed by
the production wake service.

## Stage 12C-B — bare wake fresh follow-up

A bare strict `Hey Friday` wake authorizes a turn but is not itself reused as
conversation input. Always-on wake capture pauses and
`FridayOneShotFollowUpCapture` opens a separate raw physical-microphone stream
using `WAKE_AUDIO_CONFIG`. Every call creates a fresh `SileroVad` and
`UtteranceSegmenter`; the wait is bounded to 8 seconds and the first completed
fresh utterance enters the existing main-Whisper path.

Wake stays paused while the fresh stream owns the microphone, and the stream is
closed before wake resumes. This path does not use `friday_aec_source`; AEC
remains exclusive to barge-in.

No-speech timeout and capture error close LISTENING back to IDLE, preventing a
stale runtime state from poisoning the next wake. If follow-up wiring is absent,
bare wake fails closed instead of retranscribing the wake utterance. Inline
commands remain direct-text. Follow-up lifecycle and wake-capture-error telemetry
are retained without logging complete wake ASR transcripts.

## Stage 12D — exact explicit stop

The voice conversation boundary recognizes normalized exact `stop`,
`friday stop`, and `hey friday stop`. Classification occurs in TRANSCRIBING and
transitions directly to IDLE before conversation history, LLM inference, or TTS.
The absence of acknowledgement speech is intentional.

Trusted barge-in continues to use the accepted AEC/Silero path to stop playback
and capture the interruption utterance. After Whisper, the same exact classifier
handles `Friday, stop`. Stop-like noncommands, negations, longer sentences, and
ASR mistakes remain ordinary conversation; no context-specific alias, fuzzy
matching, or suffix matching weakens the boundary.

Final physical qualification on the cleaned runtime passed inline stop, active
speech stop, and a stop-loss negative control. Active playback stopped about
3.2 ms after the trusted trigger, no second response was generated, and wake
capture resumed. Reliable transcription also required eliminating host-level
clipping; the qualified MSI used microphone volume 0.5 / hardware capture
+11.25 dB and speaker volume no higher than 1.0. These levels are operational
machine state, documented under `docs/operations/configuration.md`.

## Stage 12E — supervised capture recovery

The existing managed capture thread retries `WakeCaptureError`,
`WakeRuntimeError`, and OS transport failures after stream cleanup/reset. Retry
waits grow from one second to at most 30 seconds and reset after a run lasting
60 seconds. They are interruptible by shutdown. Unexpected programming errors or
an unsolicited normal loop return remain failed and observable. Failed audio is
never replayed, and the strict matcher is unchanged. Invalidated workers restart
on the next fresh utterance; idle-dead worker descriptors are closed first.

The raw wake/follow-up ALSA adapter uses a two-second deadline for the whole PCM
chunk, including partial reads. A stalled recorder is retired and terminated;
normal wake silence still supplies continuous PCM. Pause/stop retire nonempty
partial reads as well as EOF/errors. Late ASR results from retired streams are
discarded. The state lock serializes segmentation and reset without covering
blocking microphone reads or model inference. Stop is terminal even before run
entry, and a closed managed service cannot be restarted in place.

`/api/v1/voice/health` reports managed status (`running`, `recovering`, `failed`,
`stopped`), capture phase (`opening`, `listening`, `detecting`, `paused`, `stopped`),
thread liveness, turn activity, recovery count and last error type. A historical
error remains visible after recovery. HTTP `/health` reports only presentation
liveness. Host qualification terminated and stalled the real recorder: recovery
took 1.23 and 5.19 seconds without replacing Friday's service process. A stopped
idle Parakeet worker was recreated by a fresh physical inline wake; the command
completed through LLM/Piper and raw capture resumed. This does not claim general
AEC/Piper/model supervision or complete long-running voice stability.

A final restart gate found that Uvicorn previously began HTTP shutdown before
the CLI's `finally` closed voice capture, allowing recorder unwind to schedule a
false recovery. The published Stage 29 code's first exit signal now begins runtime
SSE shutdown, then closes voice ownership; cleanup is idempotent. The isolated
SSE process qualification does not restart voice capture or qualify task drain.

## Stage 12F — voice/presentation concurrency

Production construction shares one nonblocking coordinator between wake callbacks
and HTTP conversation admission. Voice claims before pausing the microphone or
mutating runtime. HTTP claims before returning its stream and pauses wake capture.
The losing side does no conversation work: HTTP receives 409 with the current
owner, while a wake during presentation ownership is suppressed. Completion,
failure, disconnect, and shutdown resume wake before release. The read-only
`/api/v1/interaction/state` exposes owner and monotonic generation.

An immediate client disconnect cleans an unstarted stream. A disconnect during a
synchronous model read leaves presentation ownership active until that read has
returned safely; the closed conversation becomes `CANCELLED`, then wake resumes.
This avoids both a lease leak and unsafe microphone reuse while synchronous model
work is still running.

Live qualification passed a physical `Hey Friday` count-to-100 voice turn while
the concurrent HTTP probe received 409, and a physical wake phrase during a long
presentation stream that yielded no reply or accepted wake. Both paths returned
to healthy listening. If a trusted barge-in stops playback but does not yield a
complete bounded utterance, Friday records an incomplete interruption and returns
to IDLE without forwarding partial audio to Whisper.

## Stage 12G — long-playback barge-in stability

Barge monitoring waits a bounded 30 seconds for Piper's first audible playback.
After an explicit monitor timeout it opens a new bounded pass while playback is
still active. Runtime speech events expose only outcome, pass count, elapsed time
and maximum speech probability. Real delayed playback and late exact-stop
qualification passed without a runtime error.

## Stage 12H — bare-wake ready acknowledgement

A bare wake now speaks a short local “I'm listening” cue while wake capture is
paused, returns to LISTENING, and only then opens fresh follow-up capture. This
keeps Friday's cue out of microphone input and preserves the one-shot boundary.

## Stage 12I — incremental speech

Voice response generation remains the single model-text producer. A deterministic
sentence chunker releases complete sentence-like text (or a bounded word split),
then an ordered bounded queue feeds sequential Piper requests through the existing
single playback process. The first ready sentence may move the authoritative
runtime from THINKING to SPEAKING while the model is still generating; model
completion emits its complete text without overwriting SPEAKING. The queue closes
without blocking shutdown and applies backpressure rather than dropping text.
Piper, playback, barge-in, explicit stop and wake-resume ownership remain at their
existing boundaries.

## Probe 4 — clarification and final-response playback (candidate)

The existing streaming speech path keeps the quick acknowledgment and every
subsequent complete sentence in one ordered queue and one PipeWire playback
call. `VOICE_SPEECH_COMPLETED` now reports the normalized text for all queued
segments, with their response roles, rather than only the first sentence.
Acknowledgment remains separate from a final result: a computer task is
recorded as completed only after the playback callback, while a clarification
is recorded as delivered only after that same callback returns. Failed playback
does not mark a clarification delivered or a computer task successful.

The physical Probe 4 trace showed the full clarification in the conversation
completion event and three completed Pocket/Anna synthesis requests in one
PipeWire call, while the speech-completion event text contained only the
acknowledgment. The Owner reported hearing only that acknowledgment. The trace
proves the event-text accounting defect, but not the acoustic content at the
speaker. Controlled Pocket/Anna playback through PipeWire completed both a
clarification and a terminal failure response after the acknowledgment; there
was no microphone capture or acoustic loopback in that check. Physical voice
qualification remains open.

## Session 2 — live screen questions

The normal microphone turn router classifies direct visual/deictic questions
(`what do you see`, `what is this`, `why is this failing`, `read this`) before
memory or generic capability context can answer them. A routed turn requests a
fresh local `ScreenContext` before primary Qwen generation; old chat, durable
memory and capability projections are excluded from that answer. App/window and
focused-control questions use fresh semantic evidence only. Pixel questions
capture a new frame and obtain local OCR plus the separate authenticated visual
cortex description, then pass bounded untrusted text evidence to primary Qwen.
If capture or the visual cortex is unavailable, Friday states the evidence gap
and does not fall back to an older screen or ask for an uploaded screenshot. The
existing incremental-speech path speaks a short acknowledgement before a slow
visual inference, then speaks Qwen's grounded answer. Screen observations do
not route into computer actions and do not alter the action/approval boundary.
Physical qualification confirmed fresh capture and changed-screen grounding on
two canvas-only charts and explanation of a visible terminal error. With the
512-token local visual service, the terminal turn took 102.3s from speech end
through playback completion (39.9s visual inference, 55.2s to Qwen's first
token). The latency is correct but not conversational; the live-vision route
must keep its honest acknowledgement/failure behavior while latency work
continues.


## Milestone C Probe 6 — Stop during an active computer task (candidate)

**Current physical result — Session 13: PASSED.** The post-READY physical retry
bound task `a623b966f5094866b124e794ddf4fea0` to its live voice request, verified
one create action for `/home/kumar-rishav/Downloads/copper groove`, and held
Files `open_location` at the dynamic boundary. Friday registered the real
wake-prefixed active-task Stop event, live wake counters advanced, and durable
cancellation was recorded 3.94 ms later as `cancelled_before_dispatch`. The task
ended `cancelled` with no navigation release, success event, or API/harness
cancellation. The STOP-NOW cue was closed after the window. The created directory and identity `[2050, 2514261,
1000]` are preserved. The persisted request/action used lowercase `copper
groove`, although GO specified `Copper Grove`; no audio or request text was copied
into probe evidence, and the normal task-history record retains its request
field, so the source is unknown. This proves Stop cancellation rather than
name fidelity. Cleanup restored capture listening and wake, Pocket/Anna, healthy
Qwen/vision, no active tasks, and an unloaded gate. Private correlation
and cleanup evidence are under
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe6-owner-confirmed-retry-20261011T075932Z/`.
Milestone C remains PARTIAL pending full acceptance and recovery gates.


An owner-bound voice computer task arms the existing strict wake capture before
its acknowledgment and keeps one capture reader through the final response.
While the task owns the voice interaction, only the exact busy wake remainder
`stop` routes to the active task's cancellation path. It does not wait for Qwen
planning. Stop durably requests cancellation, interrupts current speech when
needed, and prevents later task steps from reaching the actor. The separate
playback barge-in reader is not run concurrently against the same microphone;
normal barge-in remains covered when the active-task Stop reader does not own
capture. The active-task test uses the actual configured `hey friday` prefix,
so its spoken Stop phrase is “Hey Friday, stop.” Playback completion cannot
turn a cancelled task into success.

Focused regressions and controlled real-desktop cancellation passed. A later
live controlled task bound dynamically to its actual `Silver Birch` Downloads
child, verified the create action, reached the external arm acknowledgment,
and was cancelled through the authenticated local Owner API. Files navigation
was suppressed and the directory was preserved. This controlled cancellation
did not observe physical voice Stop.

The earlier 2026-10-11 physical window admitted a voice-origin task, but the
stored folder name differed from the qualification gate's then-fixed request.
The gate did not expose its Stop boundary; the task completed normally, and no
active-task Stop event or cancellation was recorded. The cause is unknown
because raw audio was not retained. The candidate now derives the target from
the validated plan.

The earlier authorized dynamic physical window reached the armed boundary
for task `3d81f020bb26444195414d7d73226d5`, verified the created
`/home/kumar-rishav/Downloads/blue lantern` directory, and held Files navigation
after issuing STOP-NOW. During the 90-second Stop window no exact Stop event was
recorded and strict-wake counters did not advance. The gate timed out closed;
the task failed with one verified create action, no navigation release, and no
success event. No audio or raw transcript was retained. The Owner later
confirmed: “No, I did not say ‘Friday, stop’ during the 90-second Probe 6
hold.” The Stop window was unused; the missing event is consistent with that
confirmation and is not evidence of a microphone, wake, recognition, barge-in,
or cancellation defect. That earlier Stop window remains **INCONCLUSIVE**; the subsequent Session 13 physical retry recorded above passed.
The folder and all earlier probe folders remain preserved. The temporary gate
was removed and cleanup restored normal candidate service at PID 34757, with
capture listening, wake armed, healthy Qwen/vision, and no active task.
The Owner confirmed Stop was not spoken and requested one coordinated retry
after explicit READY; do not arm before readiness. At that earlier checkpoint Probe 6 remained unqualified; the later retry passed.
Evidence is under
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe6-dynamic-physical-20261011T043242Z/`.

## Milestone C closure: active Stop and admitted filename fidelity (candidate)

All six physical General Computer Agency journeys remain accepted. Probe 6
task `a623b966f5094866b124e794ddf4fea0` proved that the real strict-wake
`voice_explicit_stop_active_computer_task` event cancels the active task
before the pending Files navigation action. The task is durably cancelled
with `cancelled_before_dispatch`, no Files release, and no success event.
The measured 3.94 ms is from recorded Stop-event processing to cancellation;
audio capture, ASR and end-to-end spoken Stop latency were not included.
Friday returned to listening. See the current qualification-matrix entry for
post-restart readiness and regression results.

The task's admitted request is the boundary available to the downstream
planner: the planner now must preserve a create-directory target literally
from that request, and filesystem verification records the exact path. This
does not guarantee that spoken spelling or case reaches admission unchanged.
Probe 6 GO said `Copper Grove`; the task and path say `copper groove`.
Earlier `Friday Stop Canary` / `Friday Stop canry` evidence has the same
uncertain origin. Raw audio/transcripts are unavailable, so these are
admission-name fidelity limitations, not established ASR defects. Stop
qualification remains accepted independently. No blanket capitalization
rule or routine confirmation turn was added; a precise name should be
spelled/clarified in the voice request when it matters.

The closure candidate is ready for Owner publication approval. The project
status remains PARTIAL until the separately authorized commit and remote
recovery gates are complete. No reboot occurred; full cold-boot qualification
remains PENDING.

## Stage 32 — learning turns and interruption while the model waits

The accepted wake orchestrator and `FridayVoiceConversationService` still own
capture, final ASR, runtime transitions, speech playback, and return to wake.
`FridayConversationService` forwards only voice-origin learning intents to the
canonical `VoiceLearningCoordinator`; it uses the existing local Qwen role for
teaching and the existing TEACH_BACK Reviewer for assessment. There is no new
voice process, endpoint, general-purpose model, wake detector, or audio
configuration.

The AEC interruption reader can arm while the voice turn is waiting for the
model or Reviewer, before TTS has started. The reader is bounded by the active
turn's stop event and is not started when the trusted active-task Stop listener
already owns capture. On owner speech it cancels the exact voice turn, closes
the supported model/Reviewer stream, stops active playback through the
established capture/stopper path, and forwards the completed utterance as the
next listening turn. The legacy playback-only monitor remains the fallback
when the reader does not support idle capture or fails to start. Stale chunks
are not queued after cancellation; the current turn cannot publish a late
completion that restarts speech.

The local-only race tests block Qwen before its first response chunk, interrupt
the turn, then verify no stale first-turn speech appears and the captured owner
utterance enters a fresh turn. Reviewer tests prove a cancellation before its
assessment commit leaves a confirmed attempt pending without evidence; a
post-commit Stop does not reverse persisted feedback/evidence. Synthetic ASR
and playback fixtures do not qualify real wake recognition, physical audio,
Pocket/Anna audibility, latency, or device recovery.

### Read-only production wake evidence reviewed for Stage 32

On 2026-10-16, the current Stage 31 API reported voice `running`, capture
`listening`, wake armed, no active turn, no last error, and recovery count zero;
Pocket/Anna and all three voice workers were running. The user service had
started at 16:34 local time. Journal evidence from earlier processes records a
primary `WakeRuntimeError` at startup on 2026-10-15 09:22:49 with the explicit
cause `wake worker response timed out`, followed by systemd recovery. A
pre-current process also logged five bounded retry events between 14:12 and
16:16 local time on 2026-10-16; those entries contain only the exception type,
not a more specific cause. No matching kernel OOM entry appeared for that
window. The later healthy process has not reproduced the error in this
read-only observation. Stage 32 therefore leaves the wake engine unchanged;
actual wake-after-response/Stop and worker-recovery behavior remains part of
the separately approved physical qualification.

The observed host audio endpoints were the built-in `HDA Intel PCH / ALC898
Analog` capture (`alsa_input.pci-0000_00_1f.3.analog-stereo`) and current
analog-stereo output (`alsa_output.pci-0000_00_1f.3.analog-stereo`). The
existing PipeWire AEC source `friday_aec_source` was present and shared with
the active Friday service. No physical voice test or audio setting change was
made. Stage 32 code-only qualification and the physical approval boundary are
recorded in `ROADMAP.md` and ADR 0055.

On 2026-10-18, the duplicate candidate Parakeet startup was traced to the
qualification harness waiting for candidate `wake_path_armed`; the managed
voice startup launches Parakeet and Moonshine before arming capture. Gates
covering microphone input, CPU Whisper, Pocket/Anna, and voice-learning routing
can use an isolated candidate API with wake disabled. A test-only synthetic
run passed those routing and lesson-context boundaries with temporary state;
its single live-Qwen response ended mid-sentence at the 160-token cap. No
physical capture or speaker playback occurred in that synthetic run, and
production wake policy was unchanged. At that point Gates A–C still awaited the
owner's separate physical-test approval. The
current authenticated production API has no accepted-wake event contract for
Gate D; do not infer wake qualification from wake-disabled routing or health
counters. See the updated operational evidence in `CODEX_HANDOFF.md` and
`ROADMAP.md`.

The owner approved the lightweight physical Gates A–C test on 2026-10-18. Two
complete 12-second samples were captured from the existing ALC898-backed
`friday_aec_source`; CPU Whisper returned `[BLANK_AUDIO]` both times, so no
transcript was confirmed or passed to learning. A bounded Qwen probe used typed
test text and selected the eligible `data-evaluation` lesson context in the
isolated candidate; it is not physical ASR evidence. The temporary candidate
DB gained one dynamic lesson subject and one `unverified` competency, with no
lesson attempts; production learner counts stayed unchanged.

The Pocket/Anna speaker attempt was safety-aborted when production PCM age
reached 5,319ms during VAD `detecting`. It did not preserve speaker route,
playback-stop, or owner audibility evidence. Memory pressure thresholds were
not hit. Production capture was not paused or reconfigured; after candidate
cleanup it returned to listening/armed and passed a 12-second stability check.
No wake, barge-in, or spoken Stop was attempted. Stage 32 remains PARTIAL; the
earlier physical window was closed pending PCM diagnosis. The later
owner-authorized direct root-cause retest is recorded below.

The later owner-authorized direct retest captured the spoken phrase through
both raw ALC898 input and a temporary WebRTC AEC graph. Each 15-second
16 kHz mono capture supplied all 240,000 frames, and CPU Whisper returned
“Friday continue my machine learning course.” (2.62s raw; 2.656s AEC). The
speaker monitor was linked as the AEC reference; raw PCM was memory-only and
wiped after ASR. This qualifies the physical input/ASR sample, not Friday's
wake or conversation path.

The old audio-age abort was a watchdog false-positive condition: its guard
allowed `detecting` in one phase check but separately aborted on age above 5s.
The wake loop calls its detector synchronously before it reads the next chunk.
Stage 32 health now records monotonic capture-read completion, VAD inspection,
ASR handoff, and detector duration. A focused blocking-detector test confirms
that PCM age increases while the last read is complete and the loop is in
`detecting`; it does not establish whether PipeWire stopped in the earlier
physical run.

The subsequent single isolated candidate stack startup exceeded the unchanged
resource guard: full-memory PSI avg10 exceeded 2% for 10s and reached 19.5%.
MemAvailable was about 24.25 GiB, SwapFree 4.30 GiB, and OOM counters were
zero. The candidate and temporary AEC graph were stopped before API readiness
or physical speech. Stage 31 was restarted and verified listening and
wake-armed, with Pocket/Anna, both wake workers, AEC routing, UI, Qwen, vision,
and computer-agency health intact. Production learner/task database snapshots
matched exactly, including the 12 historical `in_doubt` actions. Evidence is
under `/home/kumar-rishav/.local/state/friday-stage32-root-cause-20261018T063217Z/`.

### 2026-10-25 UTC / 2026-10-26 local — resource attribution and typed operator gate

The production-only baseline showed no system or Stage 31 service PSI, reclaim,
swap, or /dev/sdb traffic. In a fresh no-speech candidate, the unchanged guard
observed a READY state in 46.5 seconds and held it for 180 seconds without a
threshold trigger. Candidate cgroup memory.current peaked at 6.22 GiB and
memory.peak at 6.26 GiB. At the peak sample, memory.stat showed 3.86 GiB
anonymous and 2.29 GiB file-backed memory; file-backed memory reached 2.58 GiB
at a different sample. Cgroup PSI and swap stayed at zero, with no OOM/high/max
events. System PSI avg10 briefly peaked at 2.6%, below
the existing 10-second trigger duration. Available memory stayed above
23.39 GiB. The candidate API process had about 7,180 major faults; the
Parakeet, Moonshine, and Pocket/Anna managed workers had 64, 1, and 203. The
candidate performed substantial reclaim but did not stall in its cgroup.

The same observation recorded major faults and swap activity in host processes
outside the candidate, including a process reported as ChatGPT; Qwen remained
available and received no candidate inference request. Startup read about
2.87 GB from /dev/sdb without evidence of saturation. The prior sustained-PSI
abort lacks PID and mapping samples, while the first no-trigger run did not
capture mapping names at READY. Therefore the specific cause and cold/warm
residency remain unknown. No model move, resource-threshold change, or kernel
or swap adjustment is justified. Stage 32 remains PARTIAL pending cause-specific
evidence or a justified mitigation.

The earlier preflight rejected session.active even when the production
interaction lock was free, runtime state was completed, and no voice turn was
running. FridayConversationSession uses that flag to retain bounded conversation
context after completed turns. The Stage 32 harness now permits that completed
state only when the interaction lock is explicitly free and the voice-turn flag
is false; it still rejects active or unknown runtime state and unavailable
signals. The service and conversation were not directly altered.

The tracked operator flow and loopback page now require resource qualification,
the automatic restore timer, and independent abort before displaying the exact
READY message or accepting one typed START during a 300-second window. START
only records the acknowledgement; capture handoff remains an orchestrator
operation. The page withholds START SPEAKING NOW until capture/listener
readiness is verified. Its focused tests cover expiry, duplication,
cancellation, missing qualification, handoff order, and cue visibility. This
page is not yet connected to the temporary candidate orchestrator, so the
owner-facing path is not integrated or qualified. No physical gate ran.

The manual restore connection closed while the isolated controller was
shutting down. Its resource monitor lost the orchestrator cgroup identity and
invoked the idempotent restore fallback. The independent verifier confirmed the
Stage 31 release pointer, services, ALC898/AEC cleanup, live PCM/wake, single
worker stack, and unchanged production databases. Repair the monitor teardown
race before the next candidate run.

A second no-speech READY window remained under the unchanged guard for 180
seconds: system PSI avg10 peaked at 0.14%, candidate PSI stayed at zero,
MemAvailable stayed above 23.43 GiB, candidate cgroup memory peaked at 5.16
GiB, and no candidate reclaim occurred during READY. The resource sampler now
also snapshots process executable, parent PID, cgroup, PSS, and resident
mapping names at READY, in addition to trigger-time mapping capture. The
snapshot shows substantial Parakeet, candidate API, Pocket/Anna, Moonshine, and
UI residency, but the earlier trigger lacks comparable per-process evidence.
The resource cause remains inconclusive, and no resource setting or model
placement changed.

That run exposed a separate manual-restore lifecycle defect: the watchdog was
a child of the candidate service cgroup, so stopping that service terminated
the watchdog before it wrote its final report and stopped the timer. A
separate watchdog invocation completed Stage 31 and candidate cleanup
verification and stopped the timer. The tracked operator server now launches
manual restoration as a uniquely named user service outside the candidate
cgroup, returns RESTORATION_STARTED, rejects duplicate requests, and preserves
the timer on launch failure. The live restore path still needs integration and
verification in the candidate orchestrator; a temporary no-op watchdog
confirmed the service starts in its own cgroup. The typed-START page also remains
unconnected to the temporary orchestrator, so it is not yet an owner-facing
qualification path.

### 2026-10-26 — integrated operator lifecycle and physical-ready boundary

The typed-START controller now drives the real candidate orchestrator. It
requires the two guarded resource runs, a live automatic restore timer, and
verified independent manual restoration before showing the physical-ready
prompt. The 300-second acknowledgement is bound to one fresh candidate
session. The candidate voice stack is not started while waiting, so Stage 31
retains capture ownership. After START, the orchestrator switches capture and
verifies ALC898/AEC input, PCM progression, listener readiness, and candidate
capture ownership before displaying START SPEAKING NOW and the exact phrase.

The actual independent restore service passed manual abort, automatic timeout
with an active candidate unit, and automatic fallback after candidate-unit
death. Each report reached RESTORED_VERIFIED and checked its separate service
cgroup, Stage 31 release and health, AEC/wake/PCM, unchanged production learner
state, candidate cleanup, and timer cleanup after verification. A real manual
abort from the integrated pre-START session also restored Stage 31.

Two bounded 180-second no-speech READY windows passed with the existing guard
unchanged. Candidate peaks were 6.23 and 5.15 GiB, candidate PSI stayed zero,
and system PSI avg10 peaked at 2.12% and 0.18%; neither run triggered the guard.
The earlier 14.79% PSI event remains unexplained residual risk. These measured
passes qualify startup under tested conditions without claiming the historical
cause is fixed.

The first live READY page exposed invalid JavaScript for its multiline prompt;
it now serializes the prompt as a JSON string. In a later live run the Owner
typed START once and capture readiness verified the real ALC898/AEC input, PCM
progression, listener and candidate capture owner. The speaking cue appeared
at 06:51:34.854 UTC while system full-memory PSI avg10 was 3.92%; the unchanged
guard restored Stage 31 at 06:51:38.430 UTC after 10.277 seconds above 2% PSI.
Candidate cgroup PSI was 0.60%, peak memory 6.54 GiB, swap remained zero and no
OOM/high/max event occurred. No physical gate result or finalized transcript
was recorded. Root cause remains unresolved. The first measurable correlation
was Pocket/Anna worker startup reading 82.9 MiB and adding 27 major faults in a
1.139-second sample while host reclaim/swap activity rose; this is not proof of
sole causation.

The old page retained a stale speaking cue when status polling failed. Its
unavailable-state handler now clears/hides the cue, READY text and START
controls and says `CONTROL UNAVAILABLE — DO NOT SPEAK`. The candidate
orchestrator now checks the same live resource limits for 15 consecutive
seconds after capture readiness and before publishing the speaking cue. The
existing guard and independent restoration remain active; thresholds are
unchanged. This additional live gate passed focused code checks but is not yet
live-qualified. Trigger and `RESTORED_VERIFIED` reports remain in the run state
directory recorded by `CODEX_HANDOFF.md`. Stage 32 remains PARTIAL pending a
fresh bounded live resource qualification, physical Gates A–J, retained
per-turn evidence and Stage 31 restoration.

The first resource-only live preflight exited before candidate startup because
its copied operator-control process lacked `STAGE32_WORKTREE`. The automatic
failure path used the independent restore service, reached
`RESTORED_VERIFIED`, verified production learner fingerprints, and cleaned up
the timer. The launcher now passes its isolated worktree and state directory
to the control child; a focused regression covers that environment handoff.
A separate `resource_requalification_no_speech` mode now provides a
session-bound START page with no physical speech gate or speaking cue. The
first corrected session reached its waiting page but exited before typed START
when a generic pre-START safety check failed. Its 59 samples show 0% system PSI
avg10 and at least 23.32 GiB MemAvailable; it did not start a candidate voice
stack or hand off capture. The monitor's later missing-PID error followed
orchestrator teardown. The pre-START callback now records each check and
snapshot-read error before restoration. A subsequent resource-only session
accepted one fresh START and passed the real capture handoff, then remained
READY for 180.402 seconds without speech or a cue. The new stability gate held
for 16.003 seconds over 16 samples; system/candidate PSI avg10 peaked at
1.25%/0.18%. In the 180-second qualification window the peaks were
0.25%/0.03%, candidate peak memory 5.95 GiB, minimum MemAvailable 23.28 GiB,
and minimum SwapFree 5.17 GiB. The guard did not trigger, and the independent
restorer verified Stage 31 and timer cleanup. All three bounded no-speech
windows now qualify resource-safe startup under tested conditions. The
historical pressure cause remains unresolved and thresholds are unchanged. The
live handoff predicates are now also persisted to `capture-readiness.json`
before the gate so the physical session retains exact ALC898/AEC/PCM/listener
and capture-owner proof.

### 2026-10-24 post-reboot reconciliation of the READY candidate

The subsequent October 18 single-stack candidate did reach READY and emitted
one `WAKE_ACCEPTED` marker followed by five `ASR_FINAL` markers. The candidate
was configured for the exact `Friday` phrase, and the accepted marker is emitted
only after the wake-capture event reports `result.wake=true`. This evidence
does not show a wake-recognition defect. The run also recorded Pocket/Anna
playback and local-Qwen pipeline markers, but its runtime events and final
latency snapshot were not retained; the exact ASR words and measured physical
latencies therefore remain unknown. The owner-marked observations support a
physical interaction but do not complete qualification.

The missing final evidence and failed manual stop came from the test controller:
it matched the worktree path against the candidate process command line, which
contained the isolated state path to `run_candidate.py`. The manual stop did
not signal that process or invoke restoration; the separate 20-minute watchdog
restored Stage 31 and verified its release, voice, database, and service state
before the October 24 reboot. The reboot did not interrupt an active physical
test. A fresh isolated harness now matches the exact runner path, persists
final candidate events/transcripts/latency before shutdown, directly runs a
serialized restore verifier from the manual control, and monitors the test
cgroup independently for memory pressure. No production wake behavior or
threshold changed; a new owner-present physical run is still required.

### 2026-10-25 bounded candidate resource-guard abort

A fresh candidate armed its independent PSI/resource guard and production
restore timer before the Stage 31 capture handoff. Qwen and vision remained
active. The sequential Parakeet, Moonshine, and Pocket/Anna stack reached READY
on the ALC898-backed candidate AEC source, but the unchanged system full-memory
PSI guard aborted before owner speech: avg10 exceeded 2% for about 10.2 seconds,
peaked at 14.79%, and sampled 7.74% at trigger. Candidate cgroup memory was
6.42 GiB current / 6.53 GiB peak, with 3.57% full PSI, 5,964 major faults, and
about 0.64 GiB swap-out; OOM counters remained zero. No transcript, turn, or
latency event was produced. The guard restored and verified Stage 31, including
the release pointer, API/UI/Qwen/vision, listening/wake-armed PCM, workers, and
unchanged production database fingerprints. The physical behavior gates remain
pending. Follow-up samples show 3.13 GiB file-backed and 3.26 GiB anonymous
candidate pages, 48,887 file workingset refaults, 391,927 candidate reclaim
scans, and about 32 MiB swap-in alongside 0.64 GiB swap-out. The cgroup leaf
had no memory.high/max/OOM events. A same-day full-stack candidate with the
same startup order reached capture at 5.23 GiB without PSI or swap movement.

Parakeet (2.4 GiB), Moonshine (257 MiB), and Pocket (272 MiB cache) files are
under `/AI` on rotational HGST `/dev/sdb`. The sysstat interval containing the
later startup recorded 6,431 KiB/s read throughput, 385.11 KiB average request
size, 19.88 ms average wait, 0.33 average queue, and 6.18% utilization. This
confirms model-file reads but does not show disk saturation. Candidate
file-backed pages and refaults support cold model loading as part of reclaim,
but do not reveal the historical faulting PID, exact mapping, or outside
process contribution. The candidate did not call Qwen and had one worker per
voice role. No storage or startup mitigation is justified yet. The
qualification sampler now records per-process fault/I/O counters and PSS,
system vmstat, cgroup swap/I/O and ancestor limits, plus trigger-time mapping
residency summaries. The temporary operator page lacked an explicit typed
`START` and full state sequence; future physical prompts will use the visible
Codex window and one exact gate phrase at a time. Preserve the existing guard
and do not infer a wake defect from this resource abort.

### Stage 32 isolated operator event and gate bridge — 2026-10-26

The temporary Stage 32 operator remains a test-only loopback surface separate
from the approved Astra UI. A fresh candidate session receives a single-use
typed START only after resource, automatic restoration, and independent manual
restoration evidence pass. The control server binds START and owner
observations to the candidate session and checks loopback Host, exact Origin,
and CSRF. Candidate capture does not start before START, and the cue remains
withheld until ALC898/AEC, PCM progression, listener, resource stability, and
capture ownership are verified.

Before the first cue, the candidate drains its startup event cursor and records
the live voice-health baseline. Afterward, the orchestrator advances the
ordered physical gates from new candidate runtime events and live health rather
than page state or typed transcript input. The isolated page shows finalized
transcripts, assistant output, gate results, and owner-only confirmation
controls. Pocket/Anna audibility must be confirmed while playback is active
before barge-in. Explicit Stop, five seconds without stale playback, read-only
progress evidence, one isolated candidate assessment attempt, and Learn-view
synchronization each have separate evidence. Gate records retain sequenced
runtime events, live voice-health snapshots, owner confirmations, candidate
database fingerprints, and available latency; files are private to the test
state directory.

The audibility prompt is visible as `FRIDAY IS SPEAKING` only while the
learning-output gate has a session, voice-turn, playback-start sequence and
runtime start timestamp. Its confirmation request is bound to those values;
the orchestrator requires the matching non-acknowledgement start event and
rejects it after a matching playback-completion event. Request and acceptance
timestamps are retained with the gate evidence. The playback identifier is a
session/turn/sequence correlation key, not a hardware player ID. This remains
an owner-reported audibility observation, not automatic acoustic measurement.
Physical session #06 expired before START and restored Stage 31; #05's missing
confirmation remains an unconfirmed result and does not establish TTS failure.
Session #07's expected learning phrase and retrieval succeeded, but its active
assistant turn was cancelled before output acceptance. Whisper's explicit
`[BLANK_AUDIO]` sentinel is not treated as a mismatching command; a matching
cancelled assistant turn now fails that gate with a specific reason. This
repair changes only qualification classification and does not relax the
physical response or audibility requirements.
In session #08, owner-confirmed playback passed and physical speech interrupted
the active lesson playback. Whisper finalized `for how to cancel my answer.`;
Friday routed that as generic conversation because no learning answer was
pending, so the barge-in gate did not pass. A later interruption was not
qualified as spoken Stop. Independent abort restored Stage 31 and verified
timer cleanup. The physical barge-in and later gates remain unqualified.

The Stage 32 qualification cue initially used the existing learning repeat
action: `Friday, repeat that.` Its later physical transcript was `Can I repeat
that?`, so the next exact cue now uses those observed words and omits the
misrecognized wake alias. Gate acceptance binds the finalized transcript to
one post-interruption learning-context turn, its Qwen response, and playback
start. A transcript mismatch, absent learning route, or multiple follow-up
turns fails closed. This changes only the temporary qualification prompt and
gate evaluator; it does not alter production intent policy, capture, AEC, wake,
Qwen, Pocket/Anna, or the approved Astra interface. Focused tests cover both
accepted routing evidence and these fail-closed cases. Physical qualification
still requires a fresh Owner START and genuine voice evidence.

Session #10 received a valid typed START but the resource guard restored Stage
31 before the capture-ready cue. Host full-memory PSI peaked at 12.86% and
candidate cgroup PSI at 11.86%; sustained samples exceeded the unchanged
2%/10-second limit for 10.30/10.24 seconds. Candidate memory peaked at 5.89 GiB,
with zero cgroup swap-out or OOM events and 23.48 GiB host MemAvailable. The
source of the pressure remains unisolated. Independent recovery verified Stage
31 listening capture, wake, unchanged learner data, candidate shutdown, and
timer cleanup. No physical speech gate ran.

The temporary operator page now resets prior results, START text, and pending
button state when the candidate session identity changes, and clears the result
message when status polling becomes unavailable. This preserves a clear
fail-closed handoff when a tab is reused for a new test session. The resource
trigger context record also uses an undated artifact name; prior records keep
their original names. These are qualification-harness changes and do not alter
the approved production voice path or safety thresholds.

This bridge does not change production capture, wake recognition, Qwen, TTS, or
the approved UI. The focused test path passes, but physical Gates A–J are not
qualified until a fresh Owner START drives actual microphone and audible
playback evidence and Stage 31 restoration is verified afterward.

Independent manual, guard-triggered, and timer-triggered restoration services
can converge on the same session state. The restore-service boundary therefore
serializes each session through a private lock, and concurrent status/report
writers use unique private temporary files before atomic replacement. The
automatic timer remains armed until the restoration verifier confirms Stage 31
and cleanup. A live two-request qualification with a harmless sleep-only
candidate verified this behavior without starting or interrupting production
capture; the earlier fixed-temp rename race remains preserved as failure
evidence.

### 2026-10-26 — physical session #11 lease expiry and no-session preparation

Session #11 completed guarded setup and reached `AWAITING_OWNER_START`, but its
300-second typed-START lease expired at 10:57:18 UTC. The operator flow records
zero STARTs and no capture handoff; no speech gate ran. Automatic restoration
reached `RESTORED_VERIFIED`, with Stage 31 API/Astra UI/Qwen/vision, ALC898/AEC
listening capture, wake, advancing PCM, unchanged production learner data and
release pointer, candidate shutdown, and recovery timer cleanup verified. The
full session evidence remains in the #11 operator qualification state
directory.

After restoration, a host-only 15-second window measured maximum full-memory
PSI avg10 at 0.00%, minimum MemAvailable at 23.42 GiB, and minimum SwapFree at
4.71 GiB. Candidate resource safety still must pass its existing guard. At
that checkpoint the no-session `PREPARED` page had no START lease or capture
handoff. The current stable workflow below supersedes its conversational ARM
step.

## Stage 32 — independent operator service and session lifecycle

Session #12 (`8c952603ed4449d99d307fd32069f74e`) received one exact Owner
`START`; capture handoff began, then the resource guard aborted before the
speaking cue. No physical speech gate ran. Its restore report verified Stage
31 release and learner database unchanged, API/Astra UI/Qwen/vision health,
ALC898/AEC listening capture, wake, fresh PCM, candidate cleanup, and timer
cleanup. The preserved evidence is in the #12 operator qualification state
directory.

The controller was launched as a child process in the candidate orchestrator's
systemd cgroup. `start_new_session=True` changed its process session but not
its cgroup; independent restoration correctly stopped the candidate unit and
therefore killed the controller. The controller now runs in its own
`friday-stage32-operator-control.service` with `Restart=on-failure`. The
restoration watchdog verifies the controller unit is active in an independent
cgroup, that its main process is the expected control script, and that its
loopback status still projects the candidate session. A live SIGKILL recovery
restarted the service under a new PID without losing the restored session.

The stable root page resolves one validated active sibling session directory.
When and only when that session has a complete `RESTORED_VERIFIED` report, the
loopback page offers `Begin physical test`. Its exact Host, Origin, and
single-use CSRF checks launch a new private session and a separately
supervised candidate orchestrator service. The candidate reuses the persistent
controller rather than stopping or replacing it. Begin starts fresh resource,
production-health, timer, and manual-restore checks; it never authorizes
capture. The candidate session binds the later exact `START` request to its
fresh identity and only then attempts ALC898/AEC capture handoff. Idle waiting
does not hold an expiring START lease or candidate voice-worker stack.

The candidate orchestrator had a duplicate 10-second sustain clock that applied
the threshold to rolling PSI `avg10`. Raw replay of the 2026-10-26 trigger
confirmed the false sustained classification: the candidate rolling average
stayed above 2% for 10.544 seconds and was 5.16% at the abort, but cumulative
full-PSI intervals exceeded 2% continuously for at most 6.017 seconds on the
host and 4.010 seconds in the candidate cgroup. The underlying burst was real:
over 3.509 seconds system/candidate cumulative PSI rose by 1.761/1.099 seconds
of full stalls, then barely advanced before the abort. Trigger-time
`MemAvailable` was 23.79 GiB, `SwapFree` 3.56 GiB, candidate memory current/peak
6.27/6.58 GiB, and cgroup high/max/OOM counters were zero.

Both candidate and independent monitoring now use cumulative full-PSI deltas
over monotonic intervals no longer than 2.5 seconds, with the existing 2% and
10-second thresholds unchanged. The candidate sampler retains the system PSI
`total` counter. If its own loop misses an interval, it rebases only when the
same-session independent guard is active and its latest cumulative sample is
fresh; otherwise missing or invalid telemetry still triggers restoration.
The independent guard remains fail-closed. A detailed sample just after the
trigger recorded 9,144 major faults and 22.96 GB of read I/O for Qwen PID 1823,
and 4,001 major faults / 525 MB of read I/O for the candidate API. This
supports cold model/application page-ins as contributors, but does not prove
the full kernel reclaim path. The adjacent 10.22-second detail interval also
recorded host major faults +15,592, swap-in +36,473 pages, swap-out +7,155,
kswapd scans +14,403, and kswapd steals +8,295. Candidate cgroup counters in
that interval recorded major faults +6,215, scans +25,600, steals +13,591,
file refaults +467, and swap current 790,482,944→744,620,032 bytes. This proves
real reclaim and transient swap activity, not RAM exhaustion: MemAvailable
remained 23.79 GiB at the guard trigger. There was no restrictive candidate
cgroup limit or OOM kill. A post-fix guarded live candidate is still required
to requalify cold startup before physical cues.

The latest guarded candidate still restored Stage 31 after its recorded host
PSI abort; its independent guard is stopped and restoration is verified, and
no speaking cue or physical speech gate was recorded in that session. The
current boot has separately verified Stage 31 and returned the operator to
`PREPARED`. A post-fix guarded candidate startup and the physical wake,
learning, audible output, barge-in, spoken Stop, recovery, progress, assessment,
UI synchronization, resource, and final-restoration gates remain open.

### Stage 32 live Qwen inference pressure diagnosis — 2026-10-27

Physical candidate `48b9fc5932924907b55a67bda81f15d2` passed guarded preflight,
capture, and the `Friday` wake, then reached local Qwen's first token for the
learning continuation. The independent guard stopped it before the response
gate completed. This candidate did not overlap the full repository regression.

At the trigger, candidate-cgroup full PSI was 2.70% for 10.35 seconds against
the unchanged 2%/10-second threshold. The preceding resource sample captured
system full PSI avg10 at 6.45%, candidate-cgroup full PSI at 6.02%, and 5,980
major faults in ten seconds for the host `llama-server` PID 1823. Its RSS grew
from about 0.13 GiB to 17.25 GiB as the live Qwen response began. MemAvailable
remained 23.14 GiB, SwapFree 4.07 GiB, candidate memory 5.34 GiB, GPU memory
7,502/8,192 MiB, with no cgroup OOM events. This supports Qwen model-page
reloading/residency as the leading source; the exact kernel reclaim path remains
unproven. Preserve the guard threshold. A later guarded candidate completed the
live Qwen response without a resource trigger after Qwen had already been
exercised; this supports but does not prove the warm-residency hypothesis. No
general mitigation is claimed. Stage 31 was independently restored and timer
cleanup verified. Private evidence is under
`/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-physical-operator-ready-20261026T183202Z-62eec9aa8d34/`.

### 2026-10-27 — repeated physical barge-in transcript mismatch

Candidate `b4c24cfe7a6647b992fd41baccd2547e` passed guarded preflight, wake,
learning continuation with live Qwen, and owner-confirmed Pocket/Anna
audibility. Runtime sequence 183 proves the active playback was interrupted.
Finalized transcript sequence 189 returned `Can I repeat that?` from 1,472 ms
of interruption audio, while the Owner reported speaking `Friday, repeat
that.` The exact transcript gate failed and no routed repeat response or later
physical gate was credited.

The independent resource guard stayed below its unchanged thresholds during
this run: system full-memory PSI avg10 peaked at 1.99%, candidate full PSI at
0%, minimum MemAvailable at 23.15 GiB, and minimum SwapFree at 4.10 GiB. The
candidate restored Stage 31 and verified timer cleanup. The next physical cue
is `Can I repeat that?`, using the exact words actually recognized and omitting
the misrecognized wake alias. This utterance routes to the existing repeat
action; exact transcript and downstream single-turn/Qwen/Pocket/Anna proof
remain required. Evidence is under
`/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-physical-operator-ready-20261026T184026Z-be08deb5bed0/`.

### 2026-10-27 — Vite owner-capability bootstrap dependency

Candidate `aaf4f51968574c84a47fdc97ef58c7ae` received exact typed `START` and
stopped Stage 31 capture. Vite exited before the candidate API or voice workers
started because the session's private `owner/owner-capability.json` did not yet
exist. Candidate API startup normally provisions it through `LocalOwnerTrust`.
No speaking cue was released. Independent restoration verified Stage 31
listening and unchanged production learner data. The orchestrator now
preprovisions this session-scoped capability with the canonical owner-trust
implementation before Vite starts. Targeted tests verify its private
permissions, installation binding, and non-rotation when the candidate API
reuses it. The 29 orchestrator/resource regressions and targeted Ruff pass; the
next guarded run must still verify live Vite-first startup. Evidence is under
`/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-physical-operator-ready-20261026T192407Z-913165b550e0/`.

### 2026-10-27 — host memory-pressure abort during candidate worker startup

Candidate `195123a133b54ef2b5ee6b0fc1a813ea` passed preflight, received one
exact typed `START`, and began capture handoff. Parakeet, Moonshine, and
Pocket/Anna worker startup completed; the ALC898/AEC capture readiness check
reported ready, but the 15-second resource-stability gate did not complete.
The speaking cue and all physical speech gates were withheld.

The independent guard restored Stage 31 when host full-memory PSI avg10
remained above the unchanged 2% limit for 10.024 seconds (trigger 2.38%;
sampled peak 5.98%). Candidate memory reached 5.46 GiB; candidate cgroup PSI
peaked at 2.89% and measured 1.42% at the host trigger. Candidate cgroup major
faults increased by about 603 of the host's 634 major faults during the final
detailed 10-second interval. Per-process samples attribute 490 faults to the
newly launched Vite/Node process, 81 to Piper, and 18 to the candidate API;
Vite became ready just before the pressure trigger. This makes overlapping
cold Vite and voice-worker loading the strongest identified contributor, but
does not establish the sole cause or full kernel reclaim path. Host
MemAvailable remained above 23.37 GiB, SwapFree above 4.29 GiB, and candidate
OOM counters were zero. Stage 31 listening, unchanged production learner data,
candidate cleanup, and timer cleanup were verified.

The candidate now starts Vite and warms `/src/main.tsx` after exact `START` and
Stage 31 capture shutdown, then requires 15 seconds within existing resource
limits before launching voice workers. The independent guard and restoration
remain active; thresholds are unchanged. Targeted tests and a live candidate
run must verify stable startup before any speaking cue is released. Evidence
is under
`/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-physical-operator-ready-20261026T190037Z-9c9fd5233ade/`.

### Stage 32 — AEC utterance drain after playback interruption (2026-10-27; prior failed physical run)

The latest Owner-started session interrupted Pocket/Anna playback during the
spoken Stop attempt. The Owner reports saying `Friday, stop.` while Friday was
speaking and hearing playback stop immediately. Runtime sequence 349 records
the active repeat turn interrupted at `11:38:27.168Z`, 12.893 seconds after
playback sequence 208 started; the runtime returned to listening. No finalized
Stop transcript or `voice_explicit_stop` transition followed. Candidate logs
showed `TTS_CANCELLED`, `PLAYBACK_COMPLETE`, `LLM_CANCELLED`, then an 8-second
follow-up-capture timeout. The gate timed out because it had no Stop transcript
to correlate with the interruption; it did not have evidence to mark the Stop
gate passed.

The defect was a lifecycle race. `FridayBargeInMonitor` honored its shutdown
event even after VAD had confirmed speech, so playback-turn cleanup could stop
the AEC capture before the same utterance reached its end boundary. The next
one-shot follow-up stream then opened after the Owner had finished speaking.
The monitor now finishes an already-triggered utterance despite a shutdown
request, and voice-turn cleanup allows the configured 30-second maximum
utterance plus a bounded margin to drain. The operator also checks for
`voice_session_idle_timeout` after a matched playback interruption and records
`interrupted_utterance_missing_finalized_stop_transcript` instead of waiting
for the generic four-minute gate timeout. Playback cancellation and the Owner's
silence observation remain valid evidence, but the missing transcript prevents
accepting the spoken Stop or its formal stale-playback gate.

Replaying the saved event timeline through the corrected evaluator retains a
FAIL: the old result was `physical_gate_timed_out` at 240.496 seconds; the new
result is `interrupted_utterance_missing_finalized_stop_transcript` when the
listener reaches its idle timeout. This reclassification does not create ASR
evidence or change the physical outcome. The source correction passed 134
focused tests covering voice intents, AEC capture, the Stage 32 operator,
voice learning, and the voice barge-in integration, with no failures or skips;
Ruff, compilation, and `git diff --check` passed. This candidate remained
PARTIAL; its independent Stage 31 restoration was verified. The subsequent
physical acceptance is recorded below.

### Stage 32 — final physical Stop and learning acceptance (2026-10-27)

Candidate `a99591b3183d45bb83ce30b46372e7c1` ran against its matching source
snapshot and passed every physical operator gate. Evidence is preserved under
`/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-physical-operator-ready-20261027T125146Z-f61afc463909/`.

Repeated lesson playback began at 12:55:40.455605Z, sequence 222, on runtime
session `99c79c1de4a0448097c4b6235569d2b6` and playback turn
`a11c4c59a8f04ce8b3f3c97c4ad91550`. The Owner reports speaking during active
playback; the physical speech-onset timestamp is not separately available.
VAD interruption sequence 353 occurred at 12:55:56.998292Z with 514,560 PCM
bytes written. ASR finalized `Friday, stop.` at sequence 359 at 12:55:57.415961Z;
the same session then entered `voice_explicit_stop` at sequence 360,
12:55:57.416027Z. Interruption-to-final-ASR was 417.669 ms and
interruption-to-Stop-state was 417.735 ms; onset-to-stop latency is not
measurable. The candidate log records `TTS_CANCELLED` followed by
`PLAYBACK_COMPLETE`. Qwen response generation had completed before the
interruption, so no active model cancellation was pending.

The same-turn Stop gate and the separate five-second no-stale-playback gate
both passed; the latter includes typed Owner confirmation. A recovery wake,
read-only learning progress, isolated spoken assessment, and Owner-confirmed
Astra voice synchronization also passed. The assessment was marked incorrect
in candidate state, created one isolated attempt, awarded no mastery, and
produced no production write. Resource preflight passed and the guard did not
trigger. Independent restoration reached `RESTORED_VERIFIED`, preserving the
Stage 31 release pointer and production database fingerprints, verifying API,
UI, Qwen, and vision health, restoring ALC898/AEC capture to listening with
advancing PCM, stopping the candidate workers, and cleaning up the recovery
timer. Physical acceptance is complete; final full regressions and source
publication are tracked in `CODEX_HANDOFF.md`.

### 2026-10-27 — candidate launcher interpreter recovery

The next Begin request created a private session, but the persistent operator
configuration launched its candidate orchestrator with the system Python. That
interpreter lacked Friday's `pydantic` dependency, so the orchestrator exited
during imports before creating a candidate session. Stage 31 remained the
capture owner; the preceding session was already `RESTORED_VERIFIED`. The
`systemd-run` resolved the candidate venv's Python symlink, so invoking it
directly still selected the system interpreter. A lightweight systemd probe
confirmed that a Bash `exec` wrapper preserves venv discovery and imports. The
launcher now uses that wrapper, and a focused regression verifies its arguments
and venv path. The already-running persistent controller had imported the old
launcher code, so retries continued to use its old argv until the controller
is refreshed. Refreshing this isolated operator page does not restart Friday's
production services. This startup recovery does not qualify physical voice behavior;
Stage 32 remains PARTIAL. Failure evidence is under
`/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-physical-operator-ready-20261026T193043Z-6fa24e3a53a3/`.
