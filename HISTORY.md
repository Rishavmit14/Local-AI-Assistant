# Project History

This chronology records the working system that existed before this repository was bootstrapped.

Stage 11 begins by intentionally retiring the legacy Streamlit product UI, its launcher, compatibility wrappers, UI-specific configuration, dependency, and service template. Reusable repository/history/artifact/metrics/isolation/health behavior was first extracted into the presentation-neutral `FridayInterfaceService` and regression-tested before deletion. The replacement Friday conversational and cinematic interface will be built fresh above the native API/event and safety boundaries.

Stage 8 added task-bound Git worktrees, exact checkpoints and rollback, capability-aware sandbox backends, clean task environments, resource/process limits, explicit network policy, crash recovery, promotion integrity, and history/UI visibility. The current Ubuntu host exposes Bubblewrap but denies its user-namespace probe, so strong untrusted-code execution fails closed and the native backend is reported as degraded rather than overstated.

Stage 7 added a versioned local SQLite task-history service, legacy artifact indexing, lifecycle/audit/search/metrics/export CLI, and read-mostly Streamlit coding/history/metrics/system workspaces. The UI invokes existing planner and exact-plan approval services; it does not bypass execution or Git safety.

Stage 6 generalized the deterministic Stage 2 index into one capability-aware language platform. It preserved Python and added narrow Tree-sitter adapters for Rust, Solidity, TypeScript/JavaScript, SQL, C/C++, Java, and Shell; shared multi-language relationships, parser-version invalidation, filters, maps, planner/scope/test evidence, and line-chunk fallback remain under the same deterministic authority.

Stage 5 introduced typed validation plans, deterministic validator and targeted-test selection, bounded scope-enforced test generation and repair, failure/flaky classification, validation caching, deterministic/security/model review, and a final commit-or-rollback decision. The execution order now separates targeted feedback from required final validation, while Stage 3/4 plan, approval, scope, command, and Git policies remain authoritative.

The Stage 5 self-review then bound validator commands to regenerated policy/configuration, strengthened cache/environment identity, restored exact Git-visible and sensitive-file state after validator side effects, activated optional scope-enforced test-generation/TDD flow, blocked repair/test weakening, expanded redaction/security heuristics, and bound automatic commit to the exact reviewed diff before and after staging.

Stage 4 activated `ScopeGuardPolicy` against generated and post-apply Git diffs, then added typed plan-bound tools, structured multi-file edits, parsed command allowlists, bounded execution/repair, human review, timeouts, and auditable rollback-integrated execution.

The Stage 4 security review then hardened quoted/binary patch handling, stale-symbol rejection, symlink and command-argument boundaries, dry-run isolation, bounded output capture, validation-side-effect rollback, and staged-diff coverage.

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
16. Stage 1 stabilized the import as an injectable Python package: typed settings, structured logs, explicit errors and transaction summaries, canonical console commands, compatibility wrappers, configurable directories/retrieval/OCR/UI/runtime values, and comprehensive regression tests were added without changing the live external deployment.
17. Stage 2 added official Tree-sitter Python parsing, typed symbol/reference/call records, persistent incremental symbol embeddings and graphs, repository maps, deterministic queries, provenance, and symbol-first code RAG while retaining line chunks as fallback.
18. Stage 3 added deterministic affected-scope analysis, bounded structured Qwen planning, typed plan validation and persistence, dependency/migration/security awareness, explainable risk/confidence/approval policy, a future scope guard, planning CLI, and a mandatory planning gate before patch generation.
# Stage 9

The review branch adds the optional authenticated Friday-native integration gateway, typed external provenance/idempotency, bounded events, GitHub transport boundary, and controlled MCP capability facade. It remains disabled by default and does not replace the existing safety pipeline.
