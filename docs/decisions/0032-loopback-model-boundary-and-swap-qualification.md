# ADR 0032: Loopback-only model boundary and restart-based replaceability

- Status: accepted
- Date: 2026-09-28

## Context

Friday's general-purpose model is selected by deployment configuration and used
through `LocalLLM`. The `OpenAI` Python package supplies the local
OpenAI-compatible protocol; it does not make cloud inference an allowed
fallback. Previously, configuration accepted arbitrary URLs, the HTTP transport
could inherit proxy environment variables, streaming requested an optional usage
extension, and operational latency stages were QWEN-specific. Those behaviors
made local sovereignty and backend compatibility less explicit.

## Decision

- Restrict `LOCAL_AI_BASE_URL` to an HTTP(S) loopback host with no URL
  credentials, query, or fragment. Configuration errors fail at startup.
- Disable environment-derived proxies and automatic SDK retries for the model
  transport. A failed model request returns `LLMError`; no remote or second
  model is tried.
- Use only the portable text chat-completions fields Friday needs. Streaming
  usage is optional and is consumed only when a backend supplies it.
- Emit model-neutral `LOCAL_LLM_*` latency stages. Continue accepting historical
  `QWEN_*` stage names so existing telemetry consumers and stored diagnostic
  vocabulary remain compatible.
- Treat model identity, context size, endpoint, and timeout as deployment
  configuration. A compatible backend change takes effect after service
  restart, adds no browser switch, grants no authority, and requires no product
  database migration.
- Keep the selected Qwen as the sole current general-purpose model under ADR
  0014. A fixture contract pass is not quality evidence or permanent model
  approval.

## Consequences

Compatible candidate backends must support local system/user text chat,
streaming text deltas, configured model identity, temperature, and bounded
completion tokens. Function calling, structured output, multimodal input,
reasoning traces, and tokenizer-specific APIs are not required. Technical
compatibility is qualified with deterministic local fixtures and a bounded
current-Qwen smoke. A permanent replacement still needs the measured evidence
defined by ADR 0014.
