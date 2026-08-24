# Multi-language code intelligence

## Platform boundary

`LanguageRegistry` is the single extension/language authority for symbol indexing and legacy line-chunk discovery. A typed `LanguageAdapter` declares grammar identity, extensions, parser availability, capabilities, extraction, and language-aware embedding text. `TreeSitterAdapter` supplies shared parsing, exact text/range, and malformed-tree handling.

All adapters emit the same records:

- `SymbolRecord` with stable language/path/qualified-name/kind identity and extensible metadata;
- `FileRecord` with content hash, parser version, capabilities, imports, and parse errors;
- references/calls with explicit resolution state;
- unified relationships for imports, modules, implementations, inheritance, SQL dependencies, modifiers, and sourced scripts.

IDs do not depend on line numbers, so no-op refreshes and movement within the same file preserve identity. File or qualified-name changes intentionally create a new identity. For Stage 2 compatibility, repository identity is provided by the containing index rather than inserted into existing Python IDs; copying the same path/symbol between repositories can therefore produce the same record ID, while persisted indexes remain repository-bound by their owning directory.

## Incremental persistence

Schema 3 retains JSON symbols/graphs, NumPy embeddings, FAISS, checksums, and manifest-last atomic publication. Schema 2 Python indexes load and are refreshed into schema 3. Parser versions and capability snapshots are persisted per language. Content or relevant parser-version changes replace only that file's records and embeddings. Delete/rename remains delete plus add. Query-time BM25/FAISS structures are rebuilt, but unchanged symbols are not re-embedded.

A parser/file failure is recorded without destroying other files or languages. Corrupt language metadata or artifacts raise `CorruptIndexError`. An unavailable grammar is reported in index stats and does not hide already persisted mixed-language facts.

## Capability and support matrix

`Full` below means strong deterministic syntactic extraction, not runtime semantic proof. `Partial` is returned explicitly by capability-aware APIs; it is not represented as an empty successful query.

| Language | Symbols | Imports/deps | Calls | References | Inheritance/impl |
|---|---|---|---|---|---|
| Python | Full | Full | Partial | Partial | Class nesting only |
| Rust | Full | Full syntactic | Partial | Partial | Full explicit impl syntax |
| Solidity | Full syntactic | Full syntax | Partial | Partial | Partial explicit inheritance |
| TypeScript/JavaScript | Full common declarations | Partial | Partial | Partial | Partial explicit syntax |
| SQL | Partial generic dialect | Dependency references | Unavailable | Partial | Not applicable |
| C/C++ | Partial | Includes | Partial | Partial | C++ explicit inheritance partial |
| Java | Full common declarations | Full syntax | Partial | Partial | Partial explicit syntax |
| Shell/Bash | Functions | Sourced files partial | Partial | Unavailable | Not applicable |

Important limitations include Rust trait/method dispatch and macros, Solidity EVM dispatch, JS dynamic imports/prototype mutation, SQL dialect variation, C/C++ preprocessing/templates/overload resolution, Java reflection, and Shell evaluation/dynamic sourcing. These remain unresolved rather than guessed. Unsupported extensions and uncertain constructs continue through line-chunk CodeRAG.

## Consumers

CodeRAG keeps exact symbol → graph relationship → hybrid symbol → line-chunk priority and adds optional language/path/kind filters. Repository maps preserve machine-readable parent/language metadata and render nested impl/container structure.

The Stage 3 planner receives Rust impl/import/test evidence, security-sensitive Solidity paths, and migration-sensitive SQL scope. Stage 4 uses exact indexed ranges for existing symbols in every language; unknown new/deleted symbol effects remain file-level and require renewed approval when symbol-scoped. Stage 5 validator authority and command permissions are unchanged; multi-language facts improve test-impact evidence but do not expand executable commands.

