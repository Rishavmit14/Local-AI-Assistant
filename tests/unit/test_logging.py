import json
import logging

from local_ai_assistant.common.logging import JsonFormatter


def test_json_formatter_emits_structured_event_fields():
    record = logging.LogRecord(
        name="local_ai_assistant.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="index_complete",
        args=(),
        exc_info=None,
    )
    record.event = "rag.index.completed"
    record.chunk_count = 42

    payload = json.loads(JsonFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["message"] == "index_complete"
    assert payload["event"] == "rag.index.completed"
    assert payload["chunk_count"] == 42
    assert "timestamp" in payload
