import sqlite3
import os

def migrate_db():
    db_path = os.path.join(os.getcwd(), 'instance', 'kitchen.db') # Flask default location
    
    # Fallback to root if not in instance
    if not os.path.exists(db_path):
        db_path = os.path.join(os.getcwd(), 'kitchen.db')
        
    print(f"Migrating database at: {db_path}")
    
    if not os.path.exists(db_path):
        print("Database not found. Skipping migration (will be created by app).")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    columns_to_add = [
        ("total_calories", "FLOAT"),
        ("total_protein", "FLOAT"),
        ("total_carbs", "FLOAT"),
        ("total_fat", "FLOAT"),
        ("total_fiber", "FLOAT"),
        ("total_sugar", "FLOAT")
    ]
    
    # Get existing columns
    cursor.execute("PRAGMA table_info(recipe)")
    existing_columns = [row[1] for row in cursor.fetchall()]
    
    for col_name, col_type in columns_to_add:
        if col_name not in existing_columns:
            print(f"Adding column {col_name}...")
            try:
                cursor.execute(f"ALTER TABLE recipe ADD COLUMN {col_name} {col_type}")
            except Exception as e:
                print(f"Error adding {col_name}: {e}")
        else:
            print(f"Column {col_name} already exists.")
            
    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate_db()
