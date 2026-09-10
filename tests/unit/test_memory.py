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


def test_semantic_search_is_local_and_persists_rebuildable_vectors(tmp_path):
    vectors = {
        "find neural network work": (1.0, 0.0),
        "project\ntrained a neural network": (0.99, 0.01),
        "project\ncooked dinner": (0.0, 1.0),
    }
    memory = FridayMemoryService(
        tmp_path / "memory.sqlite3",
        embed=lambda texts: [vectors[text] for text in texts],
    )
    relevant = memory.remember(
        kind=MemoryKind.EPISODIC,
        subject="project",
        content="trained a neural network",
        provenance="owner",
        confidence=0.6,
    )
    memory.remember(
        kind=MemoryKind.EPISODIC,
        subject="project",
        content="cooked dinner",
        provenance="owner",
        confidence=1,
    )
    assert memory.search("find neural network work")[0] == relevant
    with memory._db() as db:
        assert db.execute("SELECT COUNT(*) FROM memory_embeddings").fetchone()[0] == 2


def test_retention_bounds_working_memory_and_expires_records(tmp_path):
    memory = FridayMemoryService(tmp_path / "memory.sqlite3", working_subject_limit=2)
    records = [
        memory.remember(
            kind=MemoryKind.WORKING,
            subject="session",
            content=f"step {number}",
            provenance="owner",
            confidence=1,
        )
        for number in range(3)
    ]
    assert memory.get(records[0].memory_id).state is MemoryState.EXPIRED
    assert [item.content for item in memory.recall("session")] == ["step 2", "step 1"]
    expired = memory.remember(
        kind=MemoryKind.WORKING,
        subject="expired",
        content="old",
        provenance="owner",
        confidence=1,
        expires_at="2000-01-01T00:00:00+00:00",
    )
    assert memory.get(expired.memory_id).state is MemoryState.EXPIRED


def test_relationships_keep_project_goal_person_provenance_and_forgetting(tmp_path):
    memory = FridayMemoryService(tmp_path / "memory.sqlite3")
    relation = memory.relate(
        source_subject="owner",
        relationship="owns_project",
        target_subject="FraudShield",
        provenance="owner",
        confidence=1,
    )
    assert memory.relationships("FraudShield") == (relation,)
    memory.forget_relationship(relation.relationship_id)
    assert not memory.relationships("owner")
