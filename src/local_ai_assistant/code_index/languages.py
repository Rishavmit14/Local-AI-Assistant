"""Authoritative language and extension registry."""

from __future__ import annotations

from dataclasses import dataclass

from local_ai_assistant.common.errors import ParserUnavailableError

from .adapters import LanguageAdapter


@dataclass(frozen=True, slots=True)
class RegisteredLanguage:
    language: str
    extensions: frozenset[str]
    adapter_type: type[LanguageAdapter] | None
    legacy_line_chunks: bool = True


class LanguageRegistry:
    def __init__(self) -> None:
        self._languages: dict[str, RegisteredLanguage] = {}
        self._extensions: dict[str, str] = {}
        self._aliases: dict[str, str] = {}
        self._frozen = False

    def register(self, item: RegisteredLanguage) -> None:
        if item.language in self._languages:
            raise ValueError(f"Duplicate language: {item.language}")
        for extension in item.extensions:
            normalized = extension.lower()
            if normalized in self._extensions:
                raise ValueError(f"Extension already registered: {normalized}")
        if self._frozen:
            raise RuntimeError("Language registry is frozen")
        for extension in item.extensions:
            normalized = extension.lower()
            self._extensions[normalized] = item.language
        self._languages[item.language] = item

    def register_alias(self, alias: str, language: str) -> None:
        if self._frozen:
            raise RuntimeError("Language registry is frozen")
        normalized = alias.strip().lower()
        if normalized in self._languages or normalized in self._aliases:
            raise ValueError(f"Duplicate language alias: {normalized}")
        if language not in self._languages:
            raise ValueError(f"Unknown language for alias: {language}")
        self._aliases[normalized] = language

    def freeze(self) -> None:
        self._frozen = True

    def normalize(self, name: str) -> str | None:
        normalized = name.strip().lower()
        if normalized in self._languages:
            return normalized
        return self._aliases.get(normalized)

    def detect(self, path: str) -> str | None:
        from pathlib import Path

        return self._extensions.get(Path(path).suffix.lower())

    def language(self, name: str) -> RegisteredLanguage | None:
        normalized = self.normalize(name)
        return self._languages.get(normalized) if normalized else None

    def adapter(self, name: str) -> LanguageAdapter:
        normalized = self.normalize(name)
        item = self._languages.get(normalized) if normalized else None
        if item is None or item.adapter_type is None:
            raise ParserUnavailableError(f"No symbol adapter is available for {name}")
        return item.adapter_type()

    def items(self) -> tuple[RegisteredLanguage, ...]:
        return tuple(self._languages[key] for key in sorted(self._languages))

    @property
    def extensions(self) -> frozenset[str]:
        return frozenset(self._extensions)


def build_language_registry() -> LanguageRegistry:
    from .generic_adapters import (
        BashAdapter,
        CAdapter,
        CppAdapter,
        JavaAdapter,
        JavaScriptAdapter,
        SolidityAdapter,
        SqlAdapter,
        TypeScriptAdapter,
    )
    from .python_parser import PythonSymbolExtractor
    from .rust_parser import RustAdapter

    registry = LanguageRegistry()
    for language, extensions, adapter in (
        ("python", {".py"}, PythonSymbolExtractor),
        ("rust", {".rs"}, RustAdapter),
        ("solidity", {".sol"}, SolidityAdapter),
        ("javascript", {".js", ".jsx", ".mjs", ".cjs"}, JavaScriptAdapter),
        ("typescript", {".ts", ".tsx", ".mts", ".cts"}, TypeScriptAdapter),
        ("sql", {".sql"}, SqlAdapter),
        ("c", {".c", ".h"}, CAdapter),
        ("cpp", {".cc", ".cpp", ".cxx", ".hpp", ".hh", ".hxx"}, CppAdapter),
        ("java", {".java"}, JavaAdapter),
        ("shell", {".sh", ".bash"}, BashAdapter),
    ):
        registry.register(RegisteredLanguage(language, frozenset(extensions), adapter))
    for language, extensions in (
        ("go", {".go"}),
        ("toml", {".toml"}),
        ("yaml", {".yaml", ".yml"}),
        ("json", {".json"}),
        ("markdown", {".md"}),
    ):
        registry.register(RegisteredLanguage(language, frozenset(extensions), None))
    for alias, language in (
        ("py", "python"),
        ("rs", "rust"),
        ("sol", "solidity"),
        ("js", "javascript"),
        ("ts", "typescript"),
        ("c++", "cpp"),
        ("cxx", "cpp"),
        ("bash", "shell"),
        ("sh", "shell"),
    ):
        registry.register_alias(alias, language)
    registry.freeze()
    return registry
