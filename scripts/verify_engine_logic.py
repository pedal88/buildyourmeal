import sys
import os
import json
from pydantic import ValidationError

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_engine import RecipeSchema

# Mock Data for Validation Test
valid_mock_recipe = {
    "title": "Simple Pasta",
    "cuisine": "Italian",
    "diet": "omnivore", 
    "difficulty": "Simplistic",
    "protein_type": "Vegetarian",
    "chef_id": "french_classic",
    "meal_types": ["Dinner"],
    "cleanup_factor": 2,
    "taste_level": 3,
    "prep_time_mins": 30, # Valid interval
    "ingredient_groups": [
        {
            "component": "Main",
            "ingredients": [
                {"name": "Pasta", "amount": 100, "unit": "g"}
            ]
        }
    ],
    "instructions": [
        {"phase": "Cook", "step_number": 1, "text": "Boil water."}
    ]
}

invalid_time_recipe = valid_mock_recipe.copy()
invalid_time_recipe["prep_time_mins"] = 23 # Should snap to 20 or 30

def test_schema_validation():
    print("Testing Schema Validation...")
    
    # 1. Valid Case
    try:
        r = RecipeSchema(**valid_mock_recipe)
        print("✅ Valid recipe passed.")
    except ValidationError as e:
        print(f"❌ Valid recipe failed: {e}")

    # 2. Time Snapping
    try:
        r = RecipeSchema(**invalid_time_recipe)
        if r.prep_time_mins in [20, 30]:
            print(f"✅ Time snapping passed. Input 23 -> Output {r.prep_time_mins}")
        else:
            print(f"❌ Time snapping failed. Input 23 -> Output {r.prep_time_mins}")
    except ValidationError as e:
         print(f"❌ Time snapping validation error: {e}")

    # 3. Chef ID Check
    # (No strict validator on chef_id in Schema other than type str, so just checking field exists)
    if hasattr(r, 'chef_id'):
        print(f"✅ Chef ID field exists.")
        
    print("Schema Validation Complete.")

if __name__ == "__main__":
    test_schema_validation()
