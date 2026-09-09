from local_ai_assistant.voice.speech_chunks import SpeechChunker


def test_chunks_complete_streamed_sentences_and_flushes_tail() -> None:
    chunker = SpeechChunker()
    assert chunker.push("Hello") == ()
    assert chunker.push(" there. Next") == ("Hello there.",)
    assert chunker.push(" sentence!") == ("Next sentence!",)
    assert chunker.push(" Tail") == ()
    assert chunker.finish() == ("Tail",)


def test_chunks_at_a_word_boundary_when_buffer_is_bounded() -> None:
    chunker = SpeechChunker(max_chars=32)
    assert chunker.push("one two three four five six seven") == (
        "one two three four five six",
    )
    assert chunker.finish() == ("seven",)
