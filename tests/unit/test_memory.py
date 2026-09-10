from local_ai_assistant.memory import FridayMemoryService, MemoryKind, MemoryState


def test_memory_provenance_supersession_and_recall(tmp_path):
    m = FridayMemoryService(tmp_path / "m.sqlite3")
    old = m.remember(
        kind=MemoryKind.PREFERENCE,
        subject="owner",
        content="short",
        provenance="owner",
        confidence=1,
    )
    new = m.remember(
        kind=MemoryKind.PREFERENCE,
        subject="owner",
        content="concise",
        provenance="owner",
        confidence=1,
        supersedes=old.memory_id,
    )
    assert m.get(old.memory_id).state is MemoryState.SUPERSEDED
    assert m.recall("owner") == (new,)


def test_conflict_delete_and_expiry_are_not_recalled(tmp_path):
    m = FridayMemoryService(tmp_path / "m.sqlite3")
    fact = m.remember(
        kind=MemoryKind.FACT, subject="x", content="a", provenance="test", confidence=0.5
    )
    expired = m.remember(
        kind=MemoryKind.WORKING,
        subject="x",
        content="b",
        provenance="test",
        confidence=0.5,
        expires_at="2000-01-01T00:00:00+00:00",
    )
    m.mark_conflicted(fact.memory_id)
    m.forget(expired.memory_id)
    assert not m.recall("x")


def test_memory_lexical_search_is_active_only(tmp_path):
    memory = FridayMemoryService(tmp_path / "memory.sqlite3")
    found = memory.remember(
        kind=MemoryKind.EPISODIC,
        subject="learning",
        content="completed PyTorch tensors",
        provenance="owner",
        confidence=0.9,
    )
    hidden = memory.remember(
        kind=MemoryKind.FACT,
        subject="learning",
        content="obsolete tensors",
        provenance="owner",
        confidence=0.8,
    )
    memory.forget(hidden.memory_id)
    assert memory.search("tensors") == (found,)
