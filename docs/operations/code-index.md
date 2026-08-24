# Code Index Operations

The canonical command is `local-ai-code-rag`. `--reindex` fully rebuilds both indexes; `--refresh` updates only content/parser-changed symbol files across registered languages. Coding-agent compatibility refreshes the legacy line fallback and incrementally refreshes symbols. Generated indexes remain under `LOCAL_AI_CODE_INDEX_DIR` and must not be committed.

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
local-ai-code-rag --list-languages
local-ai-code-rag --show-capabilities rust
local-ai-code-rag --repository-map --language rust
local-ai-code-rag --search-symbols Service --language rust --kind struct
local-ai-code-rag --implementations Repository
local-ai-code-rag --inheritance crate::service::UserService
```

Exact symbols, source, parents, definitions, dependencies, callers, and callees are deterministic and do not contact Qwen. Semantic search uses local BGE. Interactive questions use Qwen only after retrieval.

Run the synthetic incremental benchmark without repository writes:

```bash
python scripts/benchmark/symbol-index.py --files 250
```

Its deterministic hash encoder measures a mixed Python/Rust/Solidity full refresh, no-change refresh, and one-file changes per language. It isolates index mechanics; it is not an embedding-quality benchmark. Parser errors remain in file metadata. Unsupported or unavailable symbol languages remain eligible for legacy multi-extension line-chunk fallback.

Language/path/kind filters are optional. Capability-aware query APIs distinguish an unsupported graph from a supported graph with no matches. Rebuild an old schema-2 index with `--refresh` after installing Stage 6 grammar dependencies; it loads compatibly and changed parser identities are refreshed into schema 3.
