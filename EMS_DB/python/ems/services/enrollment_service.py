"""
Module 8 Phase C -- Student enrollment.

Mirrors the checkout-locking pattern from the e-commerce project, but for
seats instead of stock: `SELECT ... FOR UPDATE` on the course row
serializes concurrent enrollment attempts for that course so two students
racing for the last seat can't both get in.
"""
from dataclasses import dataclass
from datetime import date

from psycopg.errors import UniqueViolation

from ems.db.connection import get_pool
from ems.exceptions import AlreadyEnrolledError, CourseFullError, InvalidSemesterError, NotFoundError
from ems.repositories.course_repository import CourseRepository
from ems.repositories.enrollment_repository import EnrollmentRepository
from ems.repositories.semester_repository import SemesterRepository


@dataclass
class EnrollmentResult:
    enrollment_id: int
    course_id: int
    semester_id: int


class EnrollmentService:
    def __init__(self, course_repo=None, enrollment_repo=None, semester_repo=None):
        self.course_repo = course_repo or CourseRepository()
        self.enrollment_repo = enrollment_repo or EnrollmentRepository()
        self.semester_repo = semester_repo or SemesterRepository()

    def enroll(self, student_id: int, course_id: int, semester_id: int) -> EnrollmentResult:
        semester = self.semester_repo.get_by_id(semester_id)
        if semester is None:
            raise NotFoundError("Semester", semester_id)
        if semester.end_date < date.today():
            raise InvalidSemesterError(f"Semester '{semester.name}' has already ended")

        with get_pool().connection() as conn:
            try:
                course = self.course_repo.lock_for_update(conn, course_id)

                # Checked before capacity so a student re-enrolling in a
                # course they're already in (even a full one) gets an
                # accurate "already enrolled" rather than a misleading
                # "course full" -- the seat is their own.
                if self.enrollment_repo.exists(conn, student_id, course_id, semester_id):
                    raise AlreadyEnrolledError(
                        f"Student {student_id} is already enrolled in course {course_id} "
                        f"for semester {semester_id}"
                    )

                current_count = self.enrollment_repo.count_for_course_semester(
                    conn, course_id, semester_id
                )
                if current_count >= course.capacity:
                    raise CourseFullError(course_id, course.capacity)

                try:
                    enrollment_id = self.enrollment_repo.create(
                        conn, student_id, course_id, semester_id
                    )
                except UniqueViolation as exc:
                    raise AlreadyEnrolledError(
                        f"Student {student_id} is already enrolled in course {course_id} "
                        f"for semester {semester_id}"
                    ) from exc

                conn.commit()
                return EnrollmentResult(
                    enrollment_id=enrollment_id, course_id=course_id, semester_id=semester_id
                )
            except Exception:
                conn.rollback()
                raise
