"""
Module 9 -- Conversation Memory, and the orchestration that ties
retrieval + prompt building + generation into one "ask a question"
operation.
"""
from typing import Optional

from rag.repositories.audit_repository import AuditRepository
from rag.repositories.conversation_repository import ConversationRepository
from rag.repositories.message_repository import MessageRepository
from rag.services.llm.factory import get_llm_provider
from rag.services.prompt_service import build_messages
from rag.services.retriever_service import RetrieverService

CONTEXT_WINDOW_TURNS = 3
TOP_K = 5

NO_CONTEXT_ANSWER = (
    "I don't have that information in the hospital's documents. Try "
    "rephrasing the question, or ask an administrator to upload a "
    "document that covers it."
)


class ChatService:
    def __init__(
        self,
        conversation_repo=None,
        message_repo=None,
        retriever=None,
        llm_provider=None,
        audit_repo=None,
    ):
        self.conversation_repo = conversation_repo or ConversationRepository()
        self.message_repo = message_repo or MessageRepository()
        self.retriever = retriever or RetrieverService()
        self.llm_provider = llm_provider or get_llm_provider()
        self.audit_repo = audit_repo or AuditRepository()

    def get_or_create_conversation(self, user_id: int, conversation_id: Optional[int]) -> int:
        if conversation_id is not None:
            return conversation_id
        return self.conversation_repo.create(user_id)

    def ask(
        self,
        user_id: int,
        question: str,
        conversation_id: Optional[int] = None,
        department_id: Optional[int] = None,
    ) -> dict:
        conversation_id = self.get_or_create_conversation(user_id, conversation_id)

        # Bounded context window: only the last few turns are injected,
        # not the whole history -- keeps prompt size (and local-model
        # latency) predictable as a conversation grows.
        recent_turns = self.message_repo.list_recent_turns(
            conversation_id, limit_turns=CONTEXT_WINDOW_TURNS
        )
        is_first_question = not recent_turns

        chunks = self.retriever.retrieve(question, top_k=TOP_K, department_id=department_id)

        self.message_repo.create(conversation_id, "user", question)

        if chunks:
            messages = build_messages(question, chunks, recent_turns=recent_turns)
            result = self.llm_provider.generate(messages)
        else:
            # Deterministic short-circuit: skip the LLM call entirely
            # when retrieval found nothing relevant, rather than trust
            # the system prompt's "say you don't know" instruction to
            # hold. It doesn't, reliably -- caught by actually asking
            # an out-of-scope question against the small local model,
            # which answered "Paris" to "what is the capital of
            # France?" instead of admitting it had no grounding for it.
            # A weak model's instruction-following isn't a safety
            # boundary; this is. See docs/01_requirements.md.
            result = {"content": NO_CONTEXT_ANSWER, "tokens_used": None, "model": "none (no context)"}

        assistant_message_id = self.message_repo.create(
            conversation_id, "assistant", result["content"]
        )
        citations = [
            {
                "chunk_id": c["chunk_id"],
                "rank": i + 1,
                "similarity_score": round(float(c["similarity"]), 5),
            }
            for i, c in enumerate(chunks)
        ]
        self.message_repo.add_citations(assistant_message_id, citations)

        self.audit_repo.record(
            user_id,
            "ask_question",
            {
                "conversation_id": conversation_id,
                "question": question,
                "chunks_retrieved": len(chunks),
                "llm_model": result["model"],
            },
        )

        if is_first_question:
            title = question[:80] + ("..." if len(question) > 80 else "")
            self.conversation_repo.set_title(conversation_id, title)

        return {
            "conversation_id": conversation_id,
            "message_id": assistant_message_id,
            "answer": result["content"],
            "citations": chunks,
            "model": result["model"],
        }
