import os

from openai import OpenAI
from typing import Optional


DEFAULT_BASE_URL = os.environ.get("LOCAL_AI_BASE_URL", "http://127.0.0.1:8080/v1")

DEFAULT_MODEL = os.environ.get(
    "LOCAL_AI_MODEL",
    "/AI/models/qwen3.6-q4/Qwen3.6-35B-A3B-UD-Q4_K_M.gguf",
)


class LocalLLM:
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
    ):
        self.model = model
        self.client = OpenAI(
            base_url=base_url,
            api_key="local",
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
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return response.choices[0].message.content or ""

    def stream_chat(
        self,
        prompt: str,
        system_prompt: str = (
            "You are a precise and technically accurate AI assistant."
        ),
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ):
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        for chunk in stream:
            if not chunk.choices:
                continue

            content = chunk.choices[0].delta.content

            if content:
                yield content


if __name__ == "__main__":
    llm = LocalLLM()

    print("Local Qwen is ready.\n")

    for token in llm.stream_chat(
        "Explain RAG to a software engineer in five concise bullet points."
    ):
        print(token, end="", flush=True)

    print()
