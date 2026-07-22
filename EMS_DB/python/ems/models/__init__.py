from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Optional


@dataclass
class Department:
    department_id: Optional[int]
    name: str
    code: str
    parent_department_id: Optional[int] = None
    created_at: Optional[datetime] = None


@dataclass
class Admin:
    admin_id: Optional[int]
    name: str
    email: str
    password_hash: str
    created_at: Optional[datetime] = None


@dataclass
class Teacher:
    teacher_id: Optional[int]
    department_id: int
    name: str
    email: str
    hire_date: Optional[date] = None
    created_at: Optional[datetime] = None


@dataclass
class Student:
    student_id: Optional[int]
    department_id: int
    name: str
    email: str
    password_hash: str
    date_of_birth: Optional[date] = None
    enrollment_date: Optional[date] = None
    created_at: Optional[datetime] = None


@dataclass
class Semester:
    semester_id: Optional[int]
    name: str
    start_date: date
    end_date: date


@dataclass
class Course:
    course_id: Optional[int]
    department_id: int
    teacher_id: int
    code: str
    title: str
    credits: int
    capacity: int
    description: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class Enrollment:
    enrollment_id: Optional[int]
    student_id: int
    course_id: int
    semester_id: int
    status: str = "enrolled"
    enrolled_at: Optional[datetime] = None


@dataclass
class Attendance:
    attendance_id: Optional[int]
    enrollment_id: int
    session_date: date
    status: str


@dataclass
class Assignment:
    assignment_id: Optional[int]
    course_id: int
    title: str
    settings: dict
    created_at: Optional[datetime] = None


@dataclass
class AssignmentSubmission:
    submission_id: Optional[int]
    assignment_id: int
    student_id: int
    submitted_at: Optional[datetime] = None
    marks_obtained: Optional[Decimal] = None


@dataclass
class Exam:
    exam_id: Optional[int]
    course_id: int
    semester_id: int
    name: str
    exam_date: date
    max_marks: Decimal


@dataclass
class ExamResult:
    result_id: Optional[int]
    exam_id: int
    student_id: int
    marks_obtained: Decimal


@dataclass
class Grade:
    grade_id: Optional[int]
    enrollment_id: int
    total_percent: Decimal
    letter_grade: str
    gpa_points: Decimal
    computed_at: Optional[datetime] = None


@dataclass
class Payment:
    payment_id: Optional[int]
    student_id: int
    semester_id: int
    amount: Decimal
    status: str = "pending"
    method: Optional[str] = None
    paid_at: Optional[datetime] = None


@dataclass
class Certificate:
    certificate_id: Optional[int]
    student_id: int
    type: str
    verification_code: str
    issued_at: Optional[datetime] = None
