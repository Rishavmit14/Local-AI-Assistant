"""Compatibility wrapper for the pre-package ``rag`` import."""

from local_ai_assistant.rag.documents import DOCUMENT_DIR, LocalRAG, main

__all__ = ["DOCUMENT_DIR", "LocalRAG", "main"]

if __name__ == "__main__":
    raise SystemExit(main())
