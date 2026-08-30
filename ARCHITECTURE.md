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

AEC/barge-in primitives and conversational integration exist and are tested, but the normal always-on bootstrap intentionally leaves production barge-in unwired until a real PipeWire echo-cancelled capture source is identified and qualified.

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
