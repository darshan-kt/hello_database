from decimal import Decimal
from typing import Optional

from mysql.connector.abstracts import MySQLConnectionAbstract

from mini_ecommerce.db.connection import get_connection
from mini_ecommerce.models import Payment


class PaymentRepository:
    def get_by_order_id(self, order_id: int) -> Optional[Payment]:
        with get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM payments WHERE order_id = %s", (order_id,))
            row = cursor.fetchone()
            cursor.close()
            return Payment(**row) if row else None

    # -- used inside the checkout transaction, sharing the caller's connection --

    def create(
        self,
        conn: MySQLConnectionAbstract,
        order_id: int,
        amount: Decimal,
        method: str,
        status: str,
    ) -> int:
        """Record a payment attempt. A declined payment is retryable (the
        order stays 'pending'), and a retry reuses the same payment row
        rather than violating the one-payment-per-order UNIQUE constraint
        -- ON DUPLICATE KEY UPDATE overwrites the prior failed attempt."""
        cursor = conn.cursor()
        paid_at_expr = "NOW()" if status == "success" else "NULL"
        cursor.execute(
            f"""INSERT INTO payments (order_id, amount, method, status, paid_at)
                VALUES (%s, %s, %s, %s, {paid_at_expr})
                ON DUPLICATE KEY UPDATE
                    payment_id = LAST_INSERT_ID(payment_id),
                    amount = VALUES(amount),
                    method = VALUES(method),
                    status = VALUES(status),
                    paid_at = VALUES(paid_at)""",
            (order_id, amount, method, status),
        )
        payment_id = cursor.lastrowid
        cursor.close()
        return payment_id
