import re
from collections.abc import Callable, Iterator, Mapping
from dataclasses import replace
from pathlib import PurePosixPath

import httpx
from openai import OpenAI

from local_ai_assistant.common.config import AppConfig, get_config
from local_ai_assistant.common.errors import ConfigurationError, LLMError
from local_ai_assistant.common.logging import configure_logging, get_logger

_DEFAULTS = get_config().llama
DEFAULT_BASE_URL = _DEFAULTS.base_url
DEFAULT_MODEL = _DEFAULTS.model
logger = get_logger(__name__)


def safe_model_display_id(model: str) -> str:
    """Return a bounded basename suitable for operational logs and reports."""
    basename = PurePosixPath(model.replace("\\", "/")).name
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", basename).strip("._-")
    return (cleaned or "configured-local-model")[:96]


class LocalLLM:
    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        *,
        config: AppConfig | None = None,
    ) -> None:
        source_config = config or get_config()
        resolved_base_url = source_config.llama.base_url if base_url is None else base_url
        resolved_model = source_config.llama.model if model is None else model
        self.config = replace(
            source_config,
            llama=replace(
                source_config.llama,
                base_url=resolved_base_url,
                model=resolved_model,
            ),
        )
        self.model = self.config.llama.model
        self.model_display_id = safe_model_display_id(self.model)
        self._http_client = httpx.Client(
            timeout=self.config.llama.timeout_seconds,
            trust_env=False,
        )
        self.client = OpenAI(
            base_url=self.config.llama.base_url,
            api_key=self.config.llama.api_key,
            timeout=self.config.llama.timeout_seconds,
            max_retries=0,
            http_client=self._http_client,
        )
        self._latency_observer: Callable[[str, Mapping[str, int | float]], None] | None = None
        self.last_response_metadata: dict[str, object] = {}
        logger.info(
            "llm_client_initialized",
            extra={"event": "llm.client.initialized", "base_url": self.config.llama.base_url},
        )

    def set_latency_observer(
        self,
        observer: Callable[[str, Mapping[str, int | float]], None] | None,
    ) -> None:
        """Install a content-free observer for the current local model boundary."""
        self._latency_observer = observer

    def _observe(self, stage: str, **details: int | float) -> None:
        if self._latency_observer is not None:
            self._latency_observer(stage, details)

    def chat(
        self,
        prompt: str,
        system_prompt: str = (
            "You are a precise and technically accurate AI assistant."
        ),
        temperature: float = 0.2,
        max_tokens: int = 1024,
        response_format: Mapping[str, object] | None = None,
    ) -> str:
        if max_tokens < 1 or max_tokens > self.config.llama.context_size:
            raise ConfigurationError(
                f"max_tokens must be between 1 and configured context size "
                f"{self.config.llama.context_size}, got {max_tokens}"
            )
        logger.info(
            "llm_chat_started",
            extra={
                "event": "llm.chat.started",
                "model": self.model_display_id,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "prompt_characters": len(prompt),
            },
        )
        self.last_response_metadata = {"finish_reason": None, "response_format": dict(response_format) if response_format is not None else None, "max_tokens": max_tokens}
        try:
            self._observe("LOCAL_LLM_REQUEST_DISPATCHED")
            request: dict[str, object] = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if response_format is not None:
                request["response_format"] = dict(response_format)
            response = self.client.chat.completions.create(**request)
            self._observe("LOCAL_LLM_REQUEST_ACCEPTED")
            content = self._chat_content(response)
            choices = getattr(response, "choices", None) or []
            choice = choices[0] if choices else None
            self.last_response_metadata = {
                "finish_reason": getattr(choice, "finish_reason", None),
                "response_id": getattr(response, "id", None),
                "response_format": dict(response_format) if response_format is not None else None,
                "max_tokens": max_tokens,
            }
        except Exception as exc:
            logger.warning(
                "llm_chat_failed",
                extra={"event": "llm.chat.failed", "failure_type": type(exc).__name__},
            )
            if isinstance(exc, LLMError):
                raise
            raise LLMError(f"Local model request failed: {self._safe_error(exc)}") from exc
        logger.info(
            "llm_chat_completed",
            extra={"event": "llm.chat.completed", "response_characters": len(content),
                   "finish_reason": self.last_response_metadata.get("finish_reason"),
                   "response_format_type": (response_format or {}).get("type")},
        )
        return content

    @staticmethod
    def _chat_content(response: object) -> str:
        choices = getattr(response, "choices", None)
        if not choices:
            raise LLMError("Local model returned no chat choices")
        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", None)
        if not isinstance(content, str) or not content.strip():
            raise LLMError("Local model returned no text chat content")
        return content

    def _safe_error(self, error: Exception) -> str:
        message = str(error).replace(self.config.llama.api_key, "[redacted]")
        if self.model and self.model != self.model_display_id:
            message = message.replace(self.model, self.model_display_id)
        return message[:400] or type(error).__name__

    def stream_chat(
        self,
        prompt: str,
        system_prompt: str = (
            "You are a precise and technically accurate AI assistant."
        ),
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> Iterator[str]:
        if max_tokens < 1 or max_tokens > self.config.llama.context_size:
            raise ConfigurationError(
                f"max_tokens must be between 1 and configured context size "
                f"{self.config.llama.context_size}, got {max_tokens}"
            )
        logger.info(
            "llm_stream_started",
            extra={"event": "llm.stream.started", "model": self.model_display_id},
        )
        try:
            self._observe("LOCAL_LLM_REQUEST_DISPATCHED")
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            self._observe("LOCAL_LLM_REQUEST_ACCEPTED")
        except Exception as exc:
            logger.warning(
                "llm_stream_failed",
                extra={"event": "llm.stream.failed", "failure_type": type(exc).__name__},
            )
            raise LLMError(
                f"Local model streaming request failed: {self._safe_error(exc)}"
            ) from exc

        first_token = True
        try:
            for chunk in stream:
                usage = getattr(chunk, "usage", None)
                if usage is not None:
                    prompt_details = getattr(usage, "prompt_tokens_details", None)
                    cached_tokens = getattr(prompt_details, "cached_tokens", 0) if prompt_details else 0
                    self._observe(
                        "LOCAL_LLM_USAGE",
                        prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
                        cached_tokens=int(cached_tokens or 0),
                        completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
                    )
                choices = getattr(chunk, "choices", None)
                if not choices:
                    continue
                delta = getattr(choices[0], "delta", None)
                content = getattr(delta, "content", None)
                if content is None:
                    continue
                if not isinstance(content, str):
                    raise LLMError("Local model returned invalid streamed text content")
                if content:
                    if first_token:
                        first_token = False
                        self._observe("LOCAL_LLM_FIRST_TOKEN")
                    yield content
        except Exception as exc:
            logger.warning(
                "llm_stream_failed",
                extra={"event": "llm.stream.failed", "failure_type": type(exc).__name__},
            )
            if isinstance(exc, LLMError):
                raise
            raise LLMError(
                f"Local model streaming request failed: {self._safe_error(exc)}"
            ) from exc
        finally:
            close = getattr(stream, "close", None)
            if callable(close):
                close()
        if first_token:
            raise LLMError("Local model stream ended without text content")
        logger.info("llm_stream_completed", extra={"event": "llm.stream.completed"})


def main() -> int:
    config = get_config()
    configure_logging(config.runtime)
    llm = LocalLLM(config=config)

    print("Friday's configured local model is ready.\n")

    for token in llm.stream_chat(
        "Explain RAG to a software engineer in five concise bullet points."
    ):
        print(token, end="", flush=True)

    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
