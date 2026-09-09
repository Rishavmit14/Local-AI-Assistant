# Local-AI-Assistant — Canonical Codex Handoff

> Purpose: canonical engineering handoff from the ChatGPT design/build conversation into Codex.
> Repository: https://github.com/Rishavmit14/Local-AI-Assistant
> Target machine: MSI GT62VR 7RE, Ubuntu 26.04
> Constraint: final runtime remains local-first and usable without paid inference/API tokens.
> Product: Friday — Local Personal Cognitive Operating System.
> Intelligence policy: ADR 0014 Local Intelligence Sovereignty; current Qwen is
> the sole general-purpose reasoning model, with sequential roles and specialized
> local speech/embedding/OCR/vision/image components as justified.

Fresh sessions must read the durable continuous-autonomy policy in `AGENTS.md`
and the **Current cross-session handoff and Git policy** section below. Historical
bootstrap instructions describe completed work; use current recovery refs and
`ROADMAP.md` to continue automatically after each accepted checkpoint.

## 0. Non-negotiable project rules

1. Bootstrap from the actual working MSI files before refactoring; do not recreate existing code from memory when the source exists.
2. Preserve working behavior while reorganizing.
3. Keep the local Qwen model as the default runtime model.
4. Codex is the engineering agent used to build the project; Codex must not become a required runtime dependency.
5. Every coding-agent mutation stays behind Git isolation, deterministic patch validation, structural/static validation, tests, bounded repair, and rollback.
6. Prefer deterministic tools over LLM inference for facts discoverable from code, Git, parsers, tests, or build systems.
7. All agent actions must be auditable.
8. Never commit secrets, GGUF model binaries, vector indexes, private documents, embeddings, virtualenvs, caches, generated logs, or temporary databases.
9. Do not silently drop roadmap features. Codex may regroup/reorder them for engineering reasons, but ROADMAP.md must retain every capability and status.
10. Work milestone-by-milestone; do not collapse the roadmap into one giant patch.

## 1. Hardware and OS

Machine:
- MSI GT62VR 7RE / Dominator Pro
- Intel Core i7-7700HQ, 4C/8T
- 32 GB DDR4
- NVIDIA GTX 1070 Mobile, 8 GB VRAM
- 119 GB SSD for OS
- ~1 TB HDD mounted at `/AI`
- Ubuntu 26.04
- NVIDIA driver 580.173.02
- CUDA driver reports CUDA 13.0
- GCC 15.2.0
- g++ 15.2.0
- CMake 4.2.3

Large-data layout:
```text
/AI/
├── backups/
├── cache/
├── datasets/
├── embeddings/
├── logs/
├── models/
├── outputs/
├── projects/
├── runs/
└── tmp/
```

## 2. Model selection and benchmarking

Selected runtime model:
```text
Qwen3.6-35B-A3B-UD-Q4_K_M.gguf
```

Local path:
```text
/AI/models/qwen3.6-q4/Qwen3.6-35B-A3B-UD-Q4_K_M.gguf
```

Approximate characteristics:
- ~22.1 GB
- ~34.66B parameters
- MoE model
- Q4_K_M quantization

Selection goals:
- strongest practical local coding/reasoning quality on this machine
- no paid inference tokens/subscriptions required at runtime
- workable CPU/RAM offload with GTX 1070 8 GB

### llama.cpp / TurboQuant
Source tree:
```text
~/src/llama-cpp-turboquant
```

Known build metadata:
- branch: `feature/turboquant-kv-cache`
- commit: `e30664a`
- version string seen: `b1-e30664a`

Selected inference profile:
```bash
-ngl 999
-ncmoe 34
-c 262144
-b 128
-ub 32
-t 4
-tb 4
-fa off
-ctk turbo4
-ctv turbo3
--reasoning off
```

Important findings:
- larger `-ncmoe` places more MoE weights on CPU and frees VRAM.
- c262144 + ncmoe31: OOM.
- c262144 + ncmoe35: worked, ~6.5 GB VRAM, prompt ~41.7 t/s, generation ~23.4 t/s on tiny prompt.
- c262144 + ncmoe34: selected, ~7.0 GB VRAM, prompt ~42.5 t/s, generation ~23.9 t/s on tiny prompt.
- c163840 + ncmoe31: ~47.5 prompt t/s, ~24.6 gen t/s, ~7.8 GB VRAM.
- API short-prompt generation later measured ~24.03 t/s.
- `--mlock` made performance worse; do not use it by default.
- Turbo KV `turbo4/turbo3` was key to the very-large-context configuration.
- server can auto-enable flash attention for Turbo KV even if CLI says `-fa off`.
- warning `fit could not prove a viable placement; restoring the pre-fit parameters` can be non-fatal.

### Long-context tests
Known artifacts/observations:
- `/AI/datasets/context_256k.txt`: 15,318,000 bytes, ~3,114,001 tokens.
- generated ~250K-token corpus: 1,229,768 bytes, ~250,005 tokens.
- long retrieval marker: `ORION-73921`.
- full 242,312-token prefill test was stopped due runtime cost.
- successful ~4K actual-context retrieval of ORION-73921; prompt ~26.1 t/s.
- successful ~8K actual-context retrieval; prompt ~29.6 t/s.
- capacity/allocation testing was considered sufficient for now; full 256K practical fill can be revisited later.

## 3. Persistent local model API

Working manual command:
```bash
cd ~/src/llama-cpp-turboquant

./build/bin/llama-server \
  -m /AI/models/qwen3.6-q4/Qwen3.6-35B-A3B-UD-Q4_K_M.gguf \
  -ngl 999 \
  -ncmoe 34 \
  -c 262144 \
  -b 128 \
  -ub 32 \
  -t 4 \
  -tb 4 \
  -fa off \
  -ctk turbo4 \
  -ctv turbo3 \
  --reasoning off \
  --host 127.0.0.1 \
  --port 8080
```

