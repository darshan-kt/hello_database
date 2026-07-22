import psycopg

conn = psycopg.connect(
    host="postgres",
    port=5432,
    dbname="simpledb",
    user="simpledb_user",
    password="simpledb_pass",
)

with conn.cursor() as cur:
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
    rows = cur.fetchall()

conn.close()

for student_name, course_title, teacher_name in rows:
    print(f"{student_name} is taking {course_title}, taught by {teacher_name}")
