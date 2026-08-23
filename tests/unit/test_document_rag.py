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
