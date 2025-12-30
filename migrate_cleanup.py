import sqlite3
import os

DB_PATH = os.path.join("instance", "kitchen.db")

def migrate():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    
    print(f"Checking {DB_PATH} for missing columns...")
    
    # Get existing columns
    cur.execute("PRAGMA table_info(recipe)")
    columns = [info[1] for info in cur.fetchall()]
    
    if "cleanup_factor" not in columns:
        print("Adding cleanup_factor column...")
        cur.execute("ALTER TABLE recipe ADD COLUMN cleanup_factor INTEGER")
    else:
        print("cleanup_factor column already exists.")

    con.commit()
    con.close()
    print("Migration complete.")

if __name__ == "__main__":
    if os.path.exists(DB_PATH):
        migrate()
    else:
        print(f"Database not found at {DB_PATH}")
