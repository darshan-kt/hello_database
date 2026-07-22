"""
Module 9 -- Advanced PostgreSQL, all in one place.

Every "interesting" query in this project -- CTEs, window functions,
recursive CTEs, and the materialized-view refresh -- lives here rather
than scattered across entity repositories, so it's easy to find and to
point at from docs/04_interactive_learning.md.
"""
from typing import Optional

from ems.db.connection import get_connection


class ReportRepository:
    # -- CTE ------------------------------------------------------------

    def department_report(self) -> list[dict]:
        """One row per department: headcounts + average student GPA,
        each pre-aggregated in its own CTE before joining (avoids
        fan-out from joining several one-to-many relations at once)."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    WITH dept_students AS (
                        SELECT department_id, COUNT(*) AS student_count
                        FROM students GROUP BY department_id
                    ),
                    dept_teachers AS (
                        SELECT department_id, COUNT(*) AS teacher_count
                        FROM teachers GROUP BY department_id
                    ),
                    dept_courses AS (
                        SELECT department_id, COUNT(*) AS course_count
                        FROM courses GROUP BY department_id
                    ),
                    dept_gpa AS (
                        SELECT st.department_id, ROUND(AVG(g.gpa_points)::numeric, 2) AS avg_gpa
                        FROM students st
                        JOIN enrollments e ON e.student_id = st.student_id
                        JOIN grades g ON g.enrollment_id = e.enrollment_id
                        GROUP BY st.department_id
                    )
                    SELECT
                        d.department_id,
                        d.name AS department_name,
                        COALESCE(ds.student_count, 0) AS student_count,
                        COALESCE(dt.teacher_count, 0) AS teacher_count,
                        COALESCE(dc.course_count, 0) AS course_count,
                        dg.avg_gpa
                    FROM departments d
                    LEFT JOIN dept_students ds ON ds.department_id = d.department_id
                    LEFT JOIN dept_teachers dt ON dt.department_id = d.department_id
                    LEFT JOIN dept_courses dc ON dc.department_id = d.department_id
                    LEFT JOIN dept_gpa dg ON dg.department_id = d.department_id
                    ORDER BY d.department_id
                    """
                )
                return cur.fetchall()

    # -- Window functions -------------------------------------------------

    def gpa_rankings(self, department_id: Optional[int] = None) -> list[dict]:
        """RANK() both overall and within department in one pass."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                where_clause = "WHERE d.department_id = %s" if department_id else ""
                params = (department_id,) if department_id else ()
                cur.execute(
                    f"""
                    SELECT
                        st.student_id,
                        st.name AS student_name,
                        d.department_id,
                        d.name AS department_name,
                        ROUND(AVG(g.gpa_points)::numeric, 2) AS gpa,
                        RANK() OVER (ORDER BY AVG(g.gpa_points) DESC) AS overall_rank,
                        RANK() OVER (PARTITION BY d.department_id ORDER BY AVG(g.gpa_points) DESC) AS department_rank
                    FROM students st
                    JOIN departments d ON d.department_id = st.department_id
                    JOIN enrollments e ON e.student_id = st.student_id
                    JOIN grades g ON g.enrollment_id = e.enrollment_id
                    {where_clause}
                    GROUP BY st.student_id, st.name, d.department_id, d.name
                    ORDER BY overall_rank
                    """,
                    params,
                )
                return cur.fetchall()

    def course_toppers(self, course_id: int) -> list[dict]:
        """Rank students within a single course by their final grade.
        Includes semester_name because the same student can legitimately
        appear more than once -- a course can be taken across multiple
        semesters, and each enrollment gets its own grade."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        st.student_id,
                        st.name AS student_name,
                        sem.name AS semester_name,
                        g.total_percent,
                        g.letter_grade,
                        RANK() OVER (ORDER BY g.total_percent DESC) AS course_rank
                    FROM grades g
                    JOIN enrollments e ON e.enrollment_id = g.enrollment_id
                    JOIN students st ON st.student_id = e.student_id
                    JOIN semesters sem ON sem.semester_id = e.semester_id
                    WHERE e.course_id = %s
                    ORDER BY course_rank
                    """,
                    (course_id,),
                )
                return cur.fetchall()

    # -- Recursive CTEs -----------------------------------------------------

    def department_hierarchy(self) -> list[dict]:
        """Walk the self-referential department tree top-down (Schools
        with no parent, down through their departments)."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    WITH RECURSIVE dept_tree AS (
                        SELECT department_id, name, code, parent_department_id, 0 AS depth,
                               name::text AS path
                        FROM departments
                        WHERE parent_department_id IS NULL
                        UNION ALL
                        SELECT d.department_id, d.name, d.code, d.parent_department_id,
                               dt.depth + 1, dt.path || ' > ' || d.name
                        FROM departments d
                        JOIN dept_tree dt ON d.parent_department_id = dt.department_id
                    )
                    SELECT * FROM dept_tree ORDER BY path
                    """
                )
                return cur.fetchall()

    def course_prerequisite_chain(self, course_id: int) -> list[dict]:
        """All transitive prerequisites of a course (not just direct
        ones), with a `visited` array to guard against a cycle in the
        prerequisite graph turning into infinite recursion."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    WITH RECURSIVE prereq_chain AS (
                        SELECT cp.course_id, cp.prerequisite_course_id, 1 AS depth,
                               ARRAY[cp.course_id, cp.prerequisite_course_id] AS visited
                        FROM course_prerequisites cp
                        WHERE cp.course_id = %s
                        UNION ALL
                        SELECT pc.course_id, cp2.prerequisite_course_id, pc.depth + 1,
                               pc.visited || cp2.prerequisite_course_id
                        FROM prereq_chain pc
                        JOIN course_prerequisites cp2 ON cp2.course_id = pc.prerequisite_course_id
                        WHERE NOT cp2.prerequisite_course_id = ANY(pc.visited)
                    )
                    SELECT c.course_id, c.code, c.title, MIN(pc.depth) AS depth
                    FROM prereq_chain pc
                    JOIN courses c ON c.course_id = pc.prerequisite_course_id
                    GROUP BY c.course_id, c.code, c.title
                    ORDER BY depth, c.code
                    """,
                    (course_id,),
                )
                return cur.fetchall()

    # -- Materialized view --------------------------------------------------

    def semester_report(self) -> list[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM semester_report_mv ORDER BY start_date")
                return cur.fetchall()

    def refresh_semester_report(self) -> None:
        """CONCURRENTLY needs the unique index on semester_report_mv --
        without it this refresh would take an exclusive lock and block
        reads of the view for its duration."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY semester_report_mv")

    # -- Views ----------------------------------------------------------

    def admin_dashboard(self) -> dict:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM admin_dashboard_view")
                return cur.fetchone()

    def student_dashboard(self, student_id: int) -> Optional[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM student_dashboard_view WHERE student_id = %s", (student_id,)
                )
                return cur.fetchone()

    def teacher_dashboard(self, teacher_id: Optional[int] = None) -> list[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                if teacher_id:
                    cur.execute(
                        "SELECT * FROM teacher_dashboard_view WHERE teacher_id = %s",
                        (teacher_id,),
                    )
                    row = cur.fetchone()
                    return [row] if row else []
                cur.execute("SELECT * FROM teacher_dashboard_view ORDER BY teacher_id")
                return cur.fetchall()
