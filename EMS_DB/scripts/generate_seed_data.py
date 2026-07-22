"""
Module 6 -- Seed Data.

Generates a realistic, reproducible academic dataset: a 2-level
department hierarchy, teachers, students, courses with prerequisite
chains, two completed semesters plus one active semester, enrollments,
attendance, assignments (JSONB settings), exam results, computed grades,
payments, and a handful of certificates.

Deliberately smaller than the "1000 students / 5000 enrollments" scale
suggested in the original brief -- see docs/01_requirements.md's "Scope
decisions" section for why. Grades and certificates are produced by
calling the real GradingService / CertificateService rather than
hand-computing them, so seeding also exercises that production code.

Usage:
    python scripts/generate_seed_data.py           # skips if already seeded
    python scripts/generate_seed_data.py --force    # wipes and reseeds
"""
import argparse
import random
import re
import uuid
from datetime import date, timedelta
from decimal import Decimal

from faker import Faker
from psycopg.types.json import Jsonb

from ems.db.connection import get_pool
from ems.security import hash_password
from ems.services.certificate_service import CertificateService
from ems.services.grading_service import GradingService

random.seed(42)
fake = Faker()
Faker.seed(42)

SCHOOLS = [
    ("School of Engineering", "SOE", [("Computer Science", "CS"), ("Electrical Engineering", "EE")]),
    ("School of Sciences", "SOS", [("Mathematics", "MATH"), ("Physics", "PHYS")]),
    ("School of Business", "SOB", [("Finance", "FIN"), ("Marketing", "MKT")]),
    ("School of Arts", "SOA", [("History", "HIST"), ("Fine Arts", "ART")]),
]

COURSE_TITLES = {
    "CS": ["Introduction to Programming", "Data Structures", "Algorithms", "Operating Systems", "Databases"],
    "EE": ["Circuit Theory", "Digital Logic Design", "Signals and Systems", "Electromagnetics", "Control Systems"],
    "MATH": ["Calculus I", "Linear Algebra", "Probability and Statistics", "Discrete Mathematics", "Real Analysis"],
    "PHYS": ["Classical Mechanics", "Electricity and Magnetism", "Thermodynamics", "Quantum Physics I", "Optics"],
    "FIN": ["Principles of Finance", "Corporate Finance", "Investment Analysis", "Financial Markets", "Risk Management"],
    "MKT": ["Marketing Fundamentals", "Consumer Behavior", "Digital Marketing", "Brand Management", "Market Research"],
    "HIST": ["World History I", "Modern European History", "American History", "Historiography", "Global Conflicts"],
    "ART": ["Drawing Fundamentals", "Art History I", "Sculpture", "Modern Art Movements", "Studio Practice"],
}
LEVELS = [101, 102, 201, 202, 301]

STUDENTS_PER_DEPT = 19
TEACHERS_PER_DEPT = 3

TABLES_IN_FK_ORDER = [
    "certificates", "payments", "grades", "exam_results", "exams",
    "assignment_submissions", "assignments", "attendance", "enrollments",
    "course_prerequisites", "courses", "semesters", "students", "teachers",
    "admins", "departments",
]


def slugify(name: str, idx: int) -> str:
    base = re.sub(r"[^a-z]", "", name.lower())
    return f"{base}{idx}"


def already_seeded(cur) -> bool:
    cur.execute("SELECT COUNT(*) AS n FROM students")
    return cur.fetchone()["n"] > 0


def wipe(cur):
    cur.execute(f"TRUNCATE TABLE {', '.join(TABLES_IN_FK_ORDER)} RESTART IDENTITY CASCADE")


