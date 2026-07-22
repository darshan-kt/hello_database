# Module 12 — Indexing & Query Optimization

Every plan below is a real `EXPLAIN ANALYZE` run against the seeded
database (`make up && make seed`: 12 departments, 24 teachers, 153
students, 40 courses, 765 enrollments, 7,956 attendance rows, 612
grades). Numbers will differ slightly on your machine, but the plan
shapes and index choices will match.

## 1. A lesson before the wins: small tables don't use their indexes

```sql
EXPLAIN ANALYZE SELECT * FROM courses WHERE department_id = 2;
```

```
Seq Scan on courses  (cost=0.00..3.50 rows=5 width=376) (actual time=0.004..0.019 rows=5 loops=1)
  Filter: (department_id = 2)
  Rows Removed by Filter: 35
Execution Time: 0.060 ms
```

`idx_courses_department` exists, but Postgres ignores it here. This is
**correct**, not a bug: for a 40-row table, reading the whole table
sequentially is cheaper than the overhead of an index lookup plus a
heap fetch per match. The same is true of the full-text search index on
`courses` and the name-search indexes on `teachers`/`students` at this
seed scale. This is worth internalizing before chasing `EXPLAIN`
output: **an index that exists is not proof it's being used**, and an
unused index on a small table is not a problem to fix.

**A real gotcha we hit building this**: immediately after a fresh
`make seed`, this exact query picked an *index* scan instead, with a
worse cost estimate than the sequential scan. The cause wasn't the
index -- it was that a bulk load leaves the planner with stale/default
statistics until `autovacuum` gets around to analyzing the table, so
its row estimates are guesses. `scripts/generate_seed_data.py` now runs
`ANALYZE` explicitly as its last step so the plans above are what you
actually see right after seeding, not a few minutes later once
autovacuum catches up. Rule of thumb: **run `ANALYZE` after any bulk
load**, in a migration, a data import, or a seed script -- don't wait
for autovacuum if you're about to make decisions (or take screenshots)
based on `EXPLAIN` output.

To prove the GIN full-text index is wired correctly (rather than take
it on faith), force the planner to avoid sequential scans and watch it
pick the index it would use automatically once the table is large
enough for that to be the cheaper plan:

```sql
SET enable_seqscan = off;
EXPLAIN ANALYZE SELECT * FROM courses
WHERE search_vector @@ plainto_tsquery('english', 'programming');
```

```
Bitmap Heap Scan on courses  (cost=8.56..12.57 rows=1 width=376) (actual time=0.011..0.012 rows=1 loops=1)
  Recheck Cond: (search_vector @@ '''program'''::tsquery)
  ->  Bitmap Index Scan on idx_courses_search  (cost=0.00..8.56 rows=1 width=0) (actual time=0.009..0.009 rows=1 loops=1)
        Index Cond: (search_vector @@ '''program'''::tsquery)
```

## 2. Where indexes *do* win at this scale: attendance

`attendance` has 7,956 rows — enough for the planner to prefer the
index over a scan:

```sql
EXPLAIN ANALYZE SELECT * FROM attendance WHERE enrollment_id = 100;
```

```
Bitmap Heap Scan on attendance  (cost=4.36..31.20 rows=10 width=24) (actual time=0.028..0.028 rows=4 loops=1)
  ->  Bitmap Index Scan on idx_attendance_enrollment  (cost=0.00..4.36 rows=10 width=0) (actual time=0.022..0.022 rows=4 loops=1)
        Index Cond: (enrollment_id = 100)
```

## 3. A composite index that isn't earning its keep (yet)

`sql/01_schema.sql` deliberately adds
`idx_enrollments_course_semester(course_id, semester_id)` to support the
enrollment-capacity check (`COUNT(*) ... WHERE course_id = ? AND
semester_id = ?`, in `EnrollmentRepository.count_for_course_semester`).
At current volume, the planner doesn't use it:

```sql
EXPLAIN ANALYZE SELECT COUNT(*) FROM enrollments WHERE course_id = 5 AND semester_id = 1;
```

