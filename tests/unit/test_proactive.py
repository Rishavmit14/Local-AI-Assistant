import sqlite3

import pytest
from fastapi.testclient import TestClient

from local_ai_assistant.interface.api import create_presentation_app
from local_ai_assistant.interface.conversation import FridayConversationService
from local_ai_assistant.interface.runtime import FridayRuntime
from local_ai_assistant.proactive import (
    EventSource,
    ProactiveEventEngine,
    Watch,
)


class _SilentLLM:
    def stream_chat(self, *_args, **_kwargs):
        return iter(())


def watch(source=EventSource.SYSTEM, **values):
    return Watch("watch-1", source, "Local health", interval_seconds=60, **values)


def test_due_schedule_is_durable_deduplicated_and_acknowledgeable(tmp_path):
    database = tmp_path / "events.sqlite3"
    engine = ProactiveEventEngine(database)
    engine.register(watch(schedule=True))

    first = engine.poll_due(now=100)
    assert len(first) == 1
    assert engine.poll_due(now=101) == ()
    assert ProactiveEventEngine(database).notifications()[0].event_id == first[0].event_id
    acknowledged = engine.acknowledge(first[0].notification_id)
    assert acknowledged.acknowledged_at is not None
    assert engine.notifications() == ()


def test_relevance_policy_rate_limit_and_payload_deduplication(tmp_path):
    engine = ProactiveEventEngine(tmp_path / "events.sqlite3", max_notifications_per_hour=1)
    engine.register(watch(min_relevance=50))
    assert engine.ingest("watch-1", "health.changed", "low", 49) is None
    delivered = engine.ingest("watch-1", "health.changed", "high", 80, {"state": "down"})
    assert delivered is not None
    assert engine.ingest("watch-1", "health.changed", "high", 80, {"state": "down"}) is None
    assert engine.ingest("watch-1", "health.changed", "new high", 80) is None


def test_external_events_require_explicit_external_watch(tmp_path):
    engine = ProactiveEventEngine(tmp_path / "events.sqlite3")
    engine.register(watch())
    with pytest.raises(ValueError, match="external watch"):
        engine.external("watch-1", "upstream-1", "Unexpected update", 80)
    engine.register(watch(EventSource.EXTERNAL))
    assert engine.external("watch-1", "upstream-1", "Expected update", 80) is not None
    assert engine.external("watch-1", "upstream-1", "Expected update", 80) is None


def test_filesystem_observer_only_emits_after_baseline_change(tmp_path):
    root = tmp_path / "watched"
    root.mkdir()
    observer = ProactiveEventEngine.filesystem_observer(root)
    assert observer() is None
    (root / "note.txt").write_text("hello")
    event = observer()
    assert event is not None
    assert event[0] == "filesystem.changed"


def test_state_and_repository_observers_are_read_only_change_watches(tmp_path):
    state = {"health": "ok"}
    observer = ProactiveEventEngine.state_observer(EventSource.SERVICE, "Local service", lambda: state)
    assert observer() is None
    state["health"] = "down"
    assert observer()[0] == "service.changed"

    repository = tmp_path / "repository"
    repository.mkdir()
    # A non-Git directory is still safely observed as a failed local status,
    # never initialized, modified, or repaired by the observer.
    repo_observer = ProactiveEventEngine.repository_observer(repository)
    assert repo_observer() is None
    assert repo_observer() is None


def test_disabled_watch_and_invalid_notification_bounds_fail_closed(tmp_path):
    engine = ProactiveEventEngine(tmp_path / "events.sqlite3")
    engine.register(watch())
    engine.disable("watch-1")
    with pytest.raises(ValueError, match="enabled watch"):
        engine.ingest("watch-1", "health.changed", "down", 100)
    with pytest.raises(ValueError, match="limit"):
        engine.notifications(limit=0)


def test_event_metadata_is_redacted_and_bounded_before_persistence(tmp_path):
    database = tmp_path / "events.sqlite3"
    engine = ProactiveEventEngine(database)
    engine.register(watch())
    assert engine.ingest("watch-1", "system.changed", "down", 90, {"token": "secret-value"}) is not None
    with sqlite3.connect(database) as db:
        assert "secret-value" not in db.execute("SELECT metadata_json FROM proactive_events").fetchone()[0]
    with pytest.raises(ValueError, match="exceeds"):
        engine.ingest("watch-1", "system.changed", "too much", 90, {"detail": "x" * 20_000})


def test_presentation_projects_only_bounded_notification_read_and_ack(tmp_path):
    engine = ProactiveEventEngine(tmp_path / "events.sqlite3")
    engine.register(watch())
    notification = engine.ingest("watch-1", "system.changed", "Local service needs attention", 90)
    runtime = FridayRuntime("proactive-api")
    app = create_presentation_app(runtime, FridayConversationService(_SilentLLM(), runtime), proactive=engine)
    with TestClient(app) as client:
        response = client.get("/api/v1/proactive/notifications?limit=1")
        assert response.status_code == 200
        assert response.json()["notifications"][0]["notification_id"] == notification.notification_id
        acknowledged = client.post(f"/api/v1/proactive/notifications/{notification.notification_id}/acknowledge")
        assert acknowledged.status_code == 200
        assert acknowledged.json()["acknowledged_at"] is not None
