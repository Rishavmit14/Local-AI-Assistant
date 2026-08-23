"""Compatibility wrapper for the pre-package ``rag`` import."""

from local_ai_assistant.rag.documents import *  # noqa: F403
from local_ai_assistant.rag.documents import main

if __name__ == "__main__":
    raise SystemExit(main())
