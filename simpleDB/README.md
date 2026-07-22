# simpleDB

The lightest project in this repo's database-learning series — a
minimal Education Management System: 2 teachers, 2 students, 2
courses, connected by real foreign key relationships. Built to learn
the *mechanics* (Docker networking, foreign keys, joins, referential
integrity) at a scale small enough to hold in your head at once,
without the scope of the more advanced `mini_EcommerceDB` and `EMS_DB`
projects in this repo.

Unlike those two, this one wasn't built end-to-end in one pass — it
was built **step by step, by hand**, each step explained before being
typed and run. The full walkthrough — every step, every command, every
result — is in **[`basic_sql.md`](basic_sql.md)**. This README is just
the map; that file is the territory.

## Stack

- **PostgreSQL 16** — in its own Docker container
- **Python 3.11 + psycopg3** — in a *second* Docker container, talking
  to Postgres over Docker's internal network (no local `venv`, no
  Postgres installed on the host)
- **Docker Compose** — ties the two together

## Schema

```
Teachers (1) ────────< Courses

Students (many) ─────< Enrollments >───── (many) Courses
```

4 tables: `teachers`, `students`, `courses` (one-to-many via
`teacher_id`), and `enrollments` (the many-to-many bridge between
students and courses). Full definitions in [`schema.sql`](schema.sql).

## Quickstart

```bash
cd simpleDB

# 1. Start Postgres (and build the Python image)
docker compose up -d --build postgres

# 2. Load the schema (first time only)
docker exec -i simpledb_postgres psql -U simpledb_user -d simpledb < schema.sql

# 3. Seed the 2 teachers / 2 students / 2 courses / 3 enrollments
docker compose run --rm app python insert_data.py

# 4. Read it back, joined across all 4 tables
docker compose run --rm app python query_report.py

# 5. Update + delete
docker compose run --rm app python manipulate_data.py
```

Connect with `psql` directly any time:

```bash
docker exec -it simpledb_postgres psql -U simpledb_user -d simpledb
```

## Files

| File | Purpose |
|---|---|
| `docker-compose.yml` | Defines the `postgres` and `app` services and how they connect |
| `Dockerfile` | Builds the Python environment (`psycopg[binary]` installed) |
| `schema.sql` | The 4 `CREATE TABLE` statements, with foreign keys |
| `db.py` | Minimal connection test (`SELECT * FROM teachers`) |
| `insert_data.py` | Create: inserts the seed data |
| `query_report.py` | Read: a 4-table join answering "which student takes which course, taught by whom" |
| `manipulate_data.py` | Update + delete: edits a student/course, removes an enrollment |
| `basic_sql.md` | The full step-by-step learning journal — objective, every step, every result |

## The one thing worth remembering from this project

Try this, after seeding the data:

```sql
DELETE FROM teachers WHERE name = 'Asha Rao';
```

It fails, on purpose — `courses.teacher_id` still points at her. That
error *is* the foreign key constraint from `schema.sql` doing its job:
the database refusing to let your data contradict itself. See the end
of `basic_sql.md` (Step 7) for the full explanation.
