# Architecture

## Current Stage 3 system

```text
Qwen GGUF
   │
TurboQuant llama-server (127.0.0.1:8080)
   │ OpenAI-compatible API
   ├── LocalLLM
   │    └── document RAG ── Streamlit (127.0.0.1:8501)
   └── code RAG ── transactional patch agent ── target Git repository
```

`local_ai_assistant.common.config` is the typed configuration boundary. Frozen dataclasses represent llama-server metadata, runtime paths, embedding, document/code retrieval, OCR, UI, and runtime/test settings. Components accept an `AppConfig` snapshot and injectable model/embedder dependencies; environment variables remain the deployment interface.

`local_ai_assistant.llm` is the only model-client boundary. `rag` preserves private document retrieval. `code_index` provides deterministic Tree-sitter Python facts and local hybrid retrieval. `planning` classifies requests, builds affected scope from Stage 2 evidence, asks Qwen only to organize bounded evidence into typed JSON, and deterministically validates scope, risk, confidence, and approval before patch generation. `agent` preserves every Stage 1 Git transaction safeguard after the planning gate.

`local_ai_assistant.ui.app` is the canonical document-chat interface and `local-ai-ui` is its configured launcher. Root files and `ui/streamlit/app.py` are thin compatibility wrappers. `config/services` contains non-installed sanitized systemd examples. Runtime documents, indexes, patches, repositories, and logs live under environment-selected directories, defaulting to ignored `var/` paths.

`local_ai_assistant.common.logging` emits structured event records for LLM requests, indexing/retrieval/OCR, commands, tests, patches, UI startup, and Git transaction outcomes. Existing CLI progress text remains intact for compatibility. Expected operational failures use the explicit `LocalAIError` hierarchy.

Coding-agent proposal mode is read-only. Applying a patch requires the isolated-branch, structural-validation, test, and rollback safeguards as one non-bypassable CLI bundle. Automatic merge additionally requires explicit approval; no default path merges an agent branch.

The `examples/demo-app` fixture is imported without its nested Git database. It demonstrates the existing code-agent test target, not production authentication design.

## Deployment compatibility

Stages 0 through 3 do not mutate `/AI/projects/local-ai`, `/AI/projects/code-assistant`, the installed units, llama.cpp, or model storage. The packaged code uses `LOCAL_AI_*` environment variables so a reviewed deployment can point to the existing paths or new state directories. Service templates preserve the selected inference arguments and localhost binding; the UI template invokes the packaged launcher.

## Target architecture

The target remains one local platform around llama-server: chat, document and repository RAG, symbol intelligence, planner/coder/reviewer/debugger/test/security roles, controlled tools, validation and policy engines, Git transactions/worktrees, history/metrics, and the Streamlit UI. Git diffs remain mutation truth; deterministic inspection precedes inference; risk and confidence gates constrain automation. Later stages in `ROADMAP.md` introduce these pieces sequentially rather than redesigning Stage 0.

## Trust boundaries

- Model output, uploaded documents, indexed repositories, and shell output are untrusted.
- localhost binding is the default network boundary; remote exposure needs authentication and TLS.
- private/generated data never enters Git.
- high-risk production, security, payment, smart-contract, migration, and deployment changes always require explicit human review.
