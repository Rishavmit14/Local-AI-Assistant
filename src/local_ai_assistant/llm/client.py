from collections.abc import Iterator

from openai import OpenAI

from local_ai_assistant.common.config import AppConfig, get_config
from local_ai_assistant.common.errors import LLMError
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
        )
        logger.info(
            "llm_client_initialized",
            extra={"event": "llm.client.initialized", "base_url": resolved_base_url},
        )

    def chat(
        self,
        prompt: str,
        system_prompt: str = (
            "You are a precise and technically accurate AI assistant."
        ),
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> str:
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
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
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
        logger.info(
            "llm_stream_started",
            extra={"event": "llm.stream.started", "model": self.model},
        )
        try:
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
        except Exception as exc:
            logger.exception("llm_stream_failed", extra={"event": "llm.stream.failed"})
            raise LLMError(f"Local model streaming request failed: {exc}") from exc

        for chunk in stream:
            if not chunk.choices:
                continue

            content = chunk.choices[0].delta.content

            if content:
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
