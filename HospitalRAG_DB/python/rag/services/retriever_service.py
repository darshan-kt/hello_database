"""Module 6 -- Retriever. Embeds a question, runs a pgvector similarity
search, optionally scoped to a department, and drops anything below a
similarity floor -- this is what lets the assistant say "I don't know"
instead of confidently citing the least-bad match to an unrelated
question."""
from typing import Optional

from rag.repositories.chunk_repository import ChunkRepository
from rag.services.embedding_service import get_embedding_service

MIN_SIMILARITY = 0.2


class RetrieverService:
    def __init__(self, chunk_repo=None, embedding_service=None):
        self.chunk_repo = chunk_repo or ChunkRepository()
        self.embedding_service = embedding_service or get_embedding_service()

    def retrieve(
        self,
        question: str,
        top_k: int = 5,
        department_id: Optional[int] = None,
        min_similarity: float = MIN_SIMILARITY,
    ) -> list[dict]:
        query_embedding = self.embedding_service.embed_one(question)
        results = self.chunk_repo.similarity_search(
            query_embedding, top_k=top_k, department_id=department_id
        )
        return [r for r in results if r["similarity"] >= min_similarity]
