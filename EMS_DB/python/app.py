"""
Flask API + static UI host for the Education Management System.

Thin HTTP layer over the repository/service classes in `ems/` -- routes
translate requests into repository/service calls and domain exceptions
into HTTP status codes; no business logic lives here.

Two session-based roles: `student` (self-service: enroll, view grades,
pay fees, request certificates) and `admin` (registrar staff: manage the
academic catalog, record attendance/results, run reports). See
docs/01_requirements.md for why there's no separate teacher login.
"""
import dataclasses
import os
from datetime import date, datetime
from decimal import Decimal
from functools import wraps

from flask import Flask, jsonify, request, session
from flask.json.provider import DefaultJSONProvider

from ems.exceptions import (
    AlreadyEnrolledError,
    CourseFullError,
    DuplicateAttendanceError,
    DuplicateEmailError,
    EMSError,
    InvalidSemesterError,
    NotFoundError,
    PaymentRequiredError,
)
from ems.repositories.admin_repository import AdminRepository
from ems.repositories.assignment_repository import AssignmentRepository
from ems.repositories.attendance_repository import AttendanceRepository
from ems.repositories.certificate_repository import CertificateRepository
from ems.repositories.course_repository import CourseRepository
from ems.repositories.department_repository import DepartmentRepository
from ems.repositories.enrollment_repository import EnrollmentRepository
from ems.repositories.exam_repository import ExamRepository
from ems.repositories.exam_result_repository import ExamResultRepository
from ems.repositories.grade_repository import GradeRepository
from ems.repositories.payment_repository import PaymentRepository
from ems.repositories.report_repository import ReportRepository
from ems.repositories.semester_repository import SemesterRepository
from ems.repositories.student_repository import StudentRepository
from ems.repositories.submission_repository import SubmissionRepository
from ems.repositories.teacher_repository import TeacherRepository
from ems.security import hash_password
from ems.services.certificate_service import CertificateService
from ems.services.enrollment_service import EnrollmentService
from ems.services.grading_service import GradingService


class JSONProvider(DefaultJSONProvider):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, date):
            return obj.isoformat()
        return super().default(obj)


app = Flask(__name__, static_folder="static", static_url_path="")
app.json = JSONProvider(app)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")

departments = DepartmentRepository()
admins = AdminRepository()
teachers = TeacherRepository()
students = StudentRepository()
semesters = SemesterRepository()
courses = CourseRepository()
enrollments = EnrollmentRepository()
attendance = AttendanceRepository()
assignments = AssignmentRepository()
submissions = SubmissionRepository()
exams = ExamRepository()
exam_results = ExamResultRepository()
grades = GradeRepository()
payments = PaymentRepository()
certificates = CertificateRepository()
reports = ReportRepository()

enrollment_service = EnrollmentService()
grading_service = GradingService()
certificate_service = CertificateService()


