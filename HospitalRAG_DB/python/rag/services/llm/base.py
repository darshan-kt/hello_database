from abc import ABC, abstractmethod
from typing import Iterator


class LLMProvider(ABC):
    model_name: str

    @abstractmethod
    def generate(self, messages: list[dict], max_tokens: int = 300) -> dict:
        """Returns {"content": str, "tokens_used": int | None, "model": str}."""

    @abstractmethod
    def stream(self, messages: list[dict], max_tokens: int = 300) -> Iterator[str]:
        """Yields the response incrementally as plain text chunks."""
