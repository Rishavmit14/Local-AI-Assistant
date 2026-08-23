# Project History

This chronology records the working system that existed before this repository was bootstrapped.

1. `Qwen3.6-35B-A3B-UD-Q4_K_M` was selected as the strongest practical local coding/reasoning model for the MSI GT62VR hardware.
2. llama.cpp/TurboQuant profiles were benchmarked. The selected profile uses GPU layers 999, 34 CPU MoE layers, 262,144 context, 128/32 batch sizes, four threads, Turbo4/Turbo3 KV, and reasoning disabled. `--mlock` was rejected and full 242K prefill was deferred due cost.
3. A persistent localhost `llama-server` exposed the OpenAI-compatible API and was reboot-tested through systemd.
4. `LocalLLM` added normal and streaming Python clients against that API.
5. A second systemd service made the Streamlit interface persistent.
6. Document RAG added TXT, Markdown, PDF, and DOCX ingestion, token-aware chunks, SHA-256 change detection, persistent FAISS storage, then BM25 and reciprocal-rank fusion.
7. Selective Tesseract OCR was added for low-text PDF pages, retaining extraction metadata.
8. Streamlit added uploads, reindex controls, source display, chat history, and index/OCR statistics.
9. Code RAG added multi-language file discovery, overlapping line chunks, FAISS/BM25 retrieval, and repository-grounded questions.
10. The patch agent added unified-diff generation, path normalization, `git apply --check --recount`, explicit application, and detected test commands.
11. One bounded repair attempt was added after test failure. Exact failing-file contents, the current diff, test output, and retrieved context grounded repairs after hallucinated helpers and fake stubs were observed.
12. Python AST checks caught duplicate top-level definitions that syntax and tests had missed.
13. Fresh indexing before proposals and after edits addressed stale-patch failures.
14. Isolated `agent/*` branches, success auto-commit, deterministic rollback, return to the original branch, and failed-branch cleanup completed the proven Git transaction flow.
15. On 2026-08-23, Stage 0 imported the live source into this repository, introduced environment-configurable data paths, sanitized service templates, tests, documentation, and explicit generated-data exclusions. The original working directories and installed services were left unchanged for review.