```
Aggregate (actual time=0.020..0.020 rows=1 loops=1)
  ->  Index Scan using idx_enrollments_course on enrollments (actual time=0.014..0.017 rows=11 loops=1)
        Index Cond: (course_id = 5)
        Filter: (semester_id = 1)
        Rows Removed by Filter: 10
```

It picks the single-column `idx_enrollments_course` and filters
`semester_id` afterward — with ~20 enrollments per course, that filter
is nearly free, so the extra column in the composite index buys
nothing yet. The composite index earns its cost once a course
accumulates enrollments across many more semesters (so `course_id`
alone stops being selective). This is included deliberately: a
production index strategy is chosen for the data volume you'll actually
have, not the one seeded for a demo, and it's worth knowing which of
your indexes are "for later" versus pulling weight today (`pg_stat_user_indexes`
is the real tool for that in production).

## 4. Window functions: GPA ranking in one query

```sql
EXPLAIN ANALYZE
SELECT st.student_id, st.name, d.department_id,
       ROUND(AVG(g.gpa_points)::numeric, 2) AS gpa,
       RANK() OVER (ORDER BY AVG(g.gpa_points) DESC) AS overall_rank,
       RANK() OVER (PARTITION BY d.department_id ORDER BY AVG(g.gpa_points) DESC) AS department_rank
FROM students st
JOIN departments d ON d.department_id = st.department_id
JOIN enrollments e ON e.student_id = st.student_id
JOIN grades g ON g.enrollment_id = e.enrollment_id
GROUP BY st.student_id, st.name, d.department_id, d.name
ORDER BY overall_rank;
```

```
Sort (actual time=1.056..1.063 rows=153 loops=1)
  ->  WindowAgg (actual time=0.910..0.997 rows=153 loops=1)          -- department_rank
        ->  Sort
              ->  WindowAgg (actual time=0.769..0.833 rows=153 loops=1)  -- overall_rank
                    ->  Sort
                          ->  HashAggregate (actual time=0.665..0.719 rows=153 loops=1)
                                ->  Hash Join ... (grades x enrollments x students x departments)
Execution Time: 1.244 ms
```

Two `WindowAgg` nodes, one per `RANK()` call, each needing its own sort
(overall order vs. per-department order) — this is why the query groups
first (one `HashAggregate` for the average), then windows twice, rather
than computing the average once per window separately. 153 students
ranked, two ways, in 1.2ms.

## 5. Materialized view vs. the live equivalent

`semester_report_mv` exists specifically so this doesn't get recomputed
on every dashboard load:

```sql
EXPLAIN ANALYZE SELECT * FROM semester_report_mv;
-- Seq Scan on semester_report_mv ... Execution Time: 0.022 ms
```

versus running the four-CTE aggregation (enrollment counts, revenue,
avg GPA, avg attendance across 7,956 attendance rows) live:

```sql
-- the same query as the matview definition, run directly
-- Execution Time: 3.481 ms
```

**~150x** at this seed scale — and the gap widens with data volume,
since the live version re-scans `attendance` (the largest table) on
every call. The tradeoff, made explicit by `make refresh-report`
(`REFRESH MATERIALIZED VIEW CONCURRENTLY`): the view is only as fresh as
the last refresh. Right for a semester revenue dashboard (nobody needs
it to the millisecond); wrong for anything that must reflect a payment
that posted three seconds ago.

## General index rules applied in this schema

- Every foreign key has a supporting index.
- `idx_enrollments_course_semester` is a deliberate example of an index
  added for a *known future* access pattern rather than today's data —
  see Section 3 for why that's a documented tradeoff, not an oversight.
- GIN indexes back every full-text search column
  (`courses.search_vector`, and functional indexes on `teachers.name` /
  `students.name`) and every JSONB column (`assignments.settings`).
- No index was added speculatively beyond the one noted in Section 3 —
  each maps to a query pattern in `docs/01_requirements.md` or an
  endpoint in `python/app.py`.
