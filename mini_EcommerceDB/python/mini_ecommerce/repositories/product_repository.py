from decimal import Decimal
from typing import Optional

from mysql.connector.abstracts import MySQLConnectionAbstract

from mini_ecommerce.db.connection import get_connection
from mini_ecommerce.exceptions import OutOfStockError, ProductNotFoundError
from mini_ecommerce.models import Product


class ProductRepository:
    def create(
        self,
        category_id: int,
        name: str,
        price: Decimal,
        stock_quantity: int,
        description: Optional[str] = None,
    ) -> int:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO products (category_id, name, description, price, stock_quantity)
                   VALUES (%s, %s, %s, %s, %s)""",
                (category_id, name, description, price, stock_quantity),
            )
            product_id = cursor.lastrowid
            cursor.close()
            return product_id

    def get_by_id(self, product_id: int) -> Optional[Product]:
        with get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM products WHERE product_id = %s", (product_id,))
            row = cursor.fetchone()
            cursor.close()
            return Product(**row) if row else None

    def list_by_category(self, category_id: int) -> list[Product]:
        with get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT * FROM products WHERE category_id = %s AND is_active = TRUE "
                "ORDER BY product_id",
                (category_id,),
            )
            rows = cursor.fetchall()
            cursor.close()
            return [Product(**row) for row in rows]

    def list_all(self, active_only: bool = True) -> list[Product]:
        query = "SELECT * FROM products"
        if active_only:
            query += " WHERE is_active = TRUE"
        query += " ORDER BY product_id"
        with get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query)
            rows = cursor.fetchall()
            cursor.close()
            return [Product(**row) for row in rows]

    def update_stock(self, product_id: int, new_quantity: int) -> None:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE products SET stock_quantity = %s WHERE product_id = %s",
                (new_quantity, product_id),
            )
            cursor.close()

    def deactivate(self, product_id: int) -> None:
        """Soft-delete: keeps order history intact (FK is ON DELETE RESTRICT)."""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE products SET is_active = FALSE WHERE product_id = %s",
                (product_id,),
            )
            cursor.close()

    # -- used inside the checkout transaction, sharing the caller's connection --

    def lock_for_update(self, conn: MySQLConnectionAbstract, product_id: int) -> Product:
        """Row-lock a product within an existing transaction to prevent
        concurrent checkouts from overselling the same stock."""
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM products WHERE product_id = %s FOR UPDATE", (product_id,)
        )
        row = cursor.fetchone()
        cursor.close()
        if row is None:
            raise ProductNotFoundError(f"Product {product_id} does not exist")
        return Product(**row)

    def decrement_stock(
        self, conn: MySQLConnectionAbstract, product_id: int, quantity: int
    ) -> None:
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE products SET stock_quantity = stock_quantity - %s
               WHERE product_id = %s AND stock_quantity >= %s""",
            (quantity, product_id, quantity),
        )
        affected = cursor.rowcount
        cursor.close()
        if affected == 0:
            product = self.lock_for_update(conn, product_id)
            raise OutOfStockError(product_id, quantity, product.stock_quantity)