Known behavior:
- localhost-only: `127.0.0.1:8080`
- OpenAI-compatible API
- `/health` -> `{"status":"ok"}`
- `/v1/models` reports model path and `n_ctx=262144`
- server log observed: `n_slots=4`, `n_ctx_slot=262144`, `kv_unified=true`

## 4. Python local LLM layer

Project:
```text
/AI/projects/local-ai
```

Virtualenv:
```text
/AI/projects/local-ai/.venv
```

Important files:
- `/AI/projects/local-ai/test_qwen.py`
- `/AI/projects/local-ai/local_llm.py`

Client pattern:
```python
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:8080/v1", api_key="local")
```

`LocalLLM` exposes:
- `.chat()`
- `.stream_chat()`

## 5. systemd deployment

### Model service
Source of truth on MSI:
```text
/etc/systemd/system/llama-qwen.service
```
Expected behavior:
- runs as `kumar-rishav`
- starts llama-server with selected profile
- restart on failure
- enabled at boot
- reboot-tested successfully

### Historical UI service
Source of truth:
```text
/etc/systemd/system/local-ai-ui.service
```
Historical behavior:
- Required/started after `llama-qwen.service`
- ran as `kumar-rishav`
- used WorkingDirectory `/AI/projects/local-ai`
- started the former Streamlit interface with:
```text
/AI/projects/local-ai/.venv/bin/streamlit run /AI/projects/local-ai/app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false
```
- was reboot-tested successfully

This service is retained here only as historical machine-state documentation. The repository-side Streamlit product UI, launcher, dependency, configuration, compatibility wrappers, and service template are removed in Stage 11. The new Friday interface must not depend on this service.

Historical UI endpoint:
```text
http://127.0.0.1:8501
```

## 6. Document RAG

Main file:
```text
/AI/projects/local-ai/rag.py
```

Installed Python dependencies include:
- sentence-transformers
- faiss-cpu
- numpy
- pypdf
- python-docx
- rank-bm25
- pytesseract
- pdf2image
- pillow

System packages:
- tesseract-ocr
- tesseract-ocr-eng
- poppler-utils

Embedding model:
```text
BAAI/bge-small-en-v1.5
```
- CPU embeddings
- 384 dimensions
- public model; HF token not required

Supported ingestion:
- TXT
- MD
- PDF
- DOCX

Chunking:
- embedding-tokenizer based
- chunk size 450 tokens
- overlap 75

Persistent data:
```text
/AI/projects/local-ai/rag_data/
├── index.faiss
├── chunks.json
└── manifest.json
```

Features:
- SHA256 document change detection
- FAISS semantic retrieval
- BM25 lexical retrieval
- RRF fusion (`RRF_K=60`)
- small lexical overlap boost
- vector candidates 10
- BM25 candidates 10
- final top 5 chunks
- metadata for source/page/chunk
- refusal when answer is absent from supplied docs

Validated document codes included:
- `AURORA-7319`
- `TITAN-8080`

### OCR
- native PDF extraction first
- selectively OCR low-text pages
- English
- OCR minimum text length ~80
- DPI 200
- metadata: `extraction_method = native|ocr`

## 7. Historical Streamlit UI

File:
```text
/AI/projects/local-ai/app.py
```

Features of the historical interface:
- Local Qwen chat
- document upload (PDF/DOCX/TXT/MD)
- Save & Reindex
- indexed-document list
- force reindex
- clear chat
- stats (documents/chunks/FAISS/OCR)
- RAG-backed chat
- source details including page, extraction method, vector rank, BM25 rank, hybrid score

This implementation is historical only. Stage 11 removes the repository-side Streamlit presentation layer completely. Reusable non-presentation behavior is preserved behind Friday's neutral interface/services and the replacement product UI is built fresh from scratch.

## 8. Code assistant project

Root:
```text
/AI/projects/code-assistant
```

Important files:
```text
/AI/projects/code-assistant/
├── code_rag.py
├── code_agent.py
├── index/
├── patches/
└── repos/
    └── demo-app/
```

Demo app:
```text
/AI/projects/code-assistant/repos/demo-app
```

Contains:
```text
app/
├── api.py
├── auth.py
├── database.py
├── main.py
└── service.py

tests/
├── conftest.py
├── test_api.py
└── test_registration.py

README.md
.gitignore
```

Known behaviors:
- SHA256 password hashing
- verify password
- token create/verify
- SQLite user storage
- registration/login
- failed login returns 401
- username normalization: trim + lowercase
- pytest tmp DB isolation
- current baseline: 2 tests passing

## 9. Code RAG

File:
```text
/AI/projects/code-assistant/code_rag.py
```

Extensions include Python, Rust, Solidity, JS/JSX, TS/TSX, Java, C/C++, Go, SQL, shell, TOML, YAML, JSON, Markdown.

Ignored directories should include:
`.git`, `node_modules`, `target`, `dist`, `build`, `.next`, `.venv`, `venv`, `__pycache__`, `.pytest_cache`, `coverage`.

Current design:
- line chunks ~120 lines
- overlap ~20 lines
- BGE embeddings
- FAISS + BM25 + RRF
- persistent index/chunks/manifest
- full repo reindex currently acceptable

Known limitation: chunk-based, not symbol-aware yet.

## 10. Coding agent — current capabilities

File:
```text
/AI/projects/code-assistant/code_agent.py
```

Current CLI options evolved to include:
- `--apply`
- `--test`
- `--repair`
- `--branch`
- `--auto-commit`
- `--rollback-on-fail`
- `--validate`

Current capabilities:
- repo selection
- RAG retrieval
- unified Git diff generation by Qwen
- model path normalization
- `git apply --check --recount`
- explicit apply
- fresh reindex before patch generation
- reindex immediately after edits
- dirty-tree protection
- test detection
- one optional repair attempt
- exact failure-file context for repair
- Python AST structural validation
- isolated `agent/<slug>-<timestamp>` branch
- automatic commit on success
- rollback to starting commit on failure
- switch back to original branch
- delete failed agent branch

