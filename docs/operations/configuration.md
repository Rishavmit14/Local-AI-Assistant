# Configuration and Compatibility

`AppConfig.from_env()` loads a fresh immutable settings snapshot. Application components accept this object explicitly, which keeps tests independent from machine state. `.env.example` lists every non-secret setting; the optional `LOCAL_AI_API_KEY` must come from a private environment source. The application does not parse `.env` files itself, so use systemd `EnvironmentFile`, shell exports, or another trusted environment loader.

## Groups

| Group | Variables | Preserved default |
|---|---|---|
| llama-server | `LOCAL_AI_BASE_URL`, `LOCAL_AI_MODEL`, `LOCAL_AI_CONTEXT_SIZE`, optional `LOCAL_AI_API_KEY` | localhost `8080`, selected Qwen GGUF metadata, 262144 context |
| runtime paths | `LOCAL_AI_VAR_DIR`, `LOCAL_AI_DOCUMENT_DIR`, `LOCAL_AI_RAG_DATA_DIR`, `LOCAL_AI_CODE_REPO_DIR`, `LOCAL_AI_CODE_INDEX_DIR`, `LOCAL_AI_PATCH_DIR` | ignored repository `var/` tree |
| embeddings | `LOCAL_AI_EMBEDDING_MODEL`, `LOCAL_AI_EMBEDDING_DEVICE`, `LOCAL_AI_EMBEDDING_BATCH_SIZE` | BGE small English v1.5, CPU, batch 32 |
| document retrieval | `LOCAL_AI_RAG_CHUNK_SIZE`, `LOCAL_AI_RAG_CHUNK_OVERLAP`, `LOCAL_AI_RAG_VECTOR_TOP_K`, `LOCAL_AI_RAG_BM25_TOP_K`, `LOCAL_AI_RAG_FINAL_TOP_K`, `LOCAL_AI_RRF_K` | 450/75 chunks, 10/10 candidates, final 5, RRF 60 |
| code retrieval | `LOCAL_AI_CODE_CHUNK_LINES`, `LOCAL_AI_CODE_CHUNK_OVERLAP`, `LOCAL_AI_CODE_VECTOR_TOP_K`, `LOCAL_AI_CODE_BM25_TOP_K`, `LOCAL_AI_CODE_FINAL_TOP_K`, `LOCAL_AI_RRF_K` | 120/20 lines, 12/12 candidates, final 6, RRF 60 |
| OCR | `LOCAL_AI_OCR_ENABLED`, `LOCAL_AI_OCR_LANGUAGE`, `LOCAL_AI_OCR_MIN_TEXT_LENGTH`, `LOCAL_AI_OCR_DPI` | enabled, English, 80 characters, 200 DPI |
| runtime/tests | `LOCAL_AI_LOG_LEVEL`, `LOCAL_AI_LOG_FORMAT`, `LOCAL_AI_COMMAND_TIMEOUT`, `LOCAL_AI_TEST_MODE` | INFO, JSON, 900 seconds, false |

`LOCAL_AI_CONTEXT_SIZE` bounds completion-token requests made through `LocalLLM` so client requests cannot exceed the configured server context. `LOCAL_AI_TEST_MODE=true` suppresses embedding progress bars while retaining the same indexing and retrieval algorithms.

Invalid integers, booleans, or overlapping chunk ranges raise `ConfigurationError` at startup. Prompts and document contents are deliberately omitted from structured logs; only operational metadata such as sizes, counts, paths, commands, and outcomes is logged.

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
