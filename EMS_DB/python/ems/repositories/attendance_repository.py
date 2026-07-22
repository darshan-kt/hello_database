from datetime import date

from psycopg.errors import UniqueViolation

from ems.db.connection import get_connection
from ems.exceptions import DuplicateAttendanceError


class AttendanceRepository:
    def record(self, enrollment_id: int, session_date: date, status: str) -> int:
        with get_connection() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        """INSERT INTO attendance (enrollment_id, session_date, status)
                           VALUES (%s, %s, %s) RETURNING attendance_id""",
                        (enrollment_id, session_date, status),
                    )
                    return cur.fetchone()["attendance_id"]
                except UniqueViolation as exc:
                    raise DuplicateAttendanceError(
                        f"Attendance already recorded for enrollment {enrollment_id} on {session_date}"
                    ) from exc

    def list_by_enrollment(self, enrollment_id: int) -> list[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM attendance WHERE enrollment_id = %s ORDER BY session_date",
                    (enrollment_id,),
                )
                return cur.fetchall()