Test detection currently includes:
- Python: `python -m pytest -q`
- Rust: `cargo test`
- Node: `npm test -- --runInBand`

Python structural validation checks:
- syntax
- duplicate top-level functions
- duplicate top-level classes

Repair-prompt safeguards include:
- exact current file contents from traceback/changed files
- current Git diff
- test failure output
- additional retrieved context
- never import/call nonexistent symbols unless same patch defines them
- never replace real implementations with `pass`/TODO/fake stubs
- repair patch must apply to current working tree

## 11. Safety lessons from failures

### Hallucinated helper
Qwen imported nonexistent `normalize_username` from `database.py`; tests caught ImportError.

### Dangerous repair hallucination
Qwen attempted a repair containing fake `pass` implementations in `database.py`; `git apply --check` rejected it.

### Duplicate function
A docstring task produced duplicate `normalize_username()` definitions. Python and pytest still passed due name shadowing. This motivated structural AST validation.

### Stale index
A later patch targeted an old duplicate-function version; `git apply --check` rejected it. This motivated fresh reindex before every proposal.

### Persistent SQLite state
Repeated tests collided with `/tmp/demo_app.db`; fixed with `set_db_path()` and pytest `tmp_path` isolation.

## 12. Git transaction behavior — proven

### Success path
```text
master
→ agent branch
→ fresh index
→ patch
→ git apply --check
→ apply
→ structural validation PASS
→ pytest PASS
→ automatic commit
→ retain successful agent branch for review/merge
```

Known successful commit example:
```text
4ee22a0 agent: Add a concise docstring to login_user...
```
Then fast-forward merged into master.

### Failure path
Intentional task changed failed login status 401 → 200.
Observed:
- agent branch created
- patch validated/applied
- structural validation PASS
- pytest FAIL (`200 != 401`)
- repair disabled
- rollback executed
- reset to starting commit
- switched to original branch
- failed temporary branch deleted

This transaction system is a foundational invariant.

## 13. Target repository architecture

Codex should bootstrap/refactor toward this structure without breaking working local deployment unnecessarily:

```text
Local-AI-Assistant/
├── AGENTS.md
├── CODEX_HANDOFF.md
├── README.md
├── ARCHITECTURE.md
├── ROADMAP.md
├── HISTORY.md
├── SECURITY.md
├── CONTRIBUTING.md
├── LICENSE
├── .gitignore
├── .env.example
├── pyproject.toml
├── requirements/
│   ├── base.txt
│   ├── rag.txt
│   ├── coding-agent.txt
│   └── dev.txt
├── config/
│   ├── model/
│   │   └── qwen3.6-35b-a3b-q4.yaml
│   ├── services/
│   │   └── llama-qwen.service.example
│   ├── validation/
│   │   └── policies.yaml
│   └── languages/
│       ├── python.yaml
│       ├── rust.yaml
│       ├── solidity.yaml
│       └── typescript.yaml
├── docs/
│   ├── history/
│   ├── architecture/
│   ├── operations/
│   └── decisions/
├── src/
│   └── local_ai_assistant/
│       ├── llm/
│       ├── rag/
│       ├── code_index/
│       ├── agent/
│       ├── validation/
│       ├── tools/
│       ├── git/
│       ├── security/
│       ├── tasks/
│       ├── interface/
│       └── common/
├── scripts/
│   ├── bootstrap/
│   ├── benchmark/
│   ├── install/
│   └── maintenance/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   └── fixtures/
├── examples/
│   └── demo-app/
├── var/
│   └── .gitkeep
└── .github/
    ├── workflows/
    ├── ISSUE_TEMPLATE/
    └── pull_request_template.md
```

## 14. Complete remaining feature roadmap — no silent omissions

### A. Finish transactional Git foundation
- final success/failure verification
- transaction summary
- optional auto-merge after approval
- `--keep-failed-branch`
- human-review mode
- deterministic rollback
- branch cleanup
- Git worktrees later

### B. Static/structural validation
- include untracked/new files
- undefined-name checks where reliable
- invalid import checks
- Python AST/syntax
- Ruff
- mypy
- optional Pyright
- Rust `cargo check`, `cargo clippy`
- Solidity `forge build`, `forge test`
- JS/TS ESLint + `tsc --noEmit`
- ShellCheck
- language-aware validation registry

### C. Tree-sitter symbol intelligence
- Tree-sitter parsers
- functions/classes/methods/structs/traits/interfaces/contracts/modules
- import/export extraction
- exact symbol ranges/metadata
- symbol embeddings
- definition lookup
- references
- callers
- implementations
- repository map
- dependency graph
- call graph
- incremental updates

Priority languages: Python, Rust, Solidity, TS/JS, SQL, C/C++, Java, Shell.

### D. Planner
- task classification
- affected files/symbols
- ordered plan
- plan validation
- referenced-file/symbol existence checks
- risk/scope estimate
- dependency-change detection
- plan revision
- approval policy

### E. Multi-file coding
- first-class multi-file diffs
- per-file summary
- max-file policy
- unrelated-change detection
- symbol-level scope guard
- plan-vs-diff validation
- preserve unaffected code
- safe create/delete/rename
- structured edits while Git diff remains truth

### F. Agent tool loop
Controlled tools:
- read_file
- list_tree
- search_code
- find_symbol
- find_references
- find_callers
- find_implementations
- inspect_git
- git_diff
- run_tests
- run_build
- run_lint
- run_typecheck
- run_safe_command
- create_patch
- apply_patch
- rollback

Loop: request → plan → inspect → act → observe → replan/repair → verify.

### G. Controlled shell
Allowlist safe engineering commands first. Add approval/block policy for `sudo`, destructive `rm`, force push, `curl|bash`, credential ops, destructive DB ops. Add timeouts, child cleanup, cancellation, audit log, optional Docker/bubblewrap/firejail sandbox, CPU/RAM/disk limits.

