import pytest

from local_ai_assistant.code_index import adapters as adapter_module
from local_ai_assistant.code_index.languages import RegisteredLanguage, build_language_registry
from local_ai_assistant.code_index.models import (
    CapabilityStatus,
    LanguageCapability,
    Resolution,
    SymbolKind,
)
from local_ai_assistant.code_index.repository import main as code_index_main
from local_ai_assistant.code_index.rust_parser import RustAdapter
from local_ai_assistant.common.errors import ParserUnavailableError


def test_language_registry_is_authoritative_and_rejects_extension_conflicts():
    registry = build_language_registry()

    assert registry.detect("src/lib.rs") == "rust"
    assert registry.detect("web/app.tsx") == "typescript"
    assert registry.detect("script.bash") == "shell"
    assert registry.detect("README.md") == "markdown"
    assert registry.detect("unknown.xyz") is None
    with pytest.raises(ValueError, match="Extension already registered"):
        registry.register(RegisteredLanguage("other", frozenset({".rs"}), None))


def test_capabilities_are_explicit_not_inferred_from_empty_results():
    registry = build_language_registry()
    sql = registry.adapter("sql")
    rust = registry.adapter("rust")

    assert sql.capability(LanguageCapability.CALLS) is CapabilityStatus.UNAVAILABLE
    assert rust.capability(LanguageCapability.CALLS) is CapabilityStatus.PARTIAL
    assert rust.capability(LanguageCapability.IMPLEMENTATIONS) is CapabilityStatus.SUPPORTED


def test_parser_unavailable_fails_explicitly(monkeypatch):
    monkeypatch.setattr(
        adapter_module.importlib,
        "import_module",
        lambda name: (_ for _ in ()).throw(ImportError(name)),
    )
    with pytest.raises(ParserUnavailableError, match="tree-sitter-rust"):
        RustAdapter()


def test_language_cli_lists_registry_and_capabilities_without_loading_models(capsys):
    assert code_index_main(["--list-languages"]) == 0
    listed = capsys.readouterr().out
    assert '"rust"' in listed and '"symbol_adapter": true' in listed
    assert code_index_main(["--show-capabilities", "sql"]) == 0
    capabilities = capsys.readouterr().out
    assert '"sql_objects": "partial"' in capabilities
    assert code_index_main(["--search-symbols", "x", "--language", "unknown"]) == 2
    assert "Unknown language" in capsys.readouterr().out
    assert code_index_main(["--find-symbol", "x", "--kind", "not-a-kind"]) == 2
    assert "Unknown symbol kind" in capsys.readouterr().out


RUST = """
use crate::{models::User, auth::verify as check};
use external_crate::Client;
pub struct UserService<T> { value: T }
pub enum Role { Admin, User }
pub trait Repository<T> { fn get(&self, id: u64) -> T; }
impl<T> Repository<T> for UserService<T> where T: Clone {
    /// Logs a user in.
    #[tokio::test]
    pub async fn login<'a>(&self, user: &'a User) -> bool {
        helper();
        self.dynamic_call();
        true
    }
    pub fn new(value: T) -> Self { Self { value } }
}
type UserId = u64;
pub const MAX_USERS: usize = 10;
static ACTIVE: bool = true;
macro_rules! tracked { () => {}; }
fn helper() {}
"""


