# Friday Voice and Wake Architecture

## Boundary

Voice is an input/output surface and has no privileged path around Friday's native API/event/policy boundary.

## Accepted conversational path

`microphone -> Whisper STT -> local LLM streaming -> Piper TTS -> PipeWire playback`

## Accepted always-on wake path

Canonical phrase: `Hey Friday`. Wake uses 16 kHz mono PCM, Silero VAD, Parakeet Full primary ASR, and Moonshine Medium only after a primary miss. Both use the same strict matcher.

The matcher uses Unicode NFKC, case folding, punctuation-to-space normalization, and collapsed whitespace. It accepts exact `hey friday` and transcripts beginning `hey friday ` while preserving the remainder; it does not intentionally accept fuzzy aliases.

Parakeet and Moonshine run as persistent fail-closed subprocess workers. Request/protocol failures invalidate the worker before reuse so stale results cannot satisfy later requests.

On wake: pause wake capture -> Whisper -> local LLM -> Piper -> PipeWire playback -> resume wake capture.

## Deployment

The accepted always-on runtime uses the user-session systemd unit `friday-local-ai.service` with `LOCAL_AI_WAKE_ENABLED=true` and `LOCAL_AI_WAKE_PHRASE=hey friday`. A sanitized example is tracked under `config/services/`.

## Barge-in

Production natural-language barge-in is accepted. The wake bootstrap owns an ephemeral `PipeWireAecSession` configured with PipeWire WebRTC AEC and `monitor.mode=true`. The physical/default speaker monitor becomes the echo reference, `friday_aec_source` is published as the cleaned microphone source, and `PipeWirePcmCapture` targets that exact source for `FridayBargeInMonitor`. No global default source/sink is changed and the normal always-on wake capture remains on the raw microphone.

The trusted interruption policy remains Silero >= 0.85 for at least 180 ms after the AEC arm delay. Temporary acoustic qualification measured 23.75 dB speaker-only reduction; human speech over speaker playback reached probability 1.0000 and remained above threshold for 1410 ms. A controlled production restart then proved the real graph, normal wake conversation, natural interruption while Piper was actively speaking, immediate playback stop, and continuation with the interruption utterance without another wake phrase.

The AEC session is lifecycle-owned by `FridayManagedWakeVoice` and closed with the other persistent voice resources. Exact explicit stop semantics were separately accepted in Stage 12D below.

## Wake capture pause/stop lifecycle

Blocked wake reads are now hardened. The loop keeps a stream-local handle for the active `read_chunk()` while `_stream` is the lock-protected ownership reference. `pause()`/`stop()` retire `_stream` before closing the underlying stream. When the blocked read wakes, EOF or `VoiceCaptureError` from a stream that is no longer current is treated as intentional cancellation rather than as microphone failure. Genuine failures from the still-current stream continue to raise `WakeCaptureError` and fail closed.

Pause semantics are deliberately quiescent rather than terminating: the wake loop stays alive while paused, releases microphone ownership, and resume reacquires a fresh stream. Stop releases the blocked stream and terminates the loop. Deterministic tests cover pause EOF, pause-induced capture error, stop EOF, stop-induced capture error, pause->immediate-resume fresh-stream reacquisition, and genuine unexpected failure. Production qualification completed two controlled restarts with no systemd stop timeout and a live wake/pause/voice/resume turn on the patched runtime.

## Known hardening items

- streaming speech / initial-response latency;
- longer-running voice stability and richer state observability.

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
adding a direct `LISTENING -> THINKING` transition.

Bare-wake semantics are completed by Stage 12C-B below.

Known speech-output limitation: response Markdown is not yet sanitized before
Piper; emphasis syntax such as `**4**` may be verbalized literally.

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
false recovery. Friday now closes voice ownership at Uvicorn's first exit signal;
cleanup is idempotent, and the requalified restart emitted no error or retry.

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
