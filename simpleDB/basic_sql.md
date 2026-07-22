# simpleDB — Learning Journal

A record of building the lightest possible relational database project
from scratch: the objective, every step taken, and what actually
happened at each one. Kept for future reference — re-read this before
you re-derive any of it from memory.

## Original objective

> Learn by doing, step by step. Replicate the Education Management
> System idea, but at the lightest possible scale: 2 students, 2
> teachers, 2 courses. Be able to upload, retrieve, and manipulate
> data between those entities *with relationships* between them.
> Stack: PostgreSQL, Python, Docker. Start with Docker as a "virtual
> environment." Guide it step by step, intuitively — don't build it,
> teach it.

This is the deliberately-small sibling of two more advanced projects
in this repo (`mini_EcommerceDB`, `EMS_DB`) — same core ideas
(relational schema, foreign keys, a Python data layer, Docker), at a
scale small enough to hold the whole thing in your head at once.

---

## Step 1 — Docker as the "virtual environment"

**Goal:** run Postgres in an isolated container instead of installing
it on the host machine — the same isolation a Python `venv` gives you,
applied to the database itself.

**Built:** `docker-compose.yml`, a single `postgres` service:

```yaml
services:
  postgres:
    image: postgres:16
    container_name: simpledb_postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: simpledb
      POSTGRES_USER: simpledb_user
      POSTGRES_PASSWORD: simpledb_pass
    ports:
      - "5435:5432"
    volumes:
      - simpledb_data:/var/lib/postgresql/data

volumes:
  simpledb_data:
```

**Key concepts:**
- `environment:` bootstraps a database, user, and password on first
  boot only.
- `ports: "5435:5432"` maps the container's internal Postgres port
  (`5432`) to `5435` on the host, so tools *outside* Docker (like a
  local `psql`) can reach it. `5435` was chosen (not the default
  `5432`) to avoid colliding with other Postgres containers already
  running on this machine for other projects.
- `volumes:` — a named, Docker-managed volume so data survives a
  container restart/removal; without it, every `docker compose down`
  would wipe the database.

**Commands run:**
```bash
docker compose up -d
docker compose ps                                        # confirm "Up"
docker exec -it simpledb_postgres psql -U simpledb_user -d simpledb
```
```sql
\dt   -- "Did not find any relations" -- correct, nothing created yet
```

**Result:** Postgres running in Docker, reachable, empty. ✅

---

## Step 2 — Design the schema (on paper, no code yet)

**Goal:** figure out the entities and, more importantly, *how they
relate*, before writing a single `CREATE TABLE`.

**Process:** for each pair of entities, asked "can one have many of
the other, in each direction?"

- **Teachers ↔ Courses** — one teacher can teach many courses; one
  course has exactly one teacher. **One-to-many.**
- **Students ↔ Courses** — one student can take many courses; one
  course can have many students. **Many-to-many.**

```
Teachers (1) ────────< Courses

Students (many) ─────< Enrollments >───── (many) Courses
```

**Key concept:** a one-to-many relationship is just a foreign key
column on the "many" side (`courses.teacher_id`). A many-to-many
relationship *cannot* be a single column on either side — it needs a
separate **bridge table** (`enrollments`) that stores one row per
`(student_id, course_id)` pair.

**Result:** 4 tables planned — `teachers`, `students`, `courses`,
`enrollments` — before any SQL was written.

---

## Step 3 — Write the schema as SQL

**Built:** `schema.sql`

```sql
CREATE TABLE teachers (
    teacher_id  SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    email       VARCHAR(150) UNIQUE NOT NULL
);

CREATE TABLE students (
    student_id  SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    email       VARCHAR(150) UNIQUE NOT NULL
);

CREATE TABLE courses (
    course_id   SERIAL PRIMARY KEY,
    title       VARCHAR(150) NOT NULL,
    teacher_id  INT NOT NULL REFERENCES teachers(teacher_id)
);

CREATE TABLE enrollments (
    student_id  INT NOT NULL REFERENCES students(student_id),
    course_id   INT NOT NULL REFERENCES courses(course_id),
    PRIMARY KEY (student_id, course_id)
);
```

**Key concepts:**
- Table creation order matters — `teachers`/`students` first, then
  `courses` (references `teachers`), then `enrollments` (references
  both). Postgres checks foreign keys exist at creation time.
- `SERIAL PRIMARY KEY` — auto-incrementing ID, never inserted manually.
- `REFERENCES teachers(teacher_id)` — the actual foreign key. Postgres
  will reject an insert/update that points at a `teacher_id` that
  doesn't exist.
