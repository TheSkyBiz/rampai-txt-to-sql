import sqlite3

conn = sqlite3.connect("data/ramp_data.db")
cursor = conn.cursor()

tables = [
    "customer_vehicle_info",
    "employee_info",
    "job_card_details",
    "vehicle_service_details",
    "vehicle_service_summary",
    "workshop_info"
]

for table in tables:

    print("\n==============================")
    print(f"TABLE: {table}")
    print("==============================")

    print("\nColumns:")
    cursor.execute(f"PRAGMA table_info({table})")
    columns = cursor.fetchall()

    for col in columns:
        print(col)

    print("\nForeign Keys:")
    cursor.execute(f"PRAGMA foreign_key_list({table})")
    fks = cursor.fetchall()

    if len(fks) == 0:
        print("No foreign keys defined")

    for fk in fks:
        print(fk)

conn.close()