from __future__ import annotations

import os
from pathlib import Path


def env_path(name: str, default: Path) -> Path:
    """Return a path overridden by an environment variable when supplied."""
    return Path(os.environ.get(name, default)).expanduser().resolve()


PROJECT_ROOT = Path(__file__).resolve().parents[3]
VAR_DIR = env_path("LOCAL_AI_VAR_DIR", PROJECT_ROOT / "var")
DOCUMENT_DIR = env_path("LOCAL_AI_DOCUMENT_DIR", VAR_DIR / "documents")
RAG_DATA_DIR = env_path("LOCAL_AI_RAG_DATA_DIR", VAR_DIR / "rag")
CODE_REPO_DIR = env_path("LOCAL_AI_CODE_REPO_DIR", VAR_DIR / "repos")
CODE_INDEX_DIR = env_path("LOCAL_AI_CODE_INDEX_DIR", VAR_DIR / "code-index")
PATCH_DIR = env_path("LOCAL_AI_PATCH_DIR", VAR_DIR / "patches")
