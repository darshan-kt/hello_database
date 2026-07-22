# Module 0-1 — Requirement Analysis & Domain Modeling

## Business Problem

A university currently manages everything in spreadsheets: duplicate
student records, manual attendance, no reliable GPA calculation, no
enrollment history, no reporting. Build the backend for a real academic
system: departments, teachers, students, courses, semesters,
enrollments, attendance, assignments, exams, grades, payments, and
certificates — plus the reporting a registrar's office actually needs.

## Actors

- **Student** — registers, browses/searches courses, enrolls (subject to
  capacity), views attendance/grades/GPA rank, pays fees, downloads a
  certificate once eligible.
- **Admin / registrar** — manages departments, teachers, courses,
  semesters; records attendance and exam results; runs reports
  (department performance, semester revenue, GPA rankings, dashboards).

## Functional Requirements

1. A student registers with a unique email; a department is required
   (their "major").
2. Courses belong to a department and a teacher, have a fixed
   `capacity`, and may declare **prerequisites** (other courses) —
   transitively, not just one level deep.
3. Enrollment is **atomic and capacity-checked**: two students racing
   for the last seat must not both get in (mirrors the stock-locking
   problem from the e-commerce project, applied to seats instead of
   inventory).
4. Attendance is recorded per enrollment per session date; a session
   can only be marked once per student (no duplicate rows for the same
   day).
5. Assignments carry flexible, schema-light settings (deadline, rubric,
   attachments, late penalty) that vary by assignment — this is the
   natural fit for a `JSONB` column rather than a dozen nullable
   fixed columns.
6. Exams belong to a course + semester; results are recorded per
   student. A student's **final grade** for an enrollment is a computed
   roll-up of their exam results and assignment marks into a
   percentage, a letter grade, and GPA points (4.0 scale).
7. A **payment** (one fee invoice per student per semester) must be
   `paid` before a certificate can be issued for that student — this is
   a business rule enforced in the service layer, not just a UI
   affordance.
8. Departments can nest (a "School" containing several departments) —
   this is what motivates the recursive-hierarchy query in Module 9.

## Non-Functional Requirements

- Referential integrity at the database level (foreign keys), not just
  application code.
- Money as `NUMERIC`, never `FLOAT`.
- Enrollment is transactional with row-level locking to prevent
  overbooking a course.
- Reporting queries (GPA ranking, department performance, semester
  revenue) are the point of this project, not an afterthought — see
  Module 9 in `docs/02_er_diagram.md`'s companion doc and
  `docs/03_optimization.md`.

## Entities

| Entity | Description |
|---|---|
| Departments | Can nest (School → Department) via `parent_department_id` |
| Teachers | Belong to one department |
| Students | Belong to one department (major); login-capable |
| Admins | Registrar staff; login-capable. Conceptually not self-service-registerable in a real system — this build's login is demo-mode-permissive (see README's design decisions), which relaxes that on purpose |
| Semesters | e.g. "Fall 2025"; has a date range |
| Courses | Belong to a department + teacher; can declare prerequisites |
| CoursePrerequisites | Self-referential bridge on `courses` |
| Enrollments | Many-to-many bridge: student × course × semester |
| Attendance | One row per enrollment per session date |
| Assignments | Belong to a course; `settings` is `JSONB` |
| AssignmentSubmissions | Bridge: assignment × student, with a mark |
| Exams | Belong to a course + semester |
| ExamResults | Bridge: exam × student, with a mark |
| Grades | One computed row per enrollment (percentage, letter, GPA points) |
| Payments | One fee invoice per student per semester |
| Certificates | Issued to a student once payment + eligibility are satisfied |

## Scope decisions (v1)

The original brief suggests seeding **1,000 students / 5,000
enrollments / 25,000 attendance rows** — realistic for a production
load test, but not needed to make every reporting query in Module 9
meaningful, and it would make `make reset` slow for a learning project.
This build seeds ~150 students, ~40 courses, ~450 enrollments across two
semesters, and attendance/exam/assignment data sized to match — enough
for GPA rankings, department comparisons, and semester revenue reports
to show real variation, while staying fast to rebuild. See
`scripts/generate_seed_data.py` for exact counts and
`docs/04_interactive_learning.md` for how to inspect the result.

Full-text search and the recursive department-hierarchy/prerequisite
queries are built exactly as specified. Teacher and admin dashboards are
implemented as SQL views queryable by any authenticated admin (rather
than a separate teacher login portal) to keep the auth surface to two
roles (student, admin) — matching the pattern from the e-commerce
project rather than adding a third session type for a role with no
distinct write-permissions in this build.
