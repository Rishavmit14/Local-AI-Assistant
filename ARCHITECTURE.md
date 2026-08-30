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

Production qualification on Stage 12B proved two controlled restarts with no systemd stop timeout (patched shutdown ~0.18 seconds) and a full live `WAKE_ACCEPTED -> WAKE_PAUSED -> VOICE_THREAD_BEGIN -> VOICE_THREAD_COMPLETE -> WAKE_RESUMED` sequence on the patched process. Explicit stop-command semantics and remaining microphone lifecycle hardening stay in Stage 12.

See [voice and wake architecture](docs/architecture/voice-and-wake.md).

## Deployment compatibility

Stages 0 through 8 did not mutate `/AI/projects/local-ai`, `/AI/projects/code-assistant`, llama.cpp, or model storage. The packaged code uses `LOCAL_AI_*` environment variables so reviewed deployments can point to existing paths or new state directories. Stage 11 removed the obsolete Streamlit product service and introduced the persistent user-session Friday presentation/wake service. A sanitized example is tracked at `config/services/friday-local-ai.service.example`; machine-local installed units remain external deployment state.

## Target architecture

The target remains one local platform around llama-server and specialized local models: chat, private RAG/OCR, deterministic code intelligence, planner/coder/reviewer/debugger/test/security roles, controlled tools, validation/policy engines, Git transactions/worktrees, history/metrics, Friday-native integrations, persistent conversational voice, durable memory, visual perception, safe desktop control, proactive automation, and orchestrated agents/models. Git diffs remain mutation truth; deterministic inspection precedes inference; risk and confidence gates constrain automation.

The permanent authority direction is `voice/UI/external adapters -> Friday native API/event/policy boundary -> planning/approval/execution/validation/isolation/audit`. Later stages extend perception, memory, and autonomy without granting presentation, voice, vision, or external adapters a privileged shortcut. The CLI remains the recovery/power-user surface.

## Trust boundaries

- Model output, uploaded documents, indexed repositories, and shell output are untrusted.
- localhost binding is the default network boundary; remote exposure needs authentication and TLS.
- private/generated data never enters Git.
- high-risk production, security, payment, smart-contract, migration, and deployment changes always require explicit human review.

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

Known limitation: LLM Markdown can currently reach Piper unsanitized. For example,
`**4**` may be spoken as literal "asterisk asterisk four asterisk asterisk".
This is a TTS text-normalization limitation, not a wake-command routing failure.

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

There is no acknowledgement chime or spoken "Yes?" yet. Markdown normalization
at the TTS boundary remains separate work. Deployment remains the logged-in
user's `friday-local-ai.service`. The pre-Stage-12C-B recovery point is
`3ae5292bbd1b0042e01211a657dad0fd5e9078d6`; the accepted Stage 12C-B recovery
commit is the commit containing this section.
