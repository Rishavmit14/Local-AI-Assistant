# Architecture

## Current Stage 7 system

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

`local_ai_assistant.llm` is the only model-client boundary. `rag` preserves private document retrieval. `code_index` provides one deterministic, capability-aware Tree-sitter platform for Python, Rust, Solidity, TypeScript/JavaScript, SQL, C/C++, Java, and Shell plus local hybrid retrieval. `planning` classifies requests and enforces actual patch/file/symbol scope. `execution` exposes only registered typed tools, parsed allowlisted commands, bounded observations, and atomic audit history. Qwen chooses actions but deterministic policy authorizes them. `agent` wraps mutations in the proven Git transaction.

`local_ai_assistant.ui.app` is the canonical document-chat interface and `local-ai-ui` is its configured launcher. Root files and `ui/streamlit/app.py` are thin compatibility wrappers. `config/services` contains non-installed sanitized systemd examples. Runtime documents, indexes, patches, repositories, and logs live under environment-selected directories, defaulting to ignored `var/` paths.

`local_ai_assistant.common.logging` emits structured event records for LLM requests, indexing/retrieval/OCR, commands, tests, patches, UI startup, and Git transaction outcomes. Existing CLI progress text remains intact for compatibility. Expected operational failures use the explicit `LocalAIError` hierarchy.

Coding-agent proposal mode is read-only. Applying a patch requires the isolated-branch, structural-validation, test, and rollback safeguards as one non-bypassable CLI bundle. Automatic merge additionally requires explicit approval; no default path merges an agent branch.

Stage 5 adds a plan-bound validation-intelligence layer after scoped execution. It performs structural and targeted checks, bounded scope-enforced repair, required final validation, deterministic and security review, then bounded model review. A typed final decision controls commit versus rollback; required failures and deterministic policy findings cannot be overridden. See [validation intelligence](docs/architecture/validation-intelligence.md).

Stage 6 generalizes Stage 2 through a typed language registry and adapters while retaining the shared symbols, provenance, graph, persistence, planner, ScopeGuard, and validation/review pipeline. Capability status prevents unsupported static semantics from masquerading as empty facts. See [multi-language code intelligence](docs/architecture/multi-language-code-intelligence.md).

Stage 7 indexes compact task, plan, execution, validation, review, approval, scope, and metric records in a local versioned SQLite store while preserving Stage 3–5 JSON artifacts as canonical evidence. Streamlit coding/history/metrics/system workspaces and `local-ai-history` consume this service; they do not duplicate or weaken planner, execution, approval, validation, or Git policy. See [task history and operational UI](docs/architecture/task-history.md).

The `examples/demo-app` fixture is imported without its nested Git database. It demonstrates the existing code-agent test target, not production authentication design.

## Deployment compatibility

Stages 0 through 7 do not mutate `/AI/projects/local-ai`, `/AI/projects/code-assistant`, the installed units, llama.cpp, or model storage. The packaged code uses `LOCAL_AI_*` environment variables so a reviewed deployment can point to the existing paths or new state directories. Service templates preserve the selected inference arguments and localhost binding; the UI template invokes the packaged launcher.

## Target architecture

The target remains one local platform around llama-server: chat, document and repository RAG, symbol intelligence, planner/coder/reviewer/debugger/test/security roles, controlled tools, validation and policy engines, Git transactions/worktrees, history/metrics, Friday-native integration interfaces, and user interfaces. Git diffs remain mutation truth; deterministic inspection precedes inference; risk and confidence gates constrain automation. Later stages in `ROADMAP.md` introduce these pieces sequentially rather than redesigning Stage 0.

Stage 11 may add conversational voice and a cinematic frontend only above the native API/event boundary: voice/UI → Friday native API/events → existing planner, risk, approval, executor, validator, and audit services. It receives no privileged direct shell, filesystem, Git, model-tool, or approval-bypass path. Streamlit remains the engineering/admin surface and the CLI remains the recovery/power-user surface.

## Trust boundaries

- Model output, uploaded documents, indexed repositories, and shell output are untrusted.
- localhost binding is the default network boundary; remote exposure needs authentication and TLS.
- private/generated data never enters Git.
- high-risk production, security, payment, smart-contract, migration, and deployment changes always require explicit human review.