def require_student(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if session.get("role") != "student":
            return jsonify(error="Student login required"), 401
        return fn(*args, **kwargs)

    return wrapper


ALLOWED_PAYMENT_METHODS = {"card", "bank_transfer", "cash"}
ALLOWED_ATTENDANCE_STATUSES = {"present", "absent", "late"}
ALLOWED_CERTIFICATE_TYPES = {"transcript", "completion"}


def validate_enum(value, allowed: set, field_name: str):
    """Reject an invalid enum value with a clean 400 before it reaches
    Postgres -- without this, an invalid value surfaces as a raw
    InvalidTextRepresentation 500 instead of a JSON error."""
    if value not in allowed:
        return jsonify(error=f"{field_name} must be one of {sorted(allowed)}, got {value!r}"), 400
    return None


def require_admin(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            return jsonify(error="Admin login required"), 401
        return fn(*args, **kwargs)

    return wrapper


@app.errorhandler(EMSError)
def handle_domain_error(exc: EMSError):
    status = 400
    if isinstance(exc, DuplicateEmailError):
        status = 409
    elif isinstance(exc, NotFoundError):
        status = 404
    elif isinstance(exc, (CourseFullError, AlreadyEnrolledError, DuplicateAttendanceError)):
        status = 409
    elif isinstance(exc, InvalidSemesterError):
        status = 400
    elif isinstance(exc, PaymentRequiredError):
        status = 402
    return jsonify(error=str(exc), type=type(exc).__name__), status


@app.route("/")
def index():
    return app.send_static_file("index.html")


@app.get("/api/health")
def health():
    return jsonify(status="ok")


# ---------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------
@app.post("/api/auth/student/register")
def register_student():
    data = request.get_json(force=True)
    name, email, password = data.get("name"), data.get("email"), data.get("password")
    department_id = data.get("department_id")
    if not all([name, email, password, department_id]):
        return jsonify(error="name, email, password and department_id are required"), 400
    student_id = students.create(department_id, name, email, hash_password(password))
    session["role"] = "student"
    session["user_id"] = student_id
    return jsonify(student_id=student_id, name=name, email=email), 201


def _display_name_from_email(email: str) -> str:
    return email.split("@")[0].replace(".", " ").replace("_", " ").title() or "Guest"


def _default_department_id() -> int:
    """Pick a real (leaf, not a School) department for auto-created
    student accounts to belong to."""
    all_depts = departments.list_all()
    leaf = [d for d in all_depts if d.parent_department_id is not None]
    return (leaf or all_depts)[0].department_id


@app.post("/api/auth/student/login")
def login_student():
    """Demo mode: any email/password logs you in. If the email doesn't
    belong to an existing student, one is created on the spot -- this is
    a learning sandbox, not a real auth system, so there's no password
    to get wrong."""
    data = request.get_json(force=True)
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    if not email:
        return jsonify(error="email is required"), 400

    student = students.get_by_email(email)
    if student is None:
        try:
            students.create(
                _default_department_id(), _display_name_from_email(email), email, hash_password(password)
            )
        except DuplicateEmailError:
            pass  # lost a race with another request creating the same email
        student = students.get_by_email(email)

    session["role"] = "student"
    session["user_id"] = student.student_id
    return jsonify(student_id=student.student_id, name=student.name, email=student.email)


@app.post("/api/auth/admin/login")
def login_admin():
    """Demo mode: same as student login -- any email/password works,
    and a new admin account is created automatically if the email is
    unrecognized. (Admins are normally registrar-provisioned, not
    self-service; this project relaxes that for learning purposes.)"""
    data = request.get_json(force=True)
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    if not email:
        return jsonify(error="email is required"), 400

    admin = admins.get_by_email(email)
    if admin is None:
        try:
            admins.create(_display_name_from_email(email), email, hash_password(password))
        except DuplicateEmailError:
            pass  # lost a race with another request creating the same email
        admin = admins.get_by_email(email)

    session["role"] = "admin"
    session["user_id"] = admin.admin_id
    return jsonify(admin_id=admin.admin_id, name=admin.name, email=admin.email)


@app.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@app.get("/api/auth/me")
def me():
    role = session.get("role")
    if role == "student":
        student = students.get_by_id(session["user_id"])
        if student is None:
            return jsonify(error="Not logged in"), 401
        return jsonify(role="student", student_id=student.student_id, name=student.name, email=student.email)
    if role == "admin":
        admin = admins.get_by_id(session["user_id"])
        if admin is None:
            return jsonify(error="Not logged in"), 401
        return jsonify(role="admin", admin_id=admin.admin_id, name=admin.name, email=admin.email)
    return jsonify(error="Not logged in"), 401


# ---------------------------------------------------------------------
# Departments
# ---------------------------------------------------------------------
@app.get("/api/departments")
def list_departments():
    return jsonify([dataclasses.asdict(d) for d in departments.list_all()])


@app.get("/api/departments/hierarchy")
def department_hierarchy():
    """Recursive CTE: walks the School -> Department tree top-down."""
    return jsonify(reports.department_hierarchy())


@app.post("/api/departments")
@require_admin
def create_department():
    data = request.get_json(force=True)
    department_id = departments.create(
        data.get("name"), data.get("code"), data.get("parent_department_id")
    )
    return jsonify(department_id=department_id), 201


# ---------------------------------------------------------------------
# Teachers (admin directory)
# ---------------------------------------------------------------------
@app.get("/api/teachers")
@require_admin
def list_teachers():
    return jsonify([dataclasses.asdict(t) for t in teachers.list_all()])


@app.get("/api/teachers/search")
@require_admin
def search_teachers():
    query = request.args.get("q", "")
    return jsonify([dataclasses.asdict(t) for t in teachers.search(query)])


@app.post("/api/teachers")
@require_admin
def create_teacher():
    data = request.get_json(force=True)
    teacher_id = teachers.create(
        data.get("department_id"), data.get("name"), data.get("email"), data.get("hire_date")
    )
    return jsonify(teacher_id=teacher_id), 201


# ---------------------------------------------------------------------
# Students (admin directory)
# ---------------------------------------------------------------------
@app.get("/api/students")
@require_admin
def list_students():
    return jsonify([dataclasses.asdict(s) for s in students.list_all()])


@app.get("/api/students/search")
@require_admin
def search_students():
    query = request.args.get("q", "")
    return jsonify([dataclasses.asdict(s) for s in students.search(query)])


@app.get("/api/students/<int:student_id>")
@require_admin
def get_student(student_id: int):
    student = students.get_by_id(student_id)
    if student is None:
        return jsonify(error="Student not found"), 404
    return jsonify(dataclasses.asdict(student))


@app.get("/api/students/<int:student_id>/dashboard")
@require_admin
def student_dashboard_admin(student_id: int):
    dashboard = reports.student_dashboard(student_id)
    if dashboard is None:
        return jsonify(error="Student not found"), 404
    return jsonify(dashboard)


# ---------------------------------------------------------------------
# Courses
# ---------------------------------------------------------------------
@app.get("/api/courses")
def list_courses():
    department_id = request.args.get("department_id", type=int)
    items = courses.list_by_department(department_id) if department_id else courses.list_all()
    return jsonify([dataclasses.asdict(c) for c in items])


@app.get("/api/courses/search")
def search_courses():
    query = request.args.get("q", "")
    return jsonify([dataclasses.asdict(c) for c in courses.search(query)])


@app.get("/api/courses/<int:course_id>")
def get_course(course_id: int):
    course = courses.get_by_id(course_id)
    if course is None:
        return jsonify(error="Course not found"), 404
    return jsonify(dataclasses.asdict(course))


@app.get("/api/courses/<int:course_id>/prerequisites")
def course_prerequisites(course_id: int):
    """Recursive CTE: the full transitive prerequisite chain, not just
    direct prerequisites."""
    return jsonify(reports.course_prerequisite_chain(course_id))


@app.post("/api/courses")
@require_admin
def create_course():
    data = request.get_json(force=True)
    course_id = courses.create(
        data.get("department_id"),
        data.get("teacher_id"),
        data.get("code"),
        data.get("title"),
        data.get("credits"),
        data.get("capacity"),
        data.get("description"),
    )
    return jsonify(course_id=course_id), 201


@app.post("/api/courses/<int:course_id>/prerequisites")
@require_admin
def add_prerequisite(course_id: int):
    data = request.get_json(force=True)
    courses.add_prerequisite(course_id, data.get("prerequisite_course_id"))
    return jsonify(ok=True), 201


@app.get("/api/courses/<int:course_id>/assignments")
def list_course_assignments(course_id: int):
    return jsonify(assignments.list_by_course(course_id))


@app.post("/api/courses/<int:course_id>/assignments")
@require_admin
def create_assignment(course_id: int):
    data = request.get_json(force=True)
    assignment_id = assignments.create(course_id, data.get("title"), data.get("settings", {}))
    return jsonify(assignment_id=assignment_id), 201


@app.get("/api/courses/<int:course_id>/exams")
def list_course_exams(course_id: int):
    return jsonify(exams.list_by_course(course_id))


@app.post("/api/courses/<int:course_id>/exams")
@require_admin
def create_exam(course_id: int):
    data = request.get_json(force=True)
    exam_id = exams.create(
        course_id, data.get("semester_id"), data.get("name"), data.get("exam_date"), data.get("max_marks")
    )
    return jsonify(exam_id=exam_id), 201


# ---------------------------------------------------------------------
# JSONB showcase queries on assignments
# ---------------------------------------------------------------------
@app.get("/api/assignments/late-penalty")
@require_admin
def assignments_with_late_penalty():
    """`settings ? 'late_penalty'` -- JSONB key-existence operator."""
    return jsonify(assignments.list_with_late_penalty())


@app.get("/api/assignments/due-before")
@require_admin
def assignments_due_before():
    """`(settings->>'submission_deadline')::date < %s` -- JSONB field extraction + cast."""
    iso_date = request.args.get("date")
    if not iso_date:
        return jsonify(error="?date=YYYY-MM-DD is required"), 400
    return jsonify(assignments.list_due_before(iso_date))


# ---------------------------------------------------------------------
# Semesters
# ---------------------------------------------------------------------
@app.get("/api/semesters")
def list_semesters():
    return jsonify([dataclasses.asdict(s) for s in semesters.list_all()])


@app.get("/api/semesters/active")
def active_semester():
    semester = semesters.get_active()
    if semester is None:
        return jsonify(error="No active semester"), 404
    return jsonify(dataclasses.asdict(semester))


@app.post("/api/semesters")
@require_admin
def create_semester():
    data = request.get_json(force=True)
    semester_id = semesters.create(data.get("name"), data.get("start_date"), data.get("end_date"))
    return jsonify(semester_id=semester_id), 201


# ---------------------------------------------------------------------
# Enrollment (student self-service)
# ---------------------------------------------------------------------
@app.get("/api/me/enrollments")
@require_student
def my_enrollments():
    return jsonify(enrollments.list_by_student(session["user_id"]))


@app.post("/api/me/enrollments")
@require_student
def enroll():
    data = request.get_json(force=True)
    result = enrollment_service.enroll(
        session["user_id"], data.get("course_id"), data.get("semester_id")
    )
    return (
        jsonify(
            enrollment_id=result.enrollment_id,
            course_id=result.course_id,
            semester_id=result.semester_id,
        ),
        201,
    )


@app.get("/api/enrollments/<int:enrollment_id>/attendance")
def get_attendance(enrollment_id: int):
    enrollment = enrollments.get_by_id(enrollment_id)
    if enrollment is None:
        return jsonify(error="Enrollment not found"), 404
    is_owner = session.get("role") == "student" and session.get("user_id") == enrollment.student_id
    is_admin = session.get("role") == "admin"
    if not (is_owner or is_admin):
        return jsonify(error="Not authorized"), 403
    return jsonify(attendance.list_by_enrollment(enrollment_id))


@app.post("/api/enrollments/<int:enrollment_id>/attendance")
@require_admin
def record_attendance(enrollment_id: int):
    data = request.get_json(force=True)
    status = data.get("status")
    if error := validate_enum(status, ALLOWED_ATTENDANCE_STATUSES, "status"):
        return error
    attendance_id = attendance.record(enrollment_id, data.get("session_date"), status)
    return jsonify(attendance_id=attendance_id), 201


# ---------------------------------------------------------------------
# Assignment submissions & grading
# ---------------------------------------------------------------------
@app.post("/api/assignments/<int:assignment_id>/submissions")
@require_student
def submit_assignment(assignment_id: int):
    submission_id = submissions.submit(assignment_id, session["user_id"])
    return jsonify(submission_id=submission_id), 201


@app.post("/api/submissions/<int:submission_id>/grade")
@require_admin
def grade_submission(submission_id: int):
    data = request.get_json(force=True)
    submissions.grade(submission_id, data.get("marks_obtained"))
    return jsonify(ok=True)


# ---------------------------------------------------------------------
# Exam results & grade computation
# ---------------------------------------------------------------------
@app.post("/api/exams/<int:exam_id>/results")
@require_admin
def record_exam_result(exam_id: int):
    data = request.get_json(force=True)
    result_id = exam_results.record(exam_id, data.get("student_id"), data.get("marks_obtained"))
    return jsonify(result_id=result_id), 201


@app.get("/api/exams/<int:exam_id>/results")
@require_admin
def list_exam_results(exam_id: int):
    return jsonify(exam_results.list_by_exam(exam_id))


@app.post("/api/enrollments/<int:enrollment_id>/compute-grade")
@require_admin
def compute_grade(enrollment_id: int):
    return jsonify(grading_service.compute_grade(enrollment_id))


@app.get("/api/me/grades")
@require_student
def my_grades():
    my_enrollment_rows = enrollments.list_by_student(session["user_id"])
    result = []
    for enr in my_enrollment_rows:
        grade = grades.get_by_enrollment(enr["enrollment_id"])
        if grade:
            result.append({**grade, "course_code": enr["course_code"], "course_title": enr["course_title"]})
    return jsonify(result)


# ---------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------
@app.get("/api/me/payments")
@require_student
def my_payments():
    return jsonify(payments.list_by_student(session["user_id"]))


@app.post("/api/students/<int:student_id>/payments")
@require_admin
def create_invoice(student_id: int):
    data = request.get_json(force=True)
    payment_id = payments.create_invoice(student_id, data.get("semester_id"), data.get("amount"))
    return jsonify(payment_id=payment_id), 201


@app.post("/api/me/payments/<int:payment_id>/pay")
@require_student
def pay_invoice(payment_id: int):
    data = request.get_json(force=True)
    method = data.get("method", "card")
    if error := validate_enum(method, ALLOWED_PAYMENT_METHODS, "method"):
        return error
    payments.mark_paid(payment_id, method)
    return jsonify(ok=True)


# ---------------------------------------------------------------------
# Certificates
# ---------------------------------------------------------------------
@app.post("/api/me/certificates")
@require_student
def request_certificate():
    data = request.get_json(force=True)
    cert_type = data.get("type", "transcript")
    if error := validate_enum(cert_type, ALLOWED_CERTIFICATE_TYPES, "type"):
        return error
    result = certificate_service.issue(session["user_id"], cert_type)
    return jsonify(result), 201


@app.get("/api/me/certificates")
@require_student
def my_certificates():
    return jsonify(certificates.list_by_student(session["user_id"]))


@app.get("/api/certificates/verify/<code>")
def verify_certificate(code: str):
    """Public verification lookup -- no login required, like scanning a QR code on a printed certificate."""
    cert = certificates.get_by_verification_code(code)
    if cert is None:
        return jsonify(error="No certificate found for that verification code"), 404
    return jsonify(cert)


# ---------------------------------------------------------------------
# Reports (Module 9 showcase)
# ---------------------------------------------------------------------
@app.get("/api/reports/departments")
@require_admin
def department_report():
    """CTE-based rollup."""
    return jsonify(reports.department_report())


@app.get("/api/reports/gpa-rankings")
@require_admin
def gpa_rankings():
    """Window functions: RANK() overall and per-department in one query."""
    department_id = request.args.get("department_id", type=int)
    return jsonify(reports.gpa_rankings(department_id))


@app.get("/api/reports/courses/<int:course_id>/toppers")
@require_admin
def course_toppers(course_id: int):
    return jsonify(reports.course_toppers(course_id))


@app.get("/api/reports/semesters")
@require_admin
def semester_report():
    """Reads the materialized view (fast, but only as fresh as the last refresh)."""
    return jsonify(reports.semester_report())


@app.post("/api/reports/semesters/refresh")
@require_admin
def refresh_semester_report():
    reports.refresh_semester_report()
    return jsonify(ok=True)


@app.get("/api/reports/admin-dashboard")
@require_admin
def admin_dashboard():
    return jsonify(reports.admin_dashboard())


@app.get("/api/reports/teachers-dashboard")
@require_admin
def teachers_dashboard():
    teacher_id = request.args.get("teacher_id", type=int)
    return jsonify(reports.teacher_dashboard(teacher_id))


@app.get("/api/me/dashboard")
@require_student
def my_dashboard():
    return jsonify(reports.student_dashboard(session["user_id"]))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
