from datetime import date
from typing import Optional

from psycopg.errors import UniqueViolation

from ems.db.connection import get_connection
from ems.exceptions import DuplicateEmailError
from ems.models import Teacher


class TeacherRepository:
    def create(
        self, department_id: int, name: str, email: str, hire_date: Optional[date] = None
    ) -> int:
        with get_connection() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        """INSERT INTO teachers (department_id, name, email, hire_date)
                           VALUES (%s, %s, %s, COALESCE(%s, CURRENT_DATE))
                           RETURNING teacher_id""",
                        (department_id, name, email, hire_date),
                    )
                    return cur.fetchone()["teacher_id"]
                except UniqueViolation as exc:
                    raise DuplicateEmailError(f"Email already registered: {email}") from exc

    def get_by_id(self, teacher_id: int) -> Optional[Teacher]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM teachers WHERE teacher_id = %s", (teacher_id,))
                row = cur.fetchone()
                return Teacher(**row) if row else None

    def list_all(self) -> list[Teacher]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM teachers ORDER BY teacher_id")
                return [Teacher(**row) for row in cur.fetchall()]

    def list_by_department(self, department_id: int) -> list[Teacher]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM teachers WHERE department_id = %s ORDER BY teacher_id",
                    (department_id,),
                )
                return [Teacher(**row) for row in cur.fetchall()]

    def search(self, query: str) -> list[Teacher]:
        """Full-text search on teacher name (GIN index on to_tsvector(name))."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT * FROM teachers
                       WHERE to_tsvector('english', name) @@ plainto_tsquery('english', %s)
                       ORDER BY teacher_id""",
                    (query,),
                )
                return [Teacher(**row) for row in cur.fetchall()]
