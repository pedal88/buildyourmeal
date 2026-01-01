"""
Database Migration Script: Add component column to instructions table
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from database.models import Instruction

def migrate():
    with app.app_context():
        print("Running migration: Add component column to instructions...")
        
        # SQLAlchemy will handle the column addition via alembic or direct DDL
        # For SQLite in development, we can use raw SQL
        with db.engine.connect() as conn:
            try:
                # Check if column already exists
                result = conn.execute(db.text("PRAGMA table_info(instruction)"))
                columns = [row[1] for row in result.fetchall()]
                
                if 'component' not in columns:
                    print("Adding 'component' column... ")
                    conn.execute(db.text(
                        "ALTER TABLE instruction ADD COLUMN component VARCHAR(100) NOT NULL DEFAULT 'Main Dish'"
                    ))
                    conn.commit()
                    print("✅ Migration complete!")
                else:
                    print("⚠️  Column 'component' already exists. Skipping.")
                    
            except Exception as e:
                print(f"❌ Migration failed: {e}")
                raise

if __name__ == "__main__":
    migrate()
