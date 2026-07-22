from typing import Optional

import mysql.connector

from mini_ecommerce.db.connection import get_connection
from mini_ecommerce.exceptions import DuplicateEmailError
from mini_ecommerce.models import User


class UserRepository:
    def create(self, name: str, email: str, password_hash: str, role: str = "customer") -> int:
        with get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO users (name, email, password_hash, role) VALUES (%s, %s, %s, %s)",
                    (name, email, password_hash, role),
                )
                user_id = cursor.lastrowid
            except mysql.connector.IntegrityError as exc:
                if "uq_users_email" in str(exc) or "Duplicate entry" in str(exc):
                    raise DuplicateEmailError(f"Email already registered: {email}") from exc
                raise
            finally:
                cursor.close()
            return user_id

    def get_by_id(self, user_id: int) -> Optional[User]:
        with get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
            row = cursor.fetchone()
            cursor.close()
            return User(**row) if row else None

    def get_by_email(self, email: str) -> Optional[User]:
        with get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            row = cursor.fetchone()
            cursor.close()
            return User(**row) if row else None

    def list_all(self) -> list[User]:
        with get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users ORDER BY user_id")
            rows = cursor.fetchall()
            cursor.close()
            return [User(**row) for row in rows]
