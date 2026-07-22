"""
Local LLM provider: a small instruction-tuned model run in-process via
transformers, on CPU, with no API key. This is the default so
`docker compose up` answers questions with zero setup, the same
"clone and run" promise as mini_EcommerceDB and EMS_DB -- the tradeoff
is answer quality and latency, both meaningfully worse than a frontier
hosted model. See docs/01_requirements.md and the README for the
OpenAI upgrade path.
"""
from typing import Iterator

from rag.exceptions import LLMGenerationError
from rag.services.llm.base import LLMProvider
from rag.services.llm.retry import with_retries


class LocalLLMProvider(LLMProvider):
    def __init__(self, model_name: str):
        self.model_name = model_name
        self._pipe = None

    def _load(self):
        if self._pipe is None:
            from transformers import pipeline

            self._pipe = pipeline(
                "text-generation", model=self.model_name, device_map="cpu"
            )
        return self._pipe

    def _do_generate(self, messages: list[dict], max_tokens: int) -> dict:
        pipe = self._load()
        output = pipe(messages, max_new_tokens=max_tokens, do_sample=False)
        generated = output[0]["generated_text"]
        # The pipeline returns the full conversation with the new
        # assistant turn appended as the last message.
        content = generated[-1]["content"] if isinstance(generated, list) else str(generated)
        return {"content": content.strip(), "tokens_used": None, "model": self.model_name}

    def generate(self, messages: list[dict], max_tokens: int = 300) -> dict:
        try:
            return with_retries(self._do_generate, messages, max_tokens, retries=1)
        except Exception as exc:
            raise LLMGenerationError(f"Local LLM generation failed: {exc}") from exc

    def stream(self, messages: list[dict], max_tokens: int = 300) -> Iterator[str]:
        """Simulated streaming: the small local pipeline generates the
        full response synchronously, then it's yielded word-by-word so
        the UI still gets an incremental typing effect. True
        token-level local streaming needs a TextIteratorStreamer
        running in a background thread -- a real next step, deliberately
        not built here to keep this provider's code readable; the
        OpenAI provider below does stream at the token level for real."""
        result = self.generate(messages, max_tokens=max_tokens)
        for word in result["content"].split(" "):
            yield word + " "
