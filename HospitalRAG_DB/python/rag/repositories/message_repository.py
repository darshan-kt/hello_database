from rag.db.connection import get_connection


class MessageRepository:
    def create(self, conversation_id: int, role: str, content: str) -> int:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO messages (conversation_id, role, content)
                       VALUES (%s, %s, %s) RETURNING message_id""",
                    (conversation_id, role, content),
                )
                return cur.fetchone()["message_id"]

    def add_citations(self, message_id: int, citations: list[dict]) -> None:
        """citations: [{"chunk_id": int, "rank": int, "similarity_score": float}, ...]"""
        if not citations:
            return
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    """INSERT INTO message_citations (message_id, chunk_id, rank, similarity_score)
                       VALUES (%(message_id)s, %(chunk_id)s, %(rank)s, %(similarity_score)s)""",
                    [{**c, "message_id": message_id} for c in citations],
                )

    def list_by_conversation(self, conversation_id: int) -> list[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM messages WHERE conversation_id = %s ORDER BY created_at",
                    (conversation_id,),
                )
                messages = cur.fetchall()
                for message in messages:
                    cur.execute(
                        """SELECT mc.chunk_id, mc.rank, mc.similarity_score,
                                  c.content, c.document_id, d.title AS document_title
                           FROM message_citations mc
                           JOIN document_chunks c ON c.chunk_id = mc.chunk_id
                           JOIN hospital_documents d ON d.document_id = c.document_id
                           WHERE mc.message_id = %s
                           ORDER BY mc.rank""",
                        (message["message_id"],),
                    )
                    message["citations"] = cur.fetchall()
                return messages

    def list_recent_turns(self, conversation_id: int, limit_turns: int = 3) -> list[dict]:
        """Most recent N (user, assistant) turns, oldest first -- used to
        bound the context window injected into the prompt for follow-up
        questions (see chat_service.py)."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT * FROM messages WHERE conversation_id = %s
                       ORDER BY created_at DESC LIMIT %s""",
                    (conversation_id, limit_turns * 2),
                )
                rows = cur.fetchall()
                return list(reversed(rows))
