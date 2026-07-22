from decimal import Decimal
from typing import Optional

from mysql.connector.abstracts import MySQLConnectionAbstract

from mini_ecommerce.db.connection import get_connection
from mini_ecommerce.models import Order


class OrderRepository:
    def get_by_id(self, order_id: int) -> Optional[Order]:
        with get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM orders WHERE order_id = %s", (order_id,))
            row = cursor.fetchone()
            cursor.close()
            return Order(**row) if row else None

    def list_items(self, order_id: int) -> list[dict]:
        with get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """SELECT oi.order_item_id, oi.product_id, p.name AS product_name,
                          oi.quantity, oi.unit_price
                   FROM order_items oi
                   JOIN products p ON p.product_id = oi.product_id
                   WHERE oi.order_id = %s""",
                (order_id,),
            )
            rows = cursor.fetchall()
            cursor.close()
            return rows

    def list_by_user(self, user_id: int) -> list[Order]:
        with get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT * FROM orders WHERE user_id = %s ORDER BY created_at DESC",
                (user_id,),
            )
            rows = cursor.fetchall()
            cursor.close()
            return [Order(**row) for row in rows]

    def update_status(self, order_id: int, status: str) -> None:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE orders SET status = %s WHERE order_id = %s", (status, order_id)
            )
            cursor.close()

    # -- used inside the checkout transaction, sharing the caller's connection --

    def create(self, conn: MySQLConnectionAbstract, user_id: int, total_amount: Decimal) -> int:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO orders (user_id, status, total_amount) VALUES (%s, 'pending', %s)",
            (user_id, total_amount),
        )
        order_id = cursor.lastrowid
        cursor.close()
        return order_id

    def add_item(
        self,
        conn: MySQLConnectionAbstract,
        order_id: int,
        product_id: int,
        quantity: int,
        unit_price: Decimal,
    ) -> None:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO order_items (order_id, product_id, quantity, unit_price)
               VALUES (%s, %s, %s, %s)""",
            (order_id, product_id, quantity, unit_price),
        )
        cursor.close()

    def set_status(self, conn: MySQLConnectionAbstract, order_id: int, status: str) -> None:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE orders SET status = %s WHERE order_id = %s", (status, order_id)
        )
        cursor.close()