### H. Test intelligence
- automatic regression-test generation
- optional TDD
- relevant test selection
- affected-test graph
- targeted tests first
- full suite before success commit
- flaky-test handling
- failure classification
- bounded 1/2/3 repair attempts
- no infinite loops

### I. Self-review
- second-pass diff review
- task satisfaction
- unrelated changes
- architecture
- security
- performance
- test adequacy
- confidence score
- risk classification

Risk levels: low docs/tests; medium business logic; high auth/migrations/payments/security/smart contracts/deployment. High risk requires explicit approval.

### J. Project instructions/memory
- AGENTS.md
- nested AGENTS.md
- AGENTS.override.md awareness
- conventions
- build/test commands
- architecture rules
- generated-file exclusions
- dependency policy
- persistent repository memory
- project config
- ADRs

### K. Dependency protection
Detect and gate changes to requirements, pyproject, package.json/locks, Cargo files, Foundry config/deps, system packages.

### L. Security
- secret/.env/API-key/private-key/token/password scanning
- gitleaks evaluation
- path traversal
- SQL injection
- command injection
- unsafe deserialization
- SSRF
- auth bypass
- weak crypto
- insecure randomness
- Solidity reentrancy/access control/unchecked external calls/oracle/accounting/upgradeability checks

### M. Explicit modes
- ask/explain
- repo overview
- architecture trace
- code review
- bug investigation
- traceback/log debugging
- feature implementation
- test generation
- refactor
- security review
- documentation
- migration
- PR review

### N. Planner/Coder/Reviewer roles
- router
- planner
- coder
- reviewer
- debugger
- test engineer
- security reviewer
- optional small helper models for routing/ranking/classification/summarization

### O. Confidence/risk engine
Score retrieval coverage, symbols available, tests, plan consistency, scope, static validation, test results, security flags, and change risk. Gate auto-apply/commit accordingly.

### P. Database/migration awareness
- detect schema changes/framework migrations
- destructive SQL warnings
- migration validation/order/rollback strategy

### Q. Git worktrees/checkpoints
- worktree per task
- isolated filesystem
- checkpoint commits
- staged rollback
- concurrent-task safety

### R. Real-project onboarding
- detect languages/build/tests/linters/typecheckers/frameworks
- repo map
- symbol index
- AGENTS candidate
- local config
- baseline health

### S. Friday presentation interface
The Stage 7 Streamlit coding UI is retired in Stage 11. Preserve reusable repository, history, artifact, metrics, isolation, and health behavior through presentation-neutral services. Build the primary Friday interface fresh from scratch above the native API/event boundary, with contextual coding/task views rather than a permanent dashboard.

### T. Task history DB
Store task, prompt, timestamps, repo, starting commit, branch, plan, context, patch, validation, tests, repair attempts, result, commit.

### U. Metrics dashboard
Track tasks, first-pass success, repair success, rejected patches, structural/test failures, files changed, latency, local tokens/sec, prompt/version performance.

### V. Prompt/version experiments
Version planner/coder/reviewer prompts, benchmark tasks, regression suite, compare failure modes.

### W. Context management
Budget-aware context assembly, repo map first, exact symbols/deps/tests next, avoid blindly filling 256K, cache summaries/symbols, incremental embeddings, changed-only refresh, provenance.

### X. Model/runtime optimization
Coding profile, deterministic/low-temp modes, generation config, health checks, startup validation, fallbacks, context profiles, benchmark harness, alternative local model adapters.

### Y. Native integration gateway
Expose Friday through its own internal integration/service API. Prefer MCP-compatible interfaces where a standard tool protocol is useful, add WebSocket/event interfaces where justified, and keep direct adapters bounded by Git transactions, validation, approvals, command policy, and risk gates. OpenClaw is intentionally excluded.

### Z. GitHub integration
Issue → task → agent branch → tests/validation → commit → PR; PR review, CI, no force push without explicit permission.

### AA. Autonomous task queue
Only after single-task reliability: sequential queue, priority, pause/cancel, per-task Git isolation, no conflicting unattended writes, approvals.

### AB. Documentation automation
README, API docs, docstrings, changelog, architecture docs, diagrams, data flows, config docs, release notes.

### AC. Architecture understanding
Components, module dependencies, request/DB/auth/security/runtime flows, generated diagrams from graph.

### AD. Large refactor mode
Plan → dependency analysis → staged edits → checkpoint → relevant tests → full tests → next stage. No opaque giant patch.

### AE. Approval policy engine
Policy driven by risk/confidence/file type/dependency/security/migration/deployment/user config.

### AF. Sandbox/resource controls
Docker/bubblewrap/firejail evaluation, CPU/RAM/disk limits, command/generation timeouts, hung child termination, untrusted-repo mode.

### AG. Unified local platform
Final target:
```text
llama-server
    ├── Local chat
    ├── Document RAG
    ├── Code intelligence
    ├── Repository RAG
    ├── Planner
    ├── Coder
    ├── Reviewer
    ├── Debugger
    ├── Test engineer
    ├── Security reviewer
    ├── Git transaction manager
    ├── Task history
    └── Friday native interface/event boundary
```

### AH. Conversational voice and cinematic UI
After final real-repository hardening, add local microphone/wake-word/VAD/Whisper input, streaming text and sentence/chunk TTS with an original non-impersonating Friday voice, barge-in and immediate speech stop, deterministic assistant states, and a GPU-accelerated WebGL/Three.js/Canvas-style frontend driven by real runtime events. The legacy Streamlit UI is removed completely rather than retained as an engineering surface. The CLI remains the recovery/power-user interface. Voice/UI communicates only through Friday's native API/event boundary and has no direct authority over shell, filesystem or Git mutation, model tools, or approval.

## 15. Recommended implementation sequence