def test_rust_extracts_symbols_impls_visibility_docs_tests_and_conservative_calls():
    result = build_language_registry().adapter("rust").extract("src/service.rs", RUST)
    by_name = {symbol.name: symbol for symbol in result.symbols}

    assert by_name["UserService"].kind is SymbolKind.STRUCT
    assert by_name["Role"].kind is SymbolKind.ENUM
    assert {symbol.name for symbol in result.symbols if symbol.kind is SymbolKind.ENUM_VARIANT} == {
        "Admin",
        "User",
    }
    assert by_name["Repository"].kind is SymbolKind.TRAIT
    implementation = next(
        symbol for symbol in result.symbols if symbol.kind is SymbolKind.IMPLEMENTATION
    )
    assert implementation.metadata["implemented_trait"] == "Repository<T>"
    assert implementation.metadata["implemented_type"] == "UserService<T>"
    login = by_name["login"]
    assert login.kind is SymbolKind.METHOD
    assert login.visibility == "pub"
    assert login.documentation == "Logs a user in."
    assert login.metadata["async"] is True
    assert login.metadata["test"] is True
    assert "where T: Clone" in implementation.metadata["where_clause"]
    assert by_name["UserId"].kind is SymbolKind.TYPE_ALIAS
    assert by_name["MAX_USERS"].kind is SymbolKind.CONSTANT
    assert by_name["ACTIVE"].kind is SymbolKind.VARIABLE
    assert by_name["tracked"].kind is SymbolKind.MACRO
    assert result.file.imports == (
        "crate::auth::verify",
        "crate::models::User",
        "external_crate::Client",
    )
    external = next(
        edge for edge in result.relationships if edge.target == "external_crate::Client"
    )
    assert external.external is True and external.resolution is Resolution.EXTERNAL
    helper_call = next(call for call in result.calls if call.callee_name == "helper")
    method_call = next(call for call in result.calls if "dynamic_call" in call.callee_name)
    assert helper_call.resolution is Resolution.CONFIRMED
    assert method_call.resolution is Resolution.UNRESOLVED


def test_rust_nested_modules_duplicate_scopes_ranges_and_malformed_source():
    adapter = build_language_registry().adapter("rust")
    source = "mod one { fn duplicate() {} }\nmod two { fn duplicate() {} }\n"
    result = adapter.extract("src/lib.rs", source)
    duplicates = [symbol for symbol in result.symbols if symbol.name == "duplicate"]

    assert len(duplicates) == 2
    assert len({symbol.identifier for symbol in duplicates}) == 2
    assert {symbol.qualified_name for symbol in duplicates} == {
        "crate::one::duplicate",
        "crate::two::duplicate",
    }
    assert duplicates[0].start_line in {1, 2}
    assert adapter.extract("src/bad.rs", "fn broken( {").file.parse_errors


def test_rust_ids_survive_noop_and_line_movement():
    adapter = build_language_registry().adapter("rust")
    first = adapter.extract("src/lib.rs", "fn stable() {}\n")
    moved = adapter.extract("src/lib.rs", "\n\nfn stable() {}\n")
    assert first.symbols[1].identifier == moved.symbols[1].identifier


def test_rust_relative_grouped_glob_modules_and_cfg_tests_are_explicit():
    source = """use self::local::{one, two as second};
use super::shared::*;
mod child;
#[cfg(test)]
mod tests { #[test] fn works() {} }
"""
    result = build_language_registry().adapter("rust").extract("src/service/mod.rs", source)
    assert "crate::service::local::one" in result.file.imports
    assert "crate::shared::*" in result.file.imports
    glob = next(edge for edge in result.relationships if edge.target.endswith("::*"))
    assert glob.resolution is Resolution.UNRESOLVED
    assert any(symbol.metadata.get("cfg_test") for symbol in result.symbols)
    assert any(symbol.metadata.get("test") for symbol in result.symbols)


def test_solidity_symbols_inheritance_imports_and_security_metadata():
    source = """import "./Base.sol";
contract Vault is Base {
 event Deposit(address who);
 error Denied();
 struct Entry { uint value; }
 enum State { Open, Closed }
 uint public total;
 modifier onlyOwner() { _; }
 constructor() {}
 function withdraw() external payable onlyOwner {}
}
interface IVault { function total() external view returns (uint); }
library Math { function add(uint a, uint b) internal pure returns(uint) { return a+b; } }
"""
    result = build_language_registry().adapter("solidity").extract("contracts/Vault.sol", source)
    kinds = {symbol.kind for symbol in result.symbols}
    assert {
        SymbolKind.CONTRACT,
        SymbolKind.INTERFACE,
        SymbolKind.LIBRARY,
        SymbolKind.EVENT,
        SymbolKind.MODIFIER,
        SymbolKind.CONSTRUCTOR,
    }.issubset(kinds)
    vault = next(symbol for symbol in result.symbols if symbol.kind is SymbolKind.CONTRACT)
    assert vault.metadata["inherits"] == ["Base"]
    assert vault.metadata["security_sensitive"] is True
    assert result.file.imports == ("./Base.sol",)
    assert any(
        edge.relationship == "modifier_applied" and edge.target == "onlyOwner"
        for edge in result.relationships
    )


