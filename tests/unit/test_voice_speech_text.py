from local_ai_assistant.voice.speech_text import normalize_speech_text


def test_normalizes_common_markdown_for_speech() -> None:
    assert normalize_speech_text("## **Answer**\n- The sky is [blue](https://example.test).") == "Answer The sky is blue."


def test_preserves_plain_text_and_inline_code_words() -> None:
    assert normalize_speech_text("Use `Friday` with ~~no~~ emphasis.") == "Use Friday with no emphasis."


def test_normalizes_images_lists_and_identifier_separators() -> None:
    assert (
        normalize_speech_text(
            "1. Review ![Friday icon](icon.png) for `voice_runtime`."
        )
        == "Review Friday icon for voice runtime."
    )
