import json
import os
import sys
from flask import Flask

# Add root directory to path to allow importing database
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.models import db, Ingredient

def migrate():
    # Setup minimal app context
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///kitchen.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    # Locate pantry.json
    pantry_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'pantry.json')
    if not os.path.exists(pantry_path):
        pantry_path = os.path.join(os.path.dirname(__file__), '..', 'pantry.json')
        if not os.path.exists(pantry_path):
            print("Error: pantry.json not found.")
            return

    print(f"Reading from {pantry_path}...")
    with open(pantry_path, 'r') as f:
        data = json.load(f)

    ingredients = []
    
    with app.app_context():
        db.create_all() # Ensure table exists
        
        # Check if data already exists to avoid duplication
        if db.session.query(Ingredient).count() > 0:
            print("Warning: Ingredient table is not empty. Skipping migration to prevent duplicates.")
            return

        print(f"Processing {len(data)} items...")
        for item in data:
            nut = item.get('nutrition', {})
            imgs = item.get('images', {})
            
            # Helper to safely get float or None
            def get_float(val):
                if val is None: return None
                try: return float(val)
                except: return None

            ing = Ingredient(
                food_id=item['food_id'],
                name=item['food_name'],
                main_category=item.get('main_category'),
                sub_category=item.get('sub_category'),
                tags="", # Initialize empty
                
                # Physics
                default_unit=item.get('unit', 'g'),
                average_g_per_unit=None, # Not present in source
                
                # Intelligence
                aliases="[]",
                
                # Payload
                image_url=imgs.get('image_url'),
                image_prompt=imgs.get('image_prompt'),
                
                # Nutrition
                calories_per_100g=get_float(nut.get('calories_per_100g')),
                kj_per_100g=get_float(nut.get('kj_per_100g')),
                protein_per_100g=get_float(nut.get('proteins_per_100g')), # Note plural 'proteins' in JSON
                carbs_per_100g=get_float(nut.get('carbs_per_100g')),
                fat_per_100g=get_float(nut.get('fat_per_100g')),
                fat_saturated_per_100g=get_float(nut.get('fat_saturated_per_100g')),
                sugar_per_100g=get_float(nut.get('sugar_per_100g')),
                fiber_per_100g=get_float(nut.get('fiber_per_100g')),
                sodium_mg_per_100g=get_float(nut.get('sodium_mg_per_100g'))
            )
            ingredients.append(ing)
        
        try:
            db.session.add_all(ingredients)
            db.session.commit()
            print(f"Successfully migrated {len(ingredients)} ingredients to SQLite.")
        except Exception as e:
            db.session.rollback()
            print(f"Migration failed: {e}")

    # os.remove('pantry.json')

if __name__ == '__main__':
    migrate()