def test_typescript_javascript_symbols_arrows_and_dynamic_calls_stay_unresolved():
    ts = (
        build_language_registry()
        .adapter("typescript")
        .extract(
            "web/app.ts",
            """
import {x as y} from "./lib";
interface Service { run(): void }
type Name = string;
enum Role { Admin }
namespace Api { export async function load() {} }
class Client { constructor() {} async run() { this.dynamic(); } }
const handler = async () => load();
""",
        )
    )
    kinds = {symbol.kind for symbol in ts.symbols}
    assert {
        SymbolKind.INTERFACE,
        SymbolKind.TYPE_ALIAS,
        SymbolKind.ENUM,
        SymbolKind.NAMESPACE,
        SymbolKind.CLASS,
        SymbolKind.ASYNC_FUNCTION,
    }.issubset(kinds)
    assert ts.file.imports == ("./lib",)
    assert (
        next(symbol for symbol in ts.symbols if symbol.name == "constructor").kind
        is SymbolKind.CONSTRUCTOR
    )
    assert all(
        call.resolution is Resolution.UNRESOLVED for call in ts.calls if "." in call.callee_name
    )


def test_sql_c_cpp_java_and_shell_core_facts_and_limitations():
    registry = build_language_registry()
    sql = registry.adapter("sql").extract(
        "db/schema.sql",
        """
CREATE TABLE users(id INT);
CREATE VIEW active_users AS SELECT * FROM users;
ALTER TABLE users DROP COLUMN old;
DROP TABLE obsolete;
""",
    )
    assert {SymbolKind.SQL_TABLE, SymbolKind.SQL_VIEW}.issubset({s.kind for s in sql.symbols})
    assert len([s for s in sql.symbols if s.metadata.get("destructive")]) == 2
    assert any(
        edge.relationship == "depends_on" and edge.target == "users" for edge in sql.relationships
    )

    c = registry.adapter("c").extract(
        "src/a.c", '#include "a.h"\nstruct User { int id; };\nint load(int id) { return id; }'
    )
    assert {SymbolKind.STRUCT, SymbolKind.FUNCTION}.issubset({s.kind for s in c.symbols})
    assert c.file.imports == ("a.h",)

    cpp = registry.adapter("cpp").extract(
        "src/a.cpp",
        "namespace api { class C : public Base { public: void run(); }; int load(){ return 1; } }",
    )
    assert next(s for s in cpp.symbols if s.name == "load").kind is SymbolKind.FUNCTION
    assert next(s for s in cpp.symbols if s.name == "run").kind is SymbolKind.METHOD
    assert any(
        edge.relationship == "inherits" and edge.target == "Base" for edge in cpp.relationships
    )

    java = registry.adapter("java").extract(
        "src/App.java",
        "package app; import java.util.List; interface Runner {} public class App extends Base implements Runner { public App() {} public void run() {} }",
    )
    assert java.file.imports == ("java.util.List",)
    assert next(s for s in java.symbols if s.name == "run").visibility == "public"
    assert any(s.kind is SymbolKind.CONSTRUCTOR for s in java.symbols)
    assert {edge.relationship for edge in java.relationships} >= {"inherits", "implements"}

    shell = registry.adapter("shell").extract(
        "bin/run.sh", "source ./lib.sh\nrun() { echo ok; }\nrun"
    )
    assert next(s for s in shell.symbols if s.name == "run" and s.kind is SymbolKind.SHELL_FUNCTION)
    assert shell.file.imports == ("./lib.sh",)
