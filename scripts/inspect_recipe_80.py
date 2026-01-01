import sys
import os
import json
from sqlalchemy import inspect

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from database.models import Recipe, RecipeIngredient, Instruction, RecipeMealType

def object_as_dict(obj):
    return {c.key: getattr(obj, c.key) for c in inspect(obj).mapper.column_attrs}

def inspect_recipe(recipe_id):
    with app.app_context():
        recipe = db.session.get(Recipe, recipe_id)
        
        if not recipe:
            print(f"Recipe {recipe_id} not found.")
            return

        print(f"=== RECIPE {recipe_id} DATA ===")
        
        # 1. Basic Recipe Data
        recipe_data = object_as_dict(recipe)
        print("\n[BASIC INFO]")
        print(json.dumps(recipe_data, indent=2, default=str))
        
        # 2. Meal Types
        meal_types = [mt.meal_type for mt in recipe.meal_types]
        print("\n[MEAL TYPES]")
        print(meal_types)
        
        # 3. Ingredients (grouped by component)
        print("\n[INGREDIENTS]")
        ingredients = []
        for ri in recipe.ingredients:
            ing_data = object_as_dict(ri)
            # Add related Ingredient data
            ing_data['ingredient_name'] = ri.ingredient.name
            ing_data['food_id'] = ri.ingredient.food_id
            ingredients.append(ing_data)
        
        # Sort by component for readability
        ingredients.sort(key=lambda x: x.get('component', ''))
        print(json.dumps(ingredients, indent=2, default=str))

        # 4. Instructions
        print("\n[INSTRUCTIONS]")
        instructions = [object_as_dict(instr) for instr in recipe.instructions]
        # Sort by component, then step number
        instructions.sort(key=lambda x: (x.get('component', ''), x.get('step_number', 0)))
        print(json.dumps(instructions, indent=2, default=str))

if __name__ == "__main__":
    inspect_recipe(80)
