import sqlite3
import datetime

DB_PATH = "instance/kitchen.db"

def migrate():
    print(f"Migrating database at {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Add is_original column
        print("Adding is_original column...")
        cursor.execute("ALTER TABLE ingredient ADD COLUMN is_original BOOLEAN DEFAULT 0")
    except sqlite3.OperationalError as e:
        print(f"Skipping is_original (might exist): {e}")

    try:
        # Add created_at column
        print("Adding created_at column...")
        cursor.execute("ALTER TABLE ingredient ADD COLUMN created_at TEXT")
    except sqlite3.OperationalError as e:
        print(f"Skipping created_at (might exist): {e}")

    # Backfill Data
    print("Backfilling existing data...")
    cursor.execute("UPDATE ingredient SET is_original = 1 WHERE is_original IS NULL OR is_original = 0")
    
    now_str = datetime.datetime.now().isoformat()
    cursor.execute("UPDATE ingredient SET created_at = ? WHERE created_at IS NULL", (now_str,))

    conn.commit()
    conn.close()
    print("Migration complete!")

if __name__ == "__main__":
    migrate()
