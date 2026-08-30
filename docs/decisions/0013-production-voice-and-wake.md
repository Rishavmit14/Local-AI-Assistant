# ADR 0013: Strict persistent wake cascade and user-session voice deployment

- Status: accepted for Stage 11

## Context

Friday needs low-latency always-on wake recognition compatible with the logged-in PipeWire session. Energy-only segmentation proved unreliable, repeated ASR startup was wasteful, and unqualified barge-in could mistake Piper echo for a human interruption.

## Decision

Use exact `Hey Friday`, strict normalized matching, Silero VAD, Parakeet Full primary wake ASR, Moonshine Medium fallback only on primary miss, persistent fail-closed workers, one always-on wake stream, pause/resume around conversational turns, and `systemd --user` for persistent deployment. Production natural-language barge-in uses Friday-owned ephemeral PipeWire WebRTC AEC with `monitor.mode=true`: the default physical speaker monitor is the echo reference and `friday_aec_source` is explicitly captured by the trusted interruption monitor. Do not change global PipeWire defaults or move wake recognition away from the normal raw microphone path.

## Consequences

Wake latency avoids repeated model startup, fallback can recover primary misses without weakening phrase policy, Silero produces reliable completed utterances, stale worker responses cannot contaminate later requests, and Friday remains persistent in the user's audio session. Qualified WebRTC AEC now suppresses speaker/Piper echo sufficiently for natural interruption while preserving trusted human speech, so production natural-language barge-in is accepted. Stage 12 continues with explicit stop semantics and the remaining microphone/runtime lifecycle hardening.
