import pytest

from local_ai_assistant.cognition import (
    DEFAULT_BENCHMARK_SUITE,
    BenchmarkArea,
    BenchmarkResult,
    CognitiveController,
    CognitiveStore,
    EvidenceRecord,
    FailureClass,
    Strategy,
    benchmark_delta,
)


def test_cognitive_controller_scales_strategy_and_requires_evidence():
    controller = CognitiveController()
    simple = controller.classify("hello")
    deep = controller.classify(
        "Plan and implement a security architecture integration with multiple validation steps"
    )
    assert simple.strategy is Strategy.TRIVIAL
    assert deep.strategy is Strategy.DEEP and deep.critic
    assert deep.phases == (
        "objective", "inspect", "decompose", "solve", "validate", "integrate", "review"
    )
    assert controller.critique(deep, ())
    assert not controller.skill_promotable(1)
    assert controller.skill_promotable(3)


def test_controller_filters_contradictory_evidence_and_keeps_fast_budget():
    controller = CognitiveController()
    records = (
        EvidenceRecord("git", "repository", "accepted SHA", "git rev-parse"),
        EvidenceRecord("old", "memory", "stale", "memory", contradicts=("git",)),
    )
    selected = controller.select_evidence(records)
    assert [record.source for record in selected] == ["git"]
    assert controller.classify("hello").budget.iterations == 1
    assert "primary answer" in controller.prompt_guidance(
        controller.classify("debug and implement repository tests")
    )


def test_local_experience_and_skill_promotion_are_versioned(tmp_path):
    store = CognitiveStore(tmp_path / "cognition.sqlite3")
    saved = store.record_experience(
        task_type="coding",
        strategy=Strategy.COMPLEX,
        evidence=("test passed",),
        outcome="accepted",
        lesson="keep validation",
        policy_version="v1",
        failure=FailureClass.TEST,
        correction="retest",
    )
    assert store.experiences(task_type="coding") == (saved,)
    fields = dict(
        name="verify", trigger="change", inputs=("scope",), steps=("test",),
        tools=("run_tests",), evidence=("test output",), validation=("pytest",),
        failure_handling="stop", permissions=(), provenance="local",
    )
    with pytest.raises(ValueError, match="three successful"):
        store.promote_skill(**fields, successful_attempts=2)
    first = store.promote_skill(**fields, successful_attempts=3)
    second = store.promote_skill(**fields, successful_attempts=3)
    assert (first.version, second.version) == (1, 2)


def test_benchmark_suite_covers_required_areas_and_compares_same_model_only():
    assert {case.area for case in DEFAULT_BENCHMARK_SUITE} == set(BenchmarkArea)
    raw = BenchmarkResult("reasoning-001", "raw", "qwen-current", False, True, False, 10, 1, "v1")
    friday = BenchmarkResult("reasoning-001", "friday", "qwen-current", True, True, True, 14, 2, "v1")
    assert benchmark_delta(raw, friday)["evidence_positive"]
    other = BenchmarkResult("other", "friday", "qwen-current", True, True, True, 1, 1, "v1")
    with pytest.raises(ValueError, match="same case and model"):
        benchmark_delta(raw, other)
