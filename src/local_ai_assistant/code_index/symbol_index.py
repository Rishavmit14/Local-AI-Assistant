"""Persistent incremental symbol index, graph queries, and hybrid retrieval."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from rank_bm25 import BM25Okapi

from local_ai_assistant.common.errors import CorruptIndexError
from local_ai_assistant.common.logging import get_logger

from .languages import build_language_registry
from .models import (
    CallRecord,
    CapabilityResult,
    CapabilityStatus,
    FileRecord,
    LanguageCapability,
    ReferenceRecord,
    RefreshStats,
    RelationshipRecord,
    Resolution,
    SymbolKind,
    SymbolRecord,
)

logger = get_logger(__name__)
SCHEMA_VERSION = 3


def tokenize(text: str) -> list[str]:
    import re

    return re.findall(r"[A-Za-z0-9_.]+", text.lower())


def embedding_text(symbol: SymbolRecord) -> str:
    parts = [
        f"{symbol.kind.value} {symbol.qualified_name}",
        symbol.signature,
        symbol.documentation,
        symbol.source[:4000],
    ]
    return "\n".join(part for part in parts if part)


class SymbolIndex:
    def __init__(self, repository: Path, index_dir: Path, embedder) -> None:
        self.repository = repository.resolve()
        self.index_dir = index_dir.resolve()
        self.embedder = embedder
        self.language_registry = build_language_registry()
        self.adapters = {}
        self.unavailable_languages: dict[str, str] = {}
        for item in self.language_registry.items():
            if item.adapter_type is None:
                continue
            try:
                self.adapters[item.language] = item.adapter_type()
            except Exception as exc:
                self.unavailable_languages[item.language] = str(exc)
        # Stage 2 compatibility: callers may inject an extractor by extension.
        self.extractors = {
            extension: self.adapters[item.language]
            for item in self.language_registry.items()
            if item.language in self.adapters
            for extension in item.extensions
        }
        self.metadata_file = self.index_dir / "symbol_metadata.json"
        self.symbols_file = self.index_dir / "symbols.json"
        self.graph_file = self.index_dir / "symbol_graph.json"
        self.embeddings_file = self.index_dir / "symbol_embeddings.npy"
        self.faiss_file = self.index_dir / "symbols.faiss"
        self.files: dict[str, FileRecord] = {}
        self.symbols: list[SymbolRecord] = []
        self.references: list[ReferenceRecord] = []
        self.calls: list[CallRecord] = []
        self.relationships: list[RelationshipRecord] = []
        self.embeddings = np.empty((0, 0), dtype=np.float32)
        self.vector_index = None
        self.bm25 = None

    def discover_files(self) -> list[Path]:
        from .repository import SKIP_DIRS

        return sorted(
            path
            for path in self.repository.rglob("*")
            if path.is_file()
            and self.language_registry.detect(path.as_posix()) in self.adapters
            and not any(part in SKIP_DIRS for part in path.parts)
        )

    def refresh(self, *, full: bool = False) -> RefreshStats:
        started = time.perf_counter()
        discovered = self.discover_files()
        current_hashes = {self._relative(path): self._sha256(path) for path in discovered}
        if not full and self.metadata_file.exists():
            self.load()
        else:
            self._clear_memory()
        previous = set(self.files)
        current = set(current_hashes)
        deleted = previous - current
        changed = (
            current
            if full
            else {
                path
                for path, digest in current_hashes.items()
                if path not in self.files or self.files[path].sha256 != digest
            }
        )
        if not full:
            changed.update(
                path
                for path in current
                if path in self.files
                and self.files[path].parser_version
                != self.adapters[self.language_registry.detect(path)].parser_version
            )
        unchanged = current - changed
        retained_symbols = [item for item in self.symbols if item.path not in changed | deleted]
        retained_ids = {item.identifier for item in retained_symbols}
        retained_vectors = np.asarray(
            [
                vector
                for symbol, vector in zip(self.symbols, self.embeddings, strict=False)
                if symbol.identifier in retained_ids
            ],
            dtype=np.float32,
        )
        self.references = [item for item in self.references if item.path not in changed | deleted]
        self.calls = [item for item in self.calls if item.path not in changed | deleted]
        self.relationships = [
            item for item in self.relationships if item.path not in changed | deleted
        ]
        for path in deleted | changed:
            self.files.pop(path, None)
        failures: dict[str, str] = {}
        new_symbols: list[SymbolRecord] = []
        for relative in sorted(changed):
            path = self.repository / relative
            try:
                language = self.language_registry.detect(relative)
                if language is None or language not in self.adapters:
                    continue
                result = self.extractors[path.suffix.lower()].extract(
                    relative, path.read_text(encoding="utf-8", errors="replace")
                )
                self.files[relative] = result.file
                new_symbols.extend(result.symbols)
                self.references.extend(result.references)
                self.calls.extend(result.calls)
                self.relationships.extend(result.relationships)
            except Exception as exc:
                failures[relative] = str(exc)
                logger.warning(
                    "symbol_file_failed",
                    extra={
                        "event": "symbol_index.file_failed",
                        "path": relative,
                        "error": str(exc),
                    },
                )
        new_vectors = self._embed(new_symbols)
        self.symbols = retained_symbols + new_symbols
        self.embeddings = self._combine(retained_vectors, new_vectors)
        self._resolve_graph_edges()
        self._build_search_indexes()
        self.save()
        stats = RefreshStats(
            mode="full" if full else "incremental",
            elapsed_seconds=time.perf_counter() - started,
            discovered_files=len(discovered),
            changed_files=len(changed),
            deleted_files=len(deleted),
            unchanged_files=len(unchanged),
            symbol_count=len(self.symbols),
            embedding_count=len(self.embeddings),
            failures=failures,
        )
        stats.storage_bytes = sum(
            path.stat().st_size for path in self.index_dir.iterdir() if path.is_file()
        )
        logger.info(
            "symbol_refresh_completed",
            extra={"event": "symbol_index.refresh.completed", **asdict(stats)},
        )
        return stats

    def save(self) -> None:
        self.index_dir.mkdir(parents=True, exist_ok=True)
        symbols = json.dumps(
            [item.to_dict() for item in self.symbols], indent=2, ensure_ascii=False
        ).encode()
        graph = json.dumps(
            {
                "references": [item.to_dict() for item in self.references],
                "calls": [item.to_dict() for item in self.calls],
                "relationships": [item.to_dict() for item in self.relationships],
            },
            indent=2,
            ensure_ascii=False,
        ).encode()
        self._atomic_write(self.symbols_file, symbols)
        self._atomic_write(self.graph_file, graph)
        embeddings_temp = self._temporary(self.embeddings_file)
        with embeddings_temp.open("wb") as stream:
            np.save(stream, self.embeddings)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(embeddings_temp, self.embeddings_file)
        if self.vector_index is not None:
            faiss_temp = self._temporary(self.faiss_file)
            faiss.write_index(self.vector_index, str(faiss_temp))
            os.replace(faiss_temp, self.faiss_file)
        elif self.faiss_file.exists():
            self.faiss_file.unlink()
        artifacts = {
            path.name: self._sha256(path)
            for path in (self.symbols_file, self.graph_file, self.embeddings_file)
        }
        if self.faiss_file.exists():
            artifacts[self.faiss_file.name] = self._sha256(self.faiss_file)
        metadata = json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "files": {key: value.to_dict() for key, value in self.files.items()},
                "languages": {
                    name: {
                        "parser_version": adapter.parser_version,
                        "capabilities": {
                            key.value: value.value
                            for key, value in adapter.descriptor.capabilities.items()
                        },
                    }
                    for name, adapter in sorted(self.adapters.items())
                },
                "artifacts": artifacts,
            },
            indent=2,
            sort_keys=True,
        ).encode()
        # Commit marker written last: interrupted earlier replacements are detected
        # against the previous manifest rather than accepted as a valid generation.
        self._atomic_write(self.metadata_file, metadata)

    def load(self) -> bool:
        if not self.metadata_file.exists():
            return False
        try:
            metadata = json.loads(self.metadata_file.read_text(encoding="utf-8"))
            if metadata.get("schema_version") not in {2, SCHEMA_VERSION}:
                raise CorruptIndexError("Unsupported symbol index schema")
            if metadata.get("schema_version") == SCHEMA_VERSION:
                languages = metadata.get("languages")
                if not isinstance(languages, dict):
                    raise CorruptIndexError("Language metadata is missing")
                for language, details in languages.items():
                    if (
                        not isinstance(language, str)
                        or not isinstance(details, dict)
                        or not isinstance(details.get("parser_version"), str)
                        or not isinstance(details.get("capabilities"), dict)
                    ):
                        raise CorruptIndexError("Corrupted language-specific metadata")
            artifacts = metadata.get("artifacts")
            if not isinstance(artifacts, dict):
                raise CorruptIndexError("Symbol index artifact manifest is missing")
            required_names = {
                self.symbols_file.name,
                self.graph_file.name,
                self.embeddings_file.name,
            }
            allowed_names = required_names | {self.faiss_file.name}
            if not required_names.issubset(artifacts) or not set(artifacts).issubset(allowed_names):
                raise CorruptIndexError("Symbol index artifact manifest is invalid")
            for name, expected_hash in artifacts.items():
                artifact = self.index_dir / name
                if not artifact.is_file() or self._sha256(artifact) != expected_hash:
                    raise CorruptIndexError(f"Symbol index artifact failed integrity check: {name}")
            self.files = {
                key: FileRecord.from_dict(value) for key, value in metadata["files"].items()
            }
            self.symbols = [
                SymbolRecord.from_dict(item)
                for item in json.loads(self.symbols_file.read_text(encoding="utf-8"))
            ]
            graph = json.loads(self.graph_file.read_text(encoding="utf-8"))
            self.references = [ReferenceRecord.from_dict(item) for item in graph["references"]]
            self.calls = [CallRecord.from_dict(item) for item in graph["calls"]]
            self.relationships = [
                RelationshipRecord.from_dict(item) for item in graph.get("relationships", [])
            ]
            self.embeddings = np.load(self.embeddings_file, allow_pickle=False)
            if len(self.symbols) != len(self.embeddings):
                raise CorruptIndexError("Symbol/embedding count mismatch")
            self._build_search_indexes()
            if self.symbols:
                if self.faiss_file.name not in artifacts:
                    raise CorruptIndexError("FAISS artifact is missing from manifest")
                persisted_index = faiss.read_index(str(self.faiss_file))
                if (
                    persisted_index.ntotal != len(self.symbols)
                    or persisted_index.d != self.embeddings.shape[1]
                ):
                    raise CorruptIndexError("FAISS index does not match symbol embeddings")
                self.vector_index = persisted_index
        except CorruptIndexError:
            raise
        except (
            EOFError,
            KeyError,
            RuntimeError,
            ValueError,
            TypeError,
            OSError,
            json.JSONDecodeError,
        ) as exc:
            raise CorruptIndexError(f"Corrupted symbol index: {exc}") from exc
        return True

    def find_exact(
        self,
        name: str,
        *,
        language: str | None = None,
        kind: str | None = None,
        path: str | None = None,
    ) -> list[SymbolRecord]:
        return [
            item
            for item in self.symbols
            if (item.name == name or item.qualified_name == name or item.identifier == name)
            and (language is None or item.language == language)
            and (kind is None or item.kind.value == kind)
            and (path is None or item.path.startswith(path))
        ]

    def search_name(
        self, query: str, limit: int = 10, *, language: str | None = None, kind: str | None = None
    ) -> list[SymbolRecord]:
        query = query.lower()
        return sorted(
            (
                item
                for item in self.symbols
                if (query in item.name.lower() or query in item.qualified_name.lower())
                and (language is None or item.language == language)
                and (kind is None or item.kind.value == kind)
            ),
            key=lambda item: (item.name.lower() != query, len(item.qualified_name)),
        )[:limit]

    def lexical_search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        if not self.symbols:
            return []
        scores = self.bm25.get_scores(tokenize(query))
        order = np.argsort(scores)[::-1][:limit]
        return [
            {"symbol": self.symbols[int(index)], "rank": rank, "score": float(scores[index])}
            for rank, index in enumerate(order, 1)
        ]

    def semantic_search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        if not self.symbols:
            return []
        vector = np.asarray(
            self.embedder.encode([query], normalize_embeddings=True, convert_to_numpy=True),
            dtype=np.float32,
        )
        scores, indices = self.vector_index.search(vector, min(limit, len(self.symbols)))
        return [
            {"symbol": self.symbols[int(index)], "rank": rank, "score": float(score)}
            for rank, (score, index) in enumerate(zip(scores[0], indices[0]), 1)
            if index >= 0
        ]

    def hybrid_search(
        self,
        query: str,
        limit: int = 10,
        rrf_k: int = 60,
        *,
        language: str | None = None,
        kind: str | None = None,
        path: str | None = None,
    ) -> list[dict[str, Any]]:
        candidates: dict[str, dict[str, Any]] = {}
        candidate_limit = len(self.symbols) if language or kind or path else limit * 2
        for method, results in (
            ("semantic_rank", self.semantic_search(query, candidate_limit)),
            ("lexical_rank", self.lexical_search(query, candidate_limit)),
        ):
            for result in results:
                symbol = result["symbol"]
                if language is not None and symbol.language != language:
                    continue
                if kind is not None and symbol.kind.value != kind:
                    continue
                if path is not None and not symbol.path.startswith(path):
                    continue
                item = candidates.setdefault(
                    symbol.identifier,
                    {
                        "symbol": symbol,
                        "semantic_rank": None,
                        "lexical_rank": None,
                        "hybrid_score": 0.0,
                    },
                )
                item[method] = result["rank"]
                item["hybrid_score"] += 1 / (rrf_k + result["rank"])
        return sorted(candidates.values(), key=lambda item: item["hybrid_score"], reverse=True)[
            :limit
        ]

    def get_source(self, identifier: str) -> str | None:
        match = next((item for item in self.symbols if item.identifier == identifier), None)
        return match.source if match else None

    def containing_module(self, identifier: str) -> SymbolRecord | None:
        symbol = next((item for item in self.symbols if item.identifier == identifier), None)
        return next(
            (
                item
                for item in self.symbols
                if symbol and item.path == symbol.path and item.kind.value == "module"
            ),
            None,
        )

    def parent(self, identifier: str) -> SymbolRecord | None:
        symbol = next((item for item in self.symbols if item.identifier == identifier), None)
        return next(
            (
                item
                for item in self.symbols
                if symbol and item.identifier == symbol.parent_identifier
            ),
            None,
        )

    def callers(self, identifier: str) -> list[CallRecord]:
        return [item for item in self.calls if item.callee == identifier]

    def callees(self, identifier: str) -> list[CallRecord]:
        return [item for item in self.calls if item.caller == identifier]

    def capability_result(
        self, language: str, capability: LanguageCapability, items: list[Any]
    ) -> CapabilityResult:
        adapter = self.adapters.get(language)
        if adapter is None:
            reason = self.unavailable_languages.get(language, f"No adapter for {language}")
            return CapabilityResult(CapabilityStatus.UNAVAILABLE, reason=reason)
        status = adapter.capability(capability)
        reason = (
            ""
            if status is CapabilityStatus.SUPPORTED
            else (f"{capability.value} analysis is {status.value} for {language}")
        )
        return CapabilityResult(status, tuple(items), reason)

    def callers_result(self, identifier: str) -> CapabilityResult:
        symbol = next((item for item in self.symbols if item.identifier == identifier), None)
        if symbol is None:
            return CapabilityResult(CapabilityStatus.UNAVAILABLE, reason="Symbol not found")
        return self.capability_result(
            symbol.language, LanguageCapability.CALLS, self.callers(identifier)
        )

    def callees_result(self, identifier: str) -> CapabilityResult:
        symbol = next((item for item in self.symbols if item.identifier == identifier), None)
        if symbol is None:
            return CapabilityResult(CapabilityStatus.UNAVAILABLE, reason="Symbol not found")
        return self.capability_result(
            symbol.language, LanguageCapability.CALLS, self.callees(identifier)
        )

    def definitions(self, name: str) -> list[SymbolRecord]:
        return self.find_exact(name)

    def references_to(self, identifier: str) -> list[ReferenceRecord]:
        return [item for item in self.references if item.target_symbol == identifier]

    def imported_by(self, module: str) -> list[str]:
        return sorted(
            path
            for path, record in self.files.items()
            if any(
                value == module or value.startswith(module + "::") or value.startswith(module + ".")
                for value in record.imports
            )
        )

    def imports_of(self, module_or_path: str) -> list[str]:
        record = self.files.get(module_or_path)
        if record is None:
            record = next(
                (
                    item
                    for item in self.files.values()
                    if self.containing_module_for_path(item.path) == module_or_path
                ),
                None,
            )
        return list(record.imports) if record else []

    def containing_module_for_path(self, path: str) -> str:
        module = next(
            (item for item in self.symbols if item.path == path and item.kind is SymbolKind.MODULE),
            None,
        )
        return module.qualified_name if module else path

    def implementations_of_trait(self, trait: str) -> list[SymbolRecord]:
        ids = {
            edge.source
            for edge in self.relationships
            if edge.relationship == "implements"
            and (edge.target == trait or re.sub(r"<.*>$", "", edge.target) == trait)
        }
        return [item for item in self.symbols if item.identifier in ids]

    def implementations_for_type(self, type_name: str) -> list[SymbolRecord]:
        return [
            item
            for item in self.symbols
            if item.kind.value == "implementation"
            and (
                item.metadata.get("implemented_type") == type_name
                or re.sub(r"<.*>$", "", str(item.metadata.get("implemented_type", ""))) == type_name
            )
        ]

    def trait_for_impl(self, identifier: str) -> str | None:
        symbol = next((item for item in self.symbols if item.identifier == identifier), None)
        return (
            str(symbol.metadata.get("implemented_trait"))
            if symbol and symbol.metadata.get("implemented_trait")
            else None
        )

    def methods_for_type(self, type_name: str) -> list[SymbolRecord]:
        parents = {item.identifier for item in self.implementations_for_type(type_name)}
        return [item for item in self.symbols if item.parent_identifier in parents]

    def test_symbols(self, *, language: str | None = None) -> list[SymbolRecord]:
        return [
            item
            for item in self.symbols
            if (language is None or item.language == language)
            and (item.metadata.get("test") or item.metadata.get("cfg_test"))
        ]

    def inheritance_of(self, identifier: str) -> list[RelationshipRecord]:
        return [
            edge
            for edge in self.relationships
            if edge.source == identifier
            and edge.relationship in {"inherits", "implements", "implementation_for"}
        ]

    def relationships_for(
        self, identifier: str, *, relationship: str | None = None
    ) -> list[RelationshipRecord]:
        return [
            edge
            for edge in self.relationships
            if (edge.source == identifier or edge.target_symbol == identifier)
            and (relationship is None or edge.relationship == relationship)
        ]

    def repository_map(self, *, language: str | None = None) -> dict[str, list[dict[str, Any]]]:
        result: dict[str, list[dict[str, Any]]] = {}
        for symbol in self.symbols:
            if language is not None and symbol.language != language:
                continue
            if symbol.kind.value == "module":
                result.setdefault(symbol.path, [])
            else:
                result.setdefault(symbol.path, []).append(
                    {
                        "name": symbol.qualified_name,
                        "kind": symbol.kind.value,
                        "identifier": symbol.identifier,
                        "parent_identifier": symbol.parent_identifier,
                        "language": symbol.language,
                    }
                )
        return dict(sorted(result.items()))

    def render_map(self, *, language: str | None = None) -> str:
        lines = [self.repository.name]
        mapping = self.repository_map(language=language)
        for file_number, (path, symbols) in enumerate(mapping.items()):
            last_file = file_number == len(mapping) - 1
            lines.append(f"{'└──' if last_file else '├──'} {path}")
            identifiers = {item["identifier"] for item in symbols}
            children: dict[str | None, list[dict[str, Any]]] = {}
            for symbol in symbols:
                parent = symbol["parent_identifier"]
                children.setdefault(parent if parent in identifiers else None, []).append(symbol)

            def render(parent, prefix):
                values = children.get(parent, [])
                for number, symbol in enumerate(values):
                    last = number == len(values) - 1
                    label = symbol["name"]
                    lines.append(f"{prefix}{'└──' if last else '├──'} {label} [{symbol['kind']}]")
                    render(symbol["identifier"], prefix + ("    " if last else "│   "))

            render(None, "    " if last_file else "│   ")
        return "\n".join(lines)

    def stats(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for symbol in self.symbols:
            counts[symbol.language] = counts.get(symbol.language, 0) + 1
        return {
            "files": len(self.files),
            "symbols": len(self.symbols),
            "symbols_by_language": counts,
            "embeddings": len(self.embeddings),
            "references": len(self.references),
            "calls": len(self.calls),
            "relationships": len(self.relationships),
            "unavailable_languages": dict(self.unavailable_languages),
            "storage_bytes": sum(
                path.stat().st_size for path in self.index_dir.glob("*") if path.is_file()
            ),
        }

    def _resolve_graph_edges(self) -> None:
        self.relationships = [edge for edge in self.relationships if edge.relationship != "calls"]
        by_name: dict[tuple[str, str], list[SymbolRecord]] = {}
        for symbol in self.symbols:
            by_name.setdefault((symbol.language, symbol.name), []).append(symbol)
            by_name.setdefault((symbol.language, symbol.qualified_name), []).append(symbol)
        resolved_calls = []
        for item in self.calls:
            target = item.callee
            language = self.files.get(item.path).language if item.path in self.files else ""
            matches = by_name.get((language, item.callee_name), [])
            if target is None and len(matches) == 1:
                target = matches[0].identifier
            resolved_calls.append(
                CallRecord(
                    item.caller,
                    item.callee_name,
                    item.path,
                    item.line,
                    Resolution.CONFIRMED if target else Resolution.UNRESOLVED,
                    target,
                )
            )
        self.calls = resolved_calls
        self.references = [
            ReferenceRecord(
                item.source_symbol,
                item.name,
                item.path,
                item.line,
                item.resolution,
                item.target_symbol
                or (
                    by_name[(self.files[item.path].language, item.name)][0].identifier
                    if item.path in self.files
                    and len(by_name.get((self.files[item.path].language, item.name), [])) == 1
                    else None
                ),
            )
            for item in self.references
        ]
        resolved_relationships: list[RelationshipRecord] = []
        for edge in self.relationships:
            normalized = re.sub(r"<.*>$", "", edge.target).strip()
            matches = by_name.get((edge.language, edge.target), []) or by_name.get(
                (edge.language, normalized), []
            )
            target_symbol = edge.target_symbol
            resolution = edge.resolution
            if not edge.external and target_symbol is None and len(matches) == 1:
                target_symbol = matches[0].identifier
                resolution = Resolution.CONFIRMED
            resolved_relationships.append(
                RelationshipRecord(
                    edge.source,
                    edge.target,
                    edge.path,
                    edge.line,
                    edge.language,
                    edge.relationship,
                    resolution,
                    target_symbol,
                    edge.external,
                    edge.evidence,
                )
            )
        self.relationships = resolved_relationships
        existing_imports = {
            (edge.path, edge.target)
            for edge in self.relationships
            if edge.relationship == "imports"
        }
        for path, file in self.files.items():
            module = next(
                (
                    item
                    for item in self.symbols
                    if item.path == path and item.kind is SymbolKind.MODULE
                ),
                None,
            )
            if module is None:
                continue
            for target in file.imports:
                if (path, target) not in existing_imports:
                    matches = by_name.get((file.language, target), [])
                    self.relationships.append(
                        RelationshipRecord(
                            module.identifier,
                            target,
                            path,
                            1,
                            file.language,
                            "imports",
                            Resolution.CONFIRMED if len(matches) == 1 else Resolution.SYNTACTIC,
                            matches[0].identifier if len(matches) == 1 else None,
                            False,
                            target,
                        )
                    )
        for call in self.calls:
            language = self.files.get(call.path).language if call.path in self.files else "unknown"
            self.relationships.append(
                RelationshipRecord(
                    call.caller,
                    call.callee_name,
                    call.path,
                    call.line,
                    language,
                    "calls",
                    call.resolution,
                    call.callee,
                    False,
                    call.callee_name,
                )
            )

    def _embed(self, symbols: list[SymbolRecord]) -> np.ndarray:
        if not symbols:
            return np.empty(
                (
                    0,
                    self.embeddings.shape[1]
                    if self.embeddings.ndim == 2 and self.embeddings.size
                    else 0,
                ),
                dtype=np.float32,
            )
        return np.asarray(
            self.embedder.encode(
                [self._embedding_text(item) for item in symbols],
                normalize_embeddings=True,
                convert_to_numpy=True,
            ),
            dtype=np.float32,
        )

    def _embedding_text(self, symbol: SymbolRecord) -> str:
        adapter = self.adapters.get(symbol.language)
        return adapter.embedding_text(symbol) if adapter is not None else embedding_text(symbol)

    @staticmethod
    def _combine(first: np.ndarray, second: np.ndarray) -> np.ndarray:
        if not len(first):
            return second
        if not len(second):
            return first
        return np.vstack((first, second))

    def _build_search_indexes(self) -> None:
        self.bm25 = (
            BM25Okapi([tokenize(self._embedding_text(item)) for item in self.symbols])
            if self.symbols
            else None
        )
        if len(self.embeddings):
            if self.embeddings.ndim != 2:
                raise CorruptIndexError("Embeddings must be a two-dimensional matrix")
            self.vector_index = faiss.IndexFlatIP(self.embeddings.shape[1])
            self.vector_index.add(self.embeddings)
        else:
            self.vector_index = None

    def _clear_memory(self) -> None:
        self.files, self.symbols, self.references, self.calls, self.relationships = (
            {},
            [],
            [],
            [],
            [],
        )
        self.embeddings = np.empty((0, 0), dtype=np.float32)

    def _relative(self, path: Path) -> str:
        return path.relative_to(self.repository).as_posix()

    @staticmethod
    def _sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _temporary(path: Path) -> Path:
        return path.with_name(f".{path.name}.tmp")

    @classmethod
    def _atomic_write(cls, path: Path, content: bytes) -> None:
        temporary = cls._temporary(path)
        with temporary.open("wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
