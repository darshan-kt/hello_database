import hashlib

from rag.services.evaluation_service import EvalCase, EvaluationService
from rag.services.ingestion_service import IngestionService


def test_evaluation_perfect_recall_when_document_is_relevant(document_repo, sample_department_id):
    file_bytes = (
        b"Dengue fever treatment protocol: give oral rehydration and paracetamol. "
        b"Avoid NSAIDs due to bleeding risk in dengue patients."
    )
    document_id = document_repo.create(
        "Dengue Fever Treatment Protocol", "txt", "dengue.txt",
        file_hash=hashlib.sha256(file_bytes).hexdigest(), department_id=sample_department_id,
    )
    IngestionService().ingest(document_id, file_bytes, "txt")

    case = EvalCase(
        question="What is the treatment protocol for dengue fever?",
        expected_document_titles=["Dengue Fever Treatment Protocol"],
    )
    result = EvaluationService().evaluate_case(case)

    assert result.semantic_recall == 1.0
    assert "Dengue Fever Treatment Protocol" in result.retrieved_titles


def test_evaluation_zero_recall_when_nothing_ingested():
    case = EvalCase(question="Anything at all?", expected_document_titles=["Nonexistent Document"])
    result = EvaluationService().evaluate_case(case)

    assert result.semantic_recall == 0.0
    assert result.lexical_recall == 0.0


def test_evaluate_batch_averages(document_repo, sample_department_id):
    file_bytes = b"Hand hygiene requires alcohol handrub for 20-30 seconds before patient contact."
    document_id = document_repo.create(
        "Hand Hygiene SOP", "txt", "hh.txt",
        file_hash=hashlib.sha256(file_bytes).hexdigest(), department_id=sample_department_id,
    )
    IngestionService().ingest(document_id, file_bytes, "txt")

    cases = [
        EvalCase(question="What is hand hygiene technique?", expected_document_titles=["Hand Hygiene SOP"]),
        EvalCase(question="Unrelated question with no match", expected_document_titles=["Nothing"]),
    ]
    report = EvaluationService().evaluate(cases)

    assert 0.0 <= report["avg_semantic_recall"] <= 1.0
    assert len(report["cases"]) == 2
