-- Education Management System schema
-- Module 5: PostgreSQL Implementation
-- Target: PostgreSQL 16+

-- ---------------------------------------------------------------------
-- Enum types
-- ---------------------------------------------------------------------
CREATE TYPE enrollment_status AS ENUM ('enrolled', 'completed', 'dropped');
CREATE TYPE attendance_status AS ENUM ('present', 'absent', 'late');
CREATE TYPE payment_status    AS ENUM ('pending', 'paid', 'failed');
CREATE TYPE payment_method    AS ENUM ('card', 'bank_transfer', 'cash');
CREATE TYPE certificate_type  AS ENUM ('transcript', 'completion');

-- ---------------------------------------------------------------------
-- Departments (self-referential: a "School" is a department with no parent)
-- ---------------------------------------------------------------------
CREATE TABLE departments (
    department_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    parent_department_id BIGINT REFERENCES departments(department_id) ON DELETE RESTRICT,
    name                  VARCHAR(150) NOT NULL,
    code                  VARCHAR(20)  NOT NULL,
    created_at            TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT uq_departments_name UNIQUE (name),
    CONSTRAINT uq_departments_code UNIQUE (code)
);

CREATE INDEX idx_departments_parent ON departments(parent_department_id);

-- ---------------------------------------------------------------------
-- Admins (registrar staff; login-capable, not self-service-registerable)
-- ---------------------------------------------------------------------
CREATE TABLE admins (
    admin_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name          VARCHAR(120) NOT NULL,
    email         VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT uq_admins_email UNIQUE (email)
);

-- ---------------------------------------------------------------------
-- Teachers
-- ---------------------------------------------------------------------
CREATE TABLE teachers (
    teacher_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    department_id BIGINT NOT NULL REFERENCES departments(department_id) ON DELETE RESTRICT,
    name          VARCHAR(120) NOT NULL,
    email         VARCHAR(255) NOT NULL,
    hire_date     DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT uq_teachers_email UNIQUE (email)
);

CREATE INDEX idx_teachers_department ON teachers(department_id);
CREATE INDEX idx_teachers_name_search ON teachers USING GIN (to_tsvector('english', name));

-- ---------------------------------------------------------------------
-- Students (login-capable)
-- ---------------------------------------------------------------------
CREATE TABLE students (
    student_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    department_id    BIGINT NOT NULL REFERENCES departments(department_id) ON DELETE RESTRICT,
    name             VARCHAR(120) NOT NULL,
    email            VARCHAR(255) NOT NULL,
    password_hash    VARCHAR(255) NOT NULL,
    date_of_birth    DATE,
    enrollment_date  DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT uq_students_email UNIQUE (email)
);

CREATE INDEX idx_students_department ON students(department_id);
CREATE INDEX idx_students_name_search ON students USING GIN (to_tsvector('english', name));

-- ---------------------------------------------------------------------
-- Semesters
-- ---------------------------------------------------------------------
CREATE TABLE semesters (
    semester_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        VARCHAR(50) NOT NULL,
    start_date  DATE NOT NULL,
    end_date    DATE NOT NULL,
    CONSTRAINT uq_semesters_name UNIQUE (name),
    CONSTRAINT chk_semesters_dates CHECK (end_date > start_date)
);

-- ---------------------------------------------------------------------
-- Courses
-- ---------------------------------------------------------------------
CREATE TABLE courses (
    course_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    department_id  BIGINT NOT NULL REFERENCES departments(department_id) ON DELETE RESTRICT,
    teacher_id     BIGINT NOT NULL REFERENCES teachers(teacher_id) ON DELETE RESTRICT,
    code           VARCHAR(20)  NOT NULL,
    title          VARCHAR(200) NOT NULL,
    description    TEXT,
    credits        INT NOT NULL,
    capacity       INT NOT NULL,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    search_vector  tsvector GENERATED ALWAYS AS (
                       to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, ''))
                   ) STORED,
    CONSTRAINT uq_courses_code UNIQUE (code),
    CONSTRAINT chk_courses_credits_pos CHECK (credits > 0),
    CONSTRAINT chk_courses_capacity_pos CHECK (capacity > 0)
);

CREATE INDEX idx_courses_department ON courses(department_id);
CREATE INDEX idx_courses_teacher ON courses(teacher_id);
CREATE INDEX idx_courses_search ON courses USING GIN (search_vector);

