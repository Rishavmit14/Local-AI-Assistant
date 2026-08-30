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

The AEC session is lifecycle-owned by `FridayManagedWakeVoice` and closed with the other persistent voice resources. Explicit `Friday, stop` command semantics are still a Stage 12 hardening item rather than being claimed as separately qualified.

## Known hardening items

- deterministic blocked-read pause/stop race test/fix;
- wake-then-separate-command semantics;
- capture-thread health supervision/restart;
- final concurrent HTTP/presentation versus wake-turn policy.
