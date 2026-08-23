# Code Index Operations

The canonical command is `local-ai-code-rag`. `--reindex` fully rebuilds both indexes; `--refresh` updates only changed Python symbol files. Coding-agent compatibility refreshes the legacy line fallback and incrementally refreshes symbols. Generated indexes remain under `LOCAL_AI_CODE_INDEX_DIR` and must not be committed.

```bash
local-ai-code-rag --reindex
local-ai-code-rag --refresh
local-ai-code-rag --repository-map
local-ai-code-rag --find-symbol login_user
local-ai-code-rag --search-symbols "verify password"
local-ai-code-rag --callers login_user
local-ai-code-rag --callees login_user
local-ai-code-rag --imports app.api
local-ai-code-rag --reverse-imports app.service
local-ai-code-rag --index-stats
```

Exact symbols, source, parents, definitions, dependencies, callers, and callees are deterministic and do not contact Qwen. Semantic search uses local BGE. Interactive questions use Qwen only after retrieval.

Run the synthetic incremental benchmark without repository writes:

```bash
python scripts/benchmark/symbol-index.py --files 250
```

Its deterministic hash encoder isolates index mechanics; it is not an embedding-quality benchmark. Parser errors remain in file metadata. Unsupported extensions are ignored by the Python symbol layer and remain eligible for legacy multi-extension line-chunk fallback.
