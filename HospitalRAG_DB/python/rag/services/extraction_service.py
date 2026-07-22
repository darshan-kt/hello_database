"""Module 4 -- text extraction + cleaning, one strategy per source type."""
import re

from rag.exceptions import EmptyDocumentError, UnsupportedDocumentTypeError

SUPPORTED_TYPES = {"pdf", "txt", "markdown"}


def extract_text(file_bytes: bytes, source_type: str) -> str:
    if source_type not in SUPPORTED_TYPES:
        raise UnsupportedDocumentTypeError(
            f"Unsupported document type '{source_type}'. Supported: {sorted(SUPPORTED_TYPES)}"
        )

    if source_type == "pdf":
        text = _extract_pdf(file_bytes)
    elif source_type == "markdown":
        text = _clean_markdown(file_bytes.decode("utf-8", errors="replace"))
    else:  # txt
        text = file_bytes.decode("utf-8", errors="replace")

    text = _clean_whitespace(text)
    if not text.strip():
        raise EmptyDocumentError(
            "No extractable text found -- likely a scanned/image-only PDF (OCR is out of "
            "scope for this project; see docs/01_requirements.md)."
        )
    return text


def _extract_pdf(file_bytes: bytes) -> str:
    from io import BytesIO

    from pypdf import PdfReader

    reader = PdfReader(BytesIO(file_bytes))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages)


def _clean_markdown(text: str) -> str:
    """Strip Markdown syntax that adds noise to an embedding without
    adding meaning -- headings/emphasis markers, link syntax (keeping
    the link text), code fences."""
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[*_`]{1,3}", "", text)
    return text


def _clean_whitespace(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
