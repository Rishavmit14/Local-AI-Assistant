"""Conservative Tree-sitter adapters for Stage 6 languages beyond Rust."""

from __future__ import annotations

import re
from pathlib import Path

from .adapters import (
    AdapterDescriptor,
    TreeSitterAdapter,
    module_identity,
    source_hash,
    stable_symbol_id,
)
from .models import (
    CallRecord,
    CapabilityStatus,
    ExtractionResult,
    FileRecord,
    LanguageCapability,
    ReferenceRecord,
    RelationshipRecord,
    Resolution,
    SymbolKind,
    SymbolRecord,
)


class DeclarativeAdapter(TreeSitterAdapter):
    node_kinds: dict[str, SymbolKind] = {}
    container_kinds = {
        SymbolKind.CLASS,
        SymbolKind.STRUCT,
        SymbolKind.TRAIT,
        SymbolKind.INTERFACE,
        SymbolKind.CONTRACT,
        SymbolKind.LIBRARY,
        SymbolKind.ENUM,
        SymbolKind.NAMESPACE,
        SymbolKind.IMPLEMENTATION,
    }
    method_parent_kinds = {
        SymbolKind.CLASS,
        SymbolKind.STRUCT,
        SymbolKind.TRAIT,
        SymbolKind.INTERFACE,
        SymbolKind.CONTRACT,
        SymbolKind.LIBRARY,
        SymbolKind.IMPLEMENTATION,
    }
    import_node_types: frozenset[str] = frozenset()
    call_node_types: frozenset[str] = frozenset({"call_expression"})

    def extract(self, path: str, source_text: str) -> ExtractionResult:
        source = source_text.encode()
        tree = self._parse_tree(source_text)
        module_name = module_identity(self.language, path)
        digest = source_hash(source_text)
        module_id = stable_symbol_id(self.language, path, module_name, SymbolKind.MODULE)
        imports, relationships = self._extract_imports(tree.root_node, source, path, module_id)
        module = SymbolRecord(
            module_id,
            path,
            self.language,
            SymbolKind.MODULE,
            Path(path).stem,
            module_name,
            None,
            1,
            max(1, len(source_text.splitlines())),
            source_text,
            imports=tuple(imports),
            source_hash=digest,
        )
        symbols = [module]
        self._walk_symbols(
            tree.root_node,
            source,
            path,
            module_name,
            module_id,
            tuple(imports),
            symbols,
            relationships,
        )
        definitions: dict[str, list[SymbolRecord]] = {}
        for symbol in symbols:
            definitions.setdefault(symbol.name, []).append(symbol)
            definitions.setdefault(symbol.qualified_name, []).append(symbol)
        references, calls = self._extract_uses(
            tree.root_node, source, path, module_id, symbols, definitions
        )
        file = FileRecord(
            path,
            self.language,
            digest,
            tuple(imports),
            self.errors(tree.root_node),
            self.parser_version,
            {key.value: value.value for key, value in self.descriptor.capabilities.items()},
            self.descriptor.parser_package,
            self.descriptor.adapter_version,
        )
        return ExtractionResult(
            file, tuple(symbols), tuple(references), tuple(calls), tuple(relationships)
        )

    def _walk_symbols(
        self, node, source, path, parent_qname, parent_id, imports, output, relationships
    ):
        for child in node.named_children:
            kind = self.node_kinds.get(child.type)
            if kind is None:
                self._walk_symbols(
                    child, source, path, parent_qname, parent_id, imports, output, relationships
                )
                continue
            name = self._symbol_name(child, source, kind)
            if not name:
                continue
            parent = next((item for item in output if item.identifier == parent_id), None)
            if kind is SymbolKind.FUNCTION and parent and parent.kind in self.method_parent_kinds:
                kind = SymbolKind.METHOD
            if name == "constructor" and parent and parent.kind is SymbolKind.CLASS:
                kind = SymbolKind.CONSTRUCTOR
            if kind is SymbolKind.FUNCTION and re.search(
                r"\basync\s+(?:function\s+)?", self.text(source, child)[:100]
            ):
                kind = SymbolKind.ASYNC_FUNCTION
            qname = self._qualified(parent_qname, name)
            symbol_id = stable_symbol_id(self.language, path, qname, kind)
            body = self._body(child)
            signature_end = body.start_byte if body is not None else child.end_byte
            raw = self.text(source, child)
            metadata = self._metadata(child, source, kind)
            symbol = SymbolRecord(
                symbol_id,
                path,
                self.language,
                kind,
                name,
                qname,
                parent_id,
                child.start_point.row + 1,
                child.end_point.row + 1,
                raw,
                source[child.start_byte : signature_end].decode(errors="replace").rstrip(),
                self._documentation(node, child, source),
                tuple(self._attributes(child, source)),
                self._visibility(child, source),
                imports,
                source_hash(raw),
                metadata,
            )
            output.append(symbol)
            relationships.extend(self._symbol_relationships(symbol, child, source))
            if body is not None:
                self._walk_symbols(
                    body, source, path, qname, symbol_id, imports, output, relationships
                )

    def _extract_imports(self, root, source, path, module_id):
        imports: list[str] = []
        relationships: list[RelationshipRecord] = []
        for node in self.descendants(root):
            if node.type not in self.import_node_types:
                continue
            raw = self.text(source, node).strip()
            for target, external, broad in self._import_targets(raw):
                imports.append(target)
                relationships.append(
                    RelationshipRecord(
                        module_id,
                        target,
                        path,
                        node.start_point.row + 1,
                        self.language,
                        "imports",
                        Resolution.EXTERNAL
                        if external
                        else (Resolution.UNRESOLVED if broad else Resolution.SYNTACTIC),
                        external=external,
                        evidence=raw,
                    )
                )
        return sorted(set(imports)), relationships

    def _extract_uses(self, root, source, path, module_id, symbols, definitions):
        refs: list[ReferenceRecord] = []
        calls: list[CallRecord] = []
        ranged = sorted(
            symbols[1:], key=lambda item: (item.end_line - item.start_line, item.start_line)
        )
        for node in self.descendants(root):
            line = node.start_point.row + 1
            owner = next(
                (item for item in ranged if item.start_line <= line <= item.end_line), None
            )
            owner_id = owner.identifier if owner else module_id
            if node.type in self.call_node_types:
                function = node.child_by_field_name("function") or node.child_by_field_name("name")
                if function is None:
                    continue
                raw = self.text(source, function)
                name = re.split(r"[.:>]", raw)[-1]
                matches = definitions.get(name, [])
                direct = function.type in {"identifier", "scoped_identifier"} and len(matches) == 1
                calls.append(
                    CallRecord(
                        owner_id,
                        raw,
                        path,
                        line,
                        Resolution.CONFIRMED if direct else Resolution.UNRESOLVED,
                        matches[0].identifier if direct else None,
                    )
                )
        return refs, calls

    def _symbol_name(self, node, source, kind) -> str:
        name = node.child_by_field_name("name")
        if name is not None:
            return self.text(source, name)
        declarator = node.child_by_field_name("declarator")
        while declarator is not None:
            name = declarator.child_by_field_name("declarator")
            if name is None:
                break
            declarator = name
        if declarator is not None:
            return self.text(source, declarator)
        return ""

    def _qualified(self, parent: str, name: str) -> str:
        separator = "::" if self.language in {"cpp", "c", "shell"} else "."
        return f"{parent}{separator}{name}"

    @staticmethod
    def _body(node):
        return node.child_by_field_name("body") or next(
            (
                child
                for child in node.named_children
                if child.type
                in {
                    "class_body",
                    "interface_body",
                    "contract_body",
                    "declaration_list",
                    "field_declaration_list",
                    "enum_body",
                    "block",
                    "statement_block",
                }
            ),
            None,
        )

    def _visibility(self, node, source) -> str:
        raw = self.text(source, node)[:160]
        match = re.search(r"\b(public|private|protected|internal|external)\b", raw)
        return match.group(1) if match else "unknown"

    def _attributes(self, node, source) -> list[str]:
        return [
            self.text(source, child)
            for child in node.named_children
            if child.type in {"decorator", "annotation", "attribute_item", "modifiers"}
        ]

    def _documentation(self, parent, node, source) -> str:
        siblings = parent.named_children
        try:
            index = siblings.index(node)
        except ValueError:
            return ""
        docs: list[str] = []
        for previous in reversed(siblings[:index]):
            if previous.type not in {"comment", "line_comment", "block_comment"}:
                break
            raw = self.text(source, previous).strip()
            if raw.startswith(("///", "/**", "//", "--")):
                docs.insert(0, raw.strip("/*- "))
        return "\n".join(docs)

    def _metadata(self, node, source, kind) -> dict[str, object]:
        return {}

    def _symbol_relationships(self, symbol, node, source) -> list[RelationshipRecord]:
        return []

    def _import_targets(self, raw: str) -> list[tuple[str, bool, bool]]:
        return [(raw, True, False)]


