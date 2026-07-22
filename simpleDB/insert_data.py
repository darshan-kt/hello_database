import psycopg

conn = psycopg.connect(
    host="postgres",
    port=5432,
    dbname="simpledb",
    user="simpledb_user",
    password="simpledb_pass",
)

with conn.cursor() as cur:
    # --- Teachers ---
    cur.execute(
        "INSERT INTO teachers (name, email) VALUES (%s, %s) RETURNING teacher_id;",
        ("Asha Rao", "asha@example.com"),
    )
    asha_id = cur.fetchone()[0]

    cur.execute(
        "INSERT INTO teachers (name, email) VALUES (%s, %s) RETURNING teacher_id;",
        ("Vikram Shah", "vikram@example.com"),
    )
    vikram_id = cur.fetchone()[0]

    # --- Students ---
    cur.execute(
        "INSERT INTO students (name, email) VALUES (%s, %s) RETURNING student_id;",
        ("Meera Iyer", "meera@example.com"),
    )
    meera_id = cur.fetchone()[0]

    cur.execute(
        "INSERT INTO students (name, email) VALUES (%s, %s) RETURNING student_id;",
        ("Rohan Gupta", "rohan@example.com"),
    )
    rohan_id = cur.fetchone()[0]

    # --- Courses ---
    cur.execute(
        "INSERT INTO courses (title, teacher_id) VALUES (%s, %s) RETURNING course_id;",
        ("Database Systems", asha_id),
    )
    db_course_id = cur.fetchone()[0]

    cur.execute(
        "INSERT INTO courses (title, teacher_id) VALUES (%s, %s) RETURNING course_id;",
        ("Web Development", vikram_id),
    )
    web_course_id = cur.fetchone()[0]

    # --- Enrollments (this is the many-to-many bridge in action) ---
    cur.execute("INSERT INTO enrollments (student_id, course_id) VALUES (%s, %s);", (meera_id, db_course_id))
    cur.execute("INSERT INTO enrollments (student_id, course_id) VALUES (%s, %s);", (meera_id, web_course_id))
    cur.execute("INSERT INTO enrollments (student_id, course_id) VALUES (%s, %s);", (rohan_id, db_course_id))

conn.commit()
print("Seed data inserted.")
conn.close()
