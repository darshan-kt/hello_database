"""
Module 4-5 -- the document ingestion pipeline. Orchestrates extraction,
chunking, embedding, and storage, and updates the document's status as
it goes (pending -> processing -> indexed/failed) so the UI can show
what's happening without polling chunk counts.
"""
from rag.exceptions import RAGError
from rag.repositories.chunk_repository import ChunkRepository
from rag.repositories.document_repository import DocumentRepository
from rag.services.chunking_service import chunk_text, content_hash, count_tokens
from rag.services.embedding_service import get_embedding_service
from rag.services.extraction_service import extract_text


class IngestionService:
    def __init__(self, document_repo=None, chunk_repo=None, embedding_service=None):
        self.document_repo = document_repo or DocumentRepository()
        self.chunk_repo = chunk_repo or ChunkRepository()
        self.embedding_service = embedding_service or get_embedding_service()

    def ingest(self, document_id: int, file_bytes: bytes, source_type: str) -> dict:
        self.document_repo.set_status(document_id, "processing")
        try:
            text = extract_text(file_bytes, source_type)
            pieces = chunk_text(text)
            if not pieces:
                raise RAGError("Chunking produced no chunks from the extracted text")

            embeddings = self.embedding_service.embed_batch(pieces)

            stored, skipped = 0, 0
            for index, (piece, embedding) in enumerate(zip(pieces, embeddings)):
                chunk_id = self.chunk_repo.create(
                    document_id=document_id,
                    chunk_index=index,
                    content=piece,
                    content_hash=content_hash(piece),
                    token_count=count_tokens(piece),
                    embedding=embedding,
                    embedding_model=self.embedding_service.model_name,
                )
                if chunk_id is None:
                    skipped += 1  # identical content already indexed for this document
                else:
                    stored += 1

            self.document_repo.set_status(document_id, "indexed")
            return {"chunks_stored": stored, "chunks_skipped_duplicate": skipped}
        except Exception as exc:
            self.document_repo.set_status(document_id, "failed", error_message=str(exc))
            raise
