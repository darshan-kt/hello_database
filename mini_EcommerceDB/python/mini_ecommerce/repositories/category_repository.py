from typing import Optional

from mini_ecommerce.db.connection import get_connection
from mini_ecommerce.models import Category


class CategoryRepository:
    def create(self, name: str, description: Optional[str] = None) -> int:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO categories (name, description) VALUES (%s, %s)",
                (name, description),
            )
            category_id = cursor.lastrowid
            cursor.close()
            return category_id

    def get_by_id(self, category_id: int) -> Optional[Category]:
        with get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM categories WHERE category_id = %s", (category_id,))
            row = cursor.fetchone()
            cursor.close()
            return Category(**row) if row else None

    def list_all(self) -> list[Category]:
        with get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM categories ORDER BY category_id")
            rows = cursor.fetchall()
            cursor.close()
            return [Category(**row) for row in rows]
