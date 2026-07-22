from datetime import date
from typing import Optional

from ems.db.connection import get_connection
from ems.models import Semester


class SemesterRepository:
    def create(self, name: str, start_date: date, end_date: date) -> int:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO semesters (name, start_date, end_date)
                       VALUES (%s, %s, %s) RETURNING semester_id""",
                    (name, start_date, end_date),
                )
                return cur.fetchone()["semester_id"]

    def get_by_id(self, semester_id: int) -> Optional[Semester]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM semesters WHERE semester_id = %s", (semester_id,))
                row = cur.fetchone()
                return Semester(**row) if row else None

    def list_all(self) -> list[Semester]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM semesters ORDER BY start_date")
                return [Semester(**row) for row in cur.fetchall()]

    def get_active(self) -> Optional[Semester]:
        """The semester whose date range contains today, if any."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM semesters WHERE CURRENT_DATE BETWEEN start_date AND end_date "
                    "ORDER BY start_date LIMIT 1"
                )
                row = cur.fetchone()
                return Semester(**row) if row else None
