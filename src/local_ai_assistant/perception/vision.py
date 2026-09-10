"""Optional offline specialized visual classifier; never a general-purpose LLM."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class VisualLabel:
    label: str
    confidence: float


class LocalVisionClassifier:
    """Load a locally cached ViT classifier on CPU only, after an explicit request."""

    def __init__(self, cache_dir: Path, *, model_id: str = "google/vit-base-patch16-224") -> None:
        self.cache_dir = cache_dir.resolve()
        self.model_id = model_id
        self._model = None

    def _load(self):
        if self._model is not None:
            return self._model
        try:
            from transformers import AutoModelForImageClassification
        except ImportError as exc:
            raise RuntimeError("local vision dependencies are unavailable") from exc
        try:
            cache_name = self.model_id.replace("/", "--")
            snapshots = self.cache_dir / "hub" / f"models--{cache_name}" / "snapshots"
            candidates = (
                sorted(path for path in snapshots.iterdir() if path.is_dir())
                if snapshots.is_dir()
                else []
            )
            if not candidates:
                raise OSError("model snapshot is missing")
            self._model = AutoModelForImageClassification.from_pretrained(str(candidates[-1]))
            self._model.eval()
        except OSError as exc:
            raise RuntimeError("local vision model is unavailable") from exc
        return self._model

    def classify(self, image_path: Path, *, top_k: int = 3) -> tuple[VisualLabel, ...]:
        if not 1 <= top_k <= 10:
            raise ValueError("top_k must be between 1 and 10")
        try:
            import numpy as np
            import torch
            from PIL import Image
        except ImportError as exc:
            raise RuntimeError("local vision dependencies are unavailable") from exc
        with Image.open(image_path) as image:
            rgb = image.convert("RGB").resize((224, 224))
            pixels = np.asarray(rgb, dtype=np.float32) / 255.0
        tensor = torch.from_numpy(pixels).permute(2, 0, 1).unsqueeze(0)
        tensor = (tensor - torch.tensor([0.5, 0.5, 0.5]).view(1, 3, 1, 1)) / 0.5
        model = self._load()
        with torch.inference_mode():
            probabilities = torch.softmax(model(pixel_values=tensor).logits[0], dim=0)
        scores, indexes = torch.topk(probabilities, top_k)
        return tuple(
            VisualLabel(model.config.id2label[index.item()], float(score))
            for score, index in zip(scores, indexes, strict=True)
        )