def _caps(**values: CapabilityStatus) -> dict[LanguageCapability, CapabilityStatus]:
    return {LanguageCapability[key.upper()]: value for key, value in values.items()}


class SolidityAdapter(DeclarativeAdapter):
    grammar_module = "tree_sitter_solidity"
    descriptor = AdapterDescriptor(
        "solidity",
        frozenset({".sol"}),
        _caps(
            symbols=CapabilityStatus.SUPPORTED,
            imports=CapabilityStatus.SUPPORTED,
            references=CapabilityStatus.PARTIAL,
            calls=CapabilityStatus.PARTIAL,
            visibility=CapabilityStatus.SUPPORTED,
            inheritance=CapabilityStatus.SUPPORTED,
            contracts=CapabilityStatus.SUPPORTED,
        ),
        "tree-sitter-solidity",
        "1.2",
    )
    node_kinds = {
        "contract_declaration": SymbolKind.CONTRACT,
        "interface_declaration": SymbolKind.INTERFACE,
        "library_declaration": SymbolKind.LIBRARY,
        "function_definition": SymbolKind.FUNCTION,
        "constructor_definition": SymbolKind.CONSTRUCTOR,
        "modifier_definition": SymbolKind.MODIFIER,
        "event_definition": SymbolKind.EVENT,
        "error_declaration": SymbolKind.ERROR,
        "struct_declaration": SymbolKind.STRUCT,
        "enum_declaration": SymbolKind.ENUM,
        "state_variable_declaration": SymbolKind.VARIABLE,
        "enum_value": SymbolKind.ENUM_VARIANT,
    }
    import_node_types = frozenset({"import_directive"})

    def _symbol_name(self, node, source, kind):
        if kind is SymbolKind.CONSTRUCTOR:
            return "constructor"
        if kind is SymbolKind.VARIABLE:
            name = next(
                (
                    item
                    for item in self.descendants(node)
                    if item.type in {"identifier", "variable_name"}
                ),
                None,
            )
            if name is not None:
                return self.text(source, name)
        return super()._symbol_name(node, source, kind)

    def _import_targets(self, raw):
        match = re.search(r"[\"']([^\"']+)[\"']", raw)
        return [(match.group(1), not match.group(1).startswith("."), False)] if match else []

    def _metadata(self, node, source, kind):
        raw = self.text(source, node)
        bases = re.search(r"\bis\s+([^\{]+)", raw[: raw.find("{") if "{" in raw else len(raw)])
        return {
            "security_sensitive": kind
            in {SymbolKind.CONTRACT, SymbolKind.FUNCTION, SymbolKind.METHOD, SymbolKind.MODIFIER},
            "mutability": next(
                (x for x in ("pure", "view", "payable") if re.search(rf"\b{x}\b", raw)), ""
            ),
            "inherits": [part.strip() for part in bases.group(1).split(",")] if bases else [],
        }

    def _symbol_relationships(self, symbol, node, source):
        relationships = [
            RelationshipRecord(
                symbol.identifier,
                target,
                symbol.path,
                symbol.start_line,
                "solidity",
                "inherits",
                Resolution.SYNTACTIC,
                evidence=symbol.signature,
            )
            for target in symbol.metadata.get("inherits", [])
        ]
        if symbol.kind in {SymbolKind.FUNCTION, SymbolKind.METHOD, SymbolKind.CONSTRUCTOR}:
            signature = symbol.signature
            known = {
                "public",
                "private",
                "internal",
                "external",
                "view",
                "pure",
                "payable",
                "virtual",
                "override",
                "returns",
            }
            tail = signature[signature.find(")") + 1 :] if ")" in signature else ""
            for name in re.findall(r"\b([A-Za-z_]\w*)\s*(?:\([^)]*\))?", tail):
                if name not in known:
                    relationships.append(
                        RelationshipRecord(
                            symbol.identifier,
                            name,
                            symbol.path,
                            symbol.start_line,
                            "solidity",
                            "modifier_applied",
                            Resolution.SYNTACTIC,
                            evidence=signature,
                        )
                    )
        return relationships


