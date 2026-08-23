# Local-AI-Assistant

Local-AI-Assistant is a local-first Qwen platform bootstrapped from a working MSI deployment. Stage 0 preserves its three proven workflows: an OpenAI-compatible llama.cpp client, private document RAG with OCR and hybrid FAISS/BM25 retrieval, and a Git-transactional coding assistant.

The runtime does not require Codex or paid inference tokens. The default model is `Qwen3.6-35B-A3B-UD-Q4_K_M.gguf`, served only on `127.0.0.1:8080`; Streamlit binds to `127.0.0.1:8501`.

## Bootstrap

Prerequisites are Python 3.11+, a TurboQuant-capable llama.cpp build, the local model, Tesseract English data, and Poppler utilities. On Debian/Ubuntu, the system packages are `tesseract-ocr`, `tesseract-ocr-eng`, and `poppler-utils`.

```bash
scripts/bootstrap/bootstrap.sh
cp .env.example .env
source .venv/bin/activate
```

Adjust `.env` to local paths. The repository defaults runtime state to `var/`; the existing MSI deployment may continue using its external `/AI/projects/local-ai` and `/AI/projects/code-assistant` directories during review.

Start the UI after llama-server is healthy:

```bash
streamlit run ui/streamlit/app.py \
  --server.address 127.0.0.1 \
  --server.port 8501 \
  --server.headless true \
  --browser.gatherUsageStats false
```

Index repositories placed under `LOCAL_AI_CODE_REPO_DIR`:

```bash
python -m local_ai_assistant.code_index.repository --reindex
python -m local_ai_assistant.agent.code_agent --help
```

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

Tests avoid loading the embedding model or contacting llama-server unless explicitly marked as live integration tests. See `ARCHITECTURE.md` for current boundaries, `HISTORY.md` for provenance, and `ROADMAP.md` for all later stages.

## Data and privacy

Models, documents, embeddings, FAISS indexes, generated patches, logs, virtual environments, secrets, and databases are ignored and must remain untracked. See `SECURITY.md`.
