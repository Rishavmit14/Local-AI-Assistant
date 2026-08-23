# Structured Logging

Entrypoints configure the `local_ai_assistant` logger from `LOCAL_AI_LOG_LEVEL` and `LOCAL_AI_LOG_FORMAT`. JSON is the default and includes UTC timestamp, level, logger, message, stable `event`, and event-specific metadata. `text` retains a compact operator-oriented format.

Events cover LLM lifecycle, document and repository index/retrieval lifecycle, OCR failures, subprocess/test execution, patch validation/application, UI startup, and Git transaction completion. Existing stdout progress remains during Stage 1 compatibility. Logs must remain generated state and are excluded from Git.

Do not add prompt bodies, retrieved chunks, uploaded document text, credentials, or model responses to logs.
