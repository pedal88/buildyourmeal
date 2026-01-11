import sys
import os
import sqlite3
import logging
from sqlalchemy import text

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
# Import models to ensure they are registered
from database.models import User, Chef, Ingredient, Recipe, RecipeIngredient, Instruction, RecipeMealType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SQLITE_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'instance/kitchen.db')

def get_sqlite_connection():
    if not os.path.exists(SQLITE_DB_PATH):
        logger.error(f"Source database not found at {SQLITE_DB_PATH}")
        sys.exit(1)
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def migrate_users(source_conn):
    logger.info("Migrating Users...")
    rows = source_conn.execute("SELECT * FROM user").fetchall()
    count = 0
    for row in rows:
        existing = db.session.execute(db.select(User).where(User.email == row['email'])).scalar_one_or_none()
        if not existing:
            user = User(
                email=row['email'],
                password_hash=row['password_hash'],
                is_admin=row['is_admin']
            )
            # Preserve ID if possible, but postgres uses sequences. Best to let PG assign IDs unless linking.
            # However, for migration, preserving IDs is safer for FKs.
            # SQLAlchemy INSERT doesn't easily force ID unless we bypass autoincrement.
            # But wait, Recipe references Chef (String ID) and User (Int ID).
            # If User IDs change, it shouldn't matter as nothing references User in this schema (yet).
            db.session.add(user)
            count += 1
    logger.info(f"Added {count} Users.")

def migrate_chefs(source_conn):
    logger.info("Migrating Chefs...")
    rows = source_conn.execute("SELECT * FROM chef").fetchall()
    count = 0
    for row in rows:
        existing = db.session.get(Chef, row['id'])
        if not existing:
            chef = Chef(
                id=row['id'],
                name=row['name'],
                archetype=row['archetype'],
                description=row['description'],
                image_filename=row['image_filename'],
                constraints=row['constraints'],
                diet_preferences=row['diet_preferences'],
                cooking_style=row['cooking_style'],
                ingredient_logic=row['ingredient_logic'],
                instruction_style=row['instruction_style']
            )
            db.session.add(chef)
            count += 1
    logger.info(f"Added {count} Chefs.")

def migrate_ingredients(source_conn):
    logger.info("Migrating Ingredients...")
    rows = source_conn.execute("SELECT * FROM ingredient").fetchall()
    count = 0
    # Map old ID to new ID for FK fixup later
    id_map = {} 
    
    for row in rows:
        # Check by food_id (unique stable identifier)
        existing = db.session.execute(db.select(Ingredient).where(Ingredient.food_id == row['food_id'])).scalar_one_or_none()
        
        if not existing:
            ing = Ingredient(
                food_id=row['food_id'],
                name=row['name'],
                main_category=row['main_category'],
                sub_category=row['sub_category'],
                tags=row['tags'],
                default_unit=row['default_unit'],
                average_g_per_unit=row['average_g_per_unit'],
                aliases=row['aliases'],
                is_basic_ingredient=row['is_basic_ingredient'],
                is_original=row['is_original'],
                created_at=row['created_at'],
                image_url=row['image_url'],
                image_prompt=row['image_prompt'],
                calories_per_100g=row['calories_per_100g'],
                kj_per_100g=row['kj_per_100g'],
                protein_per_100g=row['protein_per_100g'],
                carbs_per_100g=row['carbs_per_100g'],
                fat_per_100g=row['fat_per_100g'],
                fat_saturated_per_100g=row['fat_saturated_per_100g'],
                sugar_per_100g=row['sugar_per_100g'],
                fiber_per_100g=row['fiber_per_100g'],
                sodium_mg_per_100g=row['sodium_mg_per_100g']
            )
            db.session.add(ing)
            db.session.flush() # Get new ID
            id_map[row['id']] = ing.id
            count += 1
        else:
            id_map[row['id']] = existing.id # Map old ID to existing ID

    logger.info(f"Added {count} Ingredients.")
    return id_map

def migrate_recipes(source_conn, ingredient_id_map):
    logger.info("Migrating Recipes...")
    rows = source_conn.execute("SELECT * FROM recipe").fetchall()
    count = 0
    
    for row in rows:
        existing = db.session.execute(db.select(Recipe).where(Recipe.title == row['title'])).scalar_one_or_none()
        if not existing:
            # 1. Create Recipe
            recipe = Recipe(
                title=row['title'],
                cuisine=row['cuisine'],
                diet=row['diet'],
                difficulty=row['difficulty'],
                protein_type=row['protein_type'],
                image_filename=row['image_filename'],
                chef_id=row['chef_id'],
                taste_level=row['taste_level'],
                prep_time_mins=row['prep_time_mins'],
                cleanup_factor=row['cleanup_factor'],
                total_calories=row['total_calories'],
                total_protein=row['total_protein'],
                total_carbs=row['total_carbs'],
                total_fat=row['total_fat'],
                total_fiber=row['total_fiber'],
                total_sugar=row['total_sugar']
            )
            db.session.add(recipe)
            db.session.flush() # Get new ID
            new_recipe_id = recipe.id
            
            # 2. Migrate Children (Meal Types)
            mt_rows = source_conn.execute("SELECT * FROM recipe_meal_type WHERE recipe_id = ?", (row['id'],)).fetchall()
            for mt_row in mt_rows:
                db.session.add(RecipeMealType(recipe_id=new_recipe_id, meal_type=mt_row['meal_type']))

            # 3. Migrate Children (Instructions)
            inst_rows = source_conn.execute("SELECT * FROM instruction WHERE recipe_id = ?", (row['id'],)).fetchall()
            for inst_row in inst_rows:
                db.session.add(Instruction(
                    recipe_id=new_recipe_id,
                    phase=inst_row['phase'],
                    component=inst_row['component'],
                    step_number=inst_row['step_number'],
                    text=inst_row['text']
                ))

            # 4. Migrate Children (Recipe Ingredients)
            ri_rows = source_conn.execute("SELECT * FROM recipe_ingredient WHERE recipe_id = ?", (row['id'],)).fetchall()
            for ri_row in ri_rows:
                old_ing_id = ri_row['ingredient_id']
                if old_ing_id in ingredient_id_map:
                    db.session.add(RecipeIngredient(
                        recipe_id=new_recipe_id,
                        ingredient_id=ingredient_id_map[old_ing_id],
                        amount=ri_row['amount'],
                        unit=ri_row['unit'],
                        component=ri_row['component']
                    ))
                else:
                    logger.warning(f"Skipping RecipeIngredient for Recipe '{recipe.title}': Source Ingredient ID {old_ing_id} not found in map.")

            count += 1
            
    logger.info(f"Added {count} Recipes (and their details).")

def migrate():
    source_conn = get_sqlite_connection()
    
    with app.app_context():
        logger.info(f"Target Database: {app.config.get('SQLALCHEMY_DATABASE_URI', 'Unknown')}")
        
        try:
            migrate_users(source_conn)
            migrate_chefs(source_conn)
            db.session.commit() # Commit base data
            
            ing_id_map = migrate_ingredients(source_conn)
            db.session.commit() # Commit ingredients to ensure IDs are stable
            
            migrate_recipes(source_conn, ing_id_map)
            db.session.commit() # Commit recipes and relations
            
            logger.info("Migration Complete!")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Migration Failed: {e}")
            raise

if __name__ == "__main__":
    migrate()
