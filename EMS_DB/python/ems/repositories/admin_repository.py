from typing import Optional

from psycopg.errors import UniqueViolation

from ems.db.connection import get_connection
from ems.exceptions import DuplicateEmailError
from ems.models import Admin


class AdminRepository:
    def create(self, name: str, email: str, password_hash: str) -> int:
        with get_connection() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        """INSERT INTO admins (name, email, password_hash)
                           VALUES (%s, %s, %s) RETURNING admin_id""",
                        (name, email, password_hash),
                    )
                    return cur.fetchone()["admin_id"]
                except UniqueViolation as exc:
                    raise DuplicateEmailError(f"Email already registered: {email}") from exc

    def get_by_id(self, admin_id: int) -> Optional[Admin]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM admins WHERE admin_id = %s", (admin_id,))
                row = cur.fetchone()
                return Admin(**row) if row else None

    def get_by_email(self, email: str) -> Optional[Admin]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM admins WHERE email = %s", (email,))
                row = cur.fetchone()
                return Admin(**row) if row else None