-- ---------------------------------------------------------------------
-- Course prerequisites (self-referential bridge; transitive closure is
-- computed with a recursive CTE at query time, see report_repository.py)
-- ---------------------------------------------------------------------
CREATE TABLE course_prerequisites (
    course_id              BIGINT NOT NULL REFERENCES courses(course_id) ON DELETE CASCADE,
    prerequisite_course_id BIGINT NOT NULL REFERENCES courses(course_id) ON DELETE RESTRICT,
    PRIMARY KEY (course_id, prerequisite_course_id),
    CONSTRAINT chk_prereq_not_self CHECK (course_id <> prerequisite_course_id)
);

CREATE INDEX idx_course_prereq_reverse ON course_prerequisites(prerequisite_course_id);

-- ---------------------------------------------------------------------
-- Enrollments (many-to-many bridge: student x course x semester)
-- ---------------------------------------------------------------------
CREATE TABLE enrollments (
    enrollment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_id    BIGINT NOT NULL REFERENCES students(student_id) ON DELETE RESTRICT,
    course_id     BIGINT NOT NULL REFERENCES courses(course_id) ON DELETE RESTRICT,
    semester_id   BIGINT NOT NULL REFERENCES semesters(semester_id) ON DELETE RESTRICT,
    status        enrollment_status NOT NULL DEFAULT 'enrolled',
    enrolled_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_enrollments_student_course_semester UNIQUE (student_id, course_id, semester_id)
);

CREATE INDEX idx_enrollments_student ON enrollments(student_id);
CREATE INDEX idx_enrollments_course ON enrollments(course_id);
CREATE INDEX idx_enrollments_semester ON enrollments(semester_id);
-- Supports "how many seats are taken in this course this semester" (the
-- capacity check) without a full table scan.
CREATE INDEX idx_enrollments_course_semester ON enrollments(course_id, semester_id);

-- ---------------------------------------------------------------------
-- Attendance
-- ---------------------------------------------------------------------
CREATE TABLE attendance (
    attendance_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    enrollment_id BIGINT NOT NULL REFERENCES enrollments(enrollment_id) ON DELETE CASCADE,
    session_date  DATE NOT NULL,
    status        attendance_status NOT NULL,
    CONSTRAINT uq_attendance_enrollment_date UNIQUE (enrollment_id, session_date)
);

CREATE INDEX idx_attendance_enrollment ON attendance(enrollment_id);