### Stage 0 — Bootstrap actual current system
1. Inspect actual MSI files.
2. Copy/refactor working source into repo.
3. Sanitize systemd templates/configs.
4. Add README/HISTORY/ARCHITECTURE/ROADMAP/AGENTS.
5. Add install/bootstrap scripts.
6. Preserve existing behavior with tests.
7. Commit/push bootstrap.

### Stage 1 — Stabilize/package current architecture
Configuration, logging, typed errors/models, package layout, compatibility wrappers, improved tests.

### Stage 2 — Code intelligence
Tree-sitter, symbols, references, callers, repo map, incremental index.

### Stage 3 — Planning/scope
Planner, validation, risk, scope guard, dependency policy.

### Stage 4 — Tool-driven loop
Controlled tools, multi-file edits, safe shell, observe/replan.

### Stage 5 — Validation/test/review intelligence
Language validators, test generation/selection, repair classification, reviewer/security/confidence.

### Stage 6 — Multi-language
Python → Rust → Solidity → TS/JS → SQL → C/C++ → Java → Shell.

### Stage 7 — UI/history/metrics
Coding UI, task DB, streaming, diff, metrics.

### Stage 8 — Advanced isolation/autonomy
Task-bound worktrees, exact checkpoints/rollback, capability-aware sandbox/resource/network controls, crash recovery, and explicit promotion. Concurrent-task locks are a safety foundation only; no autonomous queue is implemented.

### Stage 9 — Native Integration Gateway / GitHub / External Interfaces

The current review branch adds an optional localhost-bound gateway around existing services. It is authenticated, repository-ID bound, and disabled by default; GitHub/MCP inputs remain untrusted and cannot bypass approval, isolation, validation, review, or Git safety.
Friday-native service APIs, native GitHub issue/task/branch/validation/commit/PR, PR-review and CI-status integration, MCP-compatible interfaces, optional WebSocket/events, and justified direct adapters. No OpenClaw dependency; all external actions remain behind risk gates, exact plan approval, ScopeGuard, Git transactions, validation, sandbox/isolation, and audit/history.

### Stage 10 — Real-repo hardening
Onboard real repos, agent benchmark suite, measure/tune retrieval/prompts/repair/model adapters.

### Stage 11 — Conversational Voice & Cinematic UI
Remove the legacy Streamlit product UI completely after first extracting reusable non-presentation behavior. Build the Friday interface fresh from scratch with local microphone input, wake word, VAD, local Whisper, streaming text/TTS with an original Friday voice, barge-in/stop, deterministic runtime states, WebSocket/events, and a GPU-accelerated cinematic neural-core frontend. Keep the CLI for recovery/power users. The UI/voice layer has no privileged path around Friday's planning, risk, approval, execution, validation, isolation, Git, or audit boundary.

## 16. First Codex bootstrap instructions

The first Codex run should happen **locally on the MSI**, because the initially empty GitHub repo cannot expose the existing source-of-truth files.

Suggested destination:
```text
/AI/projects/Local-AI-Assistant
```

Codex must inspect:
- `/AI/projects/local-ai`
- `/AI/projects/code-assistant`
- `/etc/systemd/system/llama-qwen.service`
- `/etc/systemd/system/local-ai-ui.service`
- `~/src/llama-cpp-turboquant` for metadata only; do not vendor the fork unless explicitly requested

Do not copy:
- `.venv`
- model GGUFs
- vector indexes
- embeddings
- private user documents
- caches
- secrets
- `/tmp` DBs
- generated logs

Convert service units into sanitized examples. Document machine-local paths but do not make them the only supported deployment paths.

## 17. Master Codex prompt

```text
You are the lead engineer for Local-AI-Assistant.

Read AGENTS.md and CODEX_HANDOFF.md fully before changing anything.

This repository is being bootstrapped from a working local AI system on this MSI. Existing runtime source of truth is outside the initially empty Git repo:

/AI/projects/local-ai
/AI/projects/code-assistant
/etc/systemd/system/llama-qwen.service
/etc/systemd/system/local-ai-ui.service
~/src/llama-cpp-turboquant

Your first task is NOT to redesign from scratch.

BOOTSTRAP TASK:
1. Inspect the actual files at the paths above.
2. Inventory all code, configuration, dependencies, tests, services, and data paths.
3. Compare actual machine state to CODEX_HANDOFF.md. Where they differ, actual files/runtime win; document the discrepancy.
4. Create HISTORY.md with the chronological journey:
   Qwen3.6-35B-A3B-UD-Q4_K_M selection
   → benchmarking
   → selected TurboQuant/llama.cpp parameters
   → persistent llama-server
   → Python OpenAI-compatible local client
   → systemd
   → document RAG
   → persistent FAISS
   → hybrid FAISS+BM25
   → OCR
   → Streamlit
   → code RAG
   → patch agent
   → test/repair loop
   → repair-context grounding
   → structural validation
   → fresh-index policy
   → Git transaction branches
   → auto-commit
   → deterministic rollback/branch cleanup.
5. Create ARCHITECTURE.md for current + target architecture.
6. Create ROADMAP.md containing EVERY feature in CODEX_HANDOFF.md. Do not silently omit any feature.
7. Create root AGENTS.md with engineering/safety constraints and all required checks.
8. Import/refactor the actual working source into a maintainable repo structure.
9. Preserve current behavior using compatibility wrappers/scripts where necessary.
10. Add sanitized systemd templates.
11. Add dependencies/install/bootstrap scripts.
12. Add comprehensive .gitignore.
13. Never commit models, indexes, documents, credentials, virtualenvs, caches, generated state, or secrets.
14. Run all existing tests; add bootstrap/integration tests where needed.
15. Ensure the current local deployment remains runnable after bootstrap.
16. Make a clean bootstrap commit and push it.
17. Report files imported/excluded, discrepancies, tests, current architecture, and next milestone.

After bootstrap, proceed sequentially through ROADMAP.md milestone by milestone. Use tests and review after each milestone. Never collapse the entire roadmap into one giant patch.
```

