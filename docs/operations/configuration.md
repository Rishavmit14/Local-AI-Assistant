# Configuration and Compatibility

`AppConfig.from_env()` loads a fresh immutable settings snapshot. Application components accept this object explicitly, which keeps tests independent from machine state. `.env.example` lists every non-secret setting; the optional `LOCAL_AI_API_KEY` must come from a private environment source. The application does not parse `.env` files itself, so use systemd `EnvironmentFile`, shell exports, or another trusted environment loader.

## Groups

| Group | Variables | Preserved default |
|---|---|---|
| local model boundary | `LOCAL_AI_BASE_URL`, `LOCAL_AI_MODEL`, `LOCAL_AI_CONTEXT_SIZE`, `LOCAL_AI_LLM_TIMEOUT`, optional `LOCAL_AI_API_KEY` | loopback `8080`, selected Qwen GGUF, 262144 context, 120 second timeout |
| local visual cortex | `LOCAL_AI_VISION_BASE_URL`, `LOCAL_AI_VISION_MODEL`, private `LOCAL_AI_VISION_API_KEY`, `LOCAL_AI_VISION_TIMEOUT`, `LOCAL_AI_VISION_MAX_IMAGE_EDGE`, `LOCAL_AI_VISION_MAX_OUTPUT` | disabled; when enabled, authenticated loopback `8781`, Qwen2.5-VL 3B, 150 seconds, 1024 pixels, 2000 characters |
| runtime paths | `LOCAL_AI_VAR_DIR`, `LOCAL_AI_DOCUMENT_DIR`, `LOCAL_AI_RAG_DATA_DIR`, `LOCAL_AI_CODE_REPO_DIR`, `LOCAL_AI_CODE_INDEX_DIR`, `LOCAL_AI_PATCH_DIR` | ignored repository `var/` tree |
| embeddings | `LOCAL_AI_EMBEDDING_MODEL`, `LOCAL_AI_EMBEDDING_DEVICE`, `LOCAL_AI_EMBEDDING_BATCH_SIZE` | BGE small English v1.5, CPU, batch 32 |
| document retrieval | `LOCAL_AI_RAG_CHUNK_SIZE`, `LOCAL_AI_RAG_CHUNK_OVERLAP`, `LOCAL_AI_RAG_VECTOR_TOP_K`, `LOCAL_AI_RAG_BM25_TOP_K`, `LOCAL_AI_RAG_FINAL_TOP_K`, `LOCAL_AI_RRF_K` | 450/75 chunks, 10/10 candidates, final 5, RRF 60 |
| code retrieval | `LOCAL_AI_CODE_CHUNK_LINES`, `LOCAL_AI_CODE_CHUNK_OVERLAP`, `LOCAL_AI_CODE_VECTOR_TOP_K`, `LOCAL_AI_CODE_BM25_TOP_K`, `LOCAL_AI_CODE_FINAL_TOP_K`, `LOCAL_AI_RRF_K` | 120/20 lines, 12/12 candidates, final 6, RRF 60 |
| OCR | `LOCAL_AI_OCR_ENABLED`, `LOCAL_AI_OCR_LANGUAGE`, `LOCAL_AI_OCR_MIN_TEXT_LENGTH`, `LOCAL_AI_OCR_DPI` | enabled, English, 80 characters, 200 DPI |
| runtime/tests | `LOCAL_AI_LOG_LEVEL`, `LOCAL_AI_LOG_FORMAT`, `LOCAL_AI_COMMAND_TIMEOUT`, `LOCAL_AI_TEST_MODE` | INFO, JSON, 900 seconds, false |
| authenticated gateway/GitHub | `LOCAL_AI_GATEWAY_ENABLED`, `LOCAL_AI_GATEWAY_TOKEN_HASH`, `LOCAL_AI_GATEWAY_SCOPES`, `LOCAL_AI_GITHUB_ENABLED`, `LOCAL_AI_GITHUB_API_HOST`, exact `LOCAL_AI_GITHUB_ALLOWED_REPOSITORY`, `LOCAL_AI_GITHUB_PUBLICATION_PURPOSE`, `LOCAL_AI_GITHUB_CREDENTIAL_REF` | disabled, loopback-only, no publication credential |

