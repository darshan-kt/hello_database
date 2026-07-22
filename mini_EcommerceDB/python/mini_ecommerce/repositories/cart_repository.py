from typing import NamedTuple

import mysql.connector
from mysql.connector.abstracts import MySQLConnectionAbstract

from mini_ecommerce.db.connection import get_connection
from mini_ecommerce.exceptions import ProductNotFoundError
from mini_ecommerce.models import CartItem


class CartLine(NamedTuple):
    cart_item_id: int
    product_id: int
    product_name: str
    quantity: int
    unit_price: float


class CartRepository:
    def get_or_create_cart(self, user_id: int) -> int:
        with get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT cart_id FROM cart WHERE user_id = %s", (user_id,))
            row = cursor.fetchone()
            if row:
                cursor.close()
                return row["cart_id"]
            cursor.execute("INSERT INTO cart (user_id) VALUES (%s)", (user_id,))
            cart_id = cursor.lastrowid
            cursor.close()
            return cart_id

    def add_item(self, cart_id: int, product_id: int, quantity: int) -> None:
        """Upsert: adding an already-present product increases its quantity."""
        with get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """INSERT INTO cart_items (cart_id, product_id, quantity)
                       VALUES (%s, %s, %s)
                       ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)""",
                    (cart_id, product_id, quantity),
                )
            except mysql.connector.IntegrityError as exc:
                raise ProductNotFoundError(f"Product {product_id} does not exist") from exc
            finally:
                cursor.close()

    def remove_item(self, cart_id: int, product_id: int) -> None:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM cart_items WHERE cart_id = %s AND product_id = %s",
                (cart_id, product_id),
            )
            cursor.close()

    def list_items(self, cart_id: int) -> list[CartLine]:
        with get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """SELECT ci.cart_item_id, ci.product_id, p.name AS product_name,
                          ci.quantity, p.price AS unit_price
                   FROM cart_items ci
                   JOIN products p ON p.product_id = ci.product_id
                   WHERE ci.cart_id = %s""",
                (cart_id,),
            )
            rows = cursor.fetchall()
            cursor.close()
            return [CartLine(**row) for row in rows]

    # -- used inside the checkout transaction, sharing the caller's connection --

    def list_items_locked(self, conn: MySQLConnectionAbstract, cart_id: int) -> list[CartItem]:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM cart_items WHERE cart_id = %s FOR UPDATE", (cart_id,)
        )
        rows = cursor.fetchall()
        cursor.close()
        return [CartItem(**row) for row in rows]

    def clear(self, conn: MySQLConnectionAbstract, cart_id: int) -> None:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cart_items WHERE cart_id = %s", (cart_id,))
        cursor.close()
