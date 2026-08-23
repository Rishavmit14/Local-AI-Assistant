import hashlib

import numpy as np
import pytest

from local_ai_assistant.code_index.symbol_index import SymbolIndex, embedding_text
from local_ai_assistant.common.errors import CorruptIndexError


class DeterministicEmbedder:
    def __init__(self):
        self.embedded = []

    def encode(self, texts, **kwargs):
        self.embedded.extend(texts)
        vectors = []
        for text in texts:
            digest = hashlib.sha256(text.encode()).digest()
            vector = np.asarray([digest[index] + 1 for index in range(8)], dtype=np.float32)
            vector /= np.linalg.norm(vector)
            vectors.append(vector)
        return np.asarray(vectors, dtype=np.float32)


@pytest.fixture
def indexed(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "api.py").write_text("from service import login\n\ndef endpoint():\n    return login()\n")
    (repo / "service.py").write_text("def login():\n    return True\n")
    embedder = DeterministicEmbedder()
    index = SymbolIndex(repo, tmp_path / "index", embedder)
    stats = index.refresh(full=True)
    return repo, index, embedder, stats


def test_persistence_search_graph_map_and_provenance_foundations(indexed, tmp_path):
    repo, index, _, stats = indexed
    login = index.find_exact("login")[0]
    endpoint = index.find_exact("endpoint")[0]

    assert stats.changed_files == 2
    assert index.search_name("log")[0] == login
    assert index.lexical_search("login")
    assert index.semantic_search("authenticate user")
    assert index.hybrid_search("login")[0]["symbol"]
    assert index.get_source(login.identifier).startswith("def login")
    assert index.containing_module(login.identifier).path == "service.py"
    assert index.parent(login.identifier).path == "service.py"
    assert index.callees(endpoint.identifier)[0].callee == login.identifier
    assert index.callers(login.identifier)[0].caller == endpoint.identifier
    assert index.references_to(login.identifier)
    assert index.definitions("login") == [login]
    assert index.imports_of("api") == ["service"]
    assert index.imported_by("service") == ["api.py"]
    assert "api.endpoint" in index.render_map()
    assert index.repository_map()["api.py"]
    assert "function service.login" in embedding_text(login)

    loaded = SymbolIndex(repo, tmp_path / "index", DeterministicEmbedder())
    assert loaded.load() is True
    assert loaded.find_exact("login")[0] == login


def test_incremental_refresh_only_embeds_changed_files_and_cleans_deletes(indexed):
    repo, index, embedder, _ = indexed
    embedder.embedded.clear()
    unchanged = index.refresh()
    assert unchanged.changed_files == 0
    assert embedder.embedded == []

    (repo / "service.py").write_text("def login(name):\n    return name\n\ndef logout():\n    pass\n")
    changed = index.refresh()
    assert changed.changed_files == 1
    assert {item.name for item in index.symbols if item.path == "service.py"} == {"service", "login", "logout"}
    assert len(embedder.embedded) == 3

    (repo / "api.py").rename(repo / "routes.py")
    renamed = index.refresh()
    assert renamed.changed_files == 1
    assert renamed.deleted_files == 1
    assert not any(item.path == "api.py" for item in index.symbols)
    assert any(item.path == "routes.py" for item in index.symbols)

    (repo / "routes.py").unlink()
    deleted = index.refresh()
    assert deleted.deleted_files == 1
    assert not any(item.path == "routes.py" for item in index.symbols)


def test_corrupt_metadata_and_embedding_mismatch_are_explicit(indexed):
    repo, index, _, _ = indexed
    np.save(index.embeddings_file, np.ones((1, 8), dtype=np.float32))
    mismatch = SymbolIndex(repo, index.index_dir, DeterministicEmbedder())
    with pytest.raises(CorruptIndexError, match="count mismatch"):
        mismatch.load()

    index.save()
    index.metadata_file.write_text("not json")
    with pytest.raises(CorruptIndexError):
        index.load()


def test_unsupported_extensions_are_ignored(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "notes.txt").write_text("def not_python(): pass")
    index = SymbolIndex(repo, tmp_path / "index", DeterministicEmbedder())
    stats = index.refresh(full=True)
    assert stats.discovered_files == stats.symbol_count == 0


def test_one_file_failure_preserves_other_indexed_files(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "good.py").write_text("def good():\n    pass\n")
    (repo / "bad.py").write_text("def bad():\n    pass\n")
    index = SymbolIndex(repo, tmp_path / "index", DeterministicEmbedder())
    delegate = index.extractors[".py"]

    class FailingExtractor:
        def extract(self, path, source):
            if path == "bad.py":
                raise ValueError("fixture parser failure")
            return delegate.extract(path, source)

    index.extractors[".py"] = FailingExtractor()
    stats = index.refresh(full=True)

    assert stats.failures == {"bad.py": "fixture parser failure"}
    assert index.find_exact("good")
    assert not index.find_exact("bad")