- `PRIMARY KEY (student_id, course_id)` on `enrollments` — a
  **composite** key. Enforces "a student can't enroll in the same
  course twice" as a database-level constraint, not application logic.

**Commands run:**
```bash
docker exec -i simpledb_postgres psql -U simpledb_user -d simpledb < schema.sql
```

**Result:** `CREATE TABLE` ×4. Verified with `\dt` (4 tables) and
`\d courses` / `\d enrollments` (foreign keys and composite key visible
in the constraint list). ✅

---

## Step 4 — Connect Python to Postgres (containerized)

**Original plan:** a local Python `venv` on the host, connecting to
`localhost:5435`.

**Redirected to:** a *second Docker service* for the app, connected to
Postgres over Docker's internal network — more consistent with an
all-Docker stack, and it removes the local `venv` entirely.

**Built:** `Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
```

`requirements.txt`:
```
psycopg[binary]
```

`docker-compose.yml` gained a second service and a healthcheck on the
first:

```yaml
  postgres:
    # ...
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U simpledb_user -d simpledb"]
      interval: 5s
      timeout: 5s
      retries: 10

  app:
    build: .
    container_name: simpledb_app
    depends_on:
      postgres:
        condition: service_healthy
    volumes:
      - .:/app
```

`db.py` (the connection test):

```python
import psycopg

conn = psycopg.connect(
    host="postgres",   # the service name from docker-compose.yml, not "localhost"
    port=5432,          # the container-internal port, not 5435
    dbname="simpledb",
    user="simpledb_user",
    password="simpledb_pass",
)

with conn.cursor() as cur:
    cur.execute("SELECT * FROM teachers;")
    print(cur.fetchall())

conn.close()
```

**Key concepts:**
- **Containers reach each other by service name, not `localhost`.**
  From inside the `app` container, `localhost` means "this container,"
  not the Postgres one. Docker Compose gives every service in the file
  a shared network where each is reachable by its service name —
  here, `host="postgres"`.
- **Internal port vs. mapped port.** Container-to-container traffic
  uses Postgres's real port (`5432`) directly; the `5435` mapping from
  Step 1 is only relevant to things *outside* all containers.
- **`healthcheck` + `depends_on: condition: service_healthy`** — without
  this, `app` could start and try to connect before Postgres has
  actually finished booting, even though the *container* has started.
  `pg_isready` is what confirms Postgres itself, not just its
  container, is ready.
- **Bind mount (`.:/app`)** — local file edits are visible inside the
  container immediately, no rebuild needed for code changes (only for
  `requirements.txt` changes).

**Commands run:**
```bash
docker compose up -d --build postgres
docker compose run --rm app python db.py
```

**Result:** `[]` — empty list. Correct: connection succeeded, query
ran, table just has no rows yet. ✅

---

## Step 5 — Insert the seed data (Create)

**Built:** `insert_data.py` — inserts 2 teachers, 2 students, 2
courses, and 3 enrollments (deliberately uneven: Meera enrolled in
both courses, Rohan in only one, so a broken join would be visible
later).

```python
import psycopg

conn = psycopg.connect(
    host="postgres", port=5432, dbname="simpledb",
    user="simpledb_user", password="simpledb_pass",
)

with conn.cursor() as cur:
    cur.execute(
        "INSERT INTO teachers (name, email) VALUES (%s, %s) RETURNING teacher_id;",
        ("Asha Rao", "asha@example.com"),
    )
    asha_id = cur.fetchone()[0]
    # ... (Vikram Shah, Meera Iyer, Rohan Gupta, Database Systems, Web Development
    #      -- same INSERT ... RETURNING pattern for each)

    cur.execute("INSERT INTO enrollments (student_id, course_id) VALUES (%s, %s);", (meera_id, db_course_id))
    cur.execute("INSERT INTO enrollments (student_id, course_id) VALUES (%s, %s);", (meera_id, web_course_id))
    cur.execute("INSERT INTO enrollments (student_id, course_id) VALUES (%s, %s);", (rohan_id, db_course_id))

conn.commit()
conn.close()
```

**Key concepts:**
- **`%s` placeholders, never string-formatted SQL.**
  `cur.execute("... VALUES (%s, %s)", (name, email))` lets psycopg
  substitute values safely. Building SQL by concatenating raw values
  into a string is how SQL injection happens — never do it, even in a
  throwaway script.
- **`RETURNING teacher_id`** — a Postgres feature: an `INSERT` can hand
  the generated ID straight back, instead of a separate `SELECT`
  afterward. Needed here because `courses.teacher_id` requires a real
  ID that only exists *after* Postgres generates it.
- **`conn.commit()`** — the most common beginner gotcha. Without it,
  nothing is actually saved — the script runs, prints success, and the
  database silently stays empty. Nothing errors; it just doesn't
  persist.