The general-purpose model uses one local OpenAI-compatible chat-completions boundary. `LOCAL_AI_BASE_URL` must be HTTP(S) on a loopback host (`localhost`, `127.0.0.0/8`, or `::1`); URL credentials, query strings, fragments, remote hosts, and empty values fail at configuration time. The HTTP client ignores proxy environment variables, performs no retries, and does not fall back to a cloud or alternate model. Configure `LOCAL_AI_BASE_URL`, `LOCAL_AI_MODEL`, `LOCAL_AI_CONTEXT_SIZE`, and `LOCAL_AI_LLM_TIMEOUT` before starting Friday; changing these values takes effect on the next process start. There is no browser model switch or live hot swap. `LOCAL_AI_API_KEY` defaults to the local compatibility value `local` and is never included in model status or qualification reports.

Ordinary voice screen questions can optionally use a separate local visual cortex. It is disabled unless `LOCAL_AI_VISION_BASE_URL` is set; the URL must be plain HTTP on loopback at exactly `/v1`, and enabling it requires a private printable `LOCAL_AI_VISION_API_KEY` of at least 32 characters. The client ignores proxies, authenticates `/props` and chat requests, checks that the server advertises image support and the configured model alias, and never falls back to a remote model. Keep the bearer key in a user-private environment file (mode `0600`), never in `.env.example`, Git, logs, or the Qwen prompt. The reference llama.cpp unit is `config/services/friday-vision-cortex.service.example`; it binds `127.0.0.1`, reads a separate mode-`0600` API-key file, and uses the model GGUF plus its `mmproj` projector. The CPU-only model service stays warm while pixel inference runs only for a routed visual question. Its image-token cap is 512 on the qualified host; changing service or environment settings requires restarting Friday and the visual-cortex unit. A same-frame 1024px/512-token pass took 29.2s with all chart labels; the prior 768px/1024-minimum run took 73.7s but missed labels. Since both settings changed, the comparison does not isolate the token-cap effect. Full physical playback still measured 102.3s, so interactive latency remains a known limitation.

`LOCAL_AI_CONTEXT_SIZE` bounds requested completion tokens made through `LocalLLM`; it does not claim to measure tokenizer-specific prompt usage. The model identifier is configuration, not canonical product state, and changing it requires no database migration. `LOCAL_AI_TEST_MODE=true` suppresses embedding progress bars while retaining the same indexing and retrieval algorithms.

The supported cognition contract is local chat-completions with system/user text messages, configured model ID, temperature, and bounded `max_tokens`; chat returns text and streaming yields non-empty delta text. Empty choices/deltas and absent usage metadata are tolerated; transport, timeout, server, malformed-response, and interrupted-stream failures become `LLMError`. Function calling, tools, multimodal input, structured JSON mode, provider reasoning fields, and tokenizer-specific APIs are not part of the required contract. A passing contract qualification proves technical boundary compatibility only; it does not establish quality parity or approve a permanent model replacement. See `scripts/qualification/qualify_model_swap.py` for the repeatable fixture/current-local procedure.

Invalid integers, booleans, or overlapping chunk ranges raise `ConfigurationError` at startup. Prompts and document contents are deliberately omitted from structured logs; only operational metadata such as sizes, counts, paths, commands, and outcomes is logged.

The preferred server-side publication credential reference is
`LOCAL_AI_GITHUB_CREDENTIAL_REF=gh-keyring:github.com:ACCOUNT`, which resolves
the GitHub CLI credential from the owner's OS keyring at Friday startup and
verifies `/user` identity. The token is held only in server memory. This mode
also requires `github_write`, an exact `OWNER/REPOSITORY` allowlist, and the
`learner_project_public_proof` purpose; the transport is restricted to that
single mapped repository. The legacy `LOCAL_AI_GITHUB_TOKEN` remains supported
for protected deployments but should not be used where a keyring reference is
available. Credentials are never written to Friday configuration, onboarding
state, task history, the Learner Twin, logs, or the browser.

## MSI migration

