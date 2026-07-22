"""
Module 5 -- Embedding Pipeline.

Pluggable: EMBEDDING_PROVIDER=local (default, sentence-transformers, no
API key) or EMBEDDING_PROVIDER=openai (needs OPENAI_API_KEY). Both are
pinned to 384 dimensions -- see docs/02_er_diagram.md ("The vector
column: a schema-time commitment") for why that's not just an
implementation detail. OpenAI's v3 embedding models support truncating
their native (larger) output to a smaller dimension via the
`dimensions` parameter -- a consequence of how they're trained
(Matryoshka representation learning, where a prefix of the full vector
is already a valid, if coarser, embedding). That's what makes it
possible to keep one fixed schema regardless of provider, instead of
needing a full re-embed just to try the other one.
"""
import os
from functools import lru_cache

EMBEDDING_DIM = 384


class LocalEmbeddingProvider:
    def __init__(self, model_name: str):
        self.model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        model = self._load()
        vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [v.tolist() for v in vectors]

    def embed_one(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]


class OpenAIEmbeddingProvider:
    def __init__(self, model_name: str = "text-embedding-3-small"):
        self.model_name = model_name
        self._client = None

    def _load(self):
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI()
        return self._client

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        client = self._load()
        response = client.embeddings.create(
            model=self.model_name, input=texts, dimensions=EMBEDDING_DIM
        )
        return [item.embedding for item in response.data]

    def embed_one(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]


@lru_cache
def get_embedding_service():
    provider = os.getenv("EMBEDDING_PROVIDER", "local")
    if provider == "openai":
        return OpenAIEmbeddingProvider()
    model_name = os.getenv("LOCAL_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    return LocalEmbeddingProvider(model_name)
