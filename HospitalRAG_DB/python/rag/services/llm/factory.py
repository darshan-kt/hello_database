import os
from functools import lru_cache

from rag.services.llm.base import LLMProvider
from rag.services.llm.local_provider import LocalLLMProvider
from rag.services.llm.openai_provider import OpenAILLMProvider


@lru_cache
def get_llm_provider() -> LLMProvider:
    provider = os.getenv("LLM_PROVIDER", "local")
    if provider == "openai":
        return OpenAILLMProvider()
    model_name = os.getenv("LOCAL_LLM_MODEL", "Qwen/Qwen2.5-0.5B-Instruct")
    return LocalLLMProvider(model_name)
