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
    rows = cur.fetchall()
    print(rows)

conn.close()
