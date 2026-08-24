#!/usr/bin/env python3
"""Measure deterministic mixed-language incremental index mechanics."""

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
        language = number % 3
        if language == 0:
            path = repository / f"module_{number:04}.py"
            source = f"def function_{number}(value: int) -> int:\n    return value + {number}\n"
        elif language == 1:
            path = repository / f"module_{number:04}.rs"
            source = f"pub fn function_{number}(value: i32) -> i32 {{ value + {number} }}\n"
        else:
            path = repository / f"Contract{number:04}.sol"
            source = f"contract Contract{number:04} {{ function value() public pure returns(uint) {{ return {number}; }} }}\n"
        path.write_text(source, encoding="utf-8")


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
        python_target = repository / "module_0000.py"
        python_target.write_text(
            python_target.read_text() + "\ndef added_python():\n    return True\n"
        )
        python_changed = index.refresh()
        rust_target = repository / "module_0001.rs"
        rust_target.write_text(rust_target.read_text() + "\npub fn added_rust() {}\n")
        rust_changed = index.refresh()
        solidity_target = repository / "Contract0002.sol"
        solidity_target.write_text(solidity_target.read_text() + "\ncontract Added {}\n")
        additional_changed = index.refresh()
        print(
            json.dumps(
                {
                    "full": asdict(full),
                    "no_change": asdict(unchanged),
                    "one_python_file_change": asdict(python_changed),
                    "one_rust_file_change": asdict(rust_changed),
                    "one_additional_language_file_change": asdict(additional_changed),
                },
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