## 18. Definition of done

Feature complete means ROADMAP.md accounts for every capability above and major execution paths have automated tests.

The final assistant should support:
- local chat
- private document RAG + OCR
- repo Q&A
- symbol-aware search/tracing
- planning
- multi-file coding
- safe editing
- builds/tests/lint/typecheck
- bounded repair
- code/security review
- project instructions
- risk/confidence gates
- Git isolation, auto-commit, rollback
- optional worktrees/checkpoints
- task history/metrics
- local coding UI
- multi-language work
- Friday-native integration gateway with optional GitHub, MCP-compatible, WebSocket/event, and justified direct external adapters
- optional queued autonomy
- local conversational voice and cinematic UI through Friday's non-privileged native API/event boundary
- persistent personal memory, visual perception, safe desktop control, proactive
  automation, and bounded research/self-learning;
- provenance-bearing Market Intelligence & Adaptive Trading Research with no
  implied real-money execution authority;
- measured Cognitive Architecture & Local Intelligence Amplification using the
  same current general-purpose LLM;
- an original, provenance-safe Creator Studio & Digital Media Intelligence
  workflow with review-gated publication.

The final product is **Friday — Local Personal Cognitive Operating System**:
`CURRENT LOCAL LLM + MEMORY + KNOWLEDGE + RETRIEVAL + SKILLS + TOOLS + PLANNING
+ OBSERVATION + VERIFICATION + EXPERIENCE + SPECIALIZED CAPABILITIES = FRIDAY`.
Its target is the most capable owner-controlled local AI system practical on the
owner's hardware using free/open technologies. Internet services may provide
current information; they cannot be mandatory intelligence providers. See ADR
0014 and detailed planned Stages 20–22 in `ROADMAP.md`.

Still require explicit human review for high-risk production/security/payment/smart-contract/destructive migration/deployment changes.

## 19. Canonical continuity rule

Do not use chat history as the only project memory. The durable source of truth becomes:
- `CODEX_HANDOFF.md` — bootstrap/history context
- `HISTORY.md` — chronological project history
- `ARCHITECTURE.md` — current + target design
- `ROADMAP.md` — every capability/status
- `AGENTS.md` — persistent Codex/project instructions
- ADRs — important design decisions
- Git history — implementation truth
- tests — behavioral truth

## 20. Current implementation snapshot

As of the qualified Stage 12E candidate, Stage 8 isolation/worktree/checkpoint controls are in the current branch; Stage 9 gateway/GitHub/MCP implementation is present with real integration hardening remaining; Stage 10 onboarding is partial; and Stage 11/12 provide the production conversational/wake platform with React/native presentation services, Whisper, Piper, PipeWire, strict `Hey Friday`, Silero, Parakeet primary, Moonshine fallback, persistent fail-closed wake workers, pause/resume orchestration, enabled user-session systemd deployment, production natural-language barge-in, hardened blocked-read cancellation, inline wake commands, fresh bare-wake follow-up capture, exact explicit stop, and supervised capture/worker recovery. The accepted barge-in path uses an ephemeral Friday-owned PipeWire WebRTC AEC graph in `monitor.mode=true`, captures `friday_aec_source`, stops active playback, and feeds trusted interruption audio through main Whisper. Exact `stop`, `friday stop`, and `hey friday stop` end in IDLE without LLM or acknowledgement speech; nonexact phrases remain conversational. Stage 12 remains active for concurrency policy, observability, streaming speech latency, and longer-running stability. `ROADMAP.md` extends the product through memory, perception, desktop/autonomy/events, same-model role orchestration, research, market intelligence, cognitive amplification, and creator intelligence under Local Intelligence Sovereignty.

Stage 12F subsequently accepted the wake/HTTP concurrency policy; Stage 12 now continues with barge-in observability, streaming speech latency, and longer-running stability.

Future engineering sessions must compare this prose with the current branch, roadmap, architecture, history, ADRs, tests, and actual runtime. Actual code/runtime evidence wins when historical prose disagrees.

## Stage 12C-A — inline wake command semantics

Status: **ACCEPTED** on 2026-08-30.

What works:
- `Hey Friday, <command>` uses the strict wake matcher remainder as the first user
  text for the voice conversation.
- The original wake audio is not retranscribed by Whisper for inline commands.
- Existing runtime state semantics are preserved through a synthetic
  `TRANSCRIBING` boundary before the conversation enters `THINKING`.
- Wake capture is paused before the voice turn and resumed after completion.
- Existing production WebRTC AEC barge-in topology remains unchanged.

Live-qualified production PID before acceptance commit: 66990.

Current limitation:
- bare `Hey Friday` still follows the pre-12C-A utterance behavior; dedicated
  fresh bare-wake follow-up command capture is implemented and production-qualified in Stage 12C-B.
- Markdown intended for visual rendering is not yet normalized before Piper TTS;
  `**4**` can be verbalized with the asterisk characters.

Next Stage 12 work:
1. Capture-thread health supervision/restart.
2. Barge-in observability and longer-running voice stability.
3. Streaming speech / initial-response latency.
4. TTS text normalization for Markdown/symbol-heavy LLM output.

## Stage 12C-B — bare wake fresh follow-up semantics

Accepted behavior: bare `Hey Friday` pauses wake capture and opens a fresh,
bounded raw-microphone command capture. Only the fresh second utterance enters
main Whisper. The original wake utterance is never reused. Timeout/error closes
LISTENING to IDLE before wake resumes; a subsequent bare wake can immediately
start another follow-up turn. Inline wake remainder routing remains direct-text,
and production AEC remains barge-in-only.

<!-- FRIDAY_CROSS_SESSION_HANDOFF_START -->

## Current cross-session handoff and Git policy

Repository: `Rishavmit14/Local-AI-Assistant`

Current active development branch:
`stage-12/production-voice-lifecycle`

