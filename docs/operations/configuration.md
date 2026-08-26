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
