import sqlite3
import os

# Configuration
INPUT_FILE = "ramp_sqls.txt"
DB_NAME = "ramp_data.db"

def setup_database():
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
        print(f"🗑️  Removed existing {DB_NAME}")

    print("📖 Reading SQL file...")

    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            sql_script = f.read()
    except FileNotFoundError:
        print(f"❌ Error: Could not find '{INPUT_FILE}'. Please ensure the file exists.")
        return

    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        print("⚙️  Executing SQL script...")

        # Execute entire script safely
        cursor.executescript(sql_script)

        conn.commit()
        print("-" * 30)
        print("✅ Database Setup Complete.")
        print(f"   Created: {DB_NAME}")

    except sqlite3.Error as e:
        print(f"❌ SQLite Error: {e}")

    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    setup_database()
