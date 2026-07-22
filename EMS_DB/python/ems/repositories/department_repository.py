from typing import Optional

from ems.db.connection import get_connection
from ems.models import Department


class DepartmentRepository:
    def create(self, name: str, code: str, parent_department_id: Optional[int] = None) -> int:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO departments (name, code, parent_department_id)
                       VALUES (%s, %s, %s) RETURNING department_id""",
                    (name, code, parent_department_id),
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