class JavaScriptAdapter(DeclarativeAdapter):
    grammar_module = "tree_sitter_javascript"
    descriptor = AdapterDescriptor(
        "javascript",
        frozenset({".js", ".jsx", ".mjs", ".cjs"}),
        _caps(
            symbols=CapabilityStatus.SUPPORTED,
            imports=CapabilityStatus.PARTIAL,
            references=CapabilityStatus.PARTIAL,
            calls=CapabilityStatus.PARTIAL,
            visibility=CapabilityStatus.PARTIAL,
            inheritance=CapabilityStatus.PARTIAL,
            modules=CapabilityStatus.SUPPORTED,
        ),
        "tree-sitter-javascript",
        "0.25",
    )
    node_kinds = {
        "function_declaration": SymbolKind.FUNCTION,
        "class_declaration": SymbolKind.CLASS,
        "method_definition": SymbolKind.FUNCTION,
        "generator_function_declaration": SymbolKind.FUNCTION,
    }
    import_node_types = frozenset({"import_statement"})

    def _walk_symbols(
        self, node, source, path, parent_qname, parent_id, imports, output, relationships
    ):
        super()._walk_symbols(
            node, source, path, parent_qname, parent_id, imports, output, relationships
        )
        for child in node.named_children:
            if child.type in {"lexical_declaration", "variable_declaration"}:
                for declarator in child.named_children:
                    value = declarator.child_by_field_name("value")
                    name = declarator.child_by_field_name("name")
                    if value is not None and value.type == "arrow_function" and name is not None:
                        symbol_name = self.text(source, name)
                        qname = self._qualified(parent_qname, symbol_name)
                        kind = (
                            SymbolKind.ASYNC_FUNCTION
                            if self.text(source, value).lstrip().startswith("async")
                            else SymbolKind.FUNCTION
                        )
                        output.append(
                            SymbolRecord(
                                stable_symbol_id(self.language, path, qname, kind),
                                path,
                                self.language,
                                kind,
                                symbol_name,
                                qname,
                                parent_id,
                                child.start_point.row + 1,
                                child.end_point.row + 1,
                                self.text(source, child),
                                self.text(source, child),
                                imports=imports,
                                source_hash=source_hash(self.text(source, child)),
                                metadata={"arrow": True},
                            )
                        )

    def _import_targets(self, raw):
        match = re.search(r"(?:from\s+)?[\"']([^\"']+)[\"']", raw)
        return [(match.group(1), not match.group(1).startswith("."), False)] if match else []

    def _metadata(self, node, source, kind):
        raw = self.text(source, node)
        extends = re.search(
            r"\bextends\s+([A-Za-z_$][\w.$]*)", raw[: raw.find("{") if "{" in raw else len(raw)]
        )
        implements = re.search(
            r"\bimplements\s+([^\{]+)", raw[: raw.find("{") if "{" in raw else len(raw)]
        )
        return {
            "inherits": [extends.group(1)] if extends else [],
            "implements": [item.strip() for item in implements.group(1).split(",")]
            if implements
            else [],
            "exported": bool(re.search(r"\bexport\b", raw[:100])),
        }

    def _symbol_relationships(self, symbol, node, source):
        return [
            RelationshipRecord(
                symbol.identifier,
                target,
                symbol.path,
                symbol.start_line,
                self.language,
                relationship,
                Resolution.SYNTACTIC,
                evidence=symbol.signature,
            )
            for relationship, key in (("inherits", "inherits"), ("implements", "implements"))
            for target in symbol.metadata.get(key, [])
        ]


