from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

from local_ai_assistant.common.paths import CODE_INDEX_DIR as INDEX_DIR
from local_ai_assistant.common.paths import CODE_REPO_DIR as REPO_DIR
from local_ai_assistant.llm import LocalLLM

INDEX_FILE = INDEX_DIR / "code.faiss"
CHUNKS_FILE = INDEX_DIR / "code_chunks.json"
MANIFEST_FILE = INDEX_DIR / "manifest.json"

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"

CODE_EXTENSIONS = {
    ".py",
    ".rs",
    ".sol",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".cpp",
    ".cc",
    ".c",
    ".h",
    ".hpp",
    ".go",
    ".sql",
    ".sh",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".md",
}

SKIP_DIRS = {
    ".git",
    "node_modules",
    "target",
    "dist",
    "build",
    ".next",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    "coverage",
}

CHUNK_LINES = 120
OVERLAP_LINES = 20

VECTOR_TOP_K = 12
BM25_TOP_K = 12
FINAL_TOP_K = 6
RRF_K = 60


def lexical_tokenize(text: str) -> list[str]:
    return re.findall(
        r"[A-Za-z0-9_./:#<>-]+",
        text.lower(),
    )


class CodeRAG:
    def __init__(self):
        REPO_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        INDEX_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        print("Loading embedding model...")

        self.embedder = SentenceTransformer(
            EMBEDDING_MODEL,
            device="cpu",
        )

        self.llm = LocalLLM()

        self.chunks: list[dict[str, Any]] = []

        self.index = None
        self.bm25 = None
        self.manifest = {}

    @staticmethod
    def sha256(path: Path) -> str:
        hasher = hashlib.sha256()

        with path.open("rb") as f:
            while True:
                block = f.read(
                    1024 * 1024
                )

                if not block:
                    break

                hasher.update(block)

        return hasher.hexdigest()

    @staticmethod
    def should_skip(path: Path) -> bool:
        return any(
            part in SKIP_DIRS
            for part in path.parts
        )

    def discover_files(self):
        files = []

        for path in REPO_DIR.rglob("*"):
            if not path.is_file():
                continue

            if self.should_skip(path):
                continue

            if path.suffix.lower() not in CODE_EXTENSIONS:
                continue

            files.append(path)

        return sorted(files)

    def chunk_code(
        self,
        text: str,
    ) -> list[dict[str, Any]]:
        lines = text.splitlines()

        chunks = []

        start = 0

        while start < len(lines):
            end = min(
                start + CHUNK_LINES,
                len(lines),
            )

            block = "\n".join(
                lines[start:end]
            ).strip()

            if block:
                chunks.append(
                    {
                        "text": block,
                        "line_start": start + 1,
                        "line_end": end,
                    }
                )

            if end >= len(lines):
                break

            start = end - OVERLAP_LINES

        return chunks

    def build_chunks(self):
        files = self.discover_files()

        print(
            f"Found {len(files)} source files."
        )

        chunks = []
        manifest = {}

        for path in files:
            relative = str(
                path.relative_to(
                    REPO_DIR
                )
            )

            try:
                text = path.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )

            except Exception as exc:
                print(
                    f"Skipping {relative}: {exc}"
                )
                continue

            manifest[relative] = {
                "sha256": self.sha256(path),
                "size": path.stat().st_size,
            }

            for chunk_number, chunk in enumerate(
                self.chunk_code(text)
            ):
                chunks.append(
                    {
                        "text": chunk["text"],
                        "source": relative,
                        "chunk": chunk_number,
                        "line_start": chunk["line_start"],
                        "line_end": chunk["line_end"],
                        "extension": path.suffix.lower(),
                    }
                )

        self.chunks = chunks
        self.manifest = manifest

    def build_vector_index(self):
        if not self.chunks:
            raise RuntimeError(
                "No code chunks available."
            )

        texts = [
            chunk["text"]
            for chunk in self.chunks
        ]

        print(
            f"Embedding {len(texts)} code chunks..."
        )

        embeddings = self.embedder.encode(
            texts,
            batch_size=32,
            show_progress_bar=True,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )

        embeddings = np.asarray(
            embeddings,
            dtype=np.float32,
        )

        dimension = embeddings.shape[1]

        self.index = faiss.IndexFlatIP(
            dimension
        )

        self.index.add(
            embeddings
        )

        print(
            f"FAISS ready: "
            f"{self.index.ntotal} vectors"
        )

    def build_bm25(self):
        corpus = [
            lexical_tokenize(
                chunk["text"]
            )
            for chunk in self.chunks
        ]

        self.bm25 = BM25Okapi(
            corpus
        )

        print(
            f"BM25 ready: "
            f"{len(corpus)} chunks"
        )

    def save(self):
        faiss.write_index(
            self.index,
            str(INDEX_FILE),
        )

        CHUNKS_FILE.write_text(
            json.dumps(
                self.chunks,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        MANIFEST_FILE.write_text(
            json.dumps(
                self.manifest,
                indent=2,
            ),
            encoding="utf-8",
        )

    def load(self) -> bool:
        if (
            not INDEX_FILE.exists()
            or not CHUNKS_FILE.exists()
        ):
            return False

        self.index = faiss.read_index(
            str(INDEX_FILE)
        )

        self.chunks = json.loads(
            CHUNKS_FILE.read_text(
                encoding="utf-8"
            )
        )

        self.build_bm25()

        return True

    def reindex(self):
        self.build_chunks()
        self.build_vector_index()
        self.build_bm25()
        self.save()

        print()
        print(
            f"Indexed {len(self.chunks)} chunks."
        )

    def vector_search(
        self,
        question: str,
    ):
        query = self.embedder.encode(
            [question],
            normalize_embeddings=True,
            convert_to_numpy=True,
        )

        query = np.asarray(
            query,
            dtype=np.float32,
        )

        top_k = min(
            VECTOR_TOP_K,
            len(self.chunks),
        )

        scores, indices = self.index.search(
            query,
            top_k,
        )

        return [
            {
                "index": int(index),
                "rank": rank,
                "score": float(score),
            }
            for rank, (score, index)
            in enumerate(
                zip(
                    scores[0],
                    indices[0],
                ),
                start=1,
            )
            if index >= 0
        ]

    def bm25_search(
        self,
        question: str,
    ):
        tokens = lexical_tokenize(
            question
        )

        scores = self.bm25.get_scores(
            tokens
        )

        top_k = min(
            BM25_TOP_K,
            len(self.chunks),
        )

        indices = np.argsort(
            scores
        )[::-1][:top_k]

        return [
            {
                "index": int(index),
                "rank": rank,
                "score": float(
                    scores[index]
                ),
            }
            for rank, index
            in enumerate(
                indices,
                start=1,
            )
        ]

    def retrieve(
        self,
        question: str,
    ):
        candidates = {}

        for result in self.vector_search(
            question
        ):
            idx = result["index"]

            candidates.setdefault(
                idx,
                {
                    "rrf": 0.0,
                    "vector_rank": None,
                    "bm25_rank": None,
                },
            )

            candidates[idx][
                "vector_rank"
            ] = result["rank"]

            candidates[idx]["rrf"] += (
                1.0
                / (
                    RRF_K
                    + result["rank"]
                )
            )

        for result in self.bm25_search(
            question
        ):
            idx = result["index"]

            candidates.setdefault(
                idx,
                {
                    "rrf": 0.0,
                    "vector_rank": None,
                    "bm25_rank": None,
                },
            )

            candidates[idx][
                "bm25_rank"
            ] = result["rank"]

            candidates[idx]["rrf"] += (
                1.0
                / (
                    RRF_K
                    + result["rank"]
                )
            )

        results = []

        for idx, scores in candidates.items():
            results.append(
                {
                    **self.chunks[idx],
                    **scores,
                }
            )

        results.sort(
            key=lambda x: x["rrf"],
            reverse=True,
        )

        return results[
            :FINAL_TOP_K
        ]

    @staticmethod
    def build_context(
        results,
    ) -> str:
        blocks = []

        for number, result in enumerate(
            results,
            start=1,
        ):
            blocks.append(
                f"[SOURCE {number}: "
                f"{result['source']} "
                f"lines "
                f"{result['line_start']}-"
                f"{result['line_end']}]\n"
                f"{result['text']}"
            )

        return "\n\n".join(
            blocks
        )

    def ask(
        self,
        question: str,
    ):
        results = self.retrieve(
            question
        )

        context = self.build_context(
            results
        )

        prompt = f"""
You are analyzing a software repository.

Use only the retrieved repository context below.

You may:
- explain architecture
- locate implementations
- trace code flow
- identify likely bugs
- explain functions and classes
- compare modules

Rules:

1. Do not claim code exists unless present in the retrieved context.
2. Cite relevant code using [SOURCE 1], [SOURCE 2], etc.
3. Mention filenames and line ranges when useful.
4. If the retrieved code is insufficient, clearly say so.
5. Do not fabricate missing implementation details.

REPOSITORY CONTEXT:

{context}

QUESTION:

{question}

ANSWER:
"""

        answer = self.llm.chat(
            prompt=prompt,
            system_prompt=(
                "You are a senior software engineer "
                "analyzing a local source-code repository."
            ),
            temperature=0.1,
            max_tokens=1200,
        )

        return answer, results


def main():
    rag = CodeRAG()

    if not rag.load():
        print(
            "No code index found."
        )
        print(
            "Run with --reindex after "
            "placing a repository in:"
        )
        print(
            REPO_DIR
        )
        return

    print()
    print("LOCAL CODE RAG READY")
    print("Type /exit to quit.")
    print()

    while True:
        question = input(
            "Code question: "
        ).strip()

        if question.lower() in {
            "/exit",
            "exit",
            "quit",
        }:
            break

        if not question:
            continue

        answer, results = rag.ask(
            question
        )

        print()
        print(answer)
        print()

        print("Retrieved code:")

        for result in results:
            print(
                f"- {result['source']} "
                f"lines "
                f"{result['line_start']}-"
                f"{result['line_end']}"
            )

        print()


if __name__ == "__main__":
    import sys

    if "--reindex" in sys.argv:
        rag = CodeRAG()
        rag.reindex()
    else:
        main()
