# Interactive Learning Guide

Like the mini e-commerce project, this system is built so you can learn
by *doing* — one `make` command at a time. This project's focus is
**advanced PostgreSQL** (CTEs, window functions, recursive queries,
materialized views, JSONB, full-text search), so the guided tour spends
most of its time there.

Requires: `docker`, `make`, `curl`, `jq`.

Full command reference: `make help`. This document is the guided tour —
what to run, in what order, and *why*, mapped back to the PostgreSQL
concept each step teaches.

---

## Stage 0 — Start the environment and load data

```bash
make up
make seed
```

**What happens:** `docker compose` starts `postgres` and `backend` on a
shared network; `backend` waits for Postgres's healthcheck before
starting. Postgres auto-runs `sql/01_schema.sql` on first boot (tables,
constraints, indexes, views, the materialized view). `make seed` then
runs `scripts/generate_seed_data.py` *inside* the backend container —
a Python script using Faker to generate a reproducible academic dataset
(same `random.seed(42)` every run), not a giant static SQL file. It's
idempotent: run it again and it skips (checks `SELECT COUNT(*) FROM
students`), unless you pass `--force` (`make reseed`).

**Concept:** why seed data is Python here instead of SQL like the
e-commerce project — the volume and realism needed (150+ students with
plausible names, grades computed from a real weighted formula, GPA
rankings that vary meaningfully) is easier to generate procedurally
than to hand-write. Notice the seed script also calls the *real*
`GradingService` and `CertificateService` to compute grades and issue
certificates — seeding doubles as an integration test of that code.

---

## Stage 1 — Look at the schema before touching the API

```bash
make db-tables
make db-describe TABLE=enrollments
make db-shell        # then: SELECT * FROM student_dashboard_view LIMIT 5;
```

**What happens:** `db-tables` lists tables *and* views *and* the
materialized view (`\dt`, `\dv`, `\dm`) — this schema has 16 tables, 3
views, and 1 materialized view, and it's worth seeing them as distinct
object types before using them through the API. `db-describe` shows a
table's real constraints straight from Postgres's catalog: primary key,
foreign keys, `CHECK` constraints, and — for `courses` — the generated
`search_vector` column backing full-text search.

**Try it:** `make db-describe TABLE=courses` and look for
`search_vector | tsvector | generated always as (...) stored` — a
column Postgres computes and maintains for you, used in Stage 3.

---

## Stage 2 — Walk the student lifecycle, one call at a time

Your session persists via a cookie file (`.student_cookies.txt`) that
`make` reads and writes automatically.