class TypeScriptAdapter(JavaScriptAdapter):
    grammar_module = "tree_sitter_typescript"
    grammar_function = "language_typescript"
    descriptor = AdapterDescriptor(
        "typescript",
        frozenset({".ts", ".tsx", ".mts", ".cts"}),
        _caps(
            symbols=CapabilityStatus.SUPPORTED,
            imports=CapabilityStatus.PARTIAL,
            references=CapabilityStatus.PARTIAL,
            calls=CapabilityStatus.PARTIAL,
            visibility=CapabilityStatus.PARTIAL,
            inheritance=CapabilityStatus.PARTIAL,
            modules=CapabilityStatus.SUPPORTED,
        ),
        "tree-sitter-typescript",
        "0.23",
    )
    node_kinds = {
        **JavaScriptAdapter.node_kinds,
        "interface_declaration": SymbolKind.INTERFACE,
        "type_alias_declaration": SymbolKind.TYPE_ALIAS,
        "enum_declaration": SymbolKind.ENUM,
        "internal_module": SymbolKind.NAMESPACE,
    }

    def __init__(self) -> None:
        super().__init__()
        try:
            import tree_sitter_typescript
            from tree_sitter import Language, Parser

            self.tsx_parser = Parser(Language(tree_sitter_typescript.language_tsx()))
        except (ImportError, AttributeError, TypeError, ValueError):
            self.tsx_parser = None

    def extract(self, path: str, source_text: str) -> ExtractionResult:
        original = self.parser
        if Path(path).suffix.lower() == ".tsx" and self.tsx_parser is not None:
            self.parser = self.tsx_parser
        try:
            return super().extract(path, source_text)
        finally:
            self.parser = original


