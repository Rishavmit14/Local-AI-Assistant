# ADR 0002: Official Tree-sitter Python bindings and grammar

Status: Accepted for Stage 2

## Context

Code intelligence needs deterministic syntax facts, exact ranges, error-tolerant parsing, and a future adapter boundary. Installing a multi-grammar bundle would prematurely add Stage 6 dependencies.

## Decision

Use the official [`tree-sitter` Python bindings](https://github.com/tree-sitter/py-tree-sitter) and official [`tree-sitter-python` grammar](https://github.com/tree-sitter/tree-sitter-python), constrained to their compatible 0.25 release lines. Each future language gets a narrow extractor adapter and an explicit grammar dependency only when its roadmap stage begins.

Tree-sitter/static analysis supplies code facts. BGE, FAISS, BM25, and RRF supply retrieval. Qwen consumes retrieved evidence for reasoning/generation and never creates symbol or graph indexes.

## Consequences

Only two parser packages are added. Python parsing tolerates malformed files and records errors. Direct uniquely named calls can be confirmed; attribute/dynamic calls remain unresolved. Runtime binding, monkey-patching, reflection, and dynamic imports are outside the claims of this index.
