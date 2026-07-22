from decimal import Decimal
from typing import Optional

from ems.db.connection import get_connection


class GradeRepository:
    def upsert(
        self, enrollment_id: int, total_percent: Decimal, letter_grade: str, gpa_points: Decimal
    ) -> int:
        """Recomputing a grade (e.g. after a late mark correction)
        overwrites the previous row rather than erroring on the
        UNIQUE(enrollment_id) constraint."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO grades (enrollment_id, total_percent, letter_grade, gpa_points)
                       VALUES (%s, %s, %s, %s)
                       ON CONFLICT (enrollment_id)
                       DO UPDATE SET total_percent = EXCLUDED.total_percent,
                                     letter_grade = EXCLUDED.letter_grade,
                                     gpa_points = EXCLUDED.gpa_points,
                                     computed_at = now()
                       RETURNING grade_id""",
                    (enrollment_id, total_percent, letter_grade, gpa_points),
                )
                return cur.fetchone()["grade_id"]

    def get_by_enrollment(self, enrollment_id: int) -> Optional[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM grades WHERE enrollment_id = %s", (enrollment_id,)
                )
                return cur.fetchone()
