from collections.abc import Callable, Iterator, Mapping

from openai import OpenAI

from local_ai_assistant.common.config import AppConfig, get_config
from local_ai_assistant.common.errors import ConfigurationError, LLMError
from local_ai_assistant.common.logging import configure_logging, get_logger

_DEFAULTS = get_config().llama
DEFAULT_BASE_URL = _DEFAULTS.base_url
DEFAULT_MODEL = _DEFAULTS.model
logger = get_logger(__name__)


class LocalLLM:
    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        *,
        config: AppConfig | None = None,
    ) -> None:
        self.config = config or get_config()
        self.model = model or self.config.llama.model
        resolved_base_url = base_url or self.config.llama.base_url
        self.client = OpenAI(
            base_url=resolved_base_url,
            api_key=self.config.llama.api_key,
            timeout=self.config.llama.timeout_seconds,
        )
        self._latency_observer: Callable[[str, Mapping[str, int | float]], None] | None = None
        logger.info(
            "llm_client_initialized",
            extra={"event": "llm.client.initialized", "base_url": resolved_base_url},
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
                "model": self.model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "prompt_characters": len(prompt),
            },
        )
        try:
            self._observe("QWEN_REQUEST_DISPATCHED")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            self._observe("QWEN_REQUEST_ACCEPTED")
        except Exception as exc:
            logger.exception("llm_chat_failed", extra={"event": "llm.chat.failed"})
            raise LLMError(f"Local model request failed: {exc}") from exc

        content = response.choices[0].message.content or ""
        logger.info(
            "llm_chat_completed",
            extra={"event": "llm.chat.completed", "response_characters": len(content)},
        )
        return content

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
            extra={"event": "llm.stream.started", "model": self.model},
        )
        try:
            self._observe("QWEN_REQUEST_DISPATCHED")
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                stream_options={"include_usage": True},
            )
            self._observe("QWEN_REQUEST_ACCEPTED")
        except Exception as exc:
            logger.exception("llm_stream_failed", extra={"event": "llm.stream.failed"})
            raise LLMError(f"Local model streaming request failed: {exc}") from exc

        first_token = True
        for chunk in stream:
            usage = getattr(chunk, "usage", None)
            if usage is not None:
                prompt_details = getattr(usage, "prompt_tokens_details", None)
                cached_tokens = getattr(prompt_details, "cached_tokens", 0) if prompt_details else 0
                self._observe(
                    "QWEN_USAGE",
                    prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
                    cached_tokens=int(cached_tokens or 0),
                    completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
                )
            if not chunk.choices:
                continue

            content = chunk.choices[0].delta.content

            if content:
                if first_token:
                    first_token = False
                    self._observe("QWEN_FIRST_TOKEN")
                yield content
        logger.info("llm_stream_completed", extra={"event": "llm.stream.completed"})


def main() -> int:
    config = get_config()
    configure_logging(config.runtime)
    llm = LocalLLM(config=config)

    print("Local Qwen is ready.\n")

    for token in llm.stream_chat(
        "Explain RAG to a software engineer in five concise bullet points."
    ):
        print(token, end="", flush=True)

    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
