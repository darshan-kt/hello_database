class RAGError(Exception):
    """Base class for all domain errors."""


class DuplicateEmailError(RAGError):
    pass


class NotFoundError(RAGError):
    def __init__(self, entity: str, identifier):
        self.entity = entity
        self.identifier = identifier
        super().__init__(f"{entity} {identifier} not found")


class UnsupportedDocumentTypeError(RAGError):
    pass


class DuplicateDocumentError(RAGError):
    """Raised when a byte-identical file has already been uploaded --
    see hospital_documents.file_hash in sql/01_schema.sql."""


class EmptyDocumentError(RAGError):
    """Extraction produced no usable text (e.g. a scanned/image-only PDF)."""


class LLMGenerationError(RAGError):
    """The configured LLM provider failed after retries."""
