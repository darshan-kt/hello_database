import hashlib

import pytest

from rag.exceptions import DuplicateDocumentError, EmptyDocumentError, UnsupportedDocumentTypeError
from rag.services.extraction_service import extract_text
from rag.services.ingestion_service import IngestionService


def test_extract_txt():
    text = extract_text(b"Hello, this is a plain text document.", "txt")
    assert "plain text" in text


def test_extract_markdown_strips_syntax():
    text = extract_text(b"# Heading\n\nSome **bold** and [a link](http://x.com) text.", "markdown")
    assert "#" not in text
    assert "**" not in text
    assert "a link" in text
    assert "http://x.com" not in text


def test_extract_unsupported_type_raises():
    with pytest.raises(UnsupportedDocumentTypeError):
        extract_text(b"data", "docx")


def test_extract_empty_content_raises():
    with pytest.raises(EmptyDocumentError):
        extract_text(b"   \n\n  ", "txt")


def test_ingest_txt_document_creates_chunks(document_repo, chunk_repo, sample_department_id):
    file_bytes = ("Chest pain protocol: obtain an ECG within 10 minutes of arrival. " * 20).encode()
    document_id = document_repo.create(
        "Chest Pain Protocol", "txt", "chest_pain.txt",
        file_hash=hashlib.sha256(file_bytes).hexdigest(),
        department_id=sample_department_id,
    )
    result = IngestionService().ingest(document_id, file_bytes, "txt")

    assert result["chunks_stored"] > 0
    chunks = chunk_repo.list_by_document(document_id)
    assert len(chunks) == result["chunks_stored"]
    assert all(c["embedding_model"] for c in chunks)


def test_ingest_failure_marks_document_failed(document_repo):
    file_bytes = b"   "  # extraction will find no text
    document_id = document_repo.create(
        "Empty Doc", "txt", "empty.txt", file_hash=hashlib.sha256(file_bytes).hexdigest()
    )
    with pytest.raises(EmptyDocumentError):
        IngestionService().ingest(document_id, file_bytes, "txt")

    document = document_repo.get_by_id(document_id)
    assert document.status == "failed"
    assert document.error_message


def test_duplicate_file_upload_rejected(document_repo):
    file_bytes = b"Identical file content"
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    document_repo.create("First Upload", "txt", "a.txt", file_hash=file_hash)

    with pytest.raises(DuplicateDocumentError):
        document_repo.create("Second Upload", "txt", "b.txt", file_hash=file_hash)


def test_chunk_level_dedup_within_same_document(chunk_repo, document_repo, sample_department_id):
    file_bytes = b"x"
    document_id = document_repo.create(
        "Doc", "txt", "doc.txt", file_hash=hashlib.sha256(file_bytes).hexdigest()
    )
    embedding = [0.1] * 384

    first_id = chunk_repo.create(document_id, 0, "same content", "hash-a", 3, embedding, "test-model")
    second_id = chunk_repo.create(document_id, 1, "same content", "hash-a", 3, embedding, "test-model")

    assert first_id is not None
    assert second_id is None  # ON CONFLICT DO NOTHING -- no duplicate row
    assert len(chunk_repo.list_by_document(document_id)) == 1
