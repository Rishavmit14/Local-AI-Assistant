# Stage 0 Machine Inventory — 2026-08-23

## Imported source

- `/AI/projects/local-ai/local_llm.py` → `src/local_ai_assistant/llm/client.py`
- `/AI/projects/local-ai/rag.py` → `src/local_ai_assistant/rag/documents.py`
- `/AI/projects/local-ai/app.py` → `ui/streamlit/app.py`
- `/AI/projects/code-assistant/code_rag.py` → `src/local_ai_assistant/code_index/repository.py`
- `/AI/projects/code-assistant/code_agent.py` → `src/local_ai_assistant/agent/code_agent.py`
- `/AI/projects/code-assistant/repos/demo-app/{README.md,.gitignore,app/*.py,tests/*.py}` → `examples/demo-app/`
- Installed `llama-qwen.service` and `local-ai-ui.service` were inspected and converted to placeholder-based examples; they were not copied verbatim.
- `/home/kumar-rishav/src/llama-cpp-turboquant` was inspected only for branch/commit/build metadata and was not vendored.

Imports retain the working algorithms. Stage 0 changes absolute Python project/data paths to `LOCAL_AI_*` settings and package imports; selected model and localhost API defaults remain compatible.

## Intentionally excluded

- `/AI/projects/local-ai/.venv`, `__pycache__`, `documents`, `rag_data`, and `rag.py.backup-before-ocr`.
- `/AI/projects/code-assistant/__pycache__`, `index`, `patches`, every `code_agent.py.backup-*`, and the nested demo `.git` and `.pytest_cache` directories.
- GGUF/models, embeddings, private documents, FAISS/index JSON state, generated patches/logs, secrets, caches, and `/tmp/demo_app.db` or other database state.
- The llama.cpp/TurboQuant source/build tree; it remains an independently versioned runtime dependency.

## Handoff differences and observations

- The handoff says Ubuntu 26.04; the observed kernel string was `7.0.0-30-generic` on the named MSI host. GCC 15.2.0, g++ 15.2.0, and CMake 4.2.3 matched.
- `nvidia-smi` could not communicate with the NVIDIA driver during this sandboxed inspection, so the documented driver 580.173.02/CUDA 13.0/GPU-memory state was not revalidated. This does not prove the installed driver differs.
- Systemd unit files exactly preserve the documented users, working directories, dependencies, localhost bindings, ports, restart policy, and selected inference profile. Host-level verification confirmed both services are enabled, active, and running. A reboot was not performed during bootstrap.
- Host-level checks confirmed llama-server `/health` returns `{"status":"ok"}`, `/v1/models` reports the expected 34,660,610,688-parameter model with `n_ctx=262144`, and Streamlit reports `ok`. The original `test_qwen.py` also completed with a valid three-sentence response.
- TurboQuant matched branch `feature/turboquant-kv-cache` and commit `e30664a710b62aaf13c6b12e39e74500e6ce21ef`; the observed tag says `b10539-e30664a`, whereas the handoff mentions version string `b1-e30664a`.
- The demo app README still says its login status bug is deliberate, but actual `app/api.py` returns the corrected 401 and its Git history includes the fix. Actual behavior wins.
- The demo app’s `SECRET_KEY = "demo-secret-key"` and SHA-256 password hashing are fixture-only security weaknesses. They were retained to preserve the test fixture and are called out in `SECURITY.md`; they are not production credentials.
- The live virtual environment used Python 3.14 and included newer concrete packages than the handoff enumerated (for example OpenAI 3.3.1, Streamlit 1.62.0, FAISS CPU 1.15.0, sentence-transformers 6.0.0, pytest 9.1.1). Repository dependency ranges capture direct requirements rather than copying the whole environment.