| # | Command | HTTP call | Concept |
|---|---------|-----------|---------|
| 1 | `make register` | `POST /api/auth/student/register` | `UNIQUE(email)` constraint (still enforced -- unlike `login` below, this one really does reject a taken email) |
| 1b | `make login` | `POST /api/auth/student/login` | Demo mode: any password works, and an unrecognized email auto-creates the account -- see the README's design-decisions section for why |
| 2 | `make departments` / `make department-hierarchy` | `GET /api/departments[/hierarchy]` | Plain table vs. **recursive CTE** walking the School→Department tree |
| 3 | `make courses DEPARTMENT=2` / `make course-search Q=programming` | `GET /api/courses` | FK filter vs. **full-text search** (`search_vector @@ plainto_tsquery(...)`) |
| — | `make course-prereqs COURSE=5` | `GET /api/courses/5/prerequisites` | **Recursive CTE**: the *transitive* prerequisite chain, not just direct prerequisites |
| 4 | `make enroll COURSE=1` | `POST /api/me/enrollments` | `SELECT ... FOR UPDATE` on the course row — the same seat-locking pattern as the e-commerce project's stock check |
| 5 | `make my-enrollments` | `GET /api/me/enrollments` | Join across `enrollments`, `courses`, `semesters` |
| — | `make my-attendance ENROLLMENT=<id>` | `GET /api/enrollments/<id>/attendance` | Owner-or-admin authorization check |
| 6 | `make my-grades` | `GET /api/me/grades` | Reads the `grades` snapshot table (Stage 4 explains why it's not computed live) |
| 7 | `make my-payments` / `make pay PAYMENT=<id>` | `GET/POST /api/me/payments` | One invoice per `(student, semester)` |
| 8 | `make certificate` | `POST /api/me/certificates` | Business rule enforced in the service layer: **402** if any semester is unpaid |

Run `make demo` once to see all of this plus the admin side happen
automatically and narrated (`scripts/api_walkthrough.sh`), *then* come
back and run the individual targets yourself against the data it left
behind.

---

## Stage 3 — The admin side: attendance, exams, grading

```bash
make admin-login
make record-attendance ENROLLMENT=<id> STATUS=present
make record-exam-result EXAM=<id> STUDENT=<id> MARKS=44
make compute-grade ENROLLMENT=<id>
```

**Concept — grading as an explicit action, not a live view:**
`compute-grade` pulls every exam result and graded assignment for that
student+course, computes a weighted percentage (60% exam / 40%
assignment — see `python/ems/services/grading_service.py`), maps it to
a letter grade and GPA points, and **upserts** it into `grades`
(`INSERT ... ON CONFLICT (enrollment_id) DO UPDATE`). Run it, then
`record-exam-result` again with different marks, then `compute-grade`
again — the grade changes, same row, no duplicate-key error. This
mirrors the payment-retry upsert pattern from the e-commerce project.

**Concept — why grades aren't just a query:** if `grades` were a view
computed live from `exam_results` + `assignment_submissions`, editing
an old exam result six months later would silently change a student's
historical transcript. Finalizing a grade is a deliberate event.

---

## Stage 4 — Module 9: the advanced PostgreSQL showcase

This is the point of this project. Each of these is one `make` target,
one real PostgreSQL feature, on real seeded data.

```bash
make report-departments          # CTE: per-department rollup (students, teachers, courses, avg GPA)
make report-gpa                  # Window functions: RANK() overall AND per-department, one query
make report-gpa DEPARTMENT=2     # same window functions, scoped
make report-toppers COURSE=1     # window function: rank students within a single course
make department-hierarchy        # Recursive CTE: the School -> Department tree
make course-prereqs COURSE=5     # Recursive CTE: transitive prerequisite chain, with cycle protection
make report-semesters            # Reads semester_report_mv (a materialized view)
make report-refresh              # REFRESH MATERIALIZED VIEW CONCURRENTLY
make jsonb-late-penalty          # JSONB key-existence: settings ? 'late_penalty'
make jsonb-due-before DUE_DATE=2025-11-15   # JSONB field extraction + cast
make directory-search TYPE=teachers Q=Allison   # Full-text search on a name column
```

Open `python/ems/repositories/report_repository.py` alongside the
output — every one of these is a plain, readable SQL string; there's no
ORM translating your intent into something else. Read the query, then
read the result, then go to `make db-shell` and run the same query by
hand to confirm you understand it.

**Concept — why a materialized view instead of just a view:**
`admin_dashboard_view` and `student_dashboard_view` are *regular* views
(recomputed on every query — fine, they're small aggregates). But
`semester_report_mv` aggregates `attendance` (nearly 8,000 rows) across
every enrollment in a semester — expensive enough that a real dashboard
shouldn't recompute it on every page load. `make report-refresh` is the
`REFRESH MATERIALIZED VIEW CONCURRENTLY` call — `CONCURRENTLY` needs the
unique index on `semester_report_mv(semester_id)` (see
`sql/01_schema.sql`); without it, refreshing takes an exclusive lock
that blocks anyone reading the view while it recomputes. Full
before/after timing evidence: `docs/03_optimization.md`.

---

## Stage 5 — Indexes and `EXPLAIN ANALYZE`

```bash
make explain
```

Three real plans: a small table where the planner correctly *ignores*
an index that exists, a larger table (attendance, ~8,000 rows) where an
index clearly wins, and the materialized view read vs. its live
equivalent (about 150x faster at this seed scale). Full writeup,
including a real bug this project hit — freshly bulk-loaded data
confusing the planner until `ANALYZE` ran — in
`docs/03_optimization.md`.

---

## Stage 6 — Break it on purpose

```bash
# Duplicate email -> UNIQUE constraint, HTTP 409
make register EMAIL=demo.student@ems.test

# Invalid course -> FK doesn't even get that far; NotFoundError, HTTP 404
curl -sS -b .student_cookies.txt -X POST http://localhost:5001/api/me/enrollments \
  -H 'Content-Type: application/json' -d '{"course_id":99999,"semester_id":3}' | jq .

# Enrollment limit reached -> CourseFullError, HTTP 409, nothing partially applied
# (create a capacity-1 course as admin, enroll two different students into it)

# Invalid semester -> enroll in an already-ended semester, HTTP 400
make enroll COURSE=1 SEMESTER=1     # semester 1 is Fall 2025, already over

# Missing payment -> certificate blocked, HTTP 402
make certificate                     # before make pay
```

**Concept, enrollment limit:** `EnrollmentService.enroll()`
(`python/ems/services/enrollment_service.py`) takes `SELECT ... FOR
UPDATE` on the course row, checks the already-enrolled case *before*
the capacity count (so re-enrolling in a full course you're already in
reports "already enrolled," not a misleading "course full" — a real bug
caught by testing this exact sequence by hand), then checks capacity,
then inserts — all in one transaction. Two students racing for the last
seat can't both get in, the same way two checkouts can't both claim the
last unit of stock in the e-commerce project.

---

## Stage 7 — See it all happen automatically

```bash
make demo
```

Runs Stages 2-4 end to end against a fresh, randomly-generated student
account (safe to re-run). Read `scripts/api_walkthrough.sh` alongside
the output.

## Stage 8 — Verify your understanding against the test suite

```bash
make test
```

21 tests, one file per concern (`tests/test_enrollment.py`,
`test_grading.py`, `test_certificates.py`, `test_reports.py`,
`test_students.py`) — including tests that assert the recursive CTEs
and window functions return the exact shape you'd expect from the data
you just constructed. `make test` truncates every table (tests stay
independent of each other); `make reseed` puts the demo data back.

---

## Cheat sheet

```
make up && make seed        start everything, load demo data
make demo                    watch the full lifecycle, narrated
make db-shell                 poke at the raw tables/views yourself
make explain                  see the query plans

make register / login         student STEP 1
make courses / course-search  STEP 2-3  (browse)
make enroll                   STEP 4    (the transactional core)
make my-grades / my-payments  STEP 6-7
make certificate               STEP 8

make admin-login                        admin session
make record-attendance / record-exam-result / compute-grade
make report-departments / report-gpa / report-semesters / report-refresh
make department-hierarchy / course-prereqs     recursive CTEs
make jsonb-late-penalty / jsonb-due-before      JSONB queries
make directory-search                            full-text search

make test                     run the automated tests (truncates tables)
make reseed                    put the demo data back (--force)
make reset                     nuke everything and start over
```
