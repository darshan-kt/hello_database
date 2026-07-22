from decimal import Decimal

from ems.db.connection import get_connection


class ExamResultRepository:
    def record(self, exam_id: int, student_id: int, marks_obtained: Decimal) -> int:
        """Upsert: re-recording a result (e.g. a re-grade) overwrites the
        prior mark rather than erroring on the UNIQUE(exam_id, student_id)
        constraint."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO exam_results (exam_id, student_id, marks_obtained)
                       VALUES (%s, %s, %s)
                       ON CONFLICT (exam_id, student_id)
                       DO UPDATE SET marks_obtained = EXCLUDED.marks_obtained
                       RETURNING result_id""",
                    (exam_id, student_id, marks_obtained),
                )
                return cur.fetchone()["result_id"]

    def list_by_exam(self, exam_id: int) -> list[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT er.*, st.name AS student_name
                       FROM exam_results er
                       JOIN students st ON st.student_id = er.student_id
                       WHERE er.exam_id = %s
                       ORDER BY er.result_id""",
                    (exam_id,),
                )
                return cur.fetchall()

    def list_by_student_for_course(self, student_id: int, course_id: int) -> list[dict]:
        """Includes each exam's max_marks so callers can normalize to a
        percentage without a second query (used by GradingService)."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT er.*, e.max_marks FROM exam_results er
                       JOIN exams e ON e.exam_id = er.exam_id
                       WHERE er.student_id = %s AND e.course_id = %s""",
                    (student_id, course_id),
                )
                return cur.fetchall()
