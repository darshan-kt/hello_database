import psycopg

conn = psycopg.connect(
    host="postgres",
    port=5432,
    dbname="simpledb",
    user="simpledb_user",
    password="simpledb_pass",
)

with conn.cursor() as cur:
    # --- UPDATE: Rohan gets a new email ---
    cur.execute(
        "UPDATE students SET email = %s WHERE name = %s;",
        ("rohan.gupta@newmail.com", "Rohan Gupta"),
    )
    print(f"Updated email: {cur.rowcount} row(s) affected")

    # --- UPDATE: rename a course ---
    cur.execute(
        "UPDATE courses SET title = %s WHERE title = %s;",
        ("Modern Web Development", "Web Development"),
    )
    print(f"Renamed course: {cur.rowcount} row(s) affected")

    # --- DELETE: unenroll Meera from that course ---
    cur.execute(
        """
        DELETE FROM enrollments
        WHERE student_id = (SELECT student_id FROM students WHERE name = %s)
          AND course_id = (SELECT course_id FROM courses WHERE title = %s);
        """,
        ("Meera Iyer", "Modern Web Development"),
    )
    print(f"Removed enrollment: {cur.rowcount} row(s) affected")

conn.commit()
print("Done.")
conn.close()
