import pytest

from rag.services.chunking_service import chunk_text, content_hash, count_tokens


def test_chunk_text_short_text_single_chunk():
    chunks = chunk_text("This is a short sentence.", chunk_size=400, overlap=50)
    assert len(chunks) == 1
    assert "short sentence" in chunks[0]


def test_chunk_text_empty_returns_empty_list():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_chunk_text_long_text_produces_overlapping_chunks():
    # ~1500 tokens of repeated text
    text = "The hospital protocol requires careful monitoring. " * 150
    chunks = chunk_text(text, chunk_size=200, overlap=40)
    assert len(chunks) > 1
    # consecutive chunks should share some vocabulary because of the overlap
    assert any(word in chunks[1] for word in chunks[0].split()[-5:])


def test_chunk_text_rejects_overlap_gte_chunk_size():
    with pytest.raises(ValueError):
        chunk_text("some text", chunk_size=100, overlap=100)


def test_content_hash_deterministic_and_distinct():
    a = content_hash("hello world")
    b = content_hash("hello world")
    c = content_hash("hello there")
    assert a == b
    assert a != c


def test_count_tokens_reasonable():
    assert count_tokens("hello world") > 0
    assert count_tokens("") == 0
