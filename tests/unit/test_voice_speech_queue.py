import pytest

from local_ai_assistant.voice.speech_queue import SpeechQueue, SpeechQueueClosed


def test_queue_preserves_order_and_closes() -> None:
    queue = SpeechQueue()
    queue.put("one")
    queue.put("two")
    queue.close()
    assert list(queue) == ["one", "two"]


def test_closed_queue_rejects_new_work() -> None:
    queue = SpeechQueue()
    queue.close()
    with pytest.raises(SpeechQueueClosed):
        queue.put("late")


def test_close_after_buffered_work_drains_without_blocking() -> None:
    queue = SpeechQueue(max_items=2)
    queue.put("first")
    queue.put("second")
    queue.close()
    assert list(queue) == ["first", "second"]
