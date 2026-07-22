from decimal import Decimal
from typing import Optional

from psycopg.errors import UniqueViolation

from ems.db.connection import get_connection
from ems.exceptions import EMSError


class SubmissionRepository:
    def submit(self, assignment_id: int, student_id: int) -> int:
        with get_connection() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        """INSERT INTO assignment_submissions (assignment_id, student_id)
                           VALUES (%s, %s) RETURNING submission_id""",
                        (assignment_id, student_id),
                    )
                    return cur.fetchone()["submission_id"]
                except UniqueViolation as exc:
                    raise EMSError(
                        f"Student {student_id} already submitted assignment {assignment_id}"
                    ) from exc

    def grade(self, submission_id: int, marks_obtained: Decimal) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE assignment_submissions SET marks_obtained = %s WHERE submission_id = %s",
                    (marks_obtained, submission_id),
                )

    def list_by_assignment(self, assignment_id: int) -> list[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT sub.*, st.name AS student_name
                       FROM assignment_submissions sub
                       JOIN students st ON st.student_id = sub.student_id
                       WHERE sub.assignment_id = %s
                       ORDER BY sub.submission_id""",
                    (assignment_id,),
                )
                return cur.fetchall()

    def list_by_student_for_course(self, student_id: int, course_id: int) -> list[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT sub.* FROM assignment_submissions sub
                       JOIN assignments a ON a.assignment_id = sub.assignment_id
                       WHERE sub.student_id = %s AND a.course_id = %s""",
                    (student_id, course_id),
                )
                return cur.fetchall()
