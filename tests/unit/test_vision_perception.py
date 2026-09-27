import sys
from types import SimpleNamespace

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


def test_visual_classifier_loads_only_the_existing_local_snapshot(tmp_path, monkeypatch):
    snapshot = tmp_path / "hub" / "models--google--vit-base-patch16-224" / "snapshots" / "local-snapshot"
    snapshot.mkdir(parents=True)
    calls = []

    class Model:
        @staticmethod
        def eval():
            return None

    class Loader:
        @staticmethod
        def from_pretrained(path, **kwargs):
            calls.append((path, kwargs))
            return Model()

    monkeypatch.setitem(sys.modules, "transformers", SimpleNamespace(AutoModelForImageClassification=Loader))
    classifier = LocalVisionClassifier(tmp_path)

    classifier._load()

    assert calls == [(str(snapshot), {"local_files_only": True})]
