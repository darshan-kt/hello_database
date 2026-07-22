import hashlib

from rag.repositories.audit_repository import AuditRepository
from rag.repositories.conversation_repository import ConversationRepository
from rag.repositories.message_repository import MessageRepository
from rag.services.chat_service import NO_CONTEXT_ANSWER, ChatService
from rag.services.ingestion_service import IngestionService
from rag.services.retriever_service import RetrieverService


def _make_chat_service(fake_llm):
    return ChatService(
        conversation_repo=ConversationRepository(),
        message_repo=MessageRepository(),
        retriever=RetrieverService(),
        llm_provider=fake_llm,
        audit_repo=AuditRepository(),
    )


def _ingest(document_repo, department_id, text="Dengue treatment needs oral rehydration and paracetamol."):
    file_bytes = text.encode()
    document_id = document_repo.create(
        "Dengue Protocol", "txt", "dengue.txt",
        file_hash=hashlib.sha256(file_bytes).hexdigest(), department_id=department_id,
    )
    IngestionService().ingest(document_id, file_bytes, "txt")


def test_ask_with_context_calls_llm_and_stores_citations(
    document_repo, sample_staff_id, sample_department_id, fake_llm, message_repo
):
    _ingest(document_repo, sample_department_id)
    chat_service = _make_chat_service(fake_llm)

    result = chat_service.ask(sample_staff_id, "What is the dengue treatment?")

    assert result["answer"] == fake_llm.response
    assert len(fake_llm.calls) == 1
    assert len(result["citations"]) >= 1

    stored = message_repo.list_by_conversation(result["conversation_id"])
    assert stored[-1]["citations"], "assistant message should have stored citations"


def test_ask_without_context_skips_llm_entirely(sample_staff_id, fake_llm):
    """No documents ingested at all -- retrieval finds nothing, so the
    LLM should never be called (see chat_service.py's short-circuit)."""
    chat_service = _make_chat_service(fake_llm)

    result = chat_service.ask(sample_staff_id, "What is the capital of France?")

    assert result["answer"] == NO_CONTEXT_ANSWER
    assert fake_llm.calls == []
    assert result["citations"] == []


def test_follow_up_question_reuses_conversation_and_injects_history(
    document_repo, sample_staff_id, sample_department_id, fake_llm
):
    _ingest(document_repo, sample_department_id)
    chat_service = _make_chat_service(fake_llm)

    first = chat_service.ask(sample_staff_id, "What is the dengue treatment?")
    # Deliberately still says "dengue" -- a pronoun-only follow-up like
    # "what about severe cases?" is retrieved using *only its own text*
    # (see chat_service.py's docstring / docs/01_requirements.md): with
    # nothing to anchor it, retrieval can come back empty even though a
    # human reading the transcript would understand the reference. Real
    # query rewriting/condensation would fix that; it's a documented
    # next step, not built here. This test exercises what *is* built:
    # the conversation history reaching the prompt once retrieval does
    # succeed.
    second = chat_service.ask(
        sample_staff_id, "What about severe dengue cases?", conversation_id=first["conversation_id"]
    )

    assert second["conversation_id"] == first["conversation_id"]
    assert len(fake_llm.calls) == 2
    second_prompt_contents = [m["content"] for m in fake_llm.calls[1]]
    assert any("dengue treatment" in c for c in second_prompt_contents)
