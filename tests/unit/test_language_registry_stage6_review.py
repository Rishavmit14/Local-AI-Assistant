import hashlib

import numpy as np
import pytest

from local_ai_assistant.code_index.languages import RegisteredLanguage, build_language_registry


def test_registry_normalizes_aliases_and_is_frozen():
    registry = build_language_registry()

    assert registry.normalize("TS") == "typescript"
    assert registry.normalize("c++") == "cpp"
    assert registry.normalize("bash") == "shell"
    assert registry.detect("include/value.h") == "c"
    assert registry.detect("unknown.xyz") is None
    with pytest.raises(RuntimeError, match="frozen"):
        registry.register(RegisteredLanguage("other", frozenset({".other"}), None))


def test_language_and_kind_filters_compose_and_aliases_normalize(tmp_path):
    from local_ai_assistant.code_index.symbol_index import SymbolIndex

    class Embedder:
        def encode(self, texts, **kwargs):
            vectors = []
            for text in texts:
                digest = hashlib.sha256(text.encode()).digest()
                vector = np.asarray([byte + 1 for byte in digest[:8]], dtype=np.float32)
                vectors.append(vector / np.linalg.norm(vector))
            return np.asarray(vectors, dtype=np.float32)

    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "app.py").write_text("class Service:\n    pass\n")
    (repo / "src" / "lib.rs").write_text("pub struct Service;\n")

    index = SymbolIndex(repo, tmp_path / "index", Embedder())
    index.refresh(full=True)

    assert index.find_exact("Service", language="RS", kind="struct")
    assert not index.find_exact("Service", language="python", kind="struct")
    with pytest.raises(ValueError, match="Unknown language"):
        index.hybrid_search("Service", language="nonesuch", kind="struct")