-- ---------------------------------------------------------------------
-- Assignments (JSONB settings: deadline, rubric, attachments, late penalty)
-- ---------------------------------------------------------------------
CREATE TABLE assignments (
    assignment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    course_id     BIGINT NOT NULL REFERENCES courses(course_id) ON DELETE CASCADE,
    title         VARCHAR(200) NOT NULL,
    settings      JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_assignments_course ON assignments(course_id);
-- GIN index for containment/key-existence queries on the JSONB settings,
-- e.g. `settings @> '{"late_penalty": true}'` or `settings ? 'rubric'`.
CREATE INDEX idx_assignments_settings ON assignments USING GIN (settings);

CREATE TABLE assignment_submissions (
    submission_id  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    assignment_id  BIGINT NOT NULL REFERENCES assignments(assignment_id) ON DELETE CASCADE,
    student_id     BIGINT NOT NULL REFERENCES students(student_id) ON DELETE RESTRICT,
    submitted_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    marks_obtained NUMERIC(6, 2),
    CONSTRAINT uq_submission_assignment_student UNIQUE (assignment_id, student_id),
    CONSTRAINT chk_submission_marks_nonneg CHECK (marks_obtained IS NULL OR marks_obtained >= 0)
);

CREATE INDEX idx_submissions_assignment ON assignment_submissions(assignment_id);
CREATE INDEX idx_submissions_student ON assignment_submissions(student_id);

-- ---------------------------------------------------------------------
-- Exams
-- ---------------------------------------------------------------------
CREATE TABLE exams (
    exam_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    course_id   BIGINT NOT NULL REFERENCES courses(course_id) ON DELETE CASCADE,
    semester_id BIGINT NOT NULL REFERENCES semesters(semester_id) ON DELETE RESTRICT,
    name        VARCHAR(50) NOT NULL,
    exam_date   DATE NOT NULL,
    max_marks   NUMERIC(6, 2) NOT NULL,
    CONSTRAINT chk_exams_max_marks_pos CHECK (max_marks > 0)
);

CREATE INDEX idx_exams_course ON exams(course_id);
CREATE INDEX idx_exams_semester ON exams(semester_id);

CREATE TABLE exam_results (
    result_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_id        BIGINT NOT NULL REFERENCES exams(exam_id) ON DELETE CASCADE,
    student_id     BIGINT NOT NULL REFERENCES students(student_id) ON DELETE RESTRICT,
    marks_obtained NUMERIC(6, 2) NOT NULL,
    CONSTRAINT uq_exam_results_exam_student UNIQUE (exam_id, student_id),
    CONSTRAINT chk_exam_results_marks_nonneg CHECK (marks_obtained >= 0)
);

CREATE INDEX idx_exam_results_exam ON exam_results(exam_id);
CREATE INDEX idx_exam_results_student ON exam_results(student_id);

-- ---------------------------------------------------------------------
-- Grades (one computed row per enrollment -- see Module 8 Phase F)
-- ---------------------------------------------------------------------
CREATE TABLE grades (
    grade_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    enrollment_id BIGINT NOT NULL REFERENCES enrollments(enrollment_id) ON DELETE CASCADE,
    total_percent NUMERIC(5, 2) NOT NULL,
    letter_grade  VARCHAR(2) NOT NULL,
    gpa_points    NUMERIC(3, 2) NOT NULL,
    computed_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_grades_enrollment UNIQUE (enrollment_id),
    CONSTRAINT chk_grades_gpa_range CHECK (gpa_points BETWEEN 0 AND 4)
);

-- ---------------------------------------------------------------------
-- Payments (one fee invoice per student per semester)
-- ---------------------------------------------------------------------
CREATE TABLE payments (
    payment_id  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_id  BIGINT NOT NULL REFERENCES students(student_id) ON DELETE RESTRICT,
    semester_id BIGINT NOT NULL REFERENCES semesters(semester_id) ON DELETE RESTRICT,
    amount      NUMERIC(10, 2) NOT NULL,
    status      payment_status NOT NULL DEFAULT 'pending',
    method      payment_method,
    paid_at     TIMESTAMPTZ,
    CONSTRAINT uq_payments_student_semester UNIQUE (student_id, semester_id),
    CONSTRAINT chk_payments_amount_nonneg CHECK (amount >= 0)
);

CREATE INDEX idx_payments_student ON payments(student_id);
CREATE INDEX idx_payments_semester ON payments(semester_id);

-- ---------------------------------------------------------------------
-- Certificates
-- ---------------------------------------------------------------------
CREATE TABLE certificates (
    certificate_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_id         BIGINT NOT NULL REFERENCES students(student_id) ON DELETE RESTRICT,
    type               certificate_type NOT NULL,
    verification_code  VARCHAR(40) NOT NULL,
    issued_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_certificates_verification_code UNIQUE (verification_code)
);

CREATE INDEX idx_certificates_student ON certificates(student_id);

-- =======================================================================
-- Module 9 -- Views (student / teacher / admin dashboards)
-- Each pre-aggregates in its own CTE before joining, to avoid fan-out
-- from joining multiple one-to-many relations (attendance x payments,
-- etc.) directly in one query.
-- =======================================================================

CREATE VIEW student_dashboard_view AS
WITH enrollment_counts AS (
    SELECT student_id, COUNT(*) AS total_enrollments
    FROM enrollments
    GROUP BY student_id
),
gpa_avg AS (
    SELECT e.student_id, ROUND(AVG(g.gpa_points)::numeric, 2) AS gpa
    FROM enrollments e
    JOIN grades g ON g.enrollment_id = e.enrollment_id
    GROUP BY e.student_id
),
attendance_pct AS (
    SELECT e.student_id,
           ROUND(100.0 * COUNT(*) FILTER (WHERE a.status = 'present') / NULLIF(COUNT(*), 0), 1) AS attendance_pct
    FROM enrollments e
    JOIN attendance a ON a.enrollment_id = e.enrollment_id
    GROUP BY e.student_id
),
pending AS (
    SELECT student_id, COUNT(*) AS pending_payments
    FROM payments
    WHERE status = 'pending'
    GROUP BY student_id
)
SELECT
    s.student_id,
    s.name AS student_name,
    d.name AS department_name,
    COALESCE(ec.total_enrollments, 0) AS total_enrollments,
    ga.gpa,
    ap.attendance_pct,
    COALESCE(pd.pending_payments, 0) AS pending_payments
FROM students s
JOIN departments d ON d.department_id = s.department_id
LEFT JOIN enrollment_counts ec ON ec.student_id = s.student_id
LEFT JOIN gpa_avg ga ON ga.student_id = s.student_id
LEFT JOIN attendance_pct ap ON ap.student_id = s.student_id
LEFT JOIN pending pd ON pd.student_id = s.student_id;

CREATE VIEW teacher_dashboard_view AS
WITH course_counts AS (
    SELECT teacher_id, COUNT(*) AS course_count
    FROM courses
    GROUP BY teacher_id
),
student_counts AS (
    SELECT c.teacher_id, COUNT(DISTINCT e.student_id) AS student_count
    FROM courses c
    JOIN enrollments e ON e.course_id = c.course_id
    GROUP BY c.teacher_id
),
pending_grading AS (
    SELECT c.teacher_id, COUNT(*) AS pending_grading
    FROM courses c
    JOIN assignments a ON a.course_id = c.course_id
    JOIN assignment_submissions sub ON sub.assignment_id = a.assignment_id
    WHERE sub.marks_obtained IS NULL
    GROUP BY c.teacher_id
)
SELECT
    t.teacher_id,
    t.name AS teacher_name,
    d.name AS department_name,
    COALESCE(cc.course_count, 0) AS course_count,
    COALESCE(sc.student_count, 0) AS student_count,
    COALESCE(pg.pending_grading, 0) AS pending_grading
FROM teachers t
JOIN departments d ON d.department_id = t.department_id
LEFT JOIN course_counts cc ON cc.teacher_id = t.teacher_id
LEFT JOIN student_counts sc ON sc.teacher_id = t.teacher_id
LEFT JOIN pending_grading pg ON pg.teacher_id = t.teacher_id;

CREATE VIEW admin_dashboard_view AS
SELECT
    (SELECT COUNT(*) FROM students)                                   AS total_students,
    (SELECT COUNT(*) FROM teachers)                                   AS total_teachers,
    (SELECT COUNT(*) FROM courses)                                    AS total_courses,
    (SELECT COUNT(*) FROM departments)                                AS total_departments,
    (SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'paid') AS total_revenue,
    (SELECT COUNT(*) FROM payments WHERE status = 'pending')          AS pending_payments,
    (SELECT ROUND(AVG(gpa_points)::numeric, 2) FROM grades)           AS overall_avg_gpa;

-- =======================================================================
-- Module 9 -- Materialized view: per-semester report
-- Refreshed on demand (`make refresh-report` / POST /api/reports/refresh),
-- not on every write -- semester rollups don't need to be real-time.
-- =======================================================================

CREATE MATERIALIZED VIEW semester_report_mv AS
WITH enrollment_counts AS (
    SELECT semester_id, COUNT(*) AS enrollment_count
    FROM enrollments
    GROUP BY semester_id
),
revenue AS (
    SELECT semester_id, COALESCE(SUM(amount), 0) AS revenue
    FROM payments
    WHERE status = 'paid'
    GROUP BY semester_id
),
grade_avg AS (
    SELECT e.semester_id, ROUND(AVG(g.gpa_points)::numeric, 2) AS avg_gpa
    FROM enrollments e
    JOIN grades g ON g.enrollment_id = e.enrollment_id
    GROUP BY e.semester_id
),
attendance_avg AS (
    SELECT e.semester_id,
           ROUND(100.0 * COUNT(*) FILTER (WHERE a.status = 'present') / NULLIF(COUNT(*), 0), 1) AS avg_attendance_pct
    FROM enrollments e
    JOIN attendance a ON a.enrollment_id = e.enrollment_id
    GROUP BY e.semester_id
)
SELECT
    s.semester_id,
    s.name AS semester_name,
    s.start_date,
    s.end_date,
    COALESCE(ec.enrollment_count, 0) AS enrollment_count,
    COALESCE(r.revenue, 0) AS revenue,
    ga.avg_gpa,
    aa.avg_attendance_pct
FROM semesters s
LEFT JOIN enrollment_counts ec ON ec.semester_id = s.semester_id
LEFT JOIN revenue r ON r.semester_id = s.semester_id
LEFT JOIN grade_avg ga ON ga.semester_id = s.semester_id
LEFT JOIN attendance_avg aa ON aa.semester_id = s.semester_id;

-- A unique index is what makes `REFRESH MATERIALIZED VIEW CONCURRENTLY`
-- possible -- without one, refreshing takes an exclusive lock that blocks
-- reads of the view for the duration of the refresh.
CREATE UNIQUE INDEX idx_semester_report_mv_semester ON semester_report_mv(semester_id);
