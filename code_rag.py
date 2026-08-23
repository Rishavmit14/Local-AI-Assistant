"""Compatibility wrapper for the pre-package ``code_rag`` command/import."""

from local_ai_assistant.code_index.repository import CodeRAG, main

__all__ = ["CodeRAG", "main"]

if __name__ == "__main__":
    raise SystemExit(main())
