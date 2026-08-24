# Code Intelligence Architecture

Stage 6 extends this Stage 2 foundation through the shared adapter platform documented in [multi-language code intelligence](multi-language-code-intelligence.md). Python behavior and schema-2 loading remain compatible.

## Symbol schema

`SymbolRecord` stores a stable hash identifier, repository-relative path, language, extensible kind, name/qualified name, parent, exact lines/source, signature, documentation, decorators, deterministic visibility, imports, and source hash. Kinds reserve future struct, trait, interface, contract, enum, implementation, and namespace values without loading those grammars.

`FileRecord` stores SHA-256 content identity, language, normalized imports, parse errors, parser identity, and capability metadata. `ReferenceRecord`, `CallRecord`, and unified relationship records distinguish confirmed definitions, syntactic references, unresolved references, and external targets. IDs depend on language/path/qualified-name/kind, so unchanged symbols remain stable while a rename intentionally changes identity.

## Persistence and refresh

The index uses versioned JSON for metadata, symbols, references, and calls; NumPy stores normalized embedding vectors; FAISS stores the query index. An atomically replaced metadata manifest is committed last and contains SHA-256 checksums for every artifact, so interrupted or mixed-generation writes fail integrity validation. Refresh hashes source content rather than trusting timestamps. Unchanged symbols/vectors are retained, changed-file records are replaced, and deleted-file records are removed. A rename is one deletion plus one addition. BM25 and FAISS query structures are reconstructed after refresh, but only changed symbols are embedded.

A failed file records an explicit failure while successfully indexed files remain usable. Invalid metadata or symbol/vector mismatch raises `CorruptIndexError` rather than silently serving inconsistent results.

## Graphs and maps

Python imports form module dependency edges with relative-import normalization. Reverse imports derive from persisted file records. Direct calls with one unambiguous repository definition produce confirmed edges; dynamic/attribute calls remain unresolved. References are syntactic and do not assert Python runtime binding. Repository maps are generated from indexed paths and symbols as both JSON-compatible data and tree text.

## Retrieval

Code RAG prioritizes exact identifier matches, graph-related callers/callees, and hybrid symbol retrieval. Embedding text combines kind, qualified name, signature, docstring, and bounded source. Every result includes file/range, optional symbol ID, method, lexical/semantic ranks, hybrid score, and optional graph relationship. Existing line-chunk FAISS + BM25 + RRF results remain available and fill remaining context slots as fallback.
