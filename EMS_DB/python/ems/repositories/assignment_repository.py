from typing import Optional

from psycopg.types.json import Jsonb

from ems.db.connection import get_connection


class AssignmentRepository:
    def create(self, course_id: int, title: str, settings: dict) -> int:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO assignments (course_id, title, settings)
                       VALUES (%s, %s, %s) RETURNING assignment_id""",
                    (course_id, title, Jsonb(settings)),
                )
                return cur.fetchone()["assignment_id"]

    def get_by_id(self, assignment_id: int) -> Optional[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM assignments WHERE assignment_id = %s", (assignment_id,)
                )
                return cur.fetchone()

    def list_by_course(self, course_id: int) -> list[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM assignments WHERE course_id = %s ORDER BY assignment_id",
                    (course_id,),
                )
                return cur.fetchall()

    def list_with_late_penalty(self) -> list[dict]:
        """JSONB key-existence query: `settings ? 'late_penalty'`."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT * FROM assignments WHERE settings ? 'late_penalty'
                       ORDER BY assignment_id"""
                )
                return cur.fetchall()

    def list_due_before(self, iso_date: str) -> list[dict]:
        """JSONB field extraction + cast: `(settings->>'submission_deadline')::date`."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT * FROM assignments
                       WHERE (settings->>'submission_deadline')::date < %s
                       ORDER BY (settings->>'submission_deadline')::date""",
                    (iso_date,),
                )
                return cur.fetchall()
