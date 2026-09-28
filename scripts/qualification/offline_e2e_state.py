#!/usr/bin/env python3
"""Prepare and query isolated synthetic offline E2E data only."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/qualification"))
sys.path.insert(0, str(ROOT / "src"))

DOCUMENT_NAME = "offline-qualification-note.txt"
DOCUMENT_TEXT = (
    "Synthetic offline qualification note. The private test phrase is "
    "ochre marshmallow 42. It exists only in this disposable candidate corpus.\n"
)
CODE_NAME = "offline_marker.py"
CODE_TEXT = '''"""Synthetic local repository for offline code intelligence."""


def local_offline_revision():
    """Return the fixed marker used by the offline qualification."""
    return "violet comet 42"
'''


def _load_runtime(state_root: Path, model: str):
    from offline_candidate_runtime import _candidate_environment

    _candidate_environment(state_root, model, 18080)
    from local_ai_assistant.common.config import get_config

    return get_config()


def prepare(state_root: Path, model: str) -> int:
    state_root = state_root.resolve()
    if Path("/tmp") not in state_root.parents:
        raise ValueError("offline E2E state must be below /tmp")
    config = _load_runtime(state_root, model)

    document_dir = config.paths.document_dir
    document_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    document = document_dir / DOCUMENT_NAME
    if document.exists():
        raise FileExistsError("refusing to overwrite a candidate document fixture")
    document.write_text(DOCUMENT_TEXT, encoding="utf-8")

    repository = config.paths.code_repo_dir / "synthetic-offline-project"
    repository.mkdir(mode=0o700, parents=True, exist_ok=True)
    code = repository / CODE_NAME
    if code.exists():
        raise FileExistsError("refusing to overwrite a candidate code fixture")
    code.write_text(CODE_TEXT, encoding="utf-8")

    from local_ai_assistant.code_index.repository import CodeRAG
    from local_ai_assistant.rag.documents import LocalRAG
    from local_ai_assistant.rag.knowledge import PrivateDocumentKnowledgeService

    documents = LocalRAG(config=config)
    documents.force_reindex()
    code_rag = CodeRAG(config=config)
    code_rag.reindex(full_symbols=True)
    if not code_rag.load():
        raise RuntimeError("synthetic local code index did not reload")
    sources = PrivateDocumentKnowledgeService(config=config, llm=None).list_sources()
    source_items = sources.get("sources", [])
    if sources.get("index_status") != "available" or len(source_items) != 1:
        raise RuntimeError("synthetic private Knowledge index did not reload")
    print(json.dumps({
        "result": "prepared",
        "knowledge_source": {
            "source_id": source_items[0]["source_id"],
            "display_name": source_items[0]["display_name"],
            "sha256": source_items[0]["source_sha256"],
            "chunk_count": source_items[0]["chunk_count"],
        },
        "code_index_loaded": True,
        "code_repository": repository.name,
        "network_mode": "systemd-private-network",
        "embedding_mode": "local-cache-only",
    }, sort_keys=True), flush=True)
    return 0


def ask_code(state_root: Path, model: str) -> int:
    state_root = state_root.resolve()
    if Path("/tmp") not in state_root.parents:
        raise ValueError("offline E2E state must be below /tmp")
    config = _load_runtime(state_root, model)
    from local_ai_assistant.code_index.repository import CodeRAG

    rag = CodeRAG(config=config)
    if not rag.load():
        raise RuntimeError("synthetic local code index is unavailable")
    answer, sources = rag.ask("What does local_offline_revision return?")
    print(json.dumps({
        "answer": answer,
        "sources": [
            {"source": item.get("source"), "line_start": item.get("line_start"), "line_end": item.get("line_end")}
            for item in sources
        ],
        "network_mode": "systemd-private-network",
    }, sort_keys=True), flush=True)
    return 0 if "violet comet 42" in answer and sources else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "ask-code"))
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--model", required=True)
    args = parser.parse_args()
    return prepare(args.state_root, args.model) if args.mode == "prepare" else ask_code(args.state_root, args.model)


if __name__ == "__main__":
    raise SystemExit(main())
