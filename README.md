# Local-AI-Assistant

Local-AI-Assistant is a local-first Qwen platform combining an OpenAI-compatible llama.cpp client, private document RAG, deterministic multi-language Tree-sitter code intelligence, model-assisted but deterministically governed planning, and a Git-transactional coding assistant.

The runtime does not require Codex or paid inference tokens. The default model is `Qwen3.6-35B-A3B-UD-Q4_K_M.gguf`, served only on `127.0.0.1:8080`; Streamlit binds to `127.0.0.1:8501`.

## Bootstrap

Prerequisites are Python 3.11+, a TurboQuant-capable llama.cpp build, the local model, Tesseract English data, and Poppler utilities. On Debian/Ubuntu, the system packages are `tesseract-ocr`, `tesseract-ocr-eng`, and `poppler-utils`.

```bash
scripts/bootstrap/bootstrap.sh
cp .env.example .env
source .venv/bin/activate
```

Adjust `.env` to local paths. The repository defaults runtime state to `var/`; the existing MSI deployment may continue using its external `/AI/projects/local-ai` and `/AI/projects/code-assistant` directories during migration. See [configuration operations](docs/operations/configuration.md) for every setting.

Start the packaged UI after llama-server is healthy:

```bash
local-ai-ui
```

The Stage 0 command `streamlit run ui/streamlit/app.py` and the historical root names `app.py`, `local_llm.py`, `rag.py`, `code_rag.py`, and `code_agent.py` remain compatibility wrappers.

Index repositories placed under `LOCAL_AI_CODE_REPO_DIR`:

```bash
python -m local_ai_assistant.code_index.repository --reindex
local-ai-code-rag --repository-map
local-ai-code-rag --find-symbol login_user
local-ai-code-rag --list-languages
local-ai-code-rag --show-capabilities rust
local-ai-code-rag --search-symbols UserService --language rust --kind struct
local-ai-code-agent --help
local-ai-history --help
local-ai-plan --help
```

Tree-sitter/static analysis provides deterministic symbols and graphs. Local BGE + FAISS/BM25/RRF provides semantic retrieval, and Qwen3.6 reasons over that evidence. The original line-chunk index remains fallback. See [code intelligence architecture](docs/architecture/code-intelligence.md) and [index operations](docs/operations/code-index.md).

Stage 6 supports Python, Rust, Solidity, TypeScript/JavaScript, SQL, C/C++, Java, and Shell through one capability-aware index. Static limitations are explicit; an unsupported call/reference capability is not reported as “no results.” See the [support matrix](docs/architecture/multi-language-code-intelligence.md).

Stage 7 adds a local SQLite task history, deterministic audit/search/metrics APIs, `local-ai-history`, and Streamlit Coding, History, Metrics, and System workspaces. Existing JSON artifacts remain canonical and can be imported idempotently. See [task history architecture](docs/architecture/task-history.md) and [history operations](docs/operations/task-history.md).

Generate a no-edit plan with `local-ai-code-agent REPO REQUEST --plan-only` or use the dedicated [`local-ai-plan` workflow](docs/operations/planner.md). Deterministic validation and risk policy gate patch generation; high/critical approval is bound to the exact printed plan token and cannot silently transfer to a changed plan.

Stage 5 validation is available through `local-ai-validate`. It detects configured validators, selects evidence-backed targeted tests, runs required final checks, performs deterministic/security review, and produces an auditable final decision. In tool-loop apply mode this quality gate runs before commit; failure rolls back through the existing Git transaction. See [validation operations](docs/operations/validation.md).

Run the bounded tool workflow with `local-ai-code-agent REPO REQUEST --tool-loop` (dry run) or the existing complete `--apply --branch --test --validate --rollback-on-fail` safety bundle. See [controlled tool execution](docs/operations/tool-execution.md). Actual patch and post-apply Git scope are deterministic hard gates.

## Services

The files in `config/services/` are sanitized templates. Render machine-specific units without installing them:

```bash
scripts/install/render-systemd.sh \
  "$USER" "$PWD" /path/to/llama.cpp /path/to/model.gguf
```

Review the generated files in `var/systemd/` before any privileged installation. Existing services are deliberately untouched by Stage 0.

## Testing

```bash
python -m pytest
scripts/maintenance/verify-repository.sh
```

Stage 8 autonomous mutation uses task-scoped Git worktrees and capability-aware sandbox policy. Inspect the local boundary with `local-ai-isolation capabilities`; use `local-ai-isolation recovery` after an interrupted run. The secure default requires strong filesystem/network isolation and blocks execution if the host cannot provide it. See [isolation operations](docs/operations/isolation.md).

Tests use dependency injection to avoid loading the embedding model or contacting llama-server unless explicitly marked as live integration tests. Structured operational logs default to JSON on stderr; set `LOCAL_AI_LOG_FORMAT=text` for human-readable output. See `ARCHITECTURE.md` for current boundaries, `HISTORY.md` for provenance, and `ROADMAP.md` for later stages.

## Data and privacy

Models, documents, embeddings, FAISS indexes, generated patches, logs, virtual environments, secrets, and databases are ignored and must remain untracked. See `SECURITY.md`.
