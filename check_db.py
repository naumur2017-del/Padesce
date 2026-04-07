import sqlite3

with open("db_output_all.txt", "w") as f:
    conn = sqlite3.connect("db.sqlite3")
    cur = conn.cursor()
    cur.execute("SELECT name, sql FROM sqlite_master WHERE sql LIKE '%REFERENCES%auth_user%';")
    for row in cur.fetchall():
        f.write(f"Table {row[0]}: {row[1]}\n\n")
