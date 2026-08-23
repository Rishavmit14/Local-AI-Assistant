from local_ai_assistant.common.config import AppConfig
from local_ai_assistant.rag.documents import LocalRAG, lexical_tokenize, normalize_scores


def test_lexical_tokenizer_preserves_technical_identifiers():
    assert lexical_tokenize("ORION-73921 llama.cpp Q4_K_M /v1/chat/completions") == [
        "orion-73921",
        "llama.cpp",
        "q4_k_m",
        "/v1/chat/completions",
    ]


def test_score_normalization_handles_flat_and_ranged_values():
    assert normalize_scores([]) == []
    assert normalize_scores([0.0, 0.0]) == [0.0, 0.0]
    assert normalize_scores([2.0, 2.0]) == [1.0, 1.0]
    assert normalize_scores([2.0, 4.0]) == [0.0, 1.0]


def test_ocr_selection_uses_useful_text_threshold():
    assert LocalRAG.needs_ocr("short") is True
    assert LocalRAG.needs_ocr("Useful native PDF text. " * 10) is False


def test_hybrid_retrieval_preserves_rrf_and_lexical_overlap_ranking():
    rag = LocalRAG.__new__(LocalRAG)
    rag.config = AppConfig.from_env({})
    rag.chunks = [
        {"text": "AURORA-7319 launch code", "source": "one.txt", "chunk": 0},
        {"text": "unrelated text", "source": "two.txt", "chunk": 0},
    ]
    rag.vector_search = lambda question, top_k: [
        {"index": 1, "rank": 1, "score": 0.9},
        {"index": 0, "rank": 2, "score": 0.8},
    ]
    rag.bm25_search = lambda question, top_k: [
        {"index": 0, "rank": 1, "score": 4.0},
        {"index": 1, "rank": 2, "score": 0.0},
    ]

    results = rag.retrieve("AURORA-7319")

    assert results[0]["source"] == "one.txt"
    assert results[0]["vector_rank"] == 2
    assert results[0]["bm25_rank"] == 1
    assert results[0]["lexical_overlap"] == 1.0
