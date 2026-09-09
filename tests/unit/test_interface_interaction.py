from __future__ import annotations

import threading

from local_ai_assistant.interface.interaction import FridayInteractionCoordinator


def test_single_owner_is_nonblocking_and_generation_is_monotonic():
    interactions = FridayInteractionCoordinator()
    first = interactions.try_acquire("voice")
    assert first is not None
    assert interactions.try_acquire("presentation") is None
    assert interactions.snapshot().to_dict() == {
        "busy": True, "owner": "voice", "generation": 1,
    }
    first.release()
    first.release()
    second = interactions.try_acquire("presentation")
    assert second is not None
    assert interactions.snapshot().generation == 2
    second.release()
    assert interactions.snapshot().owner is None


def test_concurrent_claims_admit_exactly_one_owner():
    interactions = FridayInteractionCoordinator()
    barrier = threading.Barrier(3)
    leases = []

    def claim(owner):
        barrier.wait()
        leases.append(interactions.try_acquire(owner))

    threads = [threading.Thread(target=claim, args=(owner,)) for owner in ("voice", "presentation")]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join(1)
    accepted = [lease for lease in leases if lease is not None]
    assert len(accepted) == 1
    accepted[0].release()


def test_empty_owner_is_rejected_without_advancing_generation():
    interactions = FridayInteractionCoordinator()
    try:
        interactions.try_acquire("  ")
    except ValueError as exc:
        assert "owner" in str(exc)
    else:
        raise AssertionError("empty owner was accepted")
    assert interactions.snapshot().generation == 0
