from typing import Optional

from rag.db.connection import get_connection


class ConversationRepository:
    def create(self, user_id: int, title: Optional[str] = None) -> int:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO conversations (user_id, title) VALUES (%s, %s) RETURNING conversation_id",
                    (user_id, title),
                )
                return cur.fetchone()["conversation_id"]

    def get_by_id(self, conversation_id: int) -> Optional[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM conversations WHERE conversation_id = %s", (conversation_id,)
                )
                return cur.fetchone()

    def list_by_user(self, user_id: int) -> list[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM conversations WHERE user_id = %s ORDER BY created_at DESC",
                    (user_id,),
                )
                return cur.fetchall()

    def set_title(self, conversation_id: int, title: str) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE conversations SET title = %s WHERE conversation_id = %s",
                    (title, conversation_id),
                )
