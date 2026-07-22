from datetime import date
from typing import Optional

from psycopg.errors import UniqueViolation

from ems.db.connection import get_connection
from ems.exceptions import DuplicateEmailError
from ems.models import Student


class StudentRepository:
    def create(
        self,
        department_id: int,
        name: str,
        email: str,
        password_hash: str,
        date_of_birth: Optional[date] = None,
    ) -> int:
        with get_connection() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        """INSERT INTO students (department_id, name, email, password_hash, date_of_birth)
                           VALUES (%s, %s, %s, %s, %s) RETURNING student_id""",
                        (department_id, name, email, password_hash, date_of_birth),
                    )
                    return cur.fetchone()["student_id"]
                except UniqueViolation as exc:
                    raise DuplicateEmailError(f"Email already registered: {email}") from exc

    def get_by_id(self, student_id: int) -> Optional[Student]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM students WHERE student_id = %s", (student_id,))
                row = cur.fetchone()
                return Student(**row) if row else None

    def get_by_email(self, email: str) -> Optional[Student]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM students WHERE email = %s", (email,))
                row = cur.fetchone()
                return Student(**row) if row else None

    def list_all(self) -> list[Student]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM students ORDER BY student_id")
                return [Student(**row) for row in cur.fetchall()]

    def list_by_department(self, department_id: int) -> list[Student]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM students WHERE department_id = %s ORDER BY student_id",
                    (department_id,),
                )
                return [Student(**row) for row in cur.fetchall()]

    def search(self, query: str) -> list[Student]:
        """Full-text search on student name (GIN index on to_tsvector(name))."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT * FROM students
                       WHERE to_tsvector('english', name) @@ plainto_tsquery('english', %s)
                       ORDER BY student_id""",
                    (query,),
                )
                return [Student(**row) for row in cur.fetchall()]
