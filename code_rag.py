"""Compatibility wrapper for the pre-package ``code_rag`` command/import."""

from local_ai_assistant.code_index.repository import *  # noqa: F403
from local_ai_assistant.code_index.repository import main

if __name__ == "__main__":
    raise SystemExit(main())
