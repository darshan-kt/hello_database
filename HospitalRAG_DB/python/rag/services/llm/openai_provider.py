"""OpenAI LLM provider -- real token streaming, best answer quality.
Active when LLM_PROVIDER=openai and OPENAI_API_KEY is set."""
from typing import Iterator

from rag.exceptions import LLMGenerationError
from rag.services.llm.base import LLMProvider
from rag.services.llm.retry import with_retries


class OpenAILLMProvider(LLMProvider):
    def __init__(self, model_name: str = "gpt-4o-mini"):
        self.model_name = model_name
        self._client = None

    def _load(self):
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI()
        return self._client

    def _do_generate(self, messages: list[dict], max_tokens: int) -> dict:
        client = self._load()
        response = client.chat.completions.create(
            model=self.model_name, messages=messages, max_tokens=max_tokens
        )
        choice = response.choices[0]
        return {
            "content": (choice.message.content or "").strip(),
            "tokens_used": response.usage.total_tokens if response.usage else None,
            "model": self.model_name,
        }

    def generate(self, messages: list[dict], max_tokens: int = 300) -> dict:
        try:
            return with_retries(self._do_generate, messages, max_tokens, retries=2)
        except Exception as exc:
            raise LLMGenerationError(f"OpenAI generation failed: {exc}") from exc

    def stream(self, messages: list[dict], max_tokens: int = 300) -> Iterator[str]:
        client = self._load()
        try:
            response_stream = client.chat.completions.create(
                model=self.model_name, messages=messages, max_tokens=max_tokens, stream=True
            )
            for event in response_stream:
                delta = event.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as exc:
            raise LLMGenerationError(f"OpenAI streaming failed: {exc}") from exc
