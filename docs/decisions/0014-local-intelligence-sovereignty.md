# ADR 0014: Local Intelligence Sovereignty and one general-purpose model

- Status: accepted product architecture
- Date: 2026-09-09

## Context

Friday is an owner-controlled local cognitive platform. Network data can improve
answers, yet making proprietary cloud inference the source of reasoning would
weaken offline operation, privacy, recoverability, cost control, and owner
authority. The MSI has one extensively benchmarked and tuned local general-purpose
model. Loading more general models would consume scarce VRAM/RAM and add latency,
lifecycle failure modes, and maintenance without demonstrated benefit.

## Decision

Adopt **Local Intelligence Sovereignty**. Core reasoning, planning, memory,
knowledge integration, evaluation, learning, orchestration, decisions, and
autonomous execution run on owner-controlled hardware using locally controlled
models, data, tools, and free/open technologies wherever practical. Internet
access supplies owner-authorized information such as public documentation,
research, market data, media, and APIs; it is not a mandatory intelligence
provider. Offline-capable tasks remain useful without internet access.

Keep `Qwen3.6-35B-A3B-UD-Q4_K_M` as the sole current general-purpose reasoning
model. Planner, coder, reviewer, researcher, critic, strategist, market, and
creator roles may use separate prompts and sequential invocations of this same
model. Speech recognition/synthesis, VAD, embeddings, OCR, future vision/image
generation, and deterministic models remain legitimate specialized components.

Maintain the existing model-client boundary. A future additional or replacement
open general model requires measured evidence against the current model that
justifies VRAM, RAM, CPU/GPU use, latency, context/runtime complexity,
loading/unloading, reliability, and maintenance. Replaceability does not justify
adding a model now.

## Consequences

Friday is not a cloud-AI wrapper and must not require OpenAI, ChatGPT/Astra,
Anthropic, Gemini, paid inference, cloud GPUs, or proprietary intelligence
services for core cognition. External data adapters retain provenance, freshness,
permissions, and failure boundaries. Stages 20–22 specialize the same coherent
Friday platform after their prerequisite stages; they are mandatory planned
scope, not current implementation. Benchmarks must distinguish raw current-model
ability from the same model enhanced by Friday's memory, retrieval, tools,
verification, skills, and experience.
