from typing import Optional

from ems.db.connection import get_connection
from ems.models import Enrollment


class EnrollmentRepository:
    def get_by_id(self, enrollment_id: int) -> Optional[Enrollment]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM enrollments WHERE enrollment_id = %s", (enrollment_id,)
                )
                row = cur.fetchone()
                return Enrollment(**row) if row else None

    def list_by_student(self, student_id: int) -> list[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT e.*, c.code AS course_code, c.title AS course_title,
                              s.name AS semester_name
                       FROM enrollments e
                       JOIN courses c ON c.course_id = e.course_id
                       JOIN semesters s ON s.semester_id = e.semester_id
                       WHERE e.student_id = %s
                       ORDER BY e.enrolled_at DESC""",
                    (student_id,),
                )
                return cur.fetchall()

    def list_by_course(self, course_id: int, semester_id: Optional[int] = None) -> list[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                if semester_id:
                    cur.execute(
                        """SELECT e.*, st.name AS student_name
                           FROM enrollments e
                           JOIN students st ON st.student_id = e.student_id
                           WHERE e.course_id = %s AND e.semester_id = %s
                           ORDER BY e.enrollment_id""",
                        (course_id, semester_id),
                    )
                else:
                    cur.execute(
                        """SELECT e.*, st.name AS student_name
                           FROM enrollments e
                           JOIN students st ON st.student_id = e.student_id
                           WHERE e.course_id = %s
                           ORDER BY e.enrollment_id""",
                        (course_id,),
                    )
                return cur.fetchall()

    # -- used inside the enrollment transaction, sharing the caller's connection --

    def exists(self, conn, student_id: int, course_id: int, semester_id: int) -> bool:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT EXISTS (
                       SELECT 1 FROM enrollments
                       WHERE student_id = %s AND course_id = %s AND semester_id = %s
                   ) AS found""",
                (student_id, course_id, semester_id),
            )
            return cur.fetchone()["found"]

    def count_for_course_semester(self, conn, course_id: int, semester_id: int) -> int:
        """Safe to read without its own lock: the caller already holds a
        row lock on the parent course, serializing concurrent enrollment
        attempts for this course."""
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS n FROM enrollments WHERE course_id = %s AND semester_id = %s",
                (course_id, semester_id),
            )
            return cur.fetchone()["n"]

    def create(self, conn, student_id: int, course_id: int, semester_id: int) -> int:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO enrollments (student_id, course_id, semester_id)
                   VALUES (%s, %s, %s) RETURNING enrollment_id""",
                (student_id, course_id, semester_id),
            )
            return cur.fetchone()["enrollment_id"]
