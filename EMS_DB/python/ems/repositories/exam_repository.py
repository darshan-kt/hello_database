from datetime import date
from decimal import Decimal
from typing import Optional

from ems.db.connection import get_connection


class ExamRepository:
    def create(
        self, course_id: int, semester_id: int, name: str, exam_date: date, max_marks: Decimal
    ) -> int:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO exams (course_id, semester_id, name, exam_date, max_marks)
                       VALUES (%s, %s, %s, %s, %s) RETURNING exam_id""",
                    (course_id, semester_id, name, exam_date, max_marks),
                )
                return cur.fetchone()["exam_id"]

    def get_by_id(self, exam_id: int) -> Optional[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM exams WHERE exam_id = %s", (exam_id,))
                return cur.fetchone()

    def list_by_course(self, course_id: int) -> list[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM exams WHERE course_id = %s ORDER BY exam_date", (course_id,)
                )
                return cur.fetchall()
