"""
Module 4 -- the chunking step of the document ingestion pipeline.

Token-based sliding window, not a naive character split: chunk
boundaries respect the tokenizer the embedding/LLM models actually see,
and a fixed overlap keeps a sentence that straddles a chunk boundary
retrievable from at least one of the two chunks it landed in.
"""
import hashlib

import tiktoken

DEFAULT_CHUNK_SIZE = 400
DEFAULT_CHUNK_OVERLAP = 50

_encoding = None


def _get_encoding():
    global _encoding
    if _encoding is None:
        _encoding = tiktoken.get_encoding("cl100k_base")
    return _encoding


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    encoding = _get_encoding()
    tokens = encoding.encode(text)
    if not tokens:
        return []

    chunks = []
    stride = chunk_size - overlap
    for start in range(0, len(tokens), stride):
        window = tokens[start : start + chunk_size]
        if not window:
            break
        piece = encoding.decode(window).strip()
        if piece:
            chunks.append(piece)
        if start + chunk_size >= len(tokens):
            break
    return chunks


def count_tokens(text: str) -> int:
    return len(_get_encoding().encode(text))


def content_hash(text: str) -> str:
    """Identical chunk content (e.g. re-uploading the same document)
    hashes the same; UNIQUE(document_id, content_hash) + ON CONFLICT DO
    NOTHING (see ChunkRepository.create) skips re-embedding it."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
