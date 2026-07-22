import hashlib

from rag.services.ingestion_service import IngestionService
from rag.services.retriever_service import RetrieverService


def _ingest(document_repo, title, filename, text, department_id=None):
    file_bytes = text.encode()
    document_id = document_repo.create(
        title, "txt", filename, file_hash=hashlib.sha256(file_bytes).hexdigest(),
        department_id=department_id,
    )
    IngestionService().ingest(document_id, file_bytes, "txt")
    return document_id


def test_retrieve_finds_relevant_document(document_repo, sample_department_id):
    _ingest(
        document_repo, "Dengue Protocol", "dengue.txt",
        "Dengue fever treatment requires oral rehydration and paracetamol for fever control. "
        "Avoid NSAIDs due to bleeding risk.",
        department_id=sample_department_id,
    )
    _ingest(
        document_repo, "Fire Safety", "fire.txt",
        "In case of fire, evacuate via the marked stairwell and assemble at the muster point.",
        department_id=sample_department_id,
    )

    results = RetrieverService().retrieve("What is the treatment for dengue fever?", top_k=5)

    assert len(results) >= 1
    assert results[0]["document_title"] == "Dengue Protocol"


def test_retrieve_filters_by_department(document_repo):
    dept_a = _dept_id_for("Cardiology", "CARD_TEST")
    dept_b = _dept_id_for("Pharmacy", "PHARM_TEST")

    _ingest(
        document_repo, "Cardiology Note", "cardio.txt",
        "Hypertension management requires ACE inhibitors and lifestyle changes.",
        department_id=dept_a,
    )
    _ingest(
        document_repo, "Pharmacy Note", "pharm.txt",
        "Hypertension medication dosing must be adjusted for renal impairment.",
        department_id=dept_b,
    )

    results = RetrieverService().retrieve(
        "How should hypertension be managed?", top_k=5, department_id=dept_a
    )

    assert all(r["department_id"] == dept_a for r in results)
    assert any(r["document_title"] == "Cardiology Note" for r in results)


def test_retrieve_unrelated_question_returns_nothing_above_threshold(document_repo, sample_department_id):
    _ingest(
        document_repo, "Dengue Protocol", "dengue.txt",
        "Dengue fever treatment requires oral rehydration and paracetamol for fever control.",
        department_id=sample_department_id,
    )

    results = RetrieverService().retrieve("What is the capital of France?", top_k=5)

    assert results == []


def _dept_id_for(name, code):
    from rag.repositories.department_repository import DepartmentRepository

    return DepartmentRepository().create(name, code)