class SqlAdapter(DeclarativeAdapter):
    grammar_module = "tree_sitter_sql"
    descriptor = AdapterDescriptor(
        "sql",
        frozenset({".sql"}),
        _caps(
            symbols=CapabilityStatus.PARTIAL,
            imports=CapabilityStatus.UNAVAILABLE,
            references=CapabilityStatus.PARTIAL,
            calls=CapabilityStatus.UNAVAILABLE,
            sql_objects=CapabilityStatus.PARTIAL,
        ),
        "tree-sitter-sql",
        "0.3",
    )
    node_kinds = {
        "create_table": SymbolKind.SQL_TABLE,
        "create_view": SymbolKind.SQL_VIEW,
        "create_function": SymbolKind.SQL_FUNCTION,
        "create_procedure": SymbolKind.SQL_PROCEDURE,
        "create_index": SymbolKind.SQL_INDEX,
        "create_trigger": SymbolKind.SQL_TRIGGER,
    }

    def _symbol_name(self, node, source, kind):
        reference = next(
            (item for item in self.descendants(node) if item.type == "object_reference"), None
        )
        if reference is not None:
            name = reference.child_by_field_name("name")
            return self.text(source, name or reference)
        return super()._symbol_name(node, source, kind)

    def _metadata(self, node, source, kind):
        raw = self.text(source, node)
        return {
            "destructive": bool(re.search(r"\b(DROP|ALTER\s+TABLE.+(?:DROP|RENAME))\b", raw, re.I)),
            "dialect": "generic",
        }

    def extract(self, path: str, source_text: str) -> ExtractionResult:
        result = super().extract(path, source_text)
        symbols = list(result.symbols)
        module_id = symbols[0].identifier
        module_name = symbols[0].qualified_name
        for number, line in enumerate(source_text.splitlines(), 1):
            match = re.search(
                r"\b(ALTER|DROP)\s+(?:TABLE|VIEW|FUNCTION|PROCEDURE|INDEX)\s+(?:IF\s+EXISTS\s+)?([\w.]+)",
                line,
                re.I,
            )
            if not match:
                continue
            operation, target = match.group(1).upper(), match.group(2)
            name = f"{operation} {target}"
            qname = f"{module_name}.{name}"
            symbols.append(
                SymbolRecord(
                    stable_symbol_id("sql", path, qname, SymbolKind.VARIABLE),
                    path,
                    "sql",
                    SymbolKind.VARIABLE,
                    name,
                    qname,
                    module_id,
                    number,
                    number,
                    line,
                    line.strip(),
                    imports=result.file.imports,
                    source_hash=source_hash(line),
                    metadata={
                        "sql_operation": operation,
                        "target": target,
                        "destructive": True,
                        "migration_sensitive": True,
                        "dialect": "generic",
                    },
                )
            )
        relationships = list(result.relationships)
        for symbol in symbols:
            if symbol.kind not in {
                SymbolKind.SQL_VIEW,
                SymbolKind.SQL_FUNCTION,
                SymbolKind.SQL_PROCEDURE,
                SymbolKind.SQL_TRIGGER,
            }:
                continue
            targets = re.findall(r"\b(?:FROM|JOIN|UPDATE|INTO)\s+([\w.]+)", symbol.source, re.I)
            relationships.extend(
                RelationshipRecord(
                    symbol.identifier,
                    target,
                    path,
                    symbol.start_line,
                    "sql",
                    "depends_on",
                    Resolution.SYNTACTIC,
                    evidence=symbol.signature,
                )
                for target in targets
            )
        return ExtractionResult(
            result.file, tuple(symbols), result.references, result.calls, tuple(relationships)
        )


