#!/usr/bin/env python3
"""Measure deterministic Stage 2 full/no-change/one-file refresh behavior."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from dataclasses import asdict
from pathlib import Path

import numpy as np

from local_ai_assistant.code_index.symbol_index import SymbolIndex


class HashEmbedder:
    """Stable local benchmark encoder; it measures index mechanics, not BGE quality."""

    def encode(self, texts, **kwargs):
        vectors = []
        for text in texts:
            digest = hashlib.sha256(text.encode()).digest()
            vector = np.frombuffer(digest[:16], dtype=np.uint8).astype(np.float32) + 1
            vectors.append(vector / np.linalg.norm(vector))
        return np.asarray(vectors, dtype=np.float32)


def populate(repository: Path, count: int) -> None:
    repository.mkdir(parents=True)
    for number in range(count):
        (repository / f"module_{number:04}.py").write_text(
            f"def function_{number}(value: int) -> int:\n"
            f"    \"\"\"Synthetic function {number}.\"\"\"\n"
            f"    return value + {number}\n",
            encoding="utf-8",
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--files", type=int, default=250)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="local-ai-symbol-benchmark-") as directory:
        root = Path(directory)
        repository = root / "repository"
        populate(repository, args.files)
        index = SymbolIndex(repository, root / "index", HashEmbedder())
        full = index.refresh(full=True)
        unchanged = index.refresh()
        target = repository / "module_0000.py"
        target.write_text(target.read_text() + "\ndef added():\n    return True\n")
        changed = index.refresh()
        print(
            json.dumps(
                {
                    "full": asdict(full),
                    "no_change": asdict(unchanged),
                    "one_file_change": asdict(changed),
                },
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
