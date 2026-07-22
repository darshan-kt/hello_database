"""Module 7 -- Prompt Builder. Builds a grounded, citation-aware,
hallucination-resistant prompt from retrieved chunks + recent
conversation turns."""
from typing import Optional

SYSTEM_PROMPT = (
    "You are a hospital knowledge assistant. Answer ONLY using the "
    "provided context from hospital documents below.\n"
    "- If the context does not contain the answer, say clearly that you "
    "don't have that information in the hospital's documents. Do not "
    "guess or use outside knowledge.\n"
    "- Cite which document each fact comes from using the bracketed "
    "numbers, e.g. [1].\n"
    "- Be concise and clinical in tone."
)


def build_messages(
    question: str,
    context_chunks: list[dict],
    recent_turns: Optional[list[dict]] = None,
) -> list[dict]:
    """Returns a list of {role, content} messages ready for an LLM
    chat-completion call -- the same shape works for both the local and
    OpenAI providers (see services/llm/)."""
    if context_chunks:
        context_block = "\n\n".join(
            f"[{i + 1}] (Source: {c['document_title']})\n{c['content']}"
            for i, c in enumerate(context_chunks)
        )
    else:
        context_block = "(no relevant documents were found)"

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for turn in recent_turns or []:
        messages.append({"role": turn["role"], "content": turn["content"]})

    messages.append(
        {"role": "user", "content": f"Context:\n{context_block}\n\nQuestion: {question}"}
    )
    return messages
