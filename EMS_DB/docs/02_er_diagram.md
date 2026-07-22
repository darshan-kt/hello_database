# Module 2-3-4 — Database Design, ER Diagram, Normalization

## Entity-Relationship Diagram

```text
Departments (self-referential: parent_department_id)
  │
  ├──< Teachers
  ├──< Students
  └──< Courses ──< CoursePrerequisites >── Courses (self-referential)
         │
         ├──< Assignments ──< AssignmentSubmissions >── Students
         │
         └──< Exams ──< ExamResults >── Students

Students ──< Enrollments >── Courses           (also carries semester_id)
  │              │
  │              ├──< Attendance
  │              └──1:1── Grades
  │
  ├──< Payments (per semester)
  └──< Certificates

Semesters ──< Enrollments, Exams, Payments
Admins  (independent login table, no FK into the academic graph)
```

Cardinalities:

- `Departments 1 --- * Departments` (self-referential hierarchy: a
  "School" is a department with `parent_department_id IS NULL`)
- `Departments 1 --- * Teachers`, `Departments 1 --- * Students`,
  `Departments 1 --- * Courses`
- `Courses * --- * Courses` via `CoursePrerequisites` (a course can
  require several prerequisites; a course can be a prerequisite for
  several others)
- `Students * --- * Courses` via `Enrollments` (also scoped by
  `Semesters`, so the same student+course pair can re-enroll in a later
  semester — the uniqueness constraint is on the triple)
- `Enrollments 1 --- * Attendance`, `Enrollments 1 --- 1 Grades`
- `Courses 1 --- * Assignments`, `Assignments * --- * Students` via
  `AssignmentSubmissions`
- `Courses 1 --- * Exams`, `Exams * --- * Students` via `ExamResults`
- `Students 1 --- * Payments` (one per semester), `Students 1 --- * Certificates`

## Normalization

Target: **3NF**, with the same kind of deliberate, documented exception
used in the e-commerce project.

- **1NF**: no repeating groups — e.g. `AssignmentSubmissions` is its own
  table rather than a comma-separated list of student ids on
  `assignments`.
- **2NF**: every table uses a single-column surrogate key, so partial
  key dependency cannot occur.
- **3NF**: no transitive dependencies — e.g. `Courses.department_id`
  points at the department directly rather than being derived from
  `Courses.teacher_id → Teachers.department_id` (a teacher could
  theoretically teach a cross-listed course outside their home
  department, so this is a real independent fact, not a denormalized
  copy).

### Deliberate denormalization

- **`Grades`** stores a computed `total_marks` / `letter_grade` /
  `gpa_points` per enrollment rather than deriving it on every read from
  `ExamResults` + `AssignmentSubmissions`. Grade computation is a
  business event (Phase F — "compute grade"), not a live view, because
  once a grade is finalized it should not silently change if a teacher
  edits an old exam result after the fact — the same "snapshot, not live
  lookup" argument used for `order_items.unit_price` in the e-commerce
  project.
- **`Payments`** is one row per `(student_id, semester_id)`, not a
  running ledger of transactions — sufficient for "is this semester's
  fee paid," which is the only thing the certificate-eligibility rule
  needs.

## Constraints summary

| Table | Key constraints |
|---|---|
| departments | PK; UNIQUE(name), UNIQUE(code); FK parent_department_id → self (nullable) |
| teachers | PK; UNIQUE(email); FK department_id |
| students | PK; UNIQUE(email); FK department_id |
| admins | PK; UNIQUE(email) |
| semesters | PK; UNIQUE(name); CHECK(end_date > start_date) |
| courses | PK; UNIQUE(code); FK department_id, teacher_id; CHECK(credits > 0, capacity > 0) |
| course_prerequisites | PK(course_id, prerequisite_course_id); CHECK(course_id <> prerequisite_course_id) |
| enrollments | PK; FK student_id, course_id, semester_id; UNIQUE(student_id, course_id, semester_id) |
| attendance | PK; FK enrollment_id; UNIQUE(enrollment_id, session_date) |
| assignments | PK; FK course_id; `settings JSONB` |
| assignment_submissions | PK; FK assignment_id, student_id; UNIQUE(assignment_id, student_id) |
| exams | PK; FK course_id, semester_id; CHECK(max_marks > 0) |
| exam_results | PK; FK exam_id, student_id; UNIQUE(exam_id, student_id); CHECK(marks_obtained >= 0) |
| grades | PK; FK enrollment_id; UNIQUE(enrollment_id); CHECK(gpa_points BETWEEN 0 AND 4) |
| payments | PK; FK student_id, semester_id; UNIQUE(student_id, semester_id); CHECK(amount >= 0) |
| certificates | PK; FK student_id; UNIQUE(verification_code) |

## Advanced PostgreSQL features used (Module 9), and where

| Feature | Where |
|---|---|
| CTEs | `department_report()` — department-level rollups via `WITH` |
| Window functions | `gpa_rankings()` — `RANK() OVER (PARTITION BY department_id ORDER BY gpa DESC)` |
| Views | `student_dashboard_view`, `teacher_dashboard_view`, `admin_dashboard_view` |
| Materialized view | `semester_report_mv`, refreshed on demand |
| JSONB | `assignments.settings` — deadline/rubric/attachments/late penalty |
| Full-text search | `courses.search_vector` (generated `tsvector` + GIN index); teacher/student name search via functional GIN indexes |
| Recursive CTE | department hierarchy (`WITH RECURSIVE`); course prerequisite chain (transitive closure) |

See `docs/03_optimization.md` for `EXPLAIN ANALYZE` evidence on each of
these, and `docs/04_interactive_learning.md` for how to run them
yourself via `make`.
