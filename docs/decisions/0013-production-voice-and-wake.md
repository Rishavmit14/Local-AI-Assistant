# ADR 0013: Strict persistent wake cascade and user-session voice deployment

- Status: accepted for Stage 11

## Context

Friday needs low-latency always-on wake recognition compatible with the logged-in PipeWire session. Energy-only segmentation proved unreliable, repeated ASR startup was wasteful, and unqualified barge-in could mistake Piper echo for a human interruption.

## Decision

Use exact `Hey Friday`, strict normalized matching, Silero VAD, Parakeet Full primary wake ASR, Moonshine Medium fallback only on primary miss, persistent fail-closed workers, one always-on wake stream, pause/resume around conversational turns, and `systemd --user` for persistent deployment. Production natural-language barge-in uses Friday-owned ephemeral PipeWire WebRTC AEC with `monitor.mode=true`: the default physical speaker monitor is the echo reference and `friday_aec_source` is explicitly captured by the trusted interruption monitor. Do not change global PipeWire defaults or move wake recognition away from the normal raw microphone path.

## Consequences

Wake latency avoids repeated model startup, fallback can recover primary misses without weakening phrase policy, Silero produces reliable completed utterances, stale worker responses cannot contaminate later requests, and Friday remains persistent in the user's audio session. Qualified WebRTC AEC now suppresses speaker/Piper echo sufficiently for natural interruption while preserving trusted human speech, so production natural-language barge-in is accepted.

For always-on wake capture, pause/stop now use stream retirement as the cancellation boundary: the lock-protected current-stream reference is cleared before close wakes any blocked read. EOF/capture errors from the retired stream are cancellation; failures from the still-current stream remain errors and fail closed. Pause keeps the loop alive and quiescent, resume reacquires a fresh stream, and stop terminates cleanly. This behavior is deterministic-test qualified and production restart/live-turn qualified. Stage 12 continues with explicit stop semantics and the remaining microphone/runtime lifecycle hardening.

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
