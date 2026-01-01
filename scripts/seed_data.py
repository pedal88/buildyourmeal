import sys
import os
import json
import sqlite3

# Add parent directory to path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from database.models import Chef, Recipe, RecipeMealType

def load_json(filename):
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", filename)
    with open(path, 'r') as f:
        return json.load(f)

def migrate_db():
    """Manual migration to add columns if they don't exist"""
    print("Checking DB Schema...")
    db_path = 'instance/kitchen.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Ensure Chef Table Exists (handled by create_all normally, but let's be safe)
    # We will rely on db.create_all() for new tables, but for ALTERING existing ones:
    
    # Check Recipe Table Columns
    cursor.execute("PRAGMA table_info(recipe)")
    columns = [row[1] for row in cursor.fetchall()]
    
    new_cols = {
        "chef_id": "VARCHAR",
        "taste_level": "INTEGER",
        "prep_time_mins": "INTEGER",
        "cleanup_factor": "INTEGER"
    }

    for col, dtype in new_cols.items():
        if col not in columns:
            print(f"Adding column {col} to Recipe table...")
            try:
                cursor.execute(f"ALTER TABLE recipe ADD COLUMN {col} {dtype}")
            except Exception as e:
                print(f"Error adding {col}: {e}")
    
    # Check if meal_types column exists (we deprecated it, but might want to keep it or drop it?)
    # For now, we leave it as legacy data until migrated.
    
    conn.commit()
    conn.close()
    print("Schema Check Complete.")

def seed_chefs():
    print("Seeding Chefs...")
    chefs_data = load_json("agents/chefs.json")['chefs']
    
    for c_data in chefs_data:
        chef_id = c_data['id']
        existing = db.session.get(Chef, chef_id)
        if not existing:
            print(f"Creating Chef: {c_data['name']}")
            new_chef = Chef(
                id=c_data['id'],
                name=c_data['name'],
                archetype=c_data['archetype'],
                description=c_data['description'],
                image_filename=c_data['image_filename'],
                constraints=json.dumps(c_data.get('constraints', {})),
                diet_preferences=json.dumps(c_data.get('diet_preferences', [])),
                cooking_style=json.dumps(c_data.get('cooking_style', {})),
                ingredient_logic=json.dumps(c_data.get('ingredient_logic', {})),
                instruction_style=json.dumps(c_data.get('instruction_style', {}))
            )
            db.session.add(new_chef)
        else:
            print(f"Updating Chef: {c_data['name']}")
            existing.constraints = json.dumps(c_data.get('constraints', {}))
            existing.diet_preferences = json.dumps(c_data.get('diet_preferences', []))
            existing.cooking_style = json.dumps(c_data.get('cooking_style', {}))
            existing.ingredient_logic = json.dumps(c_data.get('ingredient_logic', {}))
            existing.instruction_style = json.dumps(c_data.get('instruction_style', {}))

    db.session.commit()
    print("Chefs Seeded.")

def migrate_meal_types():
    print("Migrating Meal Types to M2M...")
    all_recipes = Recipe.query.all()
    count = 0 
    for r in all_recipes:
        # Check if legacy column has data
        # Note: In new model definition `meal_types` is the relationship.
        # But we might still have access to the column via raw SQL if we removed it from the ORM.
        # WAIT. In models.py I REMOVED `meal_types: Mapped[str]`. 
        # So `r.meal_types` now refers to the relationship which is empty.
        # We need to fetch the raw JSON from the DB using SQL.
        pass
    
    # Actually, simpler approach:
    # We just nuked the `meal_types` column mapping in the class, but the data is still in the DB column `meal_types` (string).
    # We should select id, meal_types from recipe table raw.
    
    conn = sqlite3.connect('instance/kitchen.db')
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(recipe)")
    cols = [c[1] for c in cursor.fetchall()]
    
    if "meal_types" in cols:
        cursor.execute("SELECT id, meal_types FROM recipe")
        rows = cursor.fetchall()
        for rid, mt_json in rows:
            if not mt_json: continue
            try:
                tags = json.loads(mt_json)
                if not isinstance(tags, list): continue
                
                for tag in tags:
                    # check if exists
                    exists = db.session.get(RecipeMealType, (rid, tag))
                    if not exists:
                        db.session.add(RecipeMealType(recipe_id=rid, meal_type=tag))
                        count += 1
            except:
                pass
    
    db.session.commit()
    conn.close()
    print(f"Migrated {count} meal type tags.")

if __name__ == "__main__":
    with app.app_context():
        # 1. Update Schema (Add Tables)
        db.create_all()
        
        # 2. Update Schema (Add Columns manually)
        migrate_db()
        
        # 3. Seed Chefs
        seed_chefs()
        
        # 4. Migrate Meal Types
        migrate_meal_types()
        
        print("Seeding & Migration Complete!")
