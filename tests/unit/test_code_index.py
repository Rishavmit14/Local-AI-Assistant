from pathlib import Path

from local_ai_assistant.code_index.repository import CodeRAG, lexical_tokenize
from local_ai_assistant.common.config import AppConfig


def test_code_chunking_preserves_line_ranges_and_overlap():
    rag = CodeRAG.__new__(CodeRAG)
    text = "\n".join(f"line {number}" for number in range(250))

    chunks = rag.chunk_code(text)

    assert [(item["line_start"], item["line_end"]) for item in chunks] == [
        (1, 120),
        (101, 220),
        (201, 250),
    ]


def test_generated_and_dependency_directories_are_skipped():
    assert CodeRAG.should_skip(Path("repo/.git/config"))
    assert CodeRAG.should_skip(Path("repo/node_modules/package/index.js"))
    assert not CodeRAG.should_skip(Path("repo/src/index.ts"))
    assert lexical_tokenize("Vec<T> src/main.rs") == ["vec<t>", "src/main.rs"]


def test_code_hybrid_retrieval_preserves_rrf_fusion():
    rag = CodeRAG.__new__(CodeRAG)
    rag.config = AppConfig.from_env({})
    rag.chunks = [
        {"text": "def login(): pass", "source": "auth.py"},
        {"text": "def report(): pass", "source": "report.py"},
    ]
    rag.vector_search = lambda question: [
        {"index": 1, "rank": 1, "score": 0.9},
        {"index": 0, "rank": 2, "score": 0.8},
    ]
    rag.bm25_search = lambda question: [
        {"index": 0, "rank": 1, "score": 3.0},
        {"index": 1, "rank": 2, "score": 0.0},
    ]

    results = rag.retrieve("login")

    assert {result["source"] for result in results} == {"auth.py", "report.py"}
    assert results[0]["rrf"] == results[1]["rrf"]
    assert results[0]["vector_rank"] == 1
    assert all(result["retrieval_method"] == "line_chunk_fallback" for result in results)
    assert all(result["symbol_identifier"] is None for result in results)


def test_symbol_context_precedes_line_fallback_with_provenance():
    rag = CodeRAG.__new__(CodeRAG)
    rag.config = AppConfig.from_env({"LOCAL_AI_CODE_FINAL_TOP_K": "2"})
    rag.chunks = [
        {
            "text": "unrelated line chunk",
            "source": "fallback.py",
            "line_start": 1,
            "line_end": 1,
        }
    ]
    rag.vector_search = lambda question: [{"index": 0, "rank": 1, "score": 0.2}]
    rag.bm25_search = lambda question: [{"index": 0, "rank": 1, "score": 0.1}]

    class Symbol:
        identifier = "py:login"
        source = "def login(): pass"
        path = "auth.py"
        start_line = 10
        end_line = 10
        qualified_name = "auth.login"

    class Symbols:
        symbols = [Symbol()]

        def find_exact(self, name):
            return self.symbols if name == "login" else []

        def callers(self, identifier):
            return []

        def callees(self, identifier):
            return []

        def hybrid_search(self, *args):
            return []

    rag.symbol_index = Symbols()
    results = rag.retrieve("explain login")

    assert results[0]["symbol_identifier"] == "py:login"
    assert results[0]["retrieval_method"] == "exact_symbol"
    assert results[0]["hybrid_score"] is None
    assert results[1]["retrieval_method"] == "line_chunk_fallback"


def test_all_exact_symbols_precede_graph_neighbors():
    rag = CodeRAG.__new__(CodeRAG)
    rag.config = AppConfig.from_env({})

    class Symbol:
        def __init__(self, name):
            self.identifier = f"py:{name}"
            self.name = name
            self.source = f"def {name}(): pass"
            self.path = "module.py"
            self.start_line = 1
            self.end_line = 1
            self.qualified_name = f"module.{name}"

    alpha, beta, neighbor = Symbol("alpha"), Symbol("beta"), Symbol("neighbor")

    class Edge:
        caller = neighbor.identifier

    class Symbols:
        symbols = [alpha, beta, neighbor]

        def find_exact(self, name):
            return [item for item in self.symbols if item.name == name]

        def callers(self, identifier):
            return [Edge()] if identifier == alpha.identifier else []

        def callees(self, identifier):
            return []

        def hybrid_search(self, *args):
            return []

    rag.symbol_index = Symbols()
    results = rag._symbol_context("alpha beta", limit=3)

    assert [item["symbol_name"] for item in results] == [
        "module.alpha",
        "module.beta",
        "module.neighbor",
    ]
    assert results[2]["graph_relationship"] == "caller"
