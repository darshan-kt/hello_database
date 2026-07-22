"""
Module 8 Phase F -- Examinations -> Marks -> Grades -> GPA.

Grade computation is an explicit, on-demand action (not a live view) --
see the "deliberate denormalization" note in docs/02_er_diagram.md for
why a finalized grade shouldn't silently drift if an old mark is edited
later.

Weighting (documented simplification, not a registrar-grade formula):
60% exam average (each exam normalized to a percentage via its own
max_marks) + 40% assignment average (assignment marks are recorded
directly on a 0-100 scale). If only one component has data, that
component alone becomes the grade.
"""
from decimal import ROUND_HALF_UP, Decimal

from ems.exceptions import EMSError, NotFoundError
from ems.repositories.enrollment_repository import EnrollmentRepository
from ems.repositories.exam_result_repository import ExamResultRepository
from ems.repositories.grade_repository import GradeRepository
from ems.repositories.submission_repository import SubmissionRepository

GRADE_SCALE = [
    (Decimal("90"), "A", Decimal("4.00")),
    (Decimal("80"), "B", Decimal("3.00")),
    (Decimal("70"), "C", Decimal("2.00")),
    (Decimal("60"), "D", Decimal("1.00")),
    (Decimal("0"), "F", Decimal("0.00")),
]


def _letter_and_gpa(percent: Decimal) -> tuple[str, Decimal]:
    for threshold, letter, gpa in GRADE_SCALE:
        if percent >= threshold:
            return letter, gpa
    return "F", Decimal("0.00")


class GradingService:
    def __init__(
        self,
        enrollment_repo=None,
        exam_result_repo=None,
        submission_repo=None,
        grade_repo=None,
    ):
        self.enrollment_repo = enrollment_repo or EnrollmentRepository()
        self.exam_result_repo = exam_result_repo or ExamResultRepository()
        self.submission_repo = submission_repo or SubmissionRepository()
        self.grade_repo = grade_repo or GradeRepository()

    def compute_grade(self, enrollment_id: int) -> dict:
        enrollment = self.enrollment_repo.get_by_id(enrollment_id)
        if enrollment is None:
            raise NotFoundError("Enrollment", enrollment_id)

        exam_results = self.exam_result_repo.list_by_student_for_course(
            enrollment.student_id, enrollment.course_id
        )
        submissions = self.submission_repo.list_by_student_for_course(
            enrollment.student_id, enrollment.course_id
        )
        graded_submissions = [s for s in submissions if s["marks_obtained"] is not None]

        exam_pct = None
        if exam_results:
            total_obtained = sum(Decimal(str(r["marks_obtained"])) for r in exam_results)
            total_max = sum(Decimal(str(r["max_marks"])) for r in exam_results)
            if total_max:
                exam_pct = (total_obtained / total_max) * 100

        assignment_pct = None
        if graded_submissions:
            assignment_pct = sum(
                Decimal(str(s["marks_obtained"])) for s in graded_submissions
            ) / len(graded_submissions)

        if exam_pct is None and assignment_pct is None:
            raise EMSError(
                f"Cannot compute a grade for enrollment {enrollment_id}: "
                "no exam results or graded assignments recorded yet"
            )

        if exam_pct is not None and assignment_pct is not None:
            total_percent = (exam_pct * Decimal("0.6")) + (assignment_pct * Decimal("0.4"))
        else:
            total_percent = exam_pct if exam_pct is not None else assignment_pct

        total_percent = total_percent.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        letter_grade, gpa_points = _letter_and_gpa(total_percent)

        grade_id = self.grade_repo.upsert(enrollment_id, total_percent, letter_grade, gpa_points)
        return {
            "grade_id": grade_id,
            "enrollment_id": enrollment_id,
            "total_percent": total_percent,
            "letter_grade": letter_grade,
            "gpa_points": gpa_points,
        }
