"""Compatibility wrapper for the pre-package ``local_llm`` import."""

from local_ai_assistant.llm.client import *  # noqa: F403
from local_ai_assistant.llm.client import main

if __name__ == "__main__":
    raise SystemExit(main())
