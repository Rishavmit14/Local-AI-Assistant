"""Compatibility wrapper for the pre-package ``local_llm`` import."""

from local_ai_assistant.llm.client import DEFAULT_BASE_URL, DEFAULT_MODEL, LocalLLM, main

__all__ = ["DEFAULT_BASE_URL", "DEFAULT_MODEL", "LocalLLM", "main"]

if __name__ == "__main__":
    raise SystemExit(main())
