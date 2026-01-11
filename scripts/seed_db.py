import sys
import os
from sqlalchemy import select

# Add parent directory to path to import app and models
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from database.models import Ingredient, Recipe

# Essential Ingredients Data
INITIAL_INGREDIENTS = [
    {"name": "Salt", "food_id": "SEED_001", "main_category": "Pantry", "default_unit": "tsp"},
    {"name": "Black Pepper", "food_id": "SEED_002", "main_category": "Pantry", "default_unit": "tsp"},
    {"name": "Olive Oil", "food_id": "SEED_003", "main_category": "Pantry", "default_unit": "tbsp"},
    {"name": "Vegetable Oil", "food_id": "SEED_004", "main_category": "Pantry", "default_unit": "tbsp"},
    {"name": "All-Purpose Flour", "food_id": "SEED_005", "main_category": "Pantry", "default_unit": "cup"},
    {"name": "Granulated Sugar", "food_id": "SEED_006", "main_category": "Pantry", "default_unit": "cup"},
    {"name": "Brown Sugar", "food_id": "SEED_007", "main_category": "Pantry", "default_unit": "cup"},
    {"name": "Butter", "food_id": "SEED_008", "main_category": "Dairy", "default_unit": "stick"},
    {"name": "Milk", "food_id": "SEED_009", "main_category": "Dairy", "default_unit": "cup"},
    {"name": "Eggs", "food_id": "SEED_010", "main_category": "Dairy", "default_unit": "large"},
    {"name": "Water", "food_id": "SEED_011", "main_category": "Beverage", "default_unit": "cup"},
    {"name": "Garlic", "food_id": "SEED_012", "main_category": "Vegetable", "default_unit": "clove"},
    {"name": "Onion", "food_id": "SEED_013", "main_category": "Vegetable", "default_unit": "medium"},
    {"name": "Tomato", "food_id": "SEED_014", "main_category": "Vegetable", "default_unit": "medium"},
    {"name": "Lemon", "food_id": "SEED_015", "main_category": "Fruit", "default_unit": "medium"},
    {"name": "Chicken Breast", "food_id": "SEED_016", "main_category": "Meat", "default_unit": "lb"},
    {"name": "Ground Beef", "food_id": "SEED_017", "main_category": "Meat", "default_unit": "lb"},
    {"name": "Rice", "food_id": "SEED_018", "main_category": "Grain", "default_unit": "cup"},
    {"name": "Pasta", "food_id": "SEED_019", "main_category": "Grain", "default_unit": "lb"},
    {"name": "Soy Sauce", "food_id": "SEED_020", "main_category": "Condiment", "default_unit": "tbsp"},
]

def seed_ingredients():
    print("--- Seeding Ingredients ---")
    count = 0
    for data in INITIAL_INGREDIENTS:
        # Idempotency Check: Check by food_id
        stmt = select(Ingredient).where(Ingredient.food_id == data["food_id"])
        existing = db.session.execute(stmt).scalar_one_or_none()
        
        if not existing:
            # Also check by name to avoid duplicates if food_id is different but name is same
            stmt_name = select(Ingredient).where(Ingredient.name == data["name"])
            existing_name = db.session.execute(stmt_name).scalar_one_or_none()
            
            if existing_name:
                 print(f"Skipping {data['name']} (Already exists by name)")
                 continue

            new_ingredient = Ingredient(
                name=data["name"],
                food_id=data["food_id"],
                main_category=data["main_category"],
                default_unit=data["default_unit"],
                is_basic_ingredient=True,
                is_original=True
            )
            db.session.add(new_ingredient)
            count += 1
            print(f"Adding {data['name']}")
        else:
            print(f"Skipping {data['name']} (Already exists)")
    
    db.session.commit()
    print(f"Successfully added {count} new ingredients.")

def seed_database():
    with app.app_context():
        print(f"Connected to DB: {app.config.get('SQLALCHEMY_DATABASE_URI', 'Unknown')}")
        seed_ingredients()
        
        # Note on Meal Types:
        # In the current schema, 'RecipeMealType' is a join table linking a Recipe to a string meal_type.
        # It is NOT a standalone reference table, so we cannot seed 'Meal Types' without creating Recipes.
        # Meal types are effectively tags applied to recipes.
        print("\nNote: Meal Types don't require seeding (they are stored on Recipes).")

if __name__ == "__main__":
    seed_database()
