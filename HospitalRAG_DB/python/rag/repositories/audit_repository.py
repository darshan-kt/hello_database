from typing import Optional

from rag.db.connection import get_connection


class AuditRepository:
    def record(self, user_id: Optional[int], action: str, detail: Optional[dict] = None) -> int:
        from psycopg.types.json import Jsonb

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO audit_logs (user_id, action, detail)
                       VALUES (%s, %s, %s) RETURNING audit_id""",
                    (user_id, action, Jsonb(detail or {})),
                )
                return cur.fetchone()["audit_id"]

    def list_recent(self, limit: int = 50) -> list[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT al.*, u.name AS user_name
                       FROM audit_logs al
                       LEFT JOIN users u ON u.user_id = al.user_id
                       ORDER BY al.created_at DESC
                       LIMIT %s""",
                    (limit,),
                )
                return cur.fetchall()
