"""Deterministic Rust Tree-sitter adapter."""

from __future__ import annotations

import re

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


class RustAdapter(TreeSitterAdapter):
    grammar_module = "tree_sitter_rust"
    descriptor = AdapterDescriptor(
        "rust",
        frozenset({".rs"}),
        {
            LanguageCapability.SYMBOLS: CapabilityStatus.SUPPORTED,
            LanguageCapability.IMPORTS: CapabilityStatus.SUPPORTED,
            LanguageCapability.REFERENCES: CapabilityStatus.PARTIAL,
            LanguageCapability.CALLS: CapabilityStatus.PARTIAL,
            LanguageCapability.VISIBILITY: CapabilityStatus.SUPPORTED,
            LanguageCapability.IMPLEMENTATIONS: CapabilityStatus.SUPPORTED,
            LanguageCapability.MODULES: CapabilityStatus.SUPPORTED,
            LanguageCapability.TESTS: CapabilityStatus.SUPPORTED,
        },
        "tree-sitter-rust",
        "0.24",
    )

    _kinds = {
        "function_item": SymbolKind.FUNCTION,
        "function_signature_item": SymbolKind.FUNCTION_DECLARATION,
        "struct_item": SymbolKind.STRUCT,
        "enum_item": SymbolKind.ENUM,
        "enum_variant": SymbolKind.ENUM_VARIANT,
        "trait_item": SymbolKind.TRAIT,
        "impl_item": SymbolKind.IMPLEMENTATION,
        "type_item": SymbolKind.TYPE_ALIAS,
        "const_item": SymbolKind.CONSTANT,
        "static_item": SymbolKind.VARIABLE,
        "macro_definition": SymbolKind.MACRO,
        "mod_item": SymbolKind.MODULE,
    }

    def extract(self, path: str, source_text: str) -> ExtractionResult:
        source = source_text.encode()
        tree = self._parse_tree(source_text)
        module_name = module_identity("rust", path)
        digest = source_hash(source_text)
        module_id = stable_symbol_id("rust", path, module_name, SymbolKind.MODULE)
        imports, import_relationships = self._imports(source_text, path, module_id)
        module = SymbolRecord(
            module_id,
            path,
            "rust",
            SymbolKind.MODULE,
            module_name.rsplit("::", 1)[-1],
            module_name,
            None,
            1,
            max(1, len(source_text.splitlines())),
            source_text,
            imports=tuple(imports),
            source_hash=digest,
            metadata={"module_path": module_name},
        )
        symbols = [module]
        relationships = list(import_relationships)
        self._walk(
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
        references: list[ReferenceRecord] = []
        calls: list[CallRecord] = []
        self._uses(tree.root_node, source, path, module_id, symbols, definitions, references, calls)
        file = FileRecord(
            path,
            "rust",
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

    def _walk(self, node, source, path, parent_qname, parent_id, imports, symbols, relationships):
        for child in node.named_children:
            if child.type == "attribute_item":
                continue
            kind = self._kinds.get(child.type)
            if kind is None:
                self._walk(
                    child, source, path, parent_qname, parent_id, imports, symbols, relationships
                )
                continue
            name_node = child.child_by_field_name("name")
            metadata: dict[str, object] = {}
            if child.type == "impl_item":
                type_node = child.child_by_field_name("type")
                trait_node = child.child_by_field_name("trait")
                type_name = self.text(source, type_node) if type_node else "unknown"
                trait_name = self.text(source, trait_node) if trait_node else ""
                name = f"impl {trait_name + ' for ' if trait_name else ''}{type_name}"
                metadata = {
                    "implemented_type": type_name,
                    "implemented_trait": trait_name,
                    "implementation_kind": "trait" if trait_name else "inherent",
                }
            elif name_node is not None:
                name = self.text(source, name_node)
            else:
                continue
            qname = f"{parent_qname}::{name}"
            if child.type == "function_item":
                parent = next((item for item in symbols if item.identifier == parent_id), None)
                if parent and parent.kind is SymbolKind.IMPLEMENTATION:
                    kind = (
                        SymbolKind.METHOD
                        if self._has_self_parameter(child, source)
                        else SymbolKind.FUNCTION
                    )
                if self._is_async(child, source):
                    metadata["async"] = True
                    if kind is SymbolKind.FUNCTION:
                        kind = SymbolKind.ASYNC_FUNCTION
            symbol_id = stable_symbol_id("rust", path, qname, kind)
            body = child.child_by_field_name("body")
            signature_end = body.start_byte if body is not None else child.end_byte
            attributes, docs = self._leading_attributes(node, child, source)
            visibility = self._visibility(child, source)
            metadata.update(
                {
                    "test": self._is_test(attributes),
                    "cfg_test": any("cfg(test)" in item.replace(" ", "") for item in attributes),
                    "generics": self._field(child, "type_parameters", source),
                    "where_clause": self._first_child_text(child, "where_clause", source),
                }
            )
            symbol = SymbolRecord(
                symbol_id,
                path,
                "rust",
                kind,
                name,
                qname,
                parent_id,
                child.start_point.row + 1,
                child.end_point.row + 1,
                self.text(source, child),
                self.text(source, child)[: signature_end - child.start_byte].rstrip(),
                docs,
                tuple(attributes),
                visibility,
                imports,
                source_hash(self.text(source, child)),
                metadata,
            )
            symbols.append(symbol)
            if kind is SymbolKind.IMPLEMENTATION:
                relationship = (
                    "implements" if metadata.get("implemented_trait") else "implementation_for"
                )
                target = str(metadata.get("implemented_trait") or metadata.get("implemented_type"))
                relationships.append(
                    RelationshipRecord(
                        symbol_id,
                        target,
                        path,
                        symbol.start_line,
                        "rust",
                        relationship,
                        Resolution.SYNTACTIC,
                        evidence=symbol.signature,
                    )
                )
            if body is not None:
                self._walk(body, source, path, qname, symbol_id, imports, symbols, relationships)

    def _uses(self, root, source, path, module_id, symbols, definitions, references, calls):
        ranged = sorted(
            symbols[1:], key=lambda item: (item.end_line - item.start_line, item.start_line)
        )
        for node in self.descendants(root):
            line = node.start_point.row + 1
            owner = next(
                (item for item in ranged if item.start_line <= line <= item.end_line), None
            )
            owner_id = owner.identifier if owner else module_id
            if node.type == "call_expression":
                function = node.child_by_field_name("function")
                if function is None:
                    continue
                raw = self.text(source, function)
                name = raw.split("::")[-1].split(".")[-1]
                candidates = definitions.get(raw, []) or definitions.get(name, [])
                deterministic = (
                    function.type in {"identifier", "scoped_identifier"} and len(candidates) == 1
                )
                calls.append(
                    CallRecord(
                        owner_id,
                        raw,
                        path,
                        line,
                        Resolution.CONFIRMED if deterministic else Resolution.UNRESOLVED,
                        candidates[0].identifier if deterministic else None,
                    )
                )
            elif node.type in {"identifier", "type_identifier", "scoped_identifier"}:
                raw = self.text(source, node)
                candidates = definitions.get(raw, []) or definitions.get(raw.split("::")[-1], [])
                target = candidates[0].identifier if len(candidates) == 1 else None
                references.append(
                    ReferenceRecord(owner_id, raw, path, line, Resolution.SYNTACTIC, target)
                )

    @staticmethod
    def _imports(source_text: str, path: str, module_id: str):
        imports: list[str] = []
        relationships: list[RelationshipRecord] = []
        current_module = module_identity("rust", path)
        for number, line in enumerate(source_text.splitlines(), 1):
            match = re.match(r"\s*(?:pub(?:\([^)]*\))?\s+)?use\s+(.+?);\s*$", line)
            if match:
                expression = match.group(1).strip()
                expanded = RustAdapter._expand_use(expression)
                for raw_target in expanded:
                    target = RustAdapter._normalize_import(raw_target, current_module)
                    imports.append(target)
                    external = not target.startswith(("crate::", "self::", "super::"))
                    resolution = (
                        Resolution.EXTERNAL
                        if external
                        else (Resolution.UNRESOLVED if "*" in target else Resolution.SYNTACTIC)
                    )
                    relationships.append(
                        RelationshipRecord(
                            module_id,
                            target,
                            path,
                            number,
                            "rust",
                            "imports",
                            resolution,
                            external=external,
                            evidence=line.strip(),
                        )
                    )
            match = re.match(r"\s*(?:pub\s+)?mod\s+([A-Za-z_]\w*)\s*;", line)
            if match:
                target = f"{current_module}::{match.group(1)}"
                imports.append(target)
                relationships.append(
                    RelationshipRecord(
                        module_id,
                        target,
                        path,
                        number,
                        "rust",
                        "module",
                        Resolution.SYNTACTIC,
                        evidence=line.strip(),
                    )
                )
        return sorted(set(imports)), relationships

    @staticmethod
    def _normalize_import(target: str, current_module: str) -> str:
        if target.startswith("self::"):
            return current_module + target[len("self") :]
        if target.startswith("super::"):
            parent = current_module.rsplit("::", 1)[0] if "::" in current_module else "crate"
            return parent + target[len("super") :]
        return target

    @staticmethod
    def _expand_use(expression: str) -> list[str]:
        alias_removed = re.sub(r"\s+as\s+\w+$", "", expression)
        match = re.match(r"(.+?)::\{(.+)\}$", alias_removed)
        if not match:
            return [alias_removed]
        prefix, body = match.groups()
        values = [re.sub(r"\s+as\s+\w+$", "", item.strip()) for item in body.split(",")]
        return [f"{prefix}::{item}" for item in values]

    @staticmethod
    def _visibility(node, source) -> str:
        value = source[node.start_byte : min(node.end_byte, node.start_byte + 80)].decode(
            errors="replace"
        )
        match = re.match(r"\s*(pub(?:\([^)]*\))?)", value)
        return match.group(1) if match else "private"

    @staticmethod
    def _is_async(node, source) -> bool:
        return bool(
            re.search(
                r"\basync\s+fn\b",
                source[node.start_byte : node.end_byte].decode(errors="replace")[:200],
            )
        )

    @staticmethod
    def _has_self_parameter(node, source) -> bool:
        params = node.child_by_field_name("parameters")
        return params is not None and bool(re.search(r"\bself\b", RustAdapter.text(source, params)))

    @staticmethod
    def _leading_attributes(parent, node, source):
        siblings = parent.named_children
        try:
            index = siblings.index(node)
        except ValueError:
            return [], ""
        attrs: list[str] = []
        docs: list[str] = []
        for sibling in reversed(siblings[:index]):
            text = RustAdapter.text(source, sibling).strip()
            if sibling.type == "attribute_item":
                attrs.insert(0, text)
            elif sibling.type == "line_comment" and text.startswith("///"):
                docs.insert(0, text[3:].strip())
            else:
                break
        return attrs, "\n".join(docs)

    @staticmethod
    def _is_test(attributes: list[str]) -> bool:
        return any(
            re.search(r"#\[(?:tokio::|async_std::)?test(?:\([^]]*\))?\]", item)
            for item in attributes
        )

    @staticmethod
    def _field(node, name, source) -> str:
        child = node.child_by_field_name(name)
        return RustAdapter.text(source, child) if child else ""

    @staticmethod
    def _first_child_text(node, node_type, source) -> str:
        return next(
            (
                RustAdapter.text(source, child)
                for child in node.named_children
                if child.type == node_type
            ),
            "",
        )
