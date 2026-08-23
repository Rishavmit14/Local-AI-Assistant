from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

import faiss
import numpy as np
import pytesseract
from docx import Document
from pdf2image import convert_from_path
from pypdf import PdfReader
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

from local_ai_assistant.common.config import AppConfig, OCRConfig, get_config
from local_ai_assistant.common.errors import IndexingError
from local_ai_assistant.common.logging import configure_logging, get_logger
from local_ai_assistant.llm import LocalLLM

# ============================================================
# CONFIGURATION
# ============================================================

_DEFAULT_CONFIG = get_config()
DOCUMENT_DIR = _DEFAULT_CONFIG.paths.document_dir
RAG_DATA_DIR = _DEFAULT_CONFIG.paths.rag_data_dir
INDEX_FILE = RAG_DATA_DIR / "index.faiss"
CHUNKS_FILE = RAG_DATA_DIR / "chunks.json"
MANIFEST_FILE = RAG_DATA_DIR / "manifest.json"

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"

# ------------------------------------------------------------
# Chunking
# ------------------------------------------------------------

CHUNK_SIZE = 450
CHUNK_OVERLAP = 75

# ------------------------------------------------------------
# Retrieval
# ------------------------------------------------------------

VECTOR_TOP_K = 10
BM25_TOP_K = 10
FINAL_TOP_K = 5

RRF_K = 60

# ------------------------------------------------------------
# OCR
# ------------------------------------------------------------

OCR_ENABLED = True
OCR_LANGUAGE = "eng"

# If native PDF extraction returns fewer than this many useful
# characters, OCR will be attempted for that page.
OCR_MIN_TEXT_LENGTH = 80

# 200 DPI is a good CPU/speed/quality compromise.
OCR_DPI = 200

SUPPORTED_EXTENSIONS = {
    ".txt",
    ".md",
    ".pdf",
    ".docx",
}

logger = get_logger(__name__)


# ============================================================
# TEXT HELPERS
# ============================================================

def lexical_tokenize(text: str) -> list[str]:
    """
    Lightweight tokenizer for BM25.

    Keeps useful technical strings such as:

        TITAN-8080
        ORION-73921
        llama.cpp
        Q4_K_M
        function_name
        /v1/chat/completions
    """

    return re.findall(
        r"[A-Za-z0-9_./:+#-]+",
        text.lower(),
    )


def normalize_scores(values: list[float]) -> list[float]:
    if not values:
        return []

    minimum = min(values)
    maximum = max(values)

    if math.isclose(minimum, maximum):
        if maximum == 0:
            return [0.0 for _ in values]

        return [1.0 for _ in values]

    return [
        (value - minimum) / (maximum - minimum)
        for value in values
    ]


# ============================================================
# LOCAL RAG
# ============================================================