class CAdapter(DeclarativeAdapter):
    grammar_module = "tree_sitter_c"
    descriptor = AdapterDescriptor(
        "c",
        frozenset({".c", ".h"}),
        _caps(
            symbols=CapabilityStatus.PARTIAL,
            imports=CapabilityStatus.PARTIAL,
            references=CapabilityStatus.PARTIAL,
            calls=CapabilityStatus.PARTIAL,
            visibility=CapabilityStatus.PARTIAL,
        ),
        "tree-sitter-c",
        "0.24",
    )
    node_kinds = {
        "function_definition": SymbolKind.FUNCTION,
        "struct_specifier": SymbolKind.STRUCT,
        "enum_specifier": SymbolKind.ENUM,
        "type_definition": SymbolKind.TYPE_ALIAS,
    }
    import_node_types = frozenset({"preproc_include"})

    def _import_targets(self, raw):
        match = re.search(r"[<\"]([^>\"]+)[>\"]", raw)
        return [(match.group(1), raw.find("<") >= 0, False)] if match else []


class CppAdapter(CAdapter):
    grammar_module = "tree_sitter_cpp"
    descriptor = AdapterDescriptor(
        "cpp",
        frozenset({".cc", ".cpp", ".cxx", ".hpp", ".hh", ".hxx"}),
        _caps(
            symbols=CapabilityStatus.PARTIAL,
            imports=CapabilityStatus.PARTIAL,
            references=CapabilityStatus.PARTIAL,
            calls=CapabilityStatus.PARTIAL,
            visibility=CapabilityStatus.PARTIAL,
            inheritance=CapabilityStatus.PARTIAL,
        ),
        "tree-sitter-cpp",
        "0.23",
    )
    node_kinds = {
        **CAdapter.node_kinds,
        "class_specifier": SymbolKind.CLASS,
        "field_declaration": SymbolKind.FUNCTION,
        "namespace_definition": SymbolKind.NAMESPACE,
        "alias_declaration": SymbolKind.TYPE_ALIAS,
    }

    def _symbol_name(self, node, source, kind):
        if node.type == "field_declaration" and not any(
            item.type == "function_declarator" for item in self.descendants(node)
        ):
            return ""
        return super()._symbol_name(node, source, kind)

    def _metadata(self, node, source, kind):
        raw = self.text(source, node)
        match = re.search(r"\b(?:class|struct)\s+\w+\s*:\s*([^\{]+)", raw)
        return {
            "inherits": [
                re.sub(r"\b(public|protected|private|virtual)\b", "", item).strip()
                for item in match.group(1).split(",")
            ]
            if match
            else [],
            "preprocessor_limited": True,
        }

    def _symbol_relationships(self, symbol, node, source):
        return [
            RelationshipRecord(
                symbol.identifier,
                target,
                symbol.path,
                symbol.start_line,
                "cpp",
                "inherits",
                Resolution.SYNTACTIC,
                evidence=symbol.signature,
            )
            for target in symbol.metadata.get("inherits", [])
        ]


