from typing import Optional

from psycopg.errors import UniqueViolation

from rag.db.connection import get_connection
from rag.exceptions import DuplicateEmailError
from rag.models import User


class UserRepository:
    def create(
        self,
        name: str,
        email: str,
        password_hash: str,
        department_id: Optional[int] = None,
        role: str = "staff",
    ) -> int:
        with get_connection() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        """INSERT INTO users (name, email, password_hash, department_id, role)
                           VALUES (%s, %s, %s, %s, %s) RETURNING user_id""",
                        (name, email, password_hash, department_id, role),
                    )
                    return cur.fetchone()["user_id"]
                except UniqueViolation as exc:
                    raise DuplicateEmailError(f"Email already registered: {email}") from exc

    def get_by_id(self, user_id: int) -> Optional[User]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
                row = cur.fetchone()
                return User(**row) if row else None

    def get_by_email(self, email: str) -> Optional[User]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users WHERE email = %s", (email,))
                row = cur.fetchone()
                return User(**row) if row else None

    def list_all(self) -> list[User]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users ORDER BY user_id")
                return [User(**row) for row in cur.fetchall()]
