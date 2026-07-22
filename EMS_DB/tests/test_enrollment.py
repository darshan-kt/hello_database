import pytest

from ems.exceptions import AlreadyEnrolledError, CourseFullError, InvalidSemesterError, NotFoundError
from ems.repositories.student_repository import StudentRepository
from ems.services.enrollment_service import EnrollmentService


@pytest.fixture
def enrollment_service():
    return EnrollmentService()


def test_enroll_happy_path(enrollment_service, sample_student_id, sample_course_id, active_semester_id):
    result = enrollment_service.enroll(sample_student_id, sample_course_id, active_semester_id)
    assert result.course_id == sample_course_id
    assert result.semester_id == active_semester_id


def test_enroll_invalid_course_raises_not_found(enrollment_service, sample_student_id, active_semester_id):
    with pytest.raises(NotFoundError):
        enrollment_service.enroll(sample_student_id, 999999, active_semester_id)


def test_enroll_invalid_semester_raises_not_found(enrollment_service, sample_student_id, sample_course_id):
    with pytest.raises(NotFoundError):
        enrollment_service.enroll(sample_student_id, sample_course_id, 999999)


def test_enroll_in_ended_semester_raises(enrollment_service, sample_student_id, sample_course_id, ended_semester_id):
    with pytest.raises(InvalidSemesterError):
        enrollment_service.enroll(sample_student_id, sample_course_id, ended_semester_id)


def test_enroll_twice_raises_already_enrolled(
    enrollment_service, sample_student_id, sample_course_id, active_semester_id
):
    enrollment_service.enroll(sample_student_id, sample_course_id, active_semester_id)
    with pytest.raises(AlreadyEnrolledError):
        enrollment_service.enroll(sample_student_id, sample_course_id, active_semester_id)


def test_enrollment_limit_reached(
    enrollment_service, sample_department_id, sample_course_id, active_semester_id
):
    """sample_course_id has capacity=2 (see conftest.py)."""
    student_repo = StudentRepository()
    s1 = student_repo.create(sample_department_id, "Student One", "s1@example.com", "hash")
    s2 = student_repo.create(sample_department_id, "Student Two", "s2@example.com", "hash")
    s3 = student_repo.create(sample_department_id, "Student Three", "s3@example.com", "hash")

    enrollment_service.enroll(s1, sample_course_id, active_semester_id)
    enrollment_service.enroll(s2, sample_course_id, active_semester_id)

    with pytest.raises(CourseFullError):
        enrollment_service.enroll(s3, sample_course_id, active_semester_id)