**Commands run:**
```bash
docker compose run --rm app python insert_data.py
```

**Result:** "Seed data inserted." Verified via `psql`: 2 rows in
`teachers`, 2 in `students`, 2 in `courses`, 3 in `enrollments`. ✅

---

## Step 6 — Retrieve across relationships (Read, with JOINs)

**Built:** `query_report.py` — answers "which student is taking which
course, taught by whom?", a question no single table can answer alone.

```python
cur.execute("""
    SELECT
        s.name AS student_name,
        c.title AS course_title,
        t.name AS teacher_name
    FROM students s
    JOIN enrollments e ON e.student_id = s.student_id
    JOIN courses c ON c.course_id = e.course_id
    JOIN teachers t ON t.teacher_id = c.teacher_id
    ORDER BY s.name, c.title;
""")
```

**Key concepts:**
- Each `JOIN` is one hop across a foreign key from Step 2/3 — the
  query's shape mirrors the ER diagram exactly: students → enrollments
  → courses → teachers.
- **Table aliases aren't just shorthand.** `students` and `teachers`
  both have a `name` column; without `s.name` / `t.name`, `SELECT name`
  is ambiguous and Postgres errors.
- Plain `JOIN` = **inner join** — a student with zero enrollments
  would be silently excluded from the results entirely, not shown with
  blanks.

**Commands run:**
```bash
docker compose run --rm app python query_report.py
```

**Result:**
```
Meera Iyer is taking Database Systems, taught by Asha Rao
Meera Iyer is taking Web Development, taught by Vikram Shah
Rohan Gupta is taking Database Systems, taught by Asha Rao
```
Rohan appears once, matching his single enrollment — confirming the
join fans out correctly rather than duplicating or dropping rows. ✅

---

## Step 7 — Data manipulation (Update, Delete, and referential integrity)

**Built:** `manipulate_data.py` — updates a student's email, renames a
course, and removes one enrollment.

```python
cur.execute("UPDATE students SET email = %s WHERE name = %s;",
            ("rohan.gupta@newmail.com", "Rohan Gupta"))

cur.execute("UPDATE courses SET title = %s WHERE title = %s;",
            ("Modern Web Development", "Web Development"))

cur.execute("""
    DELETE FROM enrollments
    WHERE student_id = (SELECT student_id FROM students WHERE name = %s)
      AND course_id = (SELECT course_id FROM courses WHERE title = %s);
    """, ("Meera Iyer", "Modern Web Development"))

conn.commit()
```

**Key concepts:**
- **`cur.rowcount`** — how many rows a statement actually touched.
  A `WHERE` clause that matches nothing produces *no error*, just a
  silent no-op; `rowcount == 0` is how you catch that yourself.
- **Subqueries in a `WHERE` clause** — used here because only the
  student's *name* was known at that point, not their ID.
- **The danger of a missing `WHERE`** — `UPDATE courses SET title = 'X';`
  with no `WHERE` updates *every row*. Always think through the
  `WHERE` before the `SET`.

**Commands run:**
```bash
docker compose run --rm app python manipulate_data.py
```

**Result:** 3 lines of `1 row(s) affected`. ✅

**Then, deliberately tried to break referential integrity:**

```sql
DELETE FROM teachers WHERE name = 'Asha Rao';
```

**Result:**
```
ERROR:  update or delete on table "teachers" violates foreign key constraint
DETAIL:  Key (teacher_id)=(1) is still referenced from table "courses".
```

**This was the point, not a bug.** Asha still teaches "Database
Systems." If this delete had succeeded, `courses.teacher_id` would
point at a teacher that no longer exists, silently breaking every
future join through that row. This is the exact `REFERENCES
teachers(teacher_id)` constraint from Step 3, caught live, three steps
later — proof the schema design is actually enforcing the relationship,
not just documenting it. ✅

(Cascading deletes are possible via `ON DELETE CASCADE` on the foreign
key, but that's an explicit design decision to make later, not a
default.)

---

## What this project ended up proving, end to end

`docker compose up` → an isolated Postgres → a schema with real
foreign key constraints → a containerized Python app reaching it over
Docker's internal network → data created, read back *through* its
relationships, updated, deleted — and the database itself refusing an
operation that would have corrupted those relationships.

## Possible next steps (not built here)

- An interactive CLI menu instead of one-off scripts per operation.
- `try`/`except` around the foreign-key violation instead of letting
  it crash the script.
- `ON DELETE CASCADE` / `ON DELETE SET NULL` as an explicit choice on
  the `courses.teacher_id` and `enrollments` foreign keys.