The installed host units and old working directories are not modified automatically. `config/deployment/msi.env.example` documents the retained runtime paths needed by the packaged backend. Repository-local `var/` remains the safe default so an unconfigured checkout cannot write into the working deployment. `scripts/install/render-systemd.sh` now renders the llama-server unit only; inspect `var/systemd` before installing anything.

Compatibility entry points remain:

- imports from `local_llm`, `rag`, `code_rag`, and `code_agent`
- `python code_rag.py --reindex` and `python code_agent.py --help`

The legacy Streamlit commands and `local-ai-ui` launcher were intentionally removed in Stage 11. Canonical backend commands include `local-ai-chat`, `local-ai-code-rag`, `local-ai-code-agent`, `local-ai-plan`, `local-ai-execute`, `local-ai-validate`, `local-ai-history`, `local-ai-isolation`, and `local-ai-gateway`.


## Friday physical voice levels

AEC qualification depends on undistorted microphone and speaker audio. During
Stage 12D diagnosis on the MSI, microphone volume 1.0 mapped to hardware capture
+30 dB and the speaker was at 1.29. Recorded physical input clipped during
playback and stop-command transcription failed. Reducing microphone volume to
0.5 (hardware capture +11.25 dB) and speaker volume to 1.0 removed clipping in
that diagnostic recording and restored exact stop recognition.

These are machine-specific user-session levels, not universal defaults or values
Friday enforces at startup. Keep a backup of the current source/sink and mixer
levels before adjustment, verify the selected physical devices and unclipped
recorded input, and requalify wake and AEC interruption on the actual hardware.
Do not compensate for damaged audio with fuzzy stop matching or extra ASR aliases.
The raw wake microphone and the AEC-only barge-in topology stay unchanged.

## Stage 12E recovery diagnostics

Stage 12E exposes read-only `/api/v1/voice/health` on the existing localhost
presentation port. Inspect managed status together with capture phase and thread
liveness; `/health` alone does not prove microphone readiness. Retry counts and
last error type survive successful recovery within a process. Journal stages
`WAKE_CAPTURE_ERROR` and `WAKE_CAPTURE_RETRY` show failures and scheduled delays.

Production `WAKE_AUDIO_CONFIG` sets `read_timeout_seconds=2.0` for raw wake and
fresh follow-up ALSA streams. Generic audio callers retain the optional unbounded
default. Retry delay is 1/2/4/8/16/30 seconds, capped at 30, resetting after a
60-second run; shutdown interrupts the wait. No systemd-unit or host audio-level
change is required. Stage 12E qualification proved both recorder failure modes
and fresh wake-worker recreation. Voice actions must follow prepared nonblocking
evidence cursors; agent-run fault tests must target only the verified service
child PID.

Managed voice cleanup starts at Uvicorn's first exit signal. A normal controlled
restart should contain neither `WAKE_CAPTURE_ERROR` nor `WAKE_CAPTURE_RETRY`;
either entry during shutdown fails the lifecycle gate.

## Stage 12F interaction ownership

`/api/v1/interaction/state` is a read-only localhost projection of the active
interaction (`busy`, `owner`, and monotonic `generation`). It does not grant
execution authority. A presentation stream holds `owner=presentation` and pauses
raw wake capture; an overlapping request returns HTTP 409. A wake voice turn
holds `owner=voice` and likewise rejects presentation with HTTP 409.

On HTTP disconnect, Friday releases an unstarted response immediately. If a
synchronous local-model read has already begun, the presentation lease and wake
pause remain until that read reaches a safe cancellation boundary; the runtime
then reports `cancelled` before later work resets it to idle. This is intentional
fail-closed microphone ownership, not a hung wake service.

## Stage 12G barge-in monitoring

Piper first audio may take longer than a short response deadline. Friday waits a
bounded 30 seconds before declaring that barge monitoring never armed. During
long playback, an explicit monitor timeout re-arms another bounded pass. Inspect
`voice.speech.interrupted` or `voice.speech.completed` metadata for the
privacy-safe `barge_in_outcome`, monitor pass count, elapsed time, and maximum
speech probability; no microphone audio or transcript is retained by this data.
