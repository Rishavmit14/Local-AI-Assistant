# Local model boundary qualification

Phase 17 qualifies only configuration-driven, restart-based compatibility with
Friday's current general-purpose model contract. It does not rank models, claim
quality parity, approve a permanent replacement, or provide live hot swap.

## Repeatable modes

Run from the repository root with the project environment:

```sh
.venv/bin/python scripts/qualification/qualify_model_swap.py contract
.venv/bin/python scripts/qualification/qualify_model_swap.py current-local
```

`contract` starts two deterministic OpenAI-compatible HTTP fixtures on distinct
loopback ports, launches the same isolated Friday Conversation API first with
`friday-model-swap-fixture-a` and then with
`friday-model-swap-fixture-b`, and checks the actual request model and transport
destination. It exercises chat and streaming, role prompts, memory projection,
Research evidence, bounded failures, proxy isolation, malicious action-like
output, unchanged candidate SQLite fixtures, and source-tree identity across
the restart. Fixture markers prove wiring only; they are not model intelligence.

`current-local` uses the configured local endpoint and model for a health check,
bounded chat, Conversation stream, Reasoning role, and Teacher role. It prints
only the sanitized model basename, local endpoint classification, configured
context/timeout, pass/fail categories, and elapsed time; it omits responses,
prompts, API keys, and absolute model paths.

An operator may explicitly qualify an already-installed local alternate with
`alternate-local --base-url http://127.0.0.1:PORT/v1 --model MODEL_ID`. The same
bounded smoke is used. Configuration validation rejects non-loopback endpoints;
this command never downloads a model or changes persistent Friday settings.

## Required interface contract

- Locally reachable OpenAI-compatible chat completions.
- System and user text messages, configured model ID, temperature, and bounded
  `max_tokens`.
- Non-streaming assistant text and streaming non-empty delta text.
- Empty choices/deltas, usage-only chunks, absent usage, and absent cached-token
  detail are tolerated. Usage metadata is observational, not required.
- Connection, timeout, HTTP/server, malformed-response, and interrupted-stream
  failures map to `LLMError`; no cloud/model fallback is attempted.
- The OpenAI-compatible Python package is used with a loopback base URL and a
  transport that ignores proxy environment settings. The local API key default
  remains `local` and is never included in qualification output.

The only model-selection inputs are `LOCAL_AI_BASE_URL`, `LOCAL_AI_MODEL`,
`LOCAL_AI_CONTEXT_SIZE`, and `LOCAL_AI_LLM_TIMEOUT` (plus optional local
`LOCAL_AI_API_KEY`). They are read at startup. There is no browser model switch.
Restart ends process-local Conversation session state; it does not claim session
continuity. Model identity does not grant task, desktop, Memory, Research,
Career Forge, approval, execution, rollback, or recovery authority.

## Evidence categories and limits

Deterministic fixtures prove that two distinct configured loopback backends
receive their respective model IDs and serve the same Friday API path without
source edits or product-store migrations. The current Qwen smoke separately
proves bounded compatibility of the configured production model endpoint; it
does not restart production Friday or llama-server. A fixture pass does not
prove that an untested real model works, that another model is equally capable,
or that it is suitable for autonomous production use. ADR 0014 remains the
authority for any permanent model addition or replacement.

## Phase 17 execution record — 2026-09-28

The current Qwen `current-local` smoke passed endpoint health, bounded chat,
the Friday Conversation stream, Reasoning, and Teacher. The generation-start
telemetry was observed; usage metadata was absent and remains optional. The
smoke took 6.59 seconds. It did not restart Friday or llama-server.

An installed-model inventory found the current Qwen and other local GGUF
artifacts, including GLM-4.7-Flash and Qwen3.8-27B. No alternate was loaded:
the GTX 1070 had only 735 MiB free and host memory was already using swap, so
loading another general-purpose model was not resource-safe. No model was
downloaded. The deterministic fixture A/B restart suite remains the alternate
configuration evidence; it does not make a real-model compatibility or quality
claim.

The focused regression set passed 93 tests: 16 LocalLLM, 19 configuration, 3
role, 20 Conversation, 26 wake telemetry, and 9 model-swap qualification cases.
Final full-suite and frontend results are recorded in the Phase 17 history and
recovery handoff after publication.
