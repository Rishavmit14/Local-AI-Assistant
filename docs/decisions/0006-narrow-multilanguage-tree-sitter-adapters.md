# ADR 0006: Narrow Tree-sitter language adapters

- Status: accepted for Stage 6
- Date: 2026-08-24

## Context

Stage 2 established the official Tree-sitter Python bindings and a persistent symbol format. Stage 6 must add eight language families without replacing that index or introducing a large parser bundle with unrelated grammars.

## Decision

Keep `tree-sitter` 0.25 as the common Python runtime and install one grammar wheel per supported language. Rust uses the official `tree-sitter/tree-sitter-rust` grammar (`tree-sitter-rust` 0.24). JavaScript, TypeScript, C, C++, Java, and Bash use their narrow Tree-sitter project wheels. Solidity uses the community `tree-sitter-solidity` wheel (PyPI package `tree-sitter-solidity`, source `JoranHonig/tree-sitter-solidity`) and SQL uses the community `tree-sitter-sql` wheel (PyPI package `tree-sitter-sql`, source `DerekStride/tree-sitter-sql`) because neither grammar is maintained in the core Tree-sitter organization. These are explicitly distinct from official Tree-sitter organization grammars and are bounded by the dependency ranges in `pyproject.toml`.

Adapters declare capability status as `supported`, `partial`, or `unavailable`. A missing grammar disables only that adapter; other languages and legacy line chunks remain usable. Parser package/version, adapter extraction version, and capability snapshots are persisted so a grammar upgrade or downgrade invalidates only files of that language. Project code never auto-installs a missing grammar.

No grammar aggregator, cloud parser, cloud embedding, or LLM-created graph is used. Tree-sitter/static syntax owns facts; BGE with FAISS/BM25/RRF owns semantic retrieval; Qwen consumes bounded evidence for reasoning and generation.

## Consequences

All languages share `SymbolRecord`, relationship/provenance records, persistence, incremental refresh, retrieval, planner, and scope boundaries. Language adapters remain conservative where runtime binding, preprocessing, dialect semantics, type inference, macros, or dynamic evaluation prevent proof. Solidity's community wheel currently exposes the legacy integer language handle, which Tree-sitter 0.25 accepts with a deprecation warning; this is isolated to parser construction.
