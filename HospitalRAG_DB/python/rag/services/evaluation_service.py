"""
Module 10 -- Evaluation. Measures *retrieval* quality (precision/recall
against a labeled question set) rather than answer quality -- grading
generated answers well needs an LLM-as-judge pass, a real technique but
one that costs another model call per evaluation run; out of scope
here, see docs/01_requirements.md.

Also compares semantic (vector) retrieval against plain keyword search
on the same chunk store, which is the fastest way to see *why* semantic
search earns its complexity: a question that shares no vocabulary with
the source text still retrieves it semantically, and won't lexically.
"""
from dataclasses import dataclass

from rag.repositories.chunk_repository import ChunkRepository
from rag.services.embedding_service import get_embedding_service


@dataclass
class EvalCase:
    question: str
    expected_document_titles: list[str]


@dataclass
class EvalResult:
    question: str
    semantic_recall: float
    semantic_precision: float
    lexical_recall: float
    retrieved_titles: list[str]


class EvaluationService:
    def __init__(self, chunk_repo=None, embedding_service=None, top_k: int = 5):
        self.chunk_repo = chunk_repo or ChunkRepository()
        self.embedding_service = embedding_service or get_embedding_service()
        self.top_k = top_k

    def evaluate_case(self, case: EvalCase) -> EvalResult:
        query_embedding = self.embedding_service.embed_one(case.question)
        semantic_results = self.chunk_repo.similarity_search(query_embedding, top_k=self.top_k)
        lexical_results = self.chunk_repo.lexical_search(case.question, top_k=self.top_k)

        semantic_titles = {r["document_title"] for r in semantic_results}
        lexical_titles = {r["document_title"] for r in lexical_results}
        expected = set(case.expected_document_titles)

        semantic_recall = len(semantic_titles & expected) / len(expected) if expected else 0.0
        semantic_precision = (
            sum(1 for r in semantic_results if r["document_title"] in expected)
            / len(semantic_results)
            if semantic_results
            else 0.0
        )
        lexical_recall = len(lexical_titles & expected) / len(expected) if expected else 0.0

        return EvalResult(
            question=case.question,
            semantic_recall=round(semantic_recall, 3),
            semantic_precision=round(semantic_precision, 3),
            lexical_recall=round(lexical_recall, 3),
            retrieved_titles=sorted(semantic_titles),
        )

    def evaluate(self, cases: list[EvalCase]) -> dict:
        results = [self.evaluate_case(c) for c in cases]
        n = len(results) or 1
        return {
            "cases": [r.__dict__ for r in results],
            "avg_semantic_recall": round(sum(r.semantic_recall for r in results) / n, 3),
            "avg_semantic_precision": round(sum(r.semantic_precision for r in results) / n, 3),
            "avg_lexical_recall": round(sum(r.lexical_recall for r in results) / n, 3),
        }
