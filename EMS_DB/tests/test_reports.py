from datetime import date
from decimal import Decimal

import pytest

from ems.repositories.exam_repository import ExamRepository
from ems.repositories.exam_result_repository import ExamResultRepository
from ems.repositories.report_repository import ReportRepository
from ems.services.enrollment_service import EnrollmentService
from ems.services.grading_service import GradingService


@pytest.fixture
def report_repo():
    return ReportRepository()


def test_department_hierarchy_recursive_cte(department_repo):
    school_id = department_repo.create("Test School", "TS")
    child_id = department_repo.create("Test Child Dept", "TCD", parent_department_id=school_id)

    rows = ReportRepository().department_hierarchy()
    by_id = {r["department_id"]: r for r in rows}

    assert by_id[school_id]["depth"] == 0
    assert by_id[child_id]["depth"] == 1
    assert by_id[child_id]["path"] == "Test School > Test Child Dept"


def test_course_prerequisite_chain_recursive_cte(course_repo, sample_department_id, sample_teacher_id):
    c101 = course_repo.create(sample_department_id, sample_teacher_id, "C101", "Intro", credits=3, capacity=10)
    c201 = course_repo.create(sample_department_id, sample_teacher_id, "C201", "Mid", credits=3, capacity=10)
    c301 = course_repo.create(sample_department_id, sample_teacher_id, "C301", "Advanced", credits=3, capacity=10)
    course_repo.add_prerequisite(c201, c101)
    course_repo.add_prerequisite(c301, c201)

    chain = ReportRepository().course_prerequisite_chain(c301)
    codes_by_depth = {row["depth"]: row["code"] for row in chain}

    assert codes_by_depth == {1: "C201", 2: "C101"}


def test_department_report_cte(report_repo, sample_department_id, sample_teacher_id, sample_student_id):
    assert any(r["department_id"] == sample_department_id for r in report_repo.department_report())


def test_gpa_rankings_window_function(
    report_repo, sample_student_id, sample_course_id, active_semester_id, sample_department_id
):
    result = EnrollmentService().enroll(sample_student_id, sample_course_id, active_semester_id)
    exam_id = ExamRepository().create(
        sample_course_id, active_semester_id, "Midterm", date.today(), Decimal("50")
    )
    ExamResultRepository().record(exam_id, sample_student_id, Decimal("50"))  # 100%
    GradingService().compute_grade(result.enrollment_id)

    rankings = report_repo.gpa_rankings(department_id=sample_department_id)
    assert len(rankings) == 1
    assert rankings[0]["student_id"] == sample_student_id
    assert rankings[0]["overall_rank"] == 1
    assert rankings[0]["department_rank"] == 1


def test_semester_report_materialized_view_refresh(
    report_repo, sample_student_id, sample_course_id, active_semester_id
):
    EnrollmentService().enroll(sample_student_id, sample_course_id, active_semester_id)

    report_repo.refresh_semester_report()
    rows = report_repo.semester_report()

    row = next(r for r in rows if r["semester_id"] == active_semester_id)
    assert row["enrollment_count"] == 1
