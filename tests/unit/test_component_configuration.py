from dataclasses import replace
from types import SimpleNamespace

from local_ai_assistant.code_index.repository import CodeRAG
from local_ai_assistant.common.config import AppConfig, EmbeddingConfig, PathConfig
from local_ai_assistant.rag.documents import LocalRAG


class FakeEmbedder:
    tokenizer = SimpleNamespace()


class FakeLLM:
    pass


def configured_for(tmp_path):
    defaults = AppConfig.from_env({})
    return replace(
        defaults,
        paths=PathConfig(
            var_dir=tmp_path,
            document_dir=tmp_path / "documents",
            rag_data_dir=tmp_path / "rag",
            code_repo_dir=tmp_path / "repos",
            code_index_dir=tmp_path / "code-index",
            patch_dir=tmp_path / "patches",
        ),
        embedding=EmbeddingConfig(model="test-embedding", device="cpu", batch_size=3),
    )


def test_document_rag_uses_injected_paths_and_dependencies(tmp_path):
    config = configured_for(tmp_path)
    rag = LocalRAG(config=config, embedder=FakeEmbedder(), llm=FakeLLM())

    assert rag.document_dir == tmp_path / "documents"
    assert rag.index_file == tmp_path / "rag/index.faiss"
    assert rag.embedder.__class__ is FakeEmbedder
    assert rag.llm.__class__ is FakeLLM


def test_code_rag_uses_injected_paths_and_chunk_settings(tmp_path):
    config = configured_for(tmp_path)
    rag = CodeRAG(config=config, embedder=FakeEmbedder(), llm=FakeLLM())
    chunks = rag.chunk_code("\n".join(f"line {number}" for number in range(250)))

    assert rag.repo_dir == tmp_path / "repos"
    assert rag.index_file == tmp_path / "code-index/code.faiss"
    assert [(chunk["line_start"], chunk["line_end"]) for chunk in chunks] == [
        (1, 120),
        (101, 220),
        (201, 250),
    ]
