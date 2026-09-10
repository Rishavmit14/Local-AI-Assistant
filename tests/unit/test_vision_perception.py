import pytest

from local_ai_assistant.perception import LocalVisionClassifier


def test_visual_classifier_rejects_unbounded_label_requests(tmp_path):
    classifier = LocalVisionClassifier(tmp_path)
    with pytest.raises(ValueError, match="between 1 and 10"):
        classifier.classify(tmp_path / "capture.png", top_k=0)


def test_visual_classifier_fails_closed_when_no_local_snapshot_exists(tmp_path):
    classifier = LocalVisionClassifier(tmp_path)
    with pytest.raises(RuntimeError, match="local vision model is unavailable"):
        classifier._load()
