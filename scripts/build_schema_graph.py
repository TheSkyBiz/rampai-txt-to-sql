import sqlite3
import json

DB_PATH = "data/ramp_data.db"
OUTPUT_PATH = "data/schema_graph.json"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Get all tables
cursor.execute("""
SELECT name FROM sqlite_master
WHERE type='table'
AND name NOT LIKE 'sqlite_%'
""")

tables = [row[0] for row in cursor.fetchall()]

schema = {}

# Collect columns for each table
for table in tables:

    cursor.execute(f"PRAGMA table_info({table})")

    cols = [row[1] for row in cursor.fetchall()]

    schema[table] = cols


relationships = []

# Detect relationships based on shared *_id columns
for t1 in tables:
    for t2 in tables:

        if t1 == t2:
            continue

        cols1 = schema[t1]
        cols2 = schema[t2]

        common = set(cols1).intersection(set(cols2))

        for col in common:

            if col.endswith("_id"):

                relationships.append({
                    "table1": t1,
                    "table2": t2,
                    "column": col
                })


with open(OUTPUT_PATH, "w") as f:
    json.dump(relationships, f, indent=4)

print("✅ Schema graph generated")
print(f"Relationships found: {len(relationships)}")

conn.close()