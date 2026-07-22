from typing import Optional

from ems.db.connection import get_connection


class CertificateRepository:
    def issue(self, student_id: int, cert_type: str, verification_code: str) -> int:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO certificates (student_id, type, verification_code)
                       VALUES (%s, %s, %s) RETURNING certificate_id""",
                    (student_id, cert_type, verification_code),
                )
                return cur.fetchone()["certificate_id"]

    def list_by_student(self, student_id: int) -> list[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM certificates WHERE student_id = %s ORDER BY issued_at DESC",
                    (student_id,),
                )
                return cur.fetchall()

    def get_by_verification_code(self, code: str) -> Optional[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT c.*, st.name AS student_name
                       FROM certificates c
                       JOIN students st ON st.student_id = c.student_id
                       WHERE c.verification_code = %s""",
                    (code,),
                )
                return cur.fetchone()
