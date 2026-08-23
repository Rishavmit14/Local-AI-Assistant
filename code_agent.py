"""Compatibility wrapper for the pre-package ``code_agent`` command/import."""

from local_ai_assistant.agent.code_agent import main

__all__ = ["main"]

if __name__ == "__main__":
    raise SystemExit(main())
