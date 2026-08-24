"""Typed, language-extensible records for deterministic code intelligence."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class SymbolKind(StrEnum):
    MODULE = "module"
    FUNCTION = "function"
    ASYNC_FUNCTION = "async_function"
    CLASS = "class"
    METHOD = "method"
    STRUCT = "struct"
    TRAIT = "trait"
    INTERFACE = "interface"
    CONTRACT = "contract"
    ENUM = "enum"
    IMPLEMENTATION = "implementation"
    NAMESPACE = "namespace"
    ENUM_VARIANT = "enum_variant"
    LIBRARY = "library"
    EVENT = "event"
    ERROR = "error"
    MODIFIER = "modifier"
    CONSTRUCTOR = "constructor"
    FUNCTION_DECLARATION = "function_declaration"
    TYPE_ALIAS = "type_alias"
    CONSTANT = "constant"
    VARIABLE = "variable"
    MACRO = "macro"
    SQL_TABLE = "sql_table"
    SQL_VIEW = "sql_view"
    SQL_FUNCTION = "sql_function"
    SQL_PROCEDURE = "sql_procedure"
    SQL_INDEX = "sql_index"
    SQL_TRIGGER = "sql_trigger"
    SHELL_FUNCTION = "shell_function"


class Resolution(StrEnum):
    CONFIRMED = "confirmed_definition"
    SYNTACTIC = "syntactic_reference"
    UNRESOLVED = "unresolved_reference"
    EXTERNAL = "external_reference"


class CapabilityStatus(StrEnum):
    SUPPORTED = "supported"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class LanguageCapability(StrEnum):
    SYMBOLS = "symbols"
    IMPORTS = "imports"
    REFERENCES = "references"
    CALLS = "calls"
    VISIBILITY = "visibility"
    INHERITANCE = "inheritance"
    IMPLEMENTATIONS = "implementations"
    MODULES = "modules"
    CONTRACTS = "contracts"
    SQL_OBJECTS = "sql_objects"
    TESTS = "tests"


@dataclass(frozen=True, slots=True)
class SymbolRecord:
    identifier: str
    path: str
    language: str
    kind: SymbolKind
    name: str
    qualified_name: str
    parent_identifier: str | None
    start_line: int
    end_line: int
    source: str
    signature: str = ""
    documentation: str = ""
    decorators: tuple[str, ...] = ()
    visibility: str = "public"
    imports: tuple[str, ...] = ()
    source_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["kind"] = self.kind.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SymbolRecord:
        values = dict(data)
        values["kind"] = SymbolKind(values["kind"])
        values["decorators"] = tuple(values.get("decorators", ()))
        values["imports"] = tuple(values.get("imports", ()))
        values["metadata"] = dict(values.get("metadata", {}))
        return cls(**values)


@dataclass(frozen=True, slots=True)
class ReferenceRecord:
    source_symbol: str
    name: str
    path: str
    line: int
    resolution: Resolution
    target_symbol: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["resolution"] = self.resolution.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReferenceRecord:
        values = dict(data)
        values["resolution"] = Resolution(values["resolution"])
        return cls(**values)


@dataclass(frozen=True, slots=True)
class CallRecord:
    caller: str
    callee_name: str
    path: str
    line: int
    resolution: Resolution
    callee: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["resolution"] = self.resolution.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CallRecord:
        values = dict(data)
        values["resolution"] = Resolution(values["resolution"])
        return cls(**values)


@dataclass(frozen=True, slots=True)
class FileRecord:
    path: str
    language: str
    sha256: str
    imports: tuple[str, ...] = ()
    parse_errors: tuple[str, ...] = ()
    parser_version: str = ""
    capabilities: dict[str, str] = field(default_factory=dict)
    parser_package: str = ""
    adapter_version: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FileRecord:
        values = dict(data)
        values["imports"] = tuple(values.get("imports", ()))
        values["parse_errors"] = tuple(values.get("parse_errors", ()))
        values["capabilities"] = dict(values.get("capabilities", {}))
        return cls(**values)


@dataclass(frozen=True, slots=True)
class RelationshipRecord:
    source: str
    target: str
    path: str
    line: int
    language: str
    relationship: str
    resolution: Resolution
    target_symbol: str | None = None
    external: bool = False
    evidence: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["resolution"] = self.resolution.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RelationshipRecord:
        values = dict(data)
        values["resolution"] = Resolution(values["resolution"])
        return cls(**values)


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    file: FileRecord
    symbols: tuple[SymbolRecord, ...]
    references: tuple[ReferenceRecord, ...] = ()
    calls: tuple[CallRecord, ...] = ()
    relationships: tuple[RelationshipRecord, ...] = ()


@dataclass(frozen=True, slots=True)
class CapabilityResult:
    status: CapabilityStatus
    items: tuple[Any, ...] = ()
    reason: str = ""


@dataclass(frozen=True, slots=True)
class ContextProvenance:
    source: str
    line_start: int
    line_end: int
    symbol_identifier: str | None
    retrieval_method: str
    lexical_rank: int | None = None
    semantic_rank: int | None = None
    hybrid_score: float | None = None
    graph_relationship: str | None = None


@dataclass(slots=True)
class RefreshStats:
    mode: str
    elapsed_seconds: float
    discovered_files: int
    changed_files: int
    deleted_files: int
    unchanged_files: int
    symbol_count: int
    embedding_count: int
    storage_bytes: int = 0
    failures: dict[str, str] = field(default_factory=dict)
