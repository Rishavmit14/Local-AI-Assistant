"""Backward-compatible path constants.

New code should inject ``PathConfig``. These names preserve Stage 0 imports.
"""

from .config import get_config

_PATHS = get_config().paths
VAR_DIR = _PATHS.var_dir
DOCUMENT_DIR = _PATHS.document_dir
RAG_DATA_DIR = _PATHS.rag_data_dir
CODE_REPO_DIR = _PATHS.code_repo_dir
CODE_INDEX_DIR = _PATHS.code_index_dir
PATCH_DIR = _PATHS.patch_dir