Latest accepted capability recovery checkpoint:
`2ce0686cf05c379280c6643a3e6aba82ac3a58b0`
(`Stage 12D: add explicit stop semantics`, accepted and remotely verified).
Stage 12D is closed; reopen only upon evidence of a genuine regression.

Latest accepted repository recovery checkpoint:
`7cc288f089057349fd09bcfbce8115d1b0fa036d`
(`Stage 12F: enforce voice and presentation interaction ownership`). Stage/main,
fetched tracking refs, and direct remote refs were verified equal with a clean
accepted tree. The earlier Stage 12E checkpoint canonically accepted Local
Intelligence Sovereignty, the current single-general-model policy, and detailed
planned Stages 20–22 as product requirements; it does not claim those future
stages implemented.

Current capability: Stage 12G barge-in observability and longer-running voice
stability, QUALIFIED and ready for final regression/publication. Stage 12F is
accepted at `7cc288f` and must not be reopened absent genuine regression.

Initial 12F finding: production wake and HTTP conversation share one runtime and
LLM service without an admission boundary. Concurrent HTTP streams can both emit
user events before one fails an invalid transition; HTTP can win a race while a
wake callback later fails LISTENING transition; and an exception inside a lazy
stream begins after HTTP status 200, preventing a truthful busy response. The
candidate policy should admit exactly one interaction owner before state/events:
voice ownership rejects HTTP with 409, presentation ownership pauses/resumes wake
capture and suppresses an in-flight wake, concurrent presentation requests reject
without phantom events, and disconnect/error/shutdown releases ownership. Add a
read-only owner projection and deterministic race/cancellation coverage. Physical
qualification will be required after implementation; prepare nonblocking cursors.
Discovery found that capture/worker exceptions terminate the wake thread while
HTTP remains available; shutdown can feed retired partial PCM into segmentation;
raw capture reads have no deadline. Implement recovery with capped backoff,
fail-closed failed-utterance disposal, cancellation-safe capture, and read-only
voice health. Evidence is under ignored `var/stage12e/`. Stage 12D stays closed.
Candidate qualification on 2026-09-09: targeted voice/API/worker tests passed;
full repository verification passed with 683 Python tests and healthy dependency
checks. The controlled service reload installed the candidate on PID 64096.
Actual recorder termination recovered in 1.23 seconds; SIGSTOP stall recovered in
5.19 seconds with two-second PCM timeout, child termination/reaping, and backoff.
Both preserved the same Friday process and returned to IDLE/listening. Host
microphone/speaker levels remain 0.50/0.94. Evidence and rollback archive are in
`var/stage12e/`; `host-fault-results.json` and `host-fault-journal.txt` prove the
fault trials. These agent-induced faults are not product regressions.

The fresh physical wake passed. The preflight bound PID 64096, source hashes,
event cursor 0, journal cursor, and terminated Parakeet PID 64118. New Parakeet
PID 64624 recognized “Hey Friday, say recovery is working” as an inline command.
Runtime events 1–19 prove LISTENING -> TRANSCRIBING -> THINKING -> SPEAKING ->
IDLE with assistant text “Recovery is working.” The owner reported it worked
perfectly. Journal evidence proves WAKE_ACCEPTED, LLM/Piper/playback completion,
VOICE_THREAD_COMPLETE and WAKE_RESUMED; voice health then reported running,
listening, one utterance/wake, and the same service PID. No injected audio or
stdin-waiting harness was used.

The owner also added durable Local Intelligence Sovereignty, one-current-general-
model policy, and mandatory planned Stages 20–22. Their canonical scope is in
`AGENTS.md`, `ARCHITECTURE.md`, `ROADMAP.md`, README, and ADR 0014; none is
implemented or allowed to jump ahead of active dependency work.

Stage 12F implementation and qualification added one interaction coordinator
shared by production wake and presentation HTTP. Voice claims before runtime
mutation and pauses microphone ownership; active voice makes HTTP return 409.
Presentation claims before its response stream, pauses raw wake capture, and
suppresses wake dispatch. Completion, failure, disconnect and shutdown release
idempotently. Immediate disconnects release unstarted streams, while an active
synchronous model read retains ownership until safe cancellation and transitions
the runtime to `CANCELLED`. The read-only interaction endpoint exposes only
busy/owner/generation.

Live qualification passed both directions on the user-session service: a physical
count-to-100 voice turn held `owner=voice` while the HTTP probe returned 409, and
a physical wake phrase during a long presentation stream yielded no reply and
zero accepted wakes before presentation completion resumed listening. A separate
long trusted-barge-in qualification exposed an interruption stop without a
completed utterance; Friday now returns safely to IDLE without partial Whisper
input or a false runtime error. The Stage 12F acceptance recovery is the commit
containing this section; record its literal SHA in the following capability's
discovery.

Stage 12G discovery found the current barge-in monitor has a fixed 30-second
wait. A long Piper playback can outlive that one monitor pass, silently losing
interruption coverage after the wait expires. Add playback-lifetime-aware,
bounded monitoring with privacy-safe outcome/elapsed telemetry, deterministic
long-playback/cancellation/error coverage, and then requalify the real service.

Stage 12H is qualified and ready for publication: a bare wake now speaks “I'm
listening” before fresh capture. Live evidence confirmed cue -> fresh “What time
is it?” transcription -> normal response -> listening, with wake paused during
the cue and capture.

Final lifecycle finding: the first restart exposed a product race where the old
CLI waited until Uvicorn returned before closing voice; SIGTERM recorder unwind
scheduled a false retry. Cleanup now begins at Uvicorn's first exit signal and
is idempotent. PID 68914, which loaded the fix, shut down in about 0.34 seconds
with no capture error/retry; PID 69073 reached healthy IDLE/listening. Targeted
shutdown tests passed.

