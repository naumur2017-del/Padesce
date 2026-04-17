import os
import sqlite3

# Backup DB path
backup_db = "db_backup.sqlite3"
# Current DB path
current_db = "db.sqlite3"

if not os.path.exists(backup_db):
    print(f"Error: {backup_db} not found.")
    exit(1)

# Connect to both
conn_back = sqlite3.connect(backup_db)
conn_curr = sqlite3.connect(current_db)

cursor_back = conn_back.cursor()
cursor_curr = conn_curr.cursor()

# Get table name for AppelFormateur.
# It's usually 'appels_appelformateur' or similar.
cursor_back.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%appelformateur%';"
)
table_name = cursor_back.fetchone()[0]
print(f"Restoring table: {table_name}")

# Clear current table (careful!)
cursor_curr.execute(f"DELETE FROM {table_name};")

# Read from backup
cursor_back.execute(f"SELECT * FROM {table_name};")
rows = cursor_back.fetchall()

# Get columns
cursor_back.execute(f"PRAGMA table_info({table_name});")
cols = [c[1] for c in cursor_back.fetchall()]
placeholders = ", ".join(["?" for _ in cols])
cols_str = ", ".join(cols)

# Insert into current
cursor_curr.executemany(f"INSERT INTO {table_name} ({cols_str}) VALUES ({placeholders});", rows)

conn_curr.commit()
print(f"Restored {len(rows)} records to {table_name}.")

conn_back.close()
conn_curr.close()
