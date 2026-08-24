from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

from local_ai_assistant.common.config import AppConfig, get_config
from local_ai_assistant.common.errors import IndexingError
from local_ai_assistant.common.logging import configure_logging, get_logger
from local_ai_assistant.llm import LocalLLM

from .languages import build_language_registry
from .symbol_index import SymbolIndex

_DEFAULT_CONFIG = get_config()
REPO_DIR = _DEFAULT_CONFIG.paths.code_repo_dir
INDEX_DIR = _DEFAULT_CONFIG.paths.code_index_dir
INDEX_FILE = INDEX_DIR / "code.faiss"
CHUNKS_FILE = INDEX_DIR / "code_chunks.json"
MANIFEST_FILE = INDEX_DIR / "manifest.json"

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"

CODE_EXTENSIONS = set(build_language_registry().extensions)

SKIP_DIRS = {
    ".git",
    "node_modules",
    "target",
    "dist",
    "build",
    ".next",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    "coverage",
}

CHUNK_LINES = 120
OVERLAP_LINES = 20

VECTOR_TOP_K = 12
BM25_TOP_K = 12
FINAL_TOP_K = 6
RRF_K = 60
logger = get_logger(__name__)


def lexical_tokenize(text: str) -> list[str]:
    return re.findall(
        r"[A-Za-z0-9_./:#<>-]+",
        text.lower(),
    )