Final gates completed after cleanup: 686 Python tests passed twice (direct suite
and repository verifier), dependency/repository checks passed, Ruff passed on
every changed Python file, 12 frontend tests passed, and the production build
completed with only the existing large-chunk advisory. The accepted Stage 12E
recovery point is the commit containing this section; after publication record
its literal SHA here as part of the next capability's discovery.

Stage branch boundaries:

- Stage 11:
  `stage-11/conversational-voice-cinematic-ui`
  at `877cb1e6049eb6b0a6434d3eac835077be666c17`.
- Stage 12:
  `stage-12/production-voice-lifecycle`
  containing accepted Stage 12A/B/C/D work through
  `2ce0686cf05c379280c6643a3e6aba82ac3a58b0`.
- `main` tracks the newest fully qualified accepted subtask and is advanced to
  the same accepted commit after each successful stage-branch subtask.

Accepted Stage 12 checkpoints currently include:

- production PipeWire/WebRTC AEC-backed natural interruption;
- wake blocked-read pause/stop lifecycle hardening;
- inline `Hey Friday, <command>` direct-text routing without duplicate Whisper;
- bare `Hey Friday` followed by a fresh bounded microphone command capture,
  with no reuse of the wake utterance and fail-closed timeout/error handling;
- exact explicit stop without LLM or acknowledgement, including trusted AEC
  interruption and the stop-loss negative control.

Stage 12 remains active for the remaining production voice lifecycle work
recorded in `ROADMAP.md`.

### Required behavior for every future agent/session

Before making changes, read `AGENTS.md`, this handoff, `ARCHITECTURE.md`,
`ROADMAP.md`, `HISTORY.md`, and relevant architecture/ADR files.

For every accepted subtask:

1. deterministic tests / relevant live qualification;
2. update all canonical docs affected by the change;
3. full required regression;
4. commit on the owning `stage-N/...` branch with an explicit capability/stage
   heading;
5. push the stage branch;
6. fast-forward `main` to that exact accepted commit and push;
7. fetch/verify both remote refs, record the recovery SHA, and verify clean state;
8. immediately begin DISCOVERY of the next canonical-roadmap capability without
   an approval pause, following the durable owner policy in `AGENTS.md`.

A feature/capability/architecture/runtime change that exists only in code or chat
and is not reconciled into the canonical docs is **not accepted**.
<!-- FRIDAY_CROSS_SESSION_HANDOFF_END -->

## Stage 12D — explicit stop semantics (accepted, 2026-09-09)

Active branch: `stage-12/production-voice-lifecycle`. The accepted implementation handles only
normalized exact `stop`, `friday stop`, and `hey friday stop`, ends TRANSCRIBING
in IDLE before conversation/LLM/TTS, and reuses the accepted AEC/player stop path.
The rejected R2 `go ahead and stop` ASR alias and its context plumbing are removed.
Full-path tests cover exact stops and normal nonexact continuation from both
inline and audio-first turns, including stop-loss, negation, and the removed alias.

Physical evidence on PID 3408:
- inline stop passed (an earlier no-telemetry attempt remains inconclusive);
- two barge-in attempts failed when distorted audio yielded `I didn't stop.` and
  `Friday night.`, followed by unwanted conversational replies;
- recording preserved the exact Whisper input and reproduced the latter error;
  larger surrounding audio and alternate installed ASR models did not establish
  a reliable ASR-only replacement;
- raw input clipped during playback at hardware capture +30 dB / speaker 129%;
- after backing up host settings, microphone volume 0.5 (capture +11.25 dB) and
  speaker volume 1.0 eliminated clipping in the recorded raw/AEC/Whisper input;
- the owner then reported instant stop and no reply; Whisper heard `Friday stop.`,
  trusted AEC stopped playback in 3.2 ms after the trigger, explicit-stop IDLE and
  wake resume occurred, with only the initial LLM/speech turn.

After a controlled reload, final live qualification passed on PID 37679 without
companion diagnostic readers. Inline stop reached explicit-stop IDLE with no
Whisper, LLM, or playback. Trusted AEC barge-in transcribed `Friday stop.`,
stopped playback about 3.2 ms after the trigger, produced no second response,
and resumed wake capture. The stop-loss negative control completed one normal
LLM and spoken response with zero explicit-stop events. The acceptance recovery
point is the commit containing this section; verify the stage branch and `main`
remote refs resolve to that exact commit before starting further capability work.

Known latency: speech currently starts after complete response generation. The
successful counting request spent 10.7 seconds generating text plus about 3.0
seconds to first Piper audio; an earlier request spent 52.8 seconds generating.
Streaming speech/initial-response latency remains future Stage 12 work. Barge-in
monitor elapsed time is measured from monitoring start, not human speech onset.

Evidence/cursors, private recordings, model comparisons, and recovery snapshots:
`/AI/tools/friday-stage12d-live/codex_physical_20260909-003505/`.
Host audio restoration commands are in `audio-levels-before/`. Diagnostic workers
and recorders have exited. Continue physical actions through Codex replies;
never use child-process stdin prompts or substitute synthetic audio for live gates.

## Stage 12I — incremental speech (accepted, 2026-09-10)

The Stage 12I candidate keeps Qwen streaming as the sole text producer. Complete
sentences enter a deterministic bounded ordered queue, which serially feeds the
existing persistent Piper/player path. The first sentence transitions THINKING to
SPEAKING; model completion preserves SPEAKING until ordered playback completes.
Focused tests cover chunking, queue shutdown/backpressure, lifecycle completion,
early speech start and speech failure. On 2026-09-10, `Hey Friday, explain in
three short sentences why the sky appears blue` produced a correct spoken answer;
telemetry recorded Piper begin at 00:56:36 before LLM completion at 00:56:38,
then three sequential Piper requests and healthy wake resume. Complete acceptance
passed full Python regression and repository verification. The accepted remotely
recoverable checkpoint is
`17fcdf1c0733d0d5079323945f4362f52dfa7632`; the Stage 12 branch and `main`
both resolve to this commit.
