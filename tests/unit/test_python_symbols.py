from pathlib import Path

from local_ai_assistant.code_index.models import SymbolKind
from local_ai_assistant.code_index.python_parser import PythonSymbolExtractor

FIXTURE = Path(__file__).parents[1] / "fixtures/python_symbols/sample.py"


def extract(text=None):
    source = FIXTURE.read_text() if text is None else text
    return PythonSymbolExtractor().extract("package/sample.py", source)


def test_extracts_exact_python_symbols_ranges_and_metadata():
    result = extract()
    by_qname = {item.qualified_name: item for item in result.symbols}

    assert by_qname["package.sample"].kind is SymbolKind.MODULE
    assert by_qname["package.sample"].documentation == "Fixture module documentation."
    assert by_qname["package.sample.fetch"].kind is SymbolKind.ASYNC_FUNCTION
    assert by_qname["package.sample.fetch"].start_line == 22
    assert by_qname["package.sample.fetch"].end_line == 26
    assert "resource: str" in by_qname["package.sample.fetch"].signature
    service = by_qname["package.sample.Service"]
    assert service.start_line == 29
    assert service.end_line == 44
    assert service.source.startswith('@registry(\n    "service"\n)')
    assert service.decorators == ('registry(\n    "service"\n)',)
    assert service.documentation == "A decorated service."
    assert by_qname["package.sample.Service.duplicate"].kind is SymbolKind.METHOD
    assert by_qname["package.sample.Service.Nested"].parent_identifier == service.identifier
    assert "package.sample.Service.Nested.method.inner" in by_qname
    assert result.file.imports == ("json", "os", "package.helpers", "package.tools")


def test_package_init_has_package_qualified_module_identity():
    result = PythonSymbolExtractor().extract("package/__init__.py", "from . import tools\n")

    assert result.symbols[0].qualified_name == "package"
    assert result.file.imports == ("package",)


def test_duplicate_names_in_distinct_scopes_have_stable_distinct_ids():
    first = extract()
    second = extract()
    duplicates = [item for item in first.symbols if item.name == "duplicate"]

    assert len(duplicates) == 2
    assert len({item.identifier for item in duplicates}) == 2
    assert [item.identifier for item in first.symbols] == [item.identifier for item in second.symbols]


def test_empty_and_malformed_modules_remain_indexable():
    empty = extract("")
    malformed = extract("def broken(:\n    pass\n")

    assert len(empty.symbols) == 1
    assert empty.symbols[0].kind is SymbolKind.MODULE
    assert malformed.file.parse_errors


def test_static_calls_and_references_are_explicitly_qualified():
    result = extract()
    duplicate = next(item for item in result.symbols if item.qualified_name.endswith("Service.duplicate"))
    calls = [item for item in result.calls if item.caller == duplicate.identifier]

    assert calls[0].callee_name == "duplicate"
    assert calls[0].callee is None  # ambiguous across scopes, never guessed
    assert result.references
