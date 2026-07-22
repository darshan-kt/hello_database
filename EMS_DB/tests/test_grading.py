from datetime import date
from decimal import Decimal

import pytest

from ems.exceptions import EMSError
from ems.repositories.exam_repository import ExamRepository
from ems.repositories.exam_result_repository import ExamResultRepository
from ems.services.enrollment_service import EnrollmentService
from ems.services.grading_service import GradingService


@pytest.fixture
def enrollment_id(sample_student_id, sample_course_id, active_semester_id):
    result = EnrollmentService().enroll(sample_student_id, sample_course_id, active_semester_id)
    return result.enrollment_id


def test_compute_grade_from_exam_only(enrollment_id, sample_course_id, active_semester_id, sample_student_id):
    exam_repo = ExamRepository()
    exam_id = exam_repo.create(
        sample_course_id, active_semester_id, "Midterm", date.today(), Decimal("50")
    )
    ExamResultRepository().record(exam_id, sample_student_id, Decimal("45"))  # 90%

    grade = GradingService().compute_grade(enrollment_id)

    assert grade["total_percent"] == Decimal("90.00")
    assert grade["letter_grade"] == "A"
    assert grade["gpa_points"] == Decimal("4.00")


def test_compute_grade_without_any_marks_raises(enrollment_id):
    with pytest.raises(EMSError):
        GradingService().compute_grade(enrollment_id)


def test_recomputing_grade_overwrites_previous(enrollment_id, sample_course_id, active_semester_id, sample_student_id):
    exam_repo = ExamRepository()
    result_repo = ExamResultRepository()
    exam_id = exam_repo.create(
        sample_course_id, active_semester_id, "Midterm", date.today(), Decimal("50")
    )
    result_repo.record(exam_id, sample_student_id, Decimal("25"))  # 50% -> F
    first = GradingService().compute_grade(enrollment_id)
    assert first["letter_grade"] == "F"

    result_repo.record(exam_id, sample_student_id, Decimal("48"))  # corrected to 96% -> A
    second = GradingService().compute_grade(enrollment_id)
    assert second["letter_grade"] == "A"
    assert second["grade_id"] == first["grade_id"]  # same row, upserted
