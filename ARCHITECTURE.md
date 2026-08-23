# Architecture

## Current Stage 0 system

```text
Qwen GGUF
   │
TurboQuant llama-server (127.0.0.1:8080)
   │ OpenAI-compatible API
   ├── LocalLLM
   │    └── document RAG ── Streamlit (127.0.0.1:8501)
   └── code RAG ── transactional patch agent ── target Git repository
```

`local_ai_assistant.llm` is the only model-client boundary. `rag` extracts supported documents, selectively OCRs PDFs, chunks with the embedding tokenizer, and combines FAISS and BM25 ranks with RRF. `code_index` applies the same hybrid strategy to line-based source chunks. `agent` treats model diffs as untrusted: it checks and optionally applies them, validates Python structure, detects tests, permits one repair, and can transact on an isolated branch with commit or rollback.

`ui/streamlit/app.py` is the document-chat interface. `config/services` contains non-installed sanitized systemd examples. Runtime documents, indexes, patches, repositories, and logs live under environment-selected directories, defaulting to ignored `var/` paths.

The `examples/demo-app` fixture is imported without its nested Git database. It demonstrates the existing code-agent test target, not production authentication design.

## Deployment compatibility

Stage 0 does not mutate `/AI/projects/local-ai`, `/AI/projects/code-assistant`, the installed units, llama.cpp, or model storage. The packaged code uses `LOCAL_AI_*` environment variables so a reviewed deployment can point to the existing paths or new state directories. Service templates preserve the selected inference arguments and localhost binding.

## Target architecture

The target remains one local platform around llama-server: chat, document and repository RAG, symbol intelligence, planner/coder/reviewer/debugger/test/security roles, controlled tools, validation and policy engines, Git transactions/worktrees, history/metrics, and the Streamlit UI. Git diffs remain mutation truth; deterministic inspection precedes inference; risk and confidence gates constrain automation. Later stages in `ROADMAP.md` introduce these pieces sequentially rather than redesigning Stage 0.

## Trust boundaries

- Model output, uploaded documents, indexed repositories, and shell output are untrusted.
- localhost binding is the default network boundary; remote exposure needs authentication and TLS.
- private/generated data never enters Git.
- high-risk production, security, payment, smart-contract, migration, and deployment changes always require explicit human review.
