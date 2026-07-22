from typing import Optional

from rag.db.connection import get_connection
from rag.models import Department


class DepartmentRepository:
    def create(self, name: str, code: str) -> int:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO departments (name, code) VALUES (%s, %s) RETURNING department_id",
                    (name, code),
                )
                return cur.fetchone()["department_id"]

    def get_by_id(self, department_id: int) -> Optional[Department]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM departments WHERE department_id = %s", (department_id,))
                row = cur.fetchone()
                return Department(**row) if row else None

    def list_all(self) -> list[Department]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM departments ORDER BY department_id")
                return [Department(**row) for row in cur.fetchall()]
