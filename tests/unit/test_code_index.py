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
