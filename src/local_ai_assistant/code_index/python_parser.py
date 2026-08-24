"""Tree-sitter backed deterministic Python symbol extraction."""

from __future__ import annotations

import ast
import hashlib
from functools import cached_property
from pathlib import Path

from local_ai_assistant.common.errors import ParserUnavailableError

from .adapters import AdapterDescriptor, LanguageAdapter, stable_symbol_id
from .models import (
    CallRecord,
    CapabilityStatus,
    ExtractionResult,
    FileRecord,
    LanguageCapability,
    ReferenceRecord,
    Resolution,
    SymbolKind,
    SymbolRecord,
)


def _identifier(path: str, qualified_name: str, kind: SymbolKind) -> str:
    return stable_symbol_id("python", path, qualified_name, kind)


def _text(source: bytes, node) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


class PythonSymbolExtractor(LanguageAdapter):
    language = "python"
    extensions = frozenset({".py"})
    descriptor = AdapterDescriptor(
        "python",
        extensions,
        {
            LanguageCapability.SYMBOLS: CapabilityStatus.SUPPORTED,
            LanguageCapability.IMPORTS: CapabilityStatus.SUPPORTED,
            LanguageCapability.REFERENCES: CapabilityStatus.PARTIAL,
            LanguageCapability.CALLS: CapabilityStatus.PARTIAL,
            LanguageCapability.VISIBILITY: CapabilityStatus.PARTIAL,
            LanguageCapability.MODULES: CapabilityStatus.SUPPORTED,
            LanguageCapability.TESTS: CapabilityStatus.PARTIAL,
        },
        "tree-sitter-python",
        "0.25",
    )

    def capability(self, capability: LanguageCapability) -> CapabilityStatus:
        return self.descriptor.capabilities.get(capability, CapabilityStatus.UNAVAILABLE)

    @cached_property
    def parser_version(self) -> str:
        try:
            from importlib.metadata import version

            return version(self.descriptor.parser_package)
        except Exception:
            return self.descriptor.parser_version

    @staticmethod
    def embedding_text(symbol: SymbolRecord) -> str:
        return "\n".join(
            part
            for part in (
                "language python",
                f"{symbol.kind.value} {symbol.qualified_name}",
                symbol.signature,
                symbol.documentation,
                symbol.source[:4000],
            )
            if part
        )

    def __init__(self) -> None:
        try:
            import tree_sitter_python
            from tree_sitter import Language, Parser

            language = Language(tree_sitter_python.language())
            self.parser = Parser(language)
            _ = self.parser_version
        except (ImportError, TypeError, ValueError) as exc:
            raise ParserUnavailableError(
                "Python symbol indexing requires tree-sitter and tree-sitter-python"
            ) from exc

    def extract(self, path: str, source_text: str) -> ExtractionResult:
        source = source_text.encode("utf-8")
        digest = hashlib.sha256(source).hexdigest()
        tree = self.parser.parse(source)
        module_name = self.module_name(path)
        module_id = _identifier(path, module_name, SymbolKind.MODULE)
        imports = tuple(self._imports(source_text, module_name, path.endswith("/__init__.py")))
        errors = tuple(self._errors(tree.root_node))
        module = SymbolRecord(
            identifier=module_id,
            path=path,
            language="python",
            kind=SymbolKind.MODULE,
            name=module_name.rsplit(".", 1)[-1],
            qualified_name=module_name,
            parent_identifier=None,
            start_line=1,
            end_line=max(1, len(source_text.splitlines())),
            source=source_text,
            documentation=self._module_docstring(source_text),
            imports=imports,
            source_hash=digest,
        )
        symbols: list[SymbolRecord] = [module]
        references: list[ReferenceRecord] = []
        calls: list[CallRecord] = []
        self._walk_definitions(
            tree.root_node, source, path, module_name, module_id, digest, imports, symbols
        )
        definitions_by_name: dict[str, list[SymbolRecord]] = {}
        for symbol in symbols:
            definitions_by_name.setdefault(symbol.name, []).append(symbol)
        self._walk_uses(
            tree.root_node, source, path, module_id, symbols, definitions_by_name, references, calls
        )
        file_record = FileRecord(
            path,
            "python",
            digest,
            imports,
            errors,
            self.parser_version,
            {key.value: value.value for key, value in self.descriptor.capabilities.items()},
            self.descriptor.parser_package,
            self.descriptor.adapter_version,
        )
        return ExtractionResult(file_record, tuple(symbols), tuple(references), tuple(calls))

    @staticmethod
    def module_name(path: str) -> str:
        value = Path(path).with_suffix("").as_posix().replace("/", ".")
        return value[:-9] if value.endswith(".__init__") else value

    def _walk_definitions(
        self, node, source, path, parent_qname, parent_id, digest, imports, output
    ):
        for child in node.named_children:
            definition = child
            decorators: tuple[str, ...] = ()
            if child.type == "decorated_definition":
                decorators = tuple(
                    _text(source, item).lstrip("@").strip()
                    for item in child.named_children
                    if item.type == "decorator"
                )
                definition = next(
                    (
                        item
                        for item in child.named_children
                        if item.type in {"function_definition", "class_definition"}
                    ),
                    child,
                )
            if definition.type in {"function_definition", "class_definition"}:
                name_node = definition.child_by_field_name("name")
                if name_node is None:
                    continue
                name = _text(source, name_node)
                qname = f"{parent_qname}.{name}"
                parent = next((item for item in output if item.identifier == parent_id), None)
                if definition.type == "class_definition":
                    kind = SymbolKind.CLASS
                elif parent and parent.kind is SymbolKind.CLASS:
                    kind = SymbolKind.METHOD
                elif definition.child(0).type == "async":
                    kind = SymbolKind.ASYNC_FUNCTION
                else:
                    kind = SymbolKind.FUNCTION
                symbol_id = _identifier(path, qname, kind)
                body = definition.child_by_field_name("body")
                signature_end = body.start_byte if body is not None else definition.end_byte
                signature = (
                    source[definition.start_byte : signature_end]
                    .decode(errors="replace")
                    .rstrip()
                    .rstrip(":")
                )
                symbol = SymbolRecord(
                    identifier=symbol_id,
                    path=path,
                    language="python",
                    kind=kind,
                    name=name,
                    qualified_name=qname,
                    parent_identifier=parent_id,
                    start_line=child.start_point.row + 1,
                    end_line=child.end_point.row + 1,
                    source=_text(source, child),
                    signature=signature,
                    documentation=self._body_docstring(body, source),
                    decorators=decorators,
                    visibility="private"
                    if name.startswith("_") and not name.startswith("__")
                    else "public",
                    imports=imports,
                    source_hash=hashlib.sha256(_text(source, child).encode()).hexdigest(),
                )
                output.append(symbol)
                if body is not None:
                    self._walk_definitions(
                        body, source, path, qname, symbol_id, digest, imports, output
                    )
            elif child.type not in {"function_definition", "class_definition"}:
                self._walk_definitions(
                    child, source, path, parent_qname, parent_id, digest, imports, output
                )

    def _walk_uses(self, root, source, path, module_id, symbols, definitions, references, calls):
        ranged = sorted(
            symbols[1:], key=lambda item: (item.end_line - item.start_line, item.start_line)
        )
        for node in self._descendants(root):
            line = node.start_point.row + 1
            owner = next(
                (item for item in ranged if item.start_line <= line <= item.end_line), None
            )
            owner_id = owner.identifier if owner else module_id
            if node.type == "call":
                function = node.child_by_field_name("function")
                if function is None:
                    continue
                name = _text(source, function).split(".")[-1]
                target = (
                    self._resolve(name, owner, definitions)
                    if function.type == "identifier"
                    else None
                )
                calls.append(
                    CallRecord(
                        owner_id,
                        name,
                        path,
                        line,
                        Resolution.CONFIRMED if target else Resolution.UNRESOLVED,
                        target.identifier if target else None,
                    )
                )
            elif (
                node.type == "identifier"
                and node.parent
                and node.parent.type
                not in {
                    "function_definition",
                    "class_definition",
                    "parameters",
                    "import_statement",
                    "import_from_statement",
                }
            ):
                name = _text(source, node)
                target = self._resolve(name, owner, definitions)
                references.append(
                    ReferenceRecord(
                        owner_id,
                        name,
                        path,
                        line,
                        Resolution.SYNTACTIC,
                        target.identifier if target else None,
                    )
                )

    @staticmethod
    def _resolve(name, owner, definitions):
        matches = definitions.get(name, [])
        if len(matches) == 1:
            return matches[0]
        return None

    @staticmethod
    def _descendants(node):
        for child in node.named_children:
            yield child
            yield from PythonSymbolExtractor._descendants(child)

    @staticmethod
    def _errors(root):
        nodes = [root, *PythonSymbolExtractor._descendants(root)]
        errors = [
            f"syntax error at line {node.start_point.row + 1}"
            for node in nodes
            if node.type == "ERROR" or node.is_missing
        ]
        if root.has_error and not errors:
            errors.append("syntax error in parse tree")
        return errors

    @staticmethod
    def _imports(source_text: str, module_name: str, is_package_module: bool = False) -> list[str]:
        try:
            tree = ast.parse(source_text)
        except SyntaxError:
            return []
        values: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                values.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    package = module_name.split(".")
                    if not is_package_module:
                        package = package[:-1]
                    keep = max(0, len(package) - (node.level - 1))
                    parts = package[:keep]
                    if node.module:
                        parts.extend(node.module.split("."))
                    values.append(".".join(parts))
                else:
                    values.append(node.module or "")
        return sorted(set(values))

    @staticmethod
    def _module_docstring(source_text: str) -> str:
        try:
            return ast.get_docstring(ast.parse(source_text), clean=False) or ""
        except SyntaxError:
            return ""

    @staticmethod
    def _body_docstring(body, source: bytes) -> str:
        if body is None or not body.named_children:
            return ""
        first = body.named_children[0]
        if first.type != "expression_statement" or not first.named_children:
            return ""
        value = first.named_children[0]
        if value.type not in {"string", "concatenated_string"}:
            return ""
        try:
            return ast.literal_eval(_text(source, value))
        except (SyntaxError, ValueError):
            return ""
