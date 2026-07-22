from decimal import Decimal
from typing import Optional

from ems.db.connection import get_connection


class PaymentRepository:
    def create_invoice(self, student_id: int, semester_id: int, amount: Decimal) -> int:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO payments (student_id, semester_id, amount)
                       VALUES (%s, %s, %s) RETURNING payment_id""",
                    (student_id, semester_id, amount),
                )
                return cur.fetchone()["payment_id"]

    def get(self, student_id: int, semester_id: int) -> Optional[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM payments WHERE student_id = %s AND semester_id = %s",
                    (student_id, semester_id),
                )
                return cur.fetchone()

    def mark_paid(self, payment_id: int, method: str) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE payments SET status = 'paid', method = %s, paid_at = now()
                       WHERE payment_id = %s""",
                    (method, payment_id),
                )

    def list_by_student(self, student_id: int) -> list[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT p.*, s.name AS semester_name
                       FROM payments p
                       JOIN semesters s ON s.semester_id = p.semester_id
                       WHERE p.student_id = %s
                       ORDER BY s.start_date DESC""",
                    (student_id,),
                )
                return cur.fetchall()

    def has_unpaid_invoice(self, student_id: int) -> bool:
        """Certificate eligibility check: any semester with a pending/failed invoice?"""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT EXISTS (
                           SELECT 1 FROM payments
                           WHERE student_id = %s AND status != 'paid'
                       ) AS unpaid""",
                    (student_id,),
                )
                return cur.fetchone()["unpaid"]