class LocalRAG:

    def __init__(
        self,
        config: AppConfig | None = None,
        *,
        embedder=None,
        llm: LocalLLM | None = None,
    ) -> None:
        self.config = config or get_config()
        self.document_dir = self.config.paths.document_dir
        self.rag_data_dir = self.config.paths.rag_data_dir
        self.index_file = self.rag_data_dir / "index.faiss"
        self.chunks_file = self.rag_data_dir / "chunks.json"
        self.manifest_file = self.rag_data_dir / "manifest.json"

        self.document_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.rag_data_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        print("Loading embedding model...")

        logger.info(
            "document_rag_initializing",
            extra={"event": "rag.initializing", "document_dir": self.document_dir},
        )
        self.embedder = embedder or SentenceTransformer(
            self.config.embedding.model,
            device=self.config.embedding.device,
        )

        self.tokenizer = self.embedder.tokenizer

        self.llm = llm or LocalLLM(config=self.config)

        self.chunks: list[dict[str, Any]] = []

        self.index = None

        self.bm25 = None
        self.bm25_corpus: list[list[str]] = []

        self.manifest: dict[str, Any] = {}

    # ========================================================
    # FILE HASHING
    # ========================================================

    @staticmethod
    def calculate_hash(path: Path) -> str:

        sha256 = hashlib.sha256()

        with path.open("rb") as file:

            while True:

                block = file.read(
                    1024 * 1024
                )

                if not block:
                    break

                sha256.update(block)

        return sha256.hexdigest()

    # ========================================================
    # TEXT CLEANING
    # ========================================================

    @staticmethod
    def clean_extracted_text(
        text: str,
    ) -> str:

        text = text or ""

        lines = []

        for line in text.splitlines():

            line = " ".join(
                line.split()
            )

            if line:
                lines.append(line)

        return "\n".join(
            lines
        ).strip()

    # ========================================================
    # OCR DETECTION
    # ========================================================

    @staticmethod
    def needs_ocr(
        text: str,
        config: OCRConfig | None = None,
    ) -> bool:
        settings = config or OCRConfig()

        if not settings.enabled:
            return False

        cleaned = (
            LocalRAG.clean_extracted_text(
                text
            )
        )

        if len(cleaned) < settings.minimum_text_length:
            return True

        useful_chars = sum(
            character.isalnum()
            for character in cleaned
        )

        if (
            useful_chars
            < settings.minimum_text_length // 2
        ):
            return True

        return False

    # ========================================================
    # OCR ONE PDF PAGE
    # ========================================================

    def ocr_pdf_page(
        self,
        path: Path,
        page_number: int,
    ) -> str:

        """
        OCR one PDF page.

        page_number is 1-based.
        """

        try:

            images = convert_from_path(
                str(path),
                dpi=self.config.ocr.dpi,
                first_page=page_number,
                last_page=page_number,
                fmt="png",
                thread_count=1,
            )

            if not images:
                return ""

            image = images[0]

            text = pytesseract.image_to_string(
                image,
                lang=self.config.ocr.language,
                config="--psm 3",
            )

            return (
                LocalRAG.clean_extracted_text(
                    text
                )
            )

        except Exception as exc:

            logger.warning(
                "ocr_page_failed",
                extra={
                    "event": "rag.ocr.failed",
                    "source": path.name,
                    "page": page_number,
                    "error": str(exc),
                },
            )

            print(
                f"  OCR warning: "
                f"{path.name}, "
                f"page {page_number}: "
                f"{exc}"
            )

            return ""

    # ========================================================
    # TXT / MARKDOWN EXTRACTION
    # ========================================================

    @staticmethod
    def extract_txt(
        path: Path,
    ):

        text = path.read_text(
            encoding="utf-8",
            errors="ignore",
        )

        return [
            {
                "text": text,
                "page": None,
                "extraction_method": "native",
            }
        ]

    # ========================================================
    # DOCX EXTRACTION
    # ========================================================

    @staticmethod
    def extract_docx(
        path: Path,
    ):

        document = Document(path)

        paragraphs = []

        for paragraph in (
            document.paragraphs
        ):

            text = (
                paragraph.text.strip()
            )

            if text:
                paragraphs.append(text)

        return [
            {
                "text": "\n\n".join(
                    paragraphs
                ),
                "page": None,
                "extraction_method": "native",
            }
        ]

    # ========================================================
    # PDF EXTRACTION + OCR FALLBACK
    # ========================================================

    def extract_pdf(
        self,
        path: Path,
    ):

        reader = PdfReader(path)

        pages = []

        total_pages = len(
            reader.pages
        )

        print(
            f"  PDF pages: "
            f"{total_pages}"
        )

        for page_number, page in enumerate(
            reader.pages,
            start=1,
        ):

            # ------------------------------------------------
            # Native PDF text extraction
            # ------------------------------------------------

            try:

                native_text = (
                    page.extract_text()
                    or ""
                )

            except Exception as exc:

                print(
                    f"  Native extraction "
                    f"warning: "
                    f"{path.name}, "
                    f"page {page_number}: "
                    f"{exc}"
                )

                native_text = ""

            native_text = (
                LocalRAG.clean_extracted_text(
                    native_text
                )
            )

            text = native_text
            extraction_method = "native"

            # ------------------------------------------------
            # OCR fallback
            # ------------------------------------------------

            if self.needs_ocr(
                native_text,
                self.config.ocr,
            ):

                logger.info(
                    "ocr_page_started",
                    extra={
                        "event": "rag.ocr.started",
                        "source": path.name,
                        "page": page_number,
                    },
                )

                print(
                    f"  OCR page "
                    f"{page_number}/"
                    f"{total_pages}"
                )

                ocr_text = (
                    self.ocr_pdf_page(
                        path,
                        page_number,
                    )
                )

                # Prefer OCR when it recovered more useful text.
                if len(ocr_text) > len(
                    native_text
                ):

                    text = ocr_text
                    extraction_method = "ocr"
                    logger.info(
                        "ocr_page_selected",
                        extra={
                            "event": "rag.ocr.selected",
                            "source": path.name,
                            "page": page_number,
                            "characters": len(ocr_text),
                        },
                    )

            # ------------------------------------------------
            # Ignore empty pages
            # ------------------------------------------------

            if not text.strip():

                print(
                    f"  Empty page skipped: "
                    f"{page_number}"
                )

                continue

            pages.append(
                {
                    "text": text,
                    "page": page_number,
                    "extraction_method": (
                        extraction_method
                    ),
                }
            )

        return pages

    # ========================================================
    # DOCUMENT ROUTING
    # ========================================================

    def extract_document(
        self,
        path: Path,
    ):

        suffix = path.suffix.lower()

        if suffix in {
            ".txt",
            ".md",
        }:

            return self.extract_txt(
                path
            )

        if suffix == ".pdf":

            return self.extract_pdf(
                path
            )

        if suffix == ".docx":

            return self.extract_docx(
                path
            )

        return []

    # ========================================================
    # TOKEN-AWARE CHUNKING
    # ========================================================

    def chunk_text(
        self,
        text: str,
        chunk_size: int | None = None,
        overlap: int | None = None,
    ):
        chunk_size = chunk_size or self.config.document_retrieval.chunk_size
        if overlap is None:
            overlap = self.config.document_retrieval.chunk_overlap

        if not text.strip():
            return []

        tokens = self.tokenizer.encode(
            text,
            add_special_tokens=False,
        )

        chunks = []

        start = 0

        while start < len(tokens):

            end = min(
                start + chunk_size,
                len(tokens),
            )

            chunk_tokens = tokens[
                start:end
            ]

            chunk = (
                self.tokenizer.decode(
                    chunk_tokens,
                    skip_special_tokens=True,
                )
                .strip()
            )

            if chunk:
                chunks.append(chunk)

            if end >= len(tokens):
                break

            start = (
                end - overlap
            )

        return chunks

    # ========================================================
    # DOCUMENT DISCOVERY
    # ========================================================

    def discover_documents(self):

        files = []

        for path in (
            self.document_dir.rglob("*")
        ):

            if (
                path.is_file()
                and path.suffix.lower()
                in SUPPORTED_EXTENSIONS
            ):

                files.append(path)

        return sorted(files)

    # ========================================================
    # MANIFEST
    # ========================================================

    def load_manifest(self):

        if not self.manifest_file.exists():

            self.manifest = {}
            return

        try:

            self.manifest = (
                json.loads(
                    self.manifest_file.read_text(
                        encoding="utf-8"
                    )
                )
            )

        except Exception:

            self.manifest = {}

    def save_manifest(self):

        self.manifest_file.write_text(
            json.dumps(
                self.manifest,
                indent=2,
            ),
            encoding="utf-8",
        )

    # ========================================================
    # PERSISTENCE
    # ========================================================

    def save_chunks(self):

        self.chunks_file.write_text(
            json.dumps(
                self.chunks,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def load_chunks(self):

        if not self.chunks_file.exists():

            self.chunks = []
            return

        self.chunks = json.loads(
            self.chunks_file.read_text(
                encoding="utf-8"
            )
        )

    def save_index(self):

        if self.index is not None:

            faiss.write_index(
                self.index,
                str(self.index_file),
            )

    def load_index(self):

        if not self.index_file.exists():
            return False

        try:

            self.index = (
                faiss.read_index(
                    str(self.index_file)
                )
            )

        except Exception:

            return False

        return True

    # ========================================================
    # BUILD DOCUMENT CHUNKS
    # ========================================================

    def build_document_chunks(self):

        documents = (
            self.discover_documents()
        )

        all_chunks = []
        new_manifest = {}

        print(
            f"Scanning "
            f"{len(documents)} "
            f"document(s)..."
        )

        for path in documents:

            relative_path = str(
                path.relative_to(
                    self.document_dir
                )
            )

            print()
            print(
                f"Processing: "
                f"{relative_path}"
            )

            file_hash = (
                self.calculate_hash(
                    path
                )
            )

            new_manifest[
                relative_path
            ] = {

                "sha256": file_hash,

                "size": (
                    path.stat().st_size
                ),

                "mtime": (
                    path.stat().st_mtime
                ),
            }

            sections = (
                self.extract_document(
                    path
                )
            )

            document_chunk_number = 0

            for section in sections:

                page = (
                    section.get(
                        "page"
                    )
                )

                extraction_method = (
                    section.get(
                        "extraction_method",
                        "native",
                    )
                )

                text_chunks = (
                    self.chunk_text(
                        section["text"]
                    )
                )

                for text in (
                    text_chunks
                ):

                    all_chunks.append(
                        {
                            "text": text,

                            "source": (
                                relative_path
                            ),

                            "page": page,

                            "chunk": (
                                document_chunk_number
                            ),

                            "extraction_method": (
                                extraction_method
                            ),
                        }
                    )

                    document_chunk_number += 1

        self.chunks = all_chunks
        self.manifest = new_manifest

    # ========================================================
    # VECTOR INDEX
    # ========================================================

    def generate_vector_index(
        self,
    ):

        if not self.chunks:

            raise IndexingError(
                "No chunks available."
            )

        texts = [

            chunk["text"]

            for chunk in self.chunks
        ]

        logger.info(
            "document_embedding_started",
            extra={"event": "rag.index.embedding_started", "chunk_count": len(texts)},
        )

        print()
        print(
            f"Generating embeddings "
            f"for {len(texts)} chunks..."
        )

        embeddings = (
            self.embedder.encode(
                texts,
                batch_size=self.config.embedding.batch_size,
                show_progress_bar=not self.config.runtime.test_mode,
                normalize_embeddings=True,
                convert_to_numpy=True,
            )
        )

        embeddings = np.asarray(
            embeddings,
            dtype=np.float32,
        )

        dimension = (
            embeddings.shape[1]
        )

        self.index = (
            faiss.IndexFlatIP(
                dimension
            )
        )

        self.index.add(
            embeddings
        )

        logger.info(
            "document_index_created",
            extra={
                "event": "rag.index.created",
                "vector_count": int(self.index.ntotal),
                "dimensions": int(dimension),
            },
        )

        print()
        print(
            "FAISS index created:"
        )

        print(
            f"  vectors: "
            f"{self.index.ntotal}"
        )

        print(
            f"  dimensions: "
            f"{dimension}"
        )

    # ========================================================
    # BM25
    # ========================================================

    def generate_bm25_index(
        self,
    ):

        print(
            "Building BM25 index..."
        )

        self.bm25_corpus = [

            lexical_tokenize(
                chunk["text"]
            )

            for chunk in self.chunks
        ]

        self.bm25 = BM25Okapi(
            self.bm25_corpus
        )

        print(
            f"BM25 index created: "
            f"{len(self.bm25_corpus)} "
            f"chunks"
        )

    # ========================================================
    # CHANGE DETECTION
    # ========================================================

    def current_manifest(
        self,
    ):

        result = {}

        for path in (
            self.discover_documents()
        ):

            relative_path = str(
                path.relative_to(
                    self.document_dir
                )
            )

            result[
                relative_path
            ] = {

                "sha256": (
                    self.calculate_hash(
                        path
                    )
                ),

                "size": (
                    path.stat().st_size
                ),

                "mtime": (
                    path.stat().st_mtime
                ),
            }

        return result

    def index_needs_rebuild(
        self,
    ):

        if (
            not self.index_file.exists()
            or not self.chunks_file.exists()
            or not self.manifest_file.exists()
        ):
            return True

        self.load_manifest()

        current = (
            self.current_manifest()
        )

        if set(current.keys()) != set(
            self.manifest.keys()
        ):
            return True

        for filename, info in (
            current.items()
        ):

            previous = (
                self.manifest.get(
                    filename
                )
            )

            if not previous:
                return True

            if (
                previous.get(
                    "sha256"
                )
                != info["sha256"]
            ):
                return True

        return False

    # ========================================================
    # INITIALIZATION
    # ========================================================

    def initialize_index(
        self,
    ):

        logger.info("document_index_initializing", extra={"event": "rag.index.initializing"})

        if self.index_needs_rebuild():

            print(
                "Document changes detected."
            )

            print(
                "Rebuilding RAG index..."
            )

            self.build_document_chunks()

            if not self.chunks:

                print(
                    "No supported "
                    "documents found."
                )

                return False

            self.generate_vector_index()
            self.generate_bm25_index()

            self.save_index()
            self.save_chunks()
            self.save_manifest()

            print()
            print(
                "Persistent index saved."
            )

        else:

            print(
                "No document changes detected."
            )

            print(
                "Loading persistent "
                "FAISS index..."
            )

            self.load_chunks()

            if not self.load_index():

                print(
                    "FAISS load failed."
                )

                return False

            self.generate_bm25_index()

        print()
        print(
            f"Hybrid RAG ready: "
            f"{len(self.chunks)} chunks"
        )

        return True

    # ========================================================
    # VECTOR SEARCH
    # ========================================================

    def vector_search(
        self,
        question: str,
        top_k: int,
    ):

        query_embedding = (
            self.embedder.encode(
                [question],
                normalize_embeddings=True,
                convert_to_numpy=True,
            )
        )

        query_embedding = np.asarray(
            query_embedding,
            dtype=np.float32,
        )

        top_k = min(
            top_k,
            len(self.chunks),
        )

        scores, indices = (
            self.index.search(
                query_embedding,
                top_k,
            )
        )

        results = []

        for rank, (
            score,
            index,
        ) in enumerate(
            zip(
                scores[0],
                indices[0],
            ),
            start=1,
        ):

            if index < 0:
                continue

            results.append(
                {
                    "index": int(index),
                    "rank": rank,
                    "score": float(
                        score
                    ),
                }
            )

        return results

    # ========================================================
    # BM25 SEARCH
    # ========================================================

    def bm25_search(
        self,
        question: str,
        top_k: int,
    ):

        query_tokens = (
            lexical_tokenize(
                question
            )
        )

        scores = (
            self.bm25.get_scores(
                query_tokens
            )
        )

        top_k = min(
            top_k,
            len(self.chunks),
        )

        best_indices = (
            np.argsort(
                scores
            )[::-1][:top_k]
        )

        results = []

        for rank, index in enumerate(
            best_indices,
            start=1,
        ):

            results.append(
                {
                    "index": int(index),
                    "rank": rank,
                    "score": float(
                        scores[index]
                    ),
                }
            )

        return results

    # ========================================================
    # HYBRID RETRIEVAL
    # ========================================================

    def retrieve(
        self,
        question: str,
    ):

        logger.info(
            "document_retrieval_started",
            extra={"event": "rag.retrieve.started", "query_characters": len(question)},
        )

        vector_results = (
            self.vector_search(
                question,
                self.config.document_retrieval.vector_top_k,
            )
        )

        bm25_results = (
            self.bm25_search(
                question,
                self.config.document_retrieval.bm25_top_k,
            )
        )

        candidates = {}

        # ----------------------------------------------------
        # FAISS contribution
        # ----------------------------------------------------

        for result in (
            vector_results
        ):

            index = result["index"]

            candidates.setdefault(
                index,
                {
                    "vector_rank": None,
                    "vector_score": None,
                    "bm25_rank": None,
                    "bm25_score": None,
                    "rrf_score": 0.0,
                },
            )

            candidates[index][
                "vector_rank"
            ] = result["rank"]

            candidates[index][
                "vector_score"
            ] = result["score"]

            candidates[index][
                "rrf_score"
            ] += (
                1.0
                / (
                    self.config.document_retrieval.rrf_k
                    + result["rank"]
                )
            )

        # ----------------------------------------------------
        # BM25 contribution
        # ----------------------------------------------------

        for result in (
            bm25_results
        ):

            index = result["index"]

            candidates.setdefault(
                index,
                {
                    "vector_rank": None,
                    "vector_score": None,
                    "bm25_rank": None,
                    "bm25_score": None,
                    "rrf_score": 0.0,
                },
            )

            candidates[index][
                "bm25_rank"
            ] = result["rank"]

            candidates[index][
                "bm25_score"
            ] = result["score"]

            candidates[index][
                "rrf_score"
            ] += (
                1.0
                / (
                    self.config.document_retrieval.rrf_k
                    + result["rank"]
                )
            )

        question_terms = set(
            lexical_tokenize(
                question
            )
        )

        results = []

        # ----------------------------------------------------
        # Lightweight reranking
        # ----------------------------------------------------

        for index, data in (
            candidates.items()
        ):

            chunk = self.chunks[
                index
            ]

            chunk_terms = set(
                lexical_tokenize(
                    chunk["text"]
                )
            )

            if question_terms:

                overlap = (
                    len(
                        question_terms
                        & chunk_terms
                    )
                    / len(
                        question_terms
                    )
                )

            else:

                overlap = 0.0

            final_score = (
                data["rrf_score"]
                + 0.01 * overlap
            )

            results.append(
                {
                    **chunk,
                    **data,
                    "lexical_overlap": (
                        overlap
                    ),
                    "hybrid_score": (
                        final_score
                    ),
                }
            )

        results.sort(
            key=lambda item: (
                item[
                    "hybrid_score"
                ]
            ),
            reverse=True,
        )

        selected = results[
            :self.config.document_retrieval.final_top_k
        ]
        logger.info(
            "document_retrieval_completed",
            extra={"event": "rag.retrieve.completed", "result_count": len(selected)},
        )
        return selected

    # ========================================================
    # CONTEXT CONSTRUCTION
    # ========================================================

    @staticmethod
    def build_context(
        results,
    ):

        blocks = []

        for number, result in enumerate(
            results,
            start=1,
        ):

            source = (
                result["source"]
            )

            page = (
                result.get("page")
            )

            chunk_number = (
                result["chunk"]
            )

            extraction_method = (
                result.get(
                    "extraction_method",
                    "native",
                )
            )

            if page is not None:

                location = (
                    f"{source}, "
                    f"page {page}, "
                    f"chunk "
                    f"{chunk_number}, "
                    f"method "
                    f"{extraction_method}"
                )

            else:

                location = (
                    f"{source}, "
                    f"chunk "
                    f"{chunk_number}"
                )

            blocks.append(
                f"[SOURCE {number}: "
                f"{location}]\n"
                f"{result['text']}"
            )

        return "\n\n".join(
            blocks
        )

    # ========================================================
    # QUESTION ANSWERING
    # ========================================================

    def ask(
        self,
        question: str,
    ):

        results = (
            self.retrieve(
                question
            )
        )

        context = (
            self.build_context(
                results
            )
        )

        prompt = f"""
Answer the user's question using only the retrieved
document context below.

Rules:

1. Use only information supported by the context.
2. Never invent information.
3. If the answer is not supported by the context,
   respond exactly:

   I don't know based on the supplied documents.

4. Cite supporting sources using:
   [SOURCE 1], [SOURCE 2], etc.

5. Never cite a source that does not support the claim.
6. Prefer concise answers unless detail is required.

RETRIEVED CONTEXT:

{context}

USER QUESTION:

{question}

ANSWER:
"""

        answer = (
            self.llm.chat(
                prompt=prompt,
                system_prompt=(
                    "You are a local "
                    "retrieval-augmented "
                    "assistant. Ground "
                    "every factual claim "
                    "in retrieved "
                    "document context."
                ),
                temperature=0.0,
                max_tokens=768,
            )
        )

        return answer, results

    # ========================================================
    # DISPLAY RETRIEVAL RESULTS
    # ========================================================

    @staticmethod
    def display_results(
        results,
    ):

        print()
        print(
            "Hybrid retrieval results:"
        )

        for number, result in enumerate(
            results,
            start=1,
        ):

            source = (
                result["source"]
            )

            page = (
                result.get("page")
            )

            chunk = (
                result["chunk"]
            )

            method = (
                result.get(
                    "extraction_method",
                    "native",
                )
            )

            vector_rank = (
                result[
                    "vector_rank"
                ]
            )

            bm25_rank = (
                result[
                    "bm25_rank"
                ]
            )

            hybrid_score = (
                result[
                    "hybrid_score"
                ]
            )

            if page is not None:

                location = (
                    f"{source}, "
                    f"page {page}, "
                    f"chunk {chunk}, "
                    f"method={method}"
                )

            else:

                location = (
                    f"{source}, "
                    f"chunk {chunk}"
                )

            print(
                f"  SOURCE {number}"
            )

            print(
                f"    {location}"
            )

            print(
                f"    hybrid="
                f"{hybrid_score:.5f}"
            )

            print(
                f"    vector_rank="
                f"{vector_rank}"
            )

            print(
                f"    bm25_rank="
                f"{bm25_rank}"
            )

    # ========================================================
    # STATS
    # ========================================================

    def display_stats(
        self,
    ):

        print()
        print(
            "RAG statistics"
        )

        print(
            "-" * 50
        )

        print(
            f"Documents: "
            f"{len(self.manifest)}"
        )

        print(
            f"Chunks: "
            f"{len(self.chunks)}"
        )

        if self.index is not None:

            print(
                f"FAISS vectors: "
                f"{self.index.ntotal}"
            )

        print(
            f"Vector candidates: "
            f"{self.config.document_retrieval.vector_top_k}"
        )

        print(
            f"BM25 candidates: "
            f"{self.config.document_retrieval.bm25_top_k}"
        )

        print(
            f"Final context chunks: "
            f"{self.config.document_retrieval.final_top_k}"
        )

        ocr_chunks = sum(
            1
            for chunk in self.chunks
            if chunk.get(
                "extraction_method"
            )
            == "ocr"
        )

        print(
            f"OCR chunks: "
            f"{ocr_chunks}"
        )

        print()

    # ========================================================
    # FORCE REINDEX
    # ========================================================

    def force_reindex(
        self,
    ):

        logger.info("document_reindex_forced", extra={"event": "rag.index.force_rebuild"})

        print()
        print(
            "Rebuilding hybrid "
            "RAG index..."
        )

        self.build_document_chunks()

        if not self.chunks:

            print(
                "No documents found."
            )

            return

        self.generate_vector_index()
        self.generate_bm25_index()

        self.save_index()
        self.save_chunks()
        self.save_manifest()

        print()
        print(
            "Hybrid index rebuilt."
        )

    # ========================================================
    # INTERACTIVE CLI
    # ========================================================

    def interactive(
        self,
    ):

        print()
        print(
            "=" * 60
        )

        print(
            "LOCAL HYBRID RAG + OCR READY"
        )

        print(
            "=" * 60
        )

        print()
        print(
            "Retrieval:"
        )

        print(
            "  FAISS semantic search"
        )

        print(
            "  + BM25 lexical search"
        )

        print(
            "  + Reciprocal Rank Fusion"
        )

        print()
        print(
            "PDF ingestion:"
        )

        print(
            "  Native PDF extraction"
        )

        print(
            "  + selective Tesseract OCR"
        )

        print()
        print(
            "Commands:"
        )

        print(
            "  /exit"
        )

        print(
            "  /stats"
        )

        print(
            "  /reindex"
        )

        print()

        while True:

            try:

                question = input(
                    "Question: "
                ).strip()

            except (
                KeyboardInterrupt,
                EOFError,
            ):

                print()
                break

            if not question:
                continue

            command = (
                question.lower()
            )

            if command in {
                "/exit",
                "exit",
                "quit",
            }:

                break

            if command == "/stats":

                self.display_stats()
                continue

            if command == "/reindex":

                self.force_reindex()
                continue

            try:

                answer, results = (
                    self.ask(
                        question
                    )
                )

            except Exception as exc:

                print()
                print(
                    f"RAG error: "
                    f"{exc}"
                )
                print()

                continue

            print()
            print(
                "Answer:"
            )

            print(
                answer
            )

            self.display_results(
                results
            )

            print()


# ============================================================
# MAIN
# ============================================================

def main():
    config = get_config()
    configure_logging(config.runtime)
    rag = LocalRAG(config=config)

    if not rag.initialize_index():
        return

    rag.interactive()


if __name__ == "__main__":
    main()
