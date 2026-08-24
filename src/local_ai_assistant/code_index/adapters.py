"""Typed language-adapter contracts and shared Tree-sitter helpers."""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import warnings
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from local_ai_assistant.common.errors import ParserUnavailableError

from .models import CapabilityStatus, ExtractionResult, LanguageCapability, SymbolKind


@dataclass(frozen=True, slots=True)
class AdapterDescriptor:
    language: str
    extensions: frozenset[str]
    capabilities: dict[LanguageCapability, CapabilityStatus]
    parser_package: str
    parser_version: str
    adapter_version: str = "1"


class LanguageAdapter(ABC):
    descriptor: AdapterDescriptor

    @property
    def language(self) -> str:
        return self.descriptor.language

    @property
    def extensions(self) -> frozenset[str]:
        return self.descriptor.extensions

    @cached_property
    def parser_version(self) -> str:
        try:
            return importlib.metadata.version(self.descriptor.parser_package)
        except importlib.metadata.PackageNotFoundError:
            return self.descriptor.parser_version

    def capability(self, capability: LanguageCapability) -> CapabilityStatus:
        return self.descriptor.capabilities.get(capability, CapabilityStatus.UNAVAILABLE)

    @property
    def parser_identity(self) -> dict[str, object]:
        """Return every deterministic input that controls extracted records."""
        return {
            "parser_package": self.descriptor.parser_package,
            "parser_version": self.parser_version,
            "adapter_version": self.descriptor.adapter_version,
            "capabilities": {
                key.value: value.value
                for key, value in sorted(
                    self.descriptor.capabilities.items(), key=lambda item: item[0].value
                )
            },
        }

    @abstractmethod
    def extract(self, path: str, source_text: str) -> ExtractionResult: ...

    def parse_source(self, path: str, source_text: str) -> ExtractionResult:
        return self.extract(path, source_text)

    def parse_file(self, path: Path, *, relative_path: str | None = None) -> ExtractionResult:
        return self.extract(
            relative_path or path.as_posix(),
            path.read_text(encoding="utf-8", errors="replace"),
        )

    def embedding_text(self, symbol) -> str:
        metadata = " ".join(f"{key}={value}" for key, value in sorted(symbol.metadata.items()))
        return "\n".join(
            part
            for part in (
                f"language {self.language}",
                f"{symbol.kind.value} {symbol.qualified_name}",
                symbol.signature,
                symbol.documentation,
                metadata,
                symbol.source[:4000],
            )
            if part
        )


class TreeSitterAdapter(LanguageAdapter):
    grammar_module: str
    grammar_function = "language"

    def __init__(self) -> None:
        try:
            grammar = importlib.import_module(self.grammar_module)
            from tree_sitter import Language, Parser

            handle = getattr(grammar, self.grammar_function)()
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore", message="int argument support is deprecated", category=DeprecationWarning
                )
                language = Language(handle)
            self.parser = Parser(language)
            # Resolve package identity during adapter construction, outside refresh timing.
            _ = self.parser_version
        except (ImportError, AttributeError, TypeError, ValueError) as exc:
            raise ParserUnavailableError(
                f"{self.language} indexing requires {self.descriptor.parser_package}"
            ) from exc

    def _parse_tree(self, source_text: str):
        return self.parser.parse(source_text.encode("utf-8"))

    @staticmethod
    def text(source: bytes, node) -> str:
        return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")

    @classmethod
    def errors(cls, root) -> tuple[str, ...]:
        errors: list[str] = []
        for node in (root, *cls.descendants(root)):
            if node.type == "ERROR" or node.is_missing:
                errors.append(f"syntax error at line {node.start_point.row + 1}")
        if root.has_error and not errors:
            errors.append("syntax error in parse tree")
        return tuple(dict.fromkeys(errors))

    @classmethod
    def descendants(cls, node):
        for child in node.named_children:
            yield child
            yield from cls.descendants(child)


def stable_symbol_id(language: str, path: str, qualified_name: str, kind: SymbolKind) -> str:
    identity = f"{language}\0{path}\0{qualified_name}\0{kind.value}"
    prefix = {
        "python": "py",
        "rust": "rs",
        "solidity": "sol",
        "typescript": "ts",
        "javascript": "js",
        "sql": "sql",
        "c": "c",
        "cpp": "cpp",
        "java": "java",
        "shell": "sh",
    }.get(language, language[:4])
    return f"{prefix}:" + hashlib.sha256(identity.encode()).hexdigest()[:24]


def module_identity(language: str, path: str) -> str:
    value = Path(path).as_posix()
    if language == "rust":
        stem = Path(value).with_suffix("").as_posix()
        if stem in {"src/lib", "src/main"}:
            return "crate"
        if stem.endswith("/mod"):
            stem = stem[:-4]
        if stem.startswith("src/"):
            stem = stem[4:]
        return "crate" + ("::" + stem.replace("/", "::") if stem else "")
    return Path(value).with_suffix("").as_posix().replace("/", ".")


def source_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()
