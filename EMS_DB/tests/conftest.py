from datetime import date, timedelta

import pytest

from ems.db.connection import get_pool
from ems.repositories.course_repository import CourseRepository
from ems.repositories.department_repository import DepartmentRepository
from ems.repositories.enrollment_repository import EnrollmentRepository
from ems.repositories.semester_repository import SemesterRepository
from ems.repositories.student_repository import StudentRepository
from ems.repositories.teacher_repository import TeacherRepository

TABLES_IN_FK_ORDER = [
    "certificates", "payments", "grades", "exam_results", "exams",
    "assignment_submissions", "assignments", "attendance", "enrollments",
    "course_prerequisites", "courses", "semesters", "students", "teachers",
    "admins", "departments",
]


@pytest.fixture(autouse=True)
def clean_db():
    """Truncate every table before each test so tests are independent of
    seed data and of each other."""
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"TRUNCATE TABLE {', '.join(TABLES_IN_FK_ORDER)} RESTART IDENTITY CASCADE")
        conn.commit()
    yield


@pytest.fixture
def department_repo():
    return DepartmentRepository()


@pytest.fixture
def teacher_repo():
    return TeacherRepository()


@pytest.fixture
def student_repo():
    return StudentRepository()


@pytest.fixture
def course_repo():
    return CourseRepository()


@pytest.fixture
def semester_repo():
    return SemesterRepository()


@pytest.fixture
def enrollment_repo():
    return EnrollmentRepository()


@pytest.fixture
def sample_department_id(department_repo):
    return department_repo.create("Test Department", "TESTDEPT")


@pytest.fixture
def sample_teacher_id(teacher_repo, sample_department_id):
    return teacher_repo.create(sample_department_id, "Test Teacher", "teacher@example.com")


@pytest.fixture
def sample_student_id(student_repo, sample_department_id):
    return student_repo.create(sample_department_id, "Test Student", "student@example.com", "hash")


@pytest.fixture
def active_semester_id(semester_repo):
    today = date.today()
    return semester_repo.create(
        "Active Test Semester", today - timedelta(days=10), today + timedelta(days=80)
    )


@pytest.fixture
def ended_semester_id(semester_repo):
    today = date.today()
    return semester_repo.create(
        "Ended Test Semester", today - timedelta(days=200), today - timedelta(days=100)
    )


@pytest.fixture
def sample_course_id(course_repo, sample_department_id, sample_teacher_id):
    return course_repo.create(
        sample_department_id, sample_teacher_id, "TEST101", "Intro to Testing",
        credits=3, capacity=2,
    )