class CodeRAG:
    def __init__(
        self,
        config: AppConfig | None = None,
        *,
        embedder=None,
        llm: LocalLLM | None = None,
    ) -> None:
        self.config = config or get_config()
        self.repo_dir = self.config.paths.code_repo_dir
        self.index_dir = self.config.paths.code_index_dir
        self.index_file = self.index_dir / "code.faiss"
        self.chunks_file = self.index_dir / "code_chunks.json"
        self.manifest_file = self.index_dir / "manifest.json"
        self.repo_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.index_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        print("Loading embedding model...")

        logger.info(
            "repository_index_initializing",
            extra={"event": "code_index.initializing", "repository_dir": self.repo_dir},
        )
        self.embedder = embedder or SentenceTransformer(
            self.config.embedding.model,
            device=self.config.embedding.device,
        )

        self.llm = llm or LocalLLM(config=self.config)
        self.symbol_index = SymbolIndex(self.repo_dir, self.index_dir / "symbols", self.embedder)

        self.chunks: list[dict[str, Any]] = []

        self.index = None
        self.bm25 = None
        self.manifest = {}

    @staticmethod
    def sha256(path: Path) -> str:
        hasher = hashlib.sha256()

        with path.open("rb") as f:
            while True:
                block = f.read(1024 * 1024)

                if not block:
                    break

                hasher.update(block)

        return hasher.hexdigest()

    @staticmethod
    def should_skip(path: Path) -> bool:
        return any(part in SKIP_DIRS for part in path.parts)

    def discover_files(self):
        files = []

        for path in self.repo_dir.rglob("*"):
            if not path.is_file():
                continue

            if self.should_skip(path):
                continue

            if path.suffix.lower() not in CODE_EXTENSIONS:
                continue

            files.append(path)

        return sorted(files)

    def chunk_code(
        self,
        text: str,
    ) -> list[dict[str, Any]]:
        settings = getattr(self, "config", _DEFAULT_CONFIG).code_retrieval
        lines = text.splitlines()

        chunks = []

        start = 0

        while start < len(lines):
            end = min(
                start + settings.chunk_lines,
                len(lines),
            )

            block = "\n".join(lines[start:end]).strip()

            if block:
                chunks.append(
                    {
                        "text": block,
                        "line_start": start + 1,
                        "line_end": end,
                    }
                )

            if end >= len(lines):
                break

            start = end - settings.overlap_lines

        return chunks

    def build_chunks(self):
        files = self.discover_files()

        print(f"Found {len(files)} source files.")

        chunks = []
        manifest = {}

        for path in files:
            relative = str(path.relative_to(self.repo_dir))

            try:
                text = path.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )

            except Exception as exc:
                print(f"Skipping {relative}: {exc}")
                continue

            manifest[relative] = {
                "sha256": self.sha256(path),
                "size": path.stat().st_size,
            }

            for chunk_number, chunk in enumerate(self.chunk_code(text)):
                chunks.append(
                    {
                        "text": chunk["text"],
                        "source": relative,
                        "chunk": chunk_number,
                        "line_start": chunk["line_start"],
                        "line_end": chunk["line_end"],
                        "extension": path.suffix.lower(),
                    }
                )

        self.chunks = chunks
        self.manifest = manifest

    def build_vector_index(self):
        if not self.chunks:
            raise IndexingError("No code chunks available.")

        texts = [chunk["text"] for chunk in self.chunks]

        print(f"Embedding {len(texts)} code chunks...")

        embeddings = self.embedder.encode(
            texts,
            batch_size=self.config.embedding.batch_size,
            show_progress_bar=not self.config.runtime.test_mode,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )

        embeddings = np.asarray(
            embeddings,
            dtype=np.float32,
        )

        dimension = embeddings.shape[1]

        self.index = faiss.IndexFlatIP(dimension)

        self.index.add(embeddings)

        print(f"FAISS ready: {self.index.ntotal} vectors")

    def build_bm25(self):
        corpus = [lexical_tokenize(chunk["text"]) for chunk in self.chunks]

        self.bm25 = BM25Okapi(corpus)

        print(f"BM25 ready: {len(corpus)} chunks")

    def save(self):
        faiss.write_index(
            self.index,
            str(self.index_file),
        )

        self.chunks_file.write_text(
            json.dumps(
                self.chunks,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        self.manifest_file.write_text(
            json.dumps(
                self.manifest,
                indent=2,
            ),
            encoding="utf-8",
        )

    def load(self) -> bool:
        if not self.index_file.exists() or not self.chunks_file.exists():
            return False

        self.index = faiss.read_index(str(self.index_file))

        self.chunks = json.loads(self.chunks_file.read_text(encoding="utf-8"))

        self.build_bm25()

        if self.symbol_index.metadata_file.exists():
            self.symbol_index.load()

        return True

    def reindex(self, *, full_symbols: bool = False):
        logger.info(
            "repository_reindex_started",
            extra={"event": "code_index.reindex.started", "repository_dir": self.repo_dir},
        )
        self.build_chunks()
        self.build_vector_index()
        self.build_bm25()
        self.save()
        symbol_stats = self.symbol_index.refresh(full=full_symbols)

        logger.info(
            "repository_reindex_completed",
            extra={
                "event": "code_index.reindex.completed",
                "chunk_count": len(self.chunks),
                "symbol_count": symbol_stats.symbol_count,
            },
        )

        print()
        print(f"Indexed {len(self.chunks)} chunks.")

    def vector_search(
        self,
        question: str,
    ):
        query = self.embedder.encode(
            [question],
            normalize_embeddings=True,
            convert_to_numpy=True,
        )

        query = np.asarray(
            query,
            dtype=np.float32,
        )

        top_k = min(
            self.config.code_retrieval.vector_top_k,
            len(self.chunks),
        )

        scores, indices = self.index.search(
            query,
            top_k,
        )

        return [
            {
                "index": int(index),
                "rank": rank,
                "score": float(score),
            }
            for rank, (score, index) in enumerate(
                zip(
                    scores[0],
                    indices[0],
                ),
                start=1,
            )
            if index >= 0
        ]

    def bm25_search(
        self,
        question: str,
    ):
        tokens = lexical_tokenize(question)

        scores = self.bm25.get_scores(tokens)

        top_k = min(
            self.config.code_retrieval.bm25_top_k,
            len(self.chunks),
        )

        indices = np.argsort(scores)[::-1][:top_k]

        return [
            {
                "index": int(index),
                "rank": rank,
                "score": float(scores[index]),
            }
            for rank, index in enumerate(
                indices,
                start=1,
            )
        ]

    def retrieve(
        self,
        question: str,
        *,
        language: str | None = None,
        path: str | None = None,
        kind: str | None = None,
    ):
        logger.info(
            "repository_retrieval_started",
            extra={"event": "code_index.retrieve.started", "query_characters": len(question)},
        )
        candidates = {}

        for result in self.vector_search(question):
            idx = result["index"]

            candidates.setdefault(
                idx,
                {
                    "rrf": 0.0,
                    "vector_rank": None,
                    "bm25_rank": None,
                },
            )

            candidates[idx]["vector_rank"] = result["rank"]

            candidates[idx]["rrf"] += 1.0 / (self.config.code_retrieval.rrf_k + result["rank"])

        for result in self.bm25_search(question):
            idx = result["index"]

            candidates.setdefault(
                idx,
                {
                    "rrf": 0.0,
                    "vector_rank": None,
                    "bm25_rank": None,
                },
            )

            candidates[idx]["bm25_rank"] = result["rank"]

            candidates[idx]["rrf"] += 1.0 / (self.config.code_retrieval.rrf_k + result["rank"])

        results = []

        for idx, scores in candidates.items():
            results.append(
                {
                    **self.chunks[idx],
                    **scores,
                }
            )

        results.sort(
            key=lambda x: x["rrf"],
            reverse=True,
        )

        line_results = [
            item
            for item in results
            if (path is None or item["source"].startswith(path))
            and (
                language is None
                or self.symbol_index.language_registry.detect(item["source"]) == language
            )
        ]
        line_results = line_results[: self.config.code_retrieval.final_top_k]
        for result in line_results:
            result.update(
                {
                    "symbol_identifier": None,
                    "retrieval_method": "line_chunk_fallback",
                    "lexical_rank": result["bm25_rank"],
                    "semantic_rank": result["vector_rank"],
                    "hybrid_score": result["rrf"],
                    "graph_relationship": None,
                }
            )

        symbol_limit = self.config.code_retrieval.final_top_k
        if line_results:
            symbol_limit = max(0, symbol_limit - 1)
        selected = self._symbol_context(
            question, limit=symbol_limit, language=language, path=path, kind=kind
        )
        seen = {(item["source"], item.get("line_start"), item.get("line_end")) for item in selected}
        for result in line_results:
            if len(selected) >= self.config.code_retrieval.final_top_k:
                break
            key = (result["source"], result.get("line_start"), result.get("line_end"))
            if key not in seen:
                selected.append(result)
        logger.info(
            "repository_retrieval_completed",
            extra={"event": "code_index.retrieve.completed", "result_count": len(selected)},
        )
        return selected

    def _symbol_context(
        self,
        question: str,
        *,
        limit: int | None = None,
        language: str | None = None,
        path: str | None = None,
        kind: str | None = None,
    ) -> list[dict[str, Any]]:
        symbol_index = getattr(self, "symbol_index", None)
        if symbol_index is None or not symbol_index.symbols:
            return []
        identifiers = dict.fromkeys(re.findall(r"\b[A-Za-z_]\w*\b", question))
        exact = []
        for identifier in identifiers:
            if language is None and kind is None and path is None:
                exact.extend(symbol_index.find_exact(identifier))
            else:
                exact.extend(
                    symbol_index.find_exact(identifier, language=language, kind=kind, path=path)
                )
        ranked = []
        used: set[str] = set()
        exact_symbols = []
        for symbol in exact:
            if symbol.identifier not in used:
                ranked.append((symbol, "exact_symbol", None, None, None, None))
                exact_symbols.append(symbol)
                used.add(symbol.identifier)
        for symbol in exact_symbols:
            for call in symbol_index.callers(symbol.identifier):
                related = next(
                    (item for item in symbol_index.symbols if item.identifier == call.caller), None
                )
                if related and related.identifier not in used:
                    ranked.append((related, "graph", None, None, None, "caller"))
                    used.add(related.identifier)
            for call in symbol_index.callees(symbol.identifier):
                related = next(
                    (item for item in symbol_index.symbols if item.identifier == call.callee), None
                )
                if related and related.identifier not in used:
                    ranked.append((related, "graph", None, None, None, "callee"))
                    used.add(related.identifier)
            related_edges = [
                edge
                for edge in getattr(symbol_index, "relationships", ())
                if edge.source == symbol.identifier or edge.target_symbol == symbol.identifier
            ]
            for edge in related_edges[:4]:
                related_id = edge.target_symbol if edge.source == symbol.identifier else edge.source
                related = next(
                    (item for item in symbol_index.symbols if item.identifier == related_id), None
                )
                if related and related.identifier not in used:
                    ranked.append((related, "graph", None, None, None, edge.relationship))
                    used.add(related.identifier)
        if language is None and kind is None and path is None:
            hybrid = symbol_index.hybrid_search(
                question,
                self.config.code_retrieval.final_top_k,
                self.config.code_retrieval.rrf_k,
            )
        else:
            hybrid = symbol_index.hybrid_search(
                question,
                self.config.code_retrieval.final_top_k,
                self.config.code_retrieval.rrf_k,
                language=language,
                kind=kind,
                path=path,
            )
        for result in hybrid:
            symbol = result["symbol"]
            if symbol.identifier not in used:
                ranked.append(
                    (
                        symbol,
                        "symbol_hybrid",
                        result["lexical_rank"],
                        result["semantic_rank"],
                        result["hybrid_score"],
                        None,
                    )
                )
                used.add(symbol.identifier)
        result_limit = self.config.code_retrieval.final_top_k if limit is None else limit
        return [
            {
                "text": symbol.source,
                "source": symbol.path,
                "line_start": symbol.start_line,
                "line_end": symbol.end_line,
                "extension": Path(symbol.path).suffix,
                "symbol_identifier": symbol.identifier,
                "symbol_name": symbol.qualified_name,
                "retrieval_method": method,
                "lexical_rank": lexical_rank,
                "semantic_rank": semantic_rank,
                "hybrid_score": hybrid_score,
                "graph_relationship": relationship,
                "vector_rank": semantic_rank,
                "bm25_rank": lexical_rank,
                "rrf": hybrid_score or 0.0,
            }
            for symbol, method, lexical_rank, semantic_rank, hybrid_score, relationship in ranked[
                :result_limit
            ]
        ]

    @staticmethod
    def build_context(
        results,
    ) -> str:
        blocks = []

        for number, result in enumerate(
            results,
            start=1,
        ):
            blocks.append(
                f"[SOURCE {number}: "
                f"{result['source']} "
                f"lines "
                f"{result['line_start']}-"
                f"{result['line_end']}]\n"
                f"{result['text']}"
            )

        return "\n\n".join(blocks)

    def ask(
        self,
        question: str,
    ):
        results = self.retrieve(question)

        context = self.build_context(results)

        prompt = f"""
You are analyzing a software repository.

Use only the retrieved repository context below.

You may:
- explain architecture
- locate implementations
- trace code flow
- identify likely bugs
- explain functions and classes
- compare modules

Rules:

1. Do not claim code exists unless present in the retrieved context.
2. Cite relevant code using [SOURCE 1], [SOURCE 2], etc.
3. Mention filenames and line ranges when useful.
4. If the retrieved code is insufficient, clearly say so.
5. Do not fabricate missing implementation details.

REPOSITORY CONTEXT:

{context}

QUESTION:

{question}

ANSWER:
"""

        answer = self.llm.chat(
            prompt=prompt,
            system_prompt=(
                "You are a senior software engineer analyzing a local source-code repository."
            ),
            temperature=0.1,
            max_tokens=1200,
        )

        return answer, results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local repository hybrid RAG")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--reindex", action="store_true", help="Rebuild line and symbol indexes")
    actions.add_argument("--refresh", action="store_true", help="Incrementally refresh symbols")
    actions.add_argument("--repository-map", action="store_true", help="Print the indexed map")
    actions.add_argument("--find-symbol", metavar="NAME", help="Find an exact symbol")
    actions.add_argument("--search-symbols", metavar="QUERY", help="Hybrid symbol search")
    actions.add_argument("--callers", metavar="SYMBOL", help="Find callers by identifier/name")
    actions.add_argument("--callees", metavar="SYMBOL", help="Find callees by identifier/name")
    actions.add_argument("--imports", metavar="MODULE", help="List imports of a module/path")
    actions.add_argument(
        "--reverse-imports", metavar="MODULE", help="List modules importing a module"
    )
    actions.add_argument("--index-stats", action="store_true", help="Print symbol index statistics")
    actions.add_argument("--list-languages", action="store_true", help="List registered languages")
    actions.add_argument(
        "--show-capabilities", metavar="LANGUAGE", help="Show adapter capabilities"
    )
    actions.add_argument("--implementations", metavar="TYPE_OR_TRAIT", help="Find implementations")
    actions.add_argument("--inheritance", metavar="SYMBOL", help="Show inheritance/impl edges")
    parser.add_argument("--language", help="Filter map/search results by language")
    parser.add_argument("--kind", help="Filter symbol results by kind")
    parser.add_argument("--path", help="Filter symbol results by repository-relative path prefix")
    return parser


def main(argv: list[str] | None = None) -> int:
    config = get_config()
    configure_logging(config.runtime)
    args = build_parser().parse_args(argv)

    if args.list_languages or args.show_capabilities:
        registry = build_language_registry()
        items = registry.items()
        if args.list_languages:
            print(
                json.dumps(
                    [
                        {
                            "language": item.language,
                            "extensions": sorted(item.extensions),
                            "symbol_adapter": item.adapter_type is not None,
                            "line_chunk_fallback": item.legacy_line_chunks,
                        }
                        for item in items
                    ],
                    indent=2,
                )
            )
            return 0
        item = registry.language(args.show_capabilities)
        if item is None:
            print("Language not found.")
            return 1
        try:
            adapter = registry.adapter(item.language)
            reason = ""
        except Exception as exc:
            adapter = None
            reason = str(exc)
        print(
            json.dumps(
                {
                    "language": item.language,
                    "available": adapter is not None,
                    "reason": reason,
                    "capabilities": (
                        {
                            key.value: value.value
                            for key, value in adapter.descriptor.capabilities.items()
                        }
                        if adapter
                        else {}
                    ),
                },
                indent=2,
            )
        )
        return 0

    rag = CodeRAG(config=config)

    if args.reindex:
        rag.reindex(full_symbols=True)
        return 0

    if args.refresh:
        print(json.dumps(asdict(rag.symbol_index.refresh()), indent=2, default=str))
        return 0

    if not rag.load():
        print("No code index found.")
        print("Run with --reindex after placing a repository in:")
        print(rag.repo_dir)
        return 1

    def resolve(value: str):
        matches = rag.symbol_index.find_exact(value)
        return matches[0] if matches else None

    if args.repository_map:
        print(
            rag.symbol_index.render_map()
            if args.language is None
            else rag.symbol_index.render_map(language=args.language)
        )
        return 0
    if args.find_symbol:
        print(
            json.dumps(
                [
                    item.to_dict()
                    for item in rag.symbol_index.find_exact(
                        args.find_symbol, language=args.language, kind=args.kind, path=args.path
                    )
                ],
                indent=2,
            )
        )
        return 0
    if args.search_symbols:
        print(
            json.dumps(
                [
                    {**item, "symbol": item["symbol"].to_dict()}
                    for item in rag.symbol_index.hybrid_search(
                        args.search_symbols, language=args.language, kind=args.kind, path=args.path
                    )
                ],
                indent=2,
            )
        )
        return 0
    if args.callers or args.callees:
        symbol = resolve(args.callers or args.callees)
        if symbol is None:
            print("Symbol not found.")
            return 1
        edges = (
            rag.symbol_index.callers(symbol.identifier)
            if args.callers
            else rag.symbol_index.callees(symbol.identifier)
        )
        print(json.dumps([item.to_dict() for item in edges], indent=2))
        return 0
    if args.imports:
        print(json.dumps(rag.symbol_index.imports_of(args.imports), indent=2))
        return 0
    if args.reverse_imports:
        print(json.dumps(rag.symbol_index.imported_by(args.reverse_imports), indent=2))
        return 0
    if args.index_stats:
        print(json.dumps(rag.symbol_index.stats(), indent=2))
        return 0
    if args.implementations:
        values = rag.symbol_index.implementations_for_type(args.implementations)
        values += [
            item
            for item in rag.symbol_index.implementations_of_trait(args.implementations)
            if item.identifier not in {value.identifier for value in values}
        ]
        print(json.dumps([item.to_dict() for item in values], indent=2))
        return 0
    if args.inheritance:
        symbol = resolve(args.inheritance)
        if symbol is None:
            print("Symbol not found.")
            return 1
        print(
            json.dumps(
                [item.to_dict() for item in rag.symbol_index.inheritance_of(symbol.identifier)],
                indent=2,
            )
        )
        return 0

    print()
    print("LOCAL CODE RAG READY")
    print("Type /exit to quit.")
    print()

    while True:
        question = input("Code question: ").strip()

        if question.lower() in {
            "/exit",
            "exit",
            "quit",
        }:
            break

        if not question:
            continue

        answer, results = rag.ask(question)

        print()
        print(answer)
        print()

        print("Retrieved code:")

        for result in results:
            print(f"- {result['source']} lines {result['line_start']}-{result['line_end']}")

        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
