from typing import Optional

from ems.db.connection import get_connection
from ems.exceptions import NotFoundError
from ems.models import Course

# Explicit column list, excluding the generated `search_vector` column --
# `Course` has no field for it, and `SELECT *` would break every read
# with "unexpected keyword argument 'search_vector'".
COLUMNS = "course_id, department_id, teacher_id, code, title, description, credits, capacity, created_at"


class CourseRepository:
    def create(
        self,
        department_id: int,
        teacher_id: int,
        code: str,
        title: str,
        credits: int,
        capacity: int,
        description: Optional[str] = None,
    ) -> int:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO courses (department_id, teacher_id, code, title, credits, capacity, description)
                       VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING course_id""",
                    (department_id, teacher_id, code, title, credits, capacity, description),
                )
                return cur.fetchone()["course_id"]

    def get_by_id(self, course_id: int) -> Optional[Course]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT {COLUMNS} FROM courses WHERE course_id = %s", (course_id,))
                row = cur.fetchone()
                return Course(**row) if row else None

    def list_all(self) -> list[Course]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT {COLUMNS} FROM courses ORDER BY course_id")
                return [Course(**row) for row in cur.fetchall()]

    def list_by_department(self, department_id: int) -> list[Course]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {COLUMNS} FROM courses WHERE department_id = %s ORDER BY course_id",
                    (department_id,),
                )
                return [Course(**row) for row in cur.fetchall()]

    def search(self, query: str) -> list[Course]:
        """Full-text search over title+description via the generated search_vector column."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""SELECT {COLUMNS} FROM courses
                        WHERE search_vector @@ plainto_tsquery('english', %s)
                        ORDER BY course_id""",
                    (query,),
                )
                return [Course(**row) for row in cur.fetchall()]

    def add_prerequisite(self, course_id: int, prerequisite_course_id: int) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO course_prerequisites (course_id, prerequisite_course_id)
                       VALUES (%s, %s) ON CONFLICT DO NOTHING""",
                    (course_id, prerequisite_course_id),
                )

    def list_direct_prerequisites(self, course_id: int) -> list[Course]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""SELECT {', '.join('c.' + c for c in COLUMNS.split(', '))}
                        FROM course_prerequisites cp
                        JOIN courses c ON c.course_id = cp.prerequisite_course_id
                        WHERE cp.course_id = %s""",
                    (course_id,),
                )
                return [Course(**row) for row in cur.fetchall()]

    # -- used inside the enrollment transaction, sharing the caller's connection --

    def lock_for_update(self, conn, course_id: int) -> Course:
        """Row-lock a course within an existing transaction so two
        concurrent enrollments can't both slip past the capacity check."""
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT {COLUMNS} FROM courses WHERE course_id = %s FOR UPDATE", (course_id,)
            )
            row = cur.fetchone()
        if row is None:
            raise NotFoundError("Course", course_id)
        return Course(**row)