def main(force: bool):
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            if already_seeded(cur) and not force:
                print("Database already has student data -- skipping. Pass --force to wipe and reseed.")
                return
            if force:
                print("==> --force: wiping existing data...")
                wipe(cur)
        conn.commit()

        # -----------------------------------------------------------------
        print("==> Departments (4 schools -> 8 departments)...")
        dept_ids: dict[str, int] = {}
        leaf_codes: list[str] = []
        with conn.cursor() as cur:
            for school_name, school_code, children in SCHOOLS:
                cur.execute(
                    "INSERT INTO departments (name, code) VALUES (%s, %s) RETURNING department_id",
                    (school_name, school_code),
                )
                school_id = cur.fetchone()["department_id"]
                dept_ids[school_code] = school_id
                for child_name, child_code in children:
                    cur.execute(
                        """INSERT INTO departments (name, code, parent_department_id)
                           VALUES (%s, %s, %s) RETURNING department_id""",
                        (child_name, child_code, school_id),
                    )
                    dept_ids[child_code] = cur.fetchone()["department_id"]
                    leaf_codes.append(child_code)
        conn.commit()

        # -----------------------------------------------------------------
        print("==> Admin account (admin@ems.test / admin-123)...")
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO admins (name, email, password_hash) VALUES (%s, %s, %s)",
                ("Registrar Admin", "admin@ems.test", hash_password("admin-123")),
            )
        conn.commit()

        # -----------------------------------------------------------------
        print(f"==> Teachers ({TEACHERS_PER_DEPT} per department)...")
        teacher_ids: dict[str, list[int]] = {code: [] for code in leaf_codes}
        with conn.cursor() as cur:
            for code in leaf_codes:
                for _ in range(TEACHERS_PER_DEPT):
                    name = fake.name()
                    email = slugify(name, random.randint(1000, 9999)) + "@faculty.campus.edu"
                    cur.execute(
                        """INSERT INTO teachers (department_id, name, email, hire_date)
                           VALUES (%s, %s, %s, %s) RETURNING teacher_id""",
                        (dept_ids[code], name, email, fake.date_between(start_date="-10y", end_date="-1y")),
                    )
                    teacher_ids[code].append(cur.fetchone()["teacher_id"])
        conn.commit()

        # -----------------------------------------------------------------
        print(f"==> Students (1 demo account + ~{STUDENTS_PER_DEPT} per department)...")
        student_ids: dict[str, list[int]] = {code: [] for code in leaf_codes}
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO students (department_id, name, email, password_hash, date_of_birth)
                   VALUES (%s, %s, %s, %s, %s) RETURNING student_id""",
                (dept_ids["CS"], "Demo Student", "demo.student@ems.test",
                 hash_password("learn-123"), date(2004, 5, 14)),
            )
            demo_id = cur.fetchone()["student_id"]
            student_ids["CS"].append(demo_id)

            idx = 0
            for code in leaf_codes:
                for _ in range(STUDENTS_PER_DEPT):
                    idx += 1
                    name = fake.name()
                    email = slugify(name, idx) + "@campus.edu"
                    dob = fake.date_of_birth(minimum_age=18, maximum_age=24)
                    cur.execute(
                        """INSERT INTO students (department_id, name, email, password_hash, date_of_birth)
                           VALUES (%s, %s, %s, %s, %s) RETURNING student_id""",
                        (dept_ids[code], name, email, hash_password(str(uuid.uuid4())), dob),
                    )
                    student_ids[code].append(cur.fetchone()["student_id"])
        conn.commit()

        # -----------------------------------------------------------------
        print("==> Semesters (2 completed + 1 active)...")
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO semesters (name, start_date, end_date) VALUES (%s,%s,%s) RETURNING semester_id",
                ("Fall 2025", date(2025, 9, 1), date(2025, 12, 20)),
            )
            fall25 = cur.fetchone()["semester_id"]
            cur.execute(
                "INSERT INTO semesters (name, start_date, end_date) VALUES (%s,%s,%s) RETURNING semester_id",
                ("Spring 2026", date(2026, 1, 10), date(2026, 5, 10)),
            )
            spring26 = cur.fetchone()["semester_id"]
            cur.execute(
                "INSERT INTO semesters (name, start_date, end_date) VALUES (%s,%s,%s) RETURNING semester_id",
                ("Summer 2026", date(2026, 6, 1), date(2026, 8, 15)),
            )
            summer26 = cur.fetchone()["semester_id"]
        conn.commit()

        completed_semesters = [fall25, spring26]
        active_semester = summer26
        semester_dates = {
            fall25: (date(2025, 9, 1), date(2025, 12, 20)),
            spring26: (date(2026, 1, 10), date(2026, 5, 10)),
            summer26: (date(2026, 6, 1), date.today()),
        }

        # -----------------------------------------------------------------
        print("==> Courses (5 per department, each department gets a 3-deep prerequisite chain)...")
        course_ids: dict[str, list[int]] = {}
        with conn.cursor() as cur:
            for code in leaf_codes:
                titles = COURSE_TITLES[code]
                dept_course_ids = []
                for i, level in enumerate(LEVELS):
                    teacher_id = random.choice(teacher_ids[code])
                    cur.execute(
                        """INSERT INTO courses (department_id, teacher_id, code, title, description, credits, capacity)
                           VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING course_id""",
                        (dept_ids[code], teacher_id, f"{code}{level}", titles[i],
                         fake.paragraph(nb_sentences=3), random.choice([3, 4]), random.randint(20, 35)),
                    )
                    dept_course_ids.append(cur.fetchone()["course_id"])
                course_ids[code] = dept_course_ids
                # 201 needs 101, 202 needs 201, 301 needs 202 -- a 3-deep chain
                cur.execute(
                    "INSERT INTO course_prerequisites (course_id, prerequisite_course_id) VALUES (%s,%s)",
                    (dept_course_ids[2], dept_course_ids[0]),
                )
                cur.execute(
                    "INSERT INTO course_prerequisites (course_id, prerequisite_course_id) VALUES (%s,%s)",
                    (dept_course_ids[3], dept_course_ids[2]),
                )
                cur.execute(
                    "INSERT INTO course_prerequisites (course_id, prerequisite_course_id) VALUES (%s,%s)",
                    (dept_course_ids[4], dept_course_ids[3]),
                )
        conn.commit()

        # -----------------------------------------------------------------
        print("==> Enrollments (2 courses/student/completed-semester + 1 in the active semester)...")
        enrollments_by_semester: dict[int, list[dict]] = {fall25: [], spring26: [], summer26: []}
        with conn.cursor() as cur:
            for code in leaf_codes:
                for sid in student_ids[code]:
                    for sem in completed_semesters:
                        for cid in random.sample(course_ids[code], k=2):
                            cur.execute(
                                """INSERT INTO enrollments (student_id, course_id, semester_id)
                                   VALUES (%s, %s, %s) RETURNING enrollment_id""",
                                (sid, cid, sem),
                            )
                            enrollments_by_semester[sem].append(
                                {"enrollment_id": cur.fetchone()["enrollment_id"], "student_id": sid, "course_id": cid}
                            )
                    cid = random.choice(course_ids[code])
                    cur.execute(
                        """INSERT INTO enrollments (student_id, course_id, semester_id)
                           VALUES (%s, %s, %s) RETURNING enrollment_id""",
                        (sid, cid, active_semester),
                    )
                    enrollments_by_semester[active_semester].append(
                        {"enrollment_id": cur.fetchone()["enrollment_id"], "student_id": sid, "course_id": cid}
                    )
        conn.commit()
        total_enrollments = sum(len(v) for v in enrollments_by_semester.values())
        print(f"    {total_enrollments} enrollments created")

        # -----------------------------------------------------------------
        print("==> Attendance sessions...")
        with conn.cursor() as cur:
            for sem, enrollments in enrollments_by_semester.items():
                start, end = semester_dates[sem]
                total_days = max((end - start).days, 1)
                n_sessions = 12 if sem in completed_semesters else 4
                for enr in enrollments:
                    for d in sorted(random.sample(range(total_days), k=min(n_sessions, total_days))):
                        session_date = start + timedelta(days=d)
                        status = random.choices(["present", "absent", "late"], weights=[85, 10, 5])[0]
                        cur.execute(
                            """INSERT INTO attendance (enrollment_id, session_date, status)
                               VALUES (%s, %s, %s) ON CONFLICT DO NOTHING""",
                            (enr["enrollment_id"], session_date, status),
                        )
        conn.commit()

        # -----------------------------------------------------------------
        print("==> Assignments (JSONB settings: deadline, rubric, attachments, ~half with a late penalty)...")
        assignments_by_course: dict[int, list[int]] = {}
        with conn.cursor() as cur:
            for code in leaf_codes:
                for cid in course_ids[code]:
                    course_assignments = []
                    for n in (1, 2):
                        settings = {
                            "submission_deadline": (date(2025, 10, 1) + timedelta(days=30 * n)).isoformat(),
                            "rubric": {"criteria": ["correctness", "clarity", "effort"], "max_score": 100},
                            "attachments": [f"assignment{n}_instructions.pdf"],
                        }
                        if random.random() < 0.5:
                            settings["late_penalty"] = 5 * n
                        cur.execute(
                            """INSERT INTO assignments (course_id, title, settings)
                               VALUES (%s, %s, %s) RETURNING assignment_id""",
                            (cid, f"Homework {n}", Jsonb(settings)),
                        )
                        course_assignments.append(cur.fetchone()["assignment_id"])
                    assignments_by_course[cid] = course_assignments
        conn.commit()

        # -----------------------------------------------------------------
        print("==> Assignment submissions...")
        with conn.cursor() as cur:
            for sem, enrollments in enrollments_by_semester.items():
                is_completed = sem in completed_semesters
                for enr in enrollments:
                    for i, aid in enumerate(assignments_by_course[enr["course_id"]]):
                        if not is_completed and i == 1 and random.random() < 0.5:
                            continue  # active semester's 2nd assignment: not everyone has submitted yet
                        submit_ungraded = not is_completed and i == 1
                        marks = None if submit_ungraded else round(random.uniform(55, 98), 2)
                        cur.execute(
                            """INSERT INTO assignment_submissions (assignment_id, student_id, marks_obtained)
                               VALUES (%s, %s, %s) ON CONFLICT DO NOTHING""",
                            (aid, enr["student_id"], marks),
                        )
        conn.commit()

        # -----------------------------------------------------------------
        print("==> Exams (Midterm always, Final only once a semester has completed)...")
        exams_by_course_sem: dict[tuple, int] = {}
        with conn.cursor() as cur:
            for sem, enrollments in enrollments_by_semester.items():
                is_completed = sem in completed_semesters
                start, end = semester_dates[sem]
                for cid in {enr["course_id"] for enr in enrollments}:
                    cur.execute(
                        """INSERT INTO exams (course_id, semester_id, name, exam_date, max_marks)
                           VALUES (%s, %s, %s, %s, %s) RETURNING exam_id""",
                        (cid, sem, "Midterm", start + timedelta(days=45), Decimal("50")),
                    )
                    exams_by_course_sem[(cid, sem, "midterm")] = cur.fetchone()["exam_id"]
                    if is_completed:
                        cur.execute(
                            """INSERT INTO exams (course_id, semester_id, name, exam_date, max_marks)
                               VALUES (%s, %s, %s, %s, %s) RETURNING exam_id""",
                            (cid, sem, "Final", end - timedelta(days=5), Decimal("100")),
                        )
                        exams_by_course_sem[(cid, sem, "final")] = cur.fetchone()["exam_id"]
        conn.commit()

        print("==> Exam results...")
        with conn.cursor() as cur:
            for sem, enrollments in enrollments_by_semester.items():
                is_completed = sem in completed_semesters
                for enr in enrollments:
                    midterm_id = exams_by_course_sem[(enr["course_id"], sem, "midterm")]
                    cur.execute(
                        """INSERT INTO exam_results (exam_id, student_id, marks_obtained)
                           VALUES (%s, %s, %s) ON CONFLICT DO NOTHING""",
                        (midterm_id, enr["student_id"], round(random.uniform(25, 49), 2)),
                    )
                    if is_completed:
                        final_id = exams_by_course_sem[(enr["course_id"], sem, "final")]
                        cur.execute(
                            """INSERT INTO exam_results (exam_id, student_id, marks_obtained)
                               VALUES (%s, %s, %s) ON CONFLICT DO NOTHING""",
                            (final_id, enr["student_id"], round(random.uniform(55, 98), 2)),
                        )
        conn.commit()

        # -----------------------------------------------------------------
        print("==> Computing grades for completed semesters (via the real GradingService)...")
        grading_service = GradingService()
        computed = 0
        for sem in completed_semesters:
            for enr in enrollments_by_semester[sem]:
                try:
                    grading_service.compute_grade(enr["enrollment_id"])
                    computed += 1
                except Exception as exc:
                    print(f"    (skipped enrollment {enr['enrollment_id']}: {exc})")
        print(f"    {computed} grades computed")

        # -----------------------------------------------------------------
        print("==> Payments (one invoice per student per semester they were enrolled in)...")
        with conn.cursor() as cur:
            for sem, enrollments in enrollments_by_semester.items():
                is_completed = sem in completed_semesters
                amount = Decimal("45000.00") if is_completed else Decimal("48000.00")
                for sid in {enr["student_id"] for enr in enrollments}:
                    if is_completed:
                        status = random.choices(["paid", "pending", "failed"], weights=[80, 12, 8])[0]
                    else:
                        status = random.choices(["paid", "pending"], weights=[50, 50])[0]
                    method = random.choice(["card", "bank_transfer", "cash"]) if status == "paid" else None
                    paid_at_expr = "now()" if status == "paid" else "NULL"
                    cur.execute(
                        f"""INSERT INTO payments (student_id, semester_id, amount, status, method, paid_at)
                            VALUES (%s, %s, %s, %s, %s, {paid_at_expr})
                            ON CONFLICT DO NOTHING""",
                        (sid, sem, amount, status, method),
                    )

            # Make the demo student's payment story deterministic and
            # instructive: one pending invoice (so "issue certificate"
            # fails once, on purpose, in the UI walkthrough), rest paid.
            cur.execute(
                "SELECT payment_id FROM payments WHERE student_id = %s ORDER BY semester_id", (demo_id,)
            )
            demo_payments = cur.fetchall()
            for i, p in enumerate(demo_payments):
                if i == 0:
                    cur.execute(
                        "UPDATE payments SET status='pending', method=NULL, paid_at=NULL WHERE payment_id=%s",
                        (p["payment_id"],),
                    )
                else:
                    cur.execute(
                        "UPDATE payments SET status='paid', method='card', paid_at=now() WHERE payment_id=%s",
                        (p["payment_id"],),
                    )
        conn.commit()

        # -----------------------------------------------------------------
        print("==> Certificates for a handful of fully-paid students...")
        with conn.cursor() as cur:
            cur.execute(
                """SELECT student_id FROM students
                   WHERE student_id != %s AND student_id NOT IN (
                       SELECT student_id FROM payments WHERE status != 'paid'
                   )
                   ORDER BY random() LIMIT 15""",
                (demo_id,),
            )
            eligible = [r["student_id"] for r in cur.fetchall()]
        cert_service = CertificateService()
        issued = 0
        for sid in eligible:
            try:
                cert_service.issue(sid, "transcript")
                issued += 1
            except Exception as exc:
                print(f"    (skipped certificate for student {sid}: {exc})")
        print(f"    {issued} certificates issued")

        # -----------------------------------------------------------------
        print("==> Refreshing semester_report_mv...")
        with conn.cursor() as cur:
            cur.execute("REFRESH MATERIALIZED VIEW semester_report_mv")
        conn.commit()

        # -----------------------------------------------------------------
        # Bulk-loading thousands of rows leaves the query planner with
        # stale/default statistics until autovacuum gets around to it --
        # until then it can misjudge row estimates and pick a worse plan
        # (verified: right after a fresh load, a department lookup on the
        # 40-row `courses` table picked an index scan; after ANALYZE, it
        # correctly switches to the cheaper sequential scan). Run it
        # explicitly so `make explain` shows accurate plans immediately.
        print("==> Running ANALYZE so the query planner has fresh statistics...")
        with conn.cursor() as cur:
            cur.execute("ANALYZE")
        conn.commit()

    print("\nSeed complete.")
    print("  Admin login:  admin@ems.test / admin-123")
    print("  Demo student: demo.student@ems.test / learn-123 (has one pending invoice on purpose)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="wipe existing data and reseed")
    args = parser.parse_args()
    main(force=args.force)
