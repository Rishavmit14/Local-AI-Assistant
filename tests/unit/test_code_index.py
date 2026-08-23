from pathlib import Path

from local_ai_assistant.code_index.repository import CodeRAG, lexical_tokenize


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