class JavaAdapter(DeclarativeAdapter):
    grammar_module = "tree_sitter_java"
    descriptor = AdapterDescriptor(
        "java",
        frozenset({".java"}),
        _caps(
            symbols=CapabilityStatus.SUPPORTED,
            imports=CapabilityStatus.SUPPORTED,
            references=CapabilityStatus.PARTIAL,
            calls=CapabilityStatus.PARTIAL,
            visibility=CapabilityStatus.SUPPORTED,
            inheritance=CapabilityStatus.PARTIAL,
        ),
        "tree-sitter-java",
        "0.23",
    )
    node_kinds = {
        "class_declaration": SymbolKind.CLASS,
        "interface_declaration": SymbolKind.INTERFACE,
        "record_declaration": SymbolKind.STRUCT,
        "enum_declaration": SymbolKind.ENUM,
        "method_declaration": SymbolKind.FUNCTION,
        "constructor_declaration": SymbolKind.CONSTRUCTOR,
    }
    import_node_types = frozenset({"import_declaration"})

    def _import_targets(self, raw):
        target = raw.removeprefix("import").removeprefix(" static").removesuffix(";").strip()
        return [(target, True, target.endswith(".*"))]

    def _metadata(self, node, source, kind):
        raw = self.text(source, node)
        header = raw[: raw.find("{") if "{" in raw else len(raw)]
        extends = re.search(r"\bextends\s+([\w.]+)", header)
        implements = re.search(r"\bimplements\s+([^\{]+)", header)
        return {
            "inherits": [extends.group(1)] if extends else [],
            "implements": [item.strip() for item in implements.group(1).split(",")]
            if implements
            else [],
        }

    def _symbol_relationships(self, symbol, node, source):
        return [
            RelationshipRecord(
                symbol.identifier,
                target,
                symbol.path,
                symbol.start_line,
                "java",
                relationship,
                Resolution.SYNTACTIC,
                evidence=symbol.signature,
            )
            for relationship, key in (("inherits", "inherits"), ("implements", "implements"))
            for target in symbol.metadata.get(key, [])
        ]


class BashAdapter(DeclarativeAdapter):
    grammar_module = "tree_sitter_bash"
    descriptor = AdapterDescriptor(
        "shell",
        frozenset({".sh", ".bash"}),
        _caps(
            symbols=CapabilityStatus.SUPPORTED,
            imports=CapabilityStatus.PARTIAL,
            references=CapabilityStatus.UNAVAILABLE,
            calls=CapabilityStatus.PARTIAL,
            visibility=CapabilityStatus.UNAVAILABLE,
        ),
        "tree-sitter-bash",
        "0.25",
    )
    node_kinds = {"function_definition": SymbolKind.SHELL_FUNCTION}
    import_node_types = frozenset()
    call_node_types = frozenset({"command"})

    def _extract_imports(self, root, source, path, module_id):
        values: list[str] = []
        relationships: list[RelationshipRecord] = []
        for node in self.descendants(root):
            if node.type != "command":
                continue
            raw = self.text(source, node)
            match = re.match(r"\s*(?:source|\.)\s+([^\s;]+)", raw)
            if match:
                target = match.group(1)
                dynamic = "$" in target or "`" in target
                values.append(target)
                relationships.append(
                    RelationshipRecord(
                        module_id,
                        target,
                        path,
                        node.start_point.row + 1,
                        "shell",
                        "sources",
                        Resolution.UNRESOLVED if dynamic else Resolution.SYNTACTIC,
                        evidence=raw,
                    )
                )
        return sorted(set(values)), relationships
