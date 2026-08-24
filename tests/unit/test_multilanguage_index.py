import hashlib
import json

import numpy as np
import pytest

from local_ai_assistant.code_index.models import CapabilityStatus
from local_ai_assistant.code_index.symbol_index import SymbolIndex
from local_ai_assistant.common.errors import CorruptIndexError
from local_ai_assistant.planning.analysis import ScopeAnalyzer, assess_risk
from local_ai_assistant.planning.models import (
    RiskLevel,
    ScopeRole,
    TaskCategory,
    TaskClassification,
)
from local_ai_assistant.planning.patch_scope import extract_patch_scope


class Embedder:
    def __init__(self):
        self.embedded = []

    def encode(self, texts, **kwargs):
        self.embedded.extend(texts)
        vectors = []
        for text in texts:
            digest = hashlib.sha256(text.encode()).digest()
            vector = np.asarray([byte + 1 for byte in digest[:8]], dtype=np.float32)
            vectors.append(vector / np.linalg.norm(vector))
        return np.asarray(vectors, dtype=np.float32)


def build_repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "contracts").mkdir()
    (repo / "src" / "app.py").write_text("def python_entry():\n    return True\n")
    (repo / "src" / "lib.rs").write_text(
        "pub struct Service;\nimpl Service { pub fn run(&self) {} }\n"
    )
    (repo / "contracts" / "Vault.sol").write_text("contract Vault { function open() public {} }\n")
    return repo


def test_mixed_index_persistence_filters_maps_capabilities_and_impl_queries(tmp_path):
    repo = build_repo(tmp_path)
    embedder = Embedder()
    index = SymbolIndex(repo, tmp_path / "index", embedder)
    stats = index.refresh(full=True)

    assert stats.discovered_files == 3
    assert index.stats()["symbols_by_language"] == {"python": 2, "rust": 4, "solidity": 3}
    assert index.find_exact("Service", language="rust", kind="struct")
    assert not index.find_exact("Service", language="python")
    assert all(
        item["symbol"].language == "rust"
        for item in index.hybrid_search("Service", language="rust")
    )
    assert set(index.repository_map(language="rust")) == {"src/lib.rs"}
    assert index.implementations_for_type("Service")
    service = index.find_exact("run")[0]
    assert index.callers_result(service.identifier).status is CapabilityStatus.PARTIAL

    loaded = SymbolIndex(repo, tmp_path / "index", Embedder())
    assert loaded.load()
    assert {symbol.language for symbol in loaded.symbols} == {"python", "rust", "solidity"}
    metadata = json.loads(loaded.metadata_file.read_text())
    assert {"python", "rust", "solidity"}.issubset(metadata["languages"])


def test_incremental_refresh_is_language_and_file_local(tmp_path):
    repo = build_repo(tmp_path)
    embedder = Embedder()
    index = SymbolIndex(repo, tmp_path / "index", embedder)
    index.refresh(full=True)
    original_python_ids = {s.identifier for s in index.symbols if s.language == "python"}

    embedder.embedded.clear()
    unchanged = index.refresh()
    assert unchanged.changed_files == 0
    assert embedder.embedded == []

    (repo / "src" / "lib.rs").write_text(
        "pub struct Service;\nimpl Service { pub fn run(&self) {} pub fn stop(&self) {} }\n"
    )
    changed = index.refresh()
    assert changed.changed_files == 1
    assert all("language rust" in text for text in embedder.embedded)
    assert {s.identifier for s in index.symbols if s.language == "python"} == original_python_ids

    (repo / "contracts" / "Vault.sol").rename(repo / "contracts" / "Safe.sol")
    renamed = index.refresh()
    assert renamed.changed_files == 1 and renamed.deleted_files == 1
    assert not any(s.path.endswith("Vault.sol") for s in index.symbols)


def test_one_language_failure_does_not_poison_other_languages(tmp_path):
    repo = build_repo(tmp_path)
    index = SymbolIndex(repo, tmp_path / "index", Embedder())
    delegate = index.extractors[".rs"]

    class FailingRust:
        def extract(self, path, source):
            raise ValueError("rust fixture failure")

    index.extractors[".rs"] = FailingRust()
    stats = index.refresh(full=True)
    assert stats.failures == {"src/lib.rs": "rust fixture failure"}
    assert index.find_exact("python_entry")
    assert index.find_exact("Vault")
    index.extractors[".rs"] = delegate


def test_parser_version_change_invalidates_only_that_language(tmp_path):
    repo = build_repo(tmp_path)
    embedder = Embedder()
    index = SymbolIndex(repo, tmp_path / "index", embedder)
    index.refresh(full=True)
    rust = index.files["src/lib.rs"]
    index.files["src/lib.rs"] = type(rust)(
        rust.path,
        rust.language,
        rust.sha256,
        rust.imports,
        rust.parse_errors,
        "obsolete",
        rust.capabilities,
    )
    index.save()
    embedder.embedded.clear()
    stats = index.refresh()
    assert stats.changed_files == 1
    assert all("language rust" in text for text in embedder.embedded)


def test_corrupt_language_metadata_fails_explicitly(tmp_path):
    repo = build_repo(tmp_path)
    index = SymbolIndex(repo, tmp_path / "index", Embedder())
    index.refresh(full=True)
    metadata = json.loads(index.metadata_file.read_text())
    metadata["languages"]["rust"] = {"parser_version": 12, "capabilities": []}
    index.metadata_file.write_text(json.dumps(metadata))
    with pytest.raises(CorruptIndexError, match="language-specific"):
        SymbolIndex(repo, tmp_path / "index", Embedder()).load()


def test_planner_consumes_rust_relationships_and_language_risk_floors(tmp_path):
    repo = build_repo(tmp_path)
    index = SymbolIndex(repo, tmp_path / "index", Embedder())
    index.refresh(full=True)
    candidates = ScopeAnalyzer(repo, index).analyze("Change Service")

    assert any(
        item.qualified_name == "crate::Service" and item.role is ScopeRole.DIRECT
        for item in candidates
    )
    assert any(
        item.relationship == "implementation_for" and item.role is ScopeRole.DEPENDENT
        for item in candidates
    )
    classification = TaskClassification(TaskCategory.FEATURE, 0.8, ("fixture",), "change")
    assert (
        assess_risk("update vault", classification, ("contracts/Vault.sol",)).level
        is RiskLevel.HIGH
    )
    assert assess_risk("update schema", classification, ("db/schema.sql",)).level is RiskLevel.HIGH


def test_scopeguard_patch_analysis_recognizes_rust_declarations_and_existing_ranges(tmp_path):
    repo = build_repo(tmp_path)
    index = SymbolIndex(repo, tmp_path / "index", Embedder())
    index.refresh(full=True)
    diff = """diff --git a/src/lib.rs b/src/lib.rs
--- a/src/lib.rs
+++ b/src/lib.rs
@@ -1,2 +1,3 @@
 pub struct Service;
-impl Service { pub fn run(&self) {} }
+impl Service { pub fn run(&self) { helper(); } }
+pub fn helper() {}
"""
    scope = extract_patch_scope(diff, tuple(index.symbols))
    assert any(
        effect.effect == "symbol_added" and effect.symbol == "helper"
        for effect in scope.symbol_effects
    )
    assert scope.changed_symbols
