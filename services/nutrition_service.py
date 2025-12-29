from database.models import Recipe, Ingredient, RecipeIngredient
from database.models import db

def calculate_nutritional_totals(recipe_id):
    """
    Calculates the total kcal, protein, carbs, fat, fiber, sugar for a recipe
    by summing up the nutrition of its ingredients.
    Updates the Recipe record in place and commits.
    """
    recipe = db.session.get(Recipe, recipe_id)
    if not recipe:
        return None

    total_stats = {
        "calories": 0.0,
        "protein": 0.0,
        "carbs": 0.0,
        "fat": 0.0,
        "fiber": 0.0,
        "sugar": 0.0
    }

    # Weight Conversions (Simplified for Standard Units)
    # Ideally this would use a robust unit conversion library or table
    UNIT_TO_GRAMS = {
        'g': 1.0,
        'kg': 1000.0,
        'mg': 0.001,
        'oz': 28.35,
        'lb': 453.59,
        'ml': 1.0, # Water density assumption fallback
        'l': 1000.0,
        'tbsp': 15.0, # Water density
        'tsp': 5.0,   # Water density
        'cup': 240.0, # Water density
        'pinch': 0.5,
        'clove': 5.0, # Garlic
        'piece': 100.0, # Major assumption, prone to error without specific item data
        'unit': 100.0   # Same as piece
    }

    for ri in recipe.ingredients:
        ing = ri.ingredient
        if not ing: continue

        # 1. Determine Gram Weight
        grams = 0.0
        unit_lower = ri.unit.lower().strip()
        
        # Check if ingredient has a specific density for 'unit' types (like 1 'unit' or 'serving')
        if ing.average_g_per_unit and unit_lower in ['unit', 'piece', 'serving', 'slices', 'slice']:
             grams = ri.amount * ing.average_g_per_unit
        
        # Use Standard Conversion Table
        elif unit_lower in UNIT_TO_GRAMS:
             grams = ri.amount * UNIT_TO_GRAMS[unit_lower]
        
        # Fallback for known specific words
        elif 'onion' in ing.name.lower() and unit_lower in ['unit', 'whole']:
             grams = ri.amount * 150.0 # Medium Onion
        
        # Ultimate Fallback: Treat as grams if unknown (Dangerous but better than 0 for logic flow?)
        # Or just Skip? Let's Skip but log implicitly by not adding.
        if grams <= 0:
            continue

        # 2. Add Nutrients (Nutrient per 100g * (grams / 100))
        multiplier = grams / 100.0
        
        if ing.calories_per_100g:
            total_stats["calories"] += (ing.calories_per_100g * multiplier)
        if ing.protein_per_100g:
             total_stats["protein"] += (ing.protein_per_100g * multiplier)
        if ing.carbs_per_100g:
             total_stats["carbs"] += (ing.carbs_per_100g * multiplier)
        if ing.fat_per_100g:
             total_stats["fat"] += (ing.fat_per_100g * multiplier)
        if ing.fiber_per_100g:
             total_stats["fiber"] += (ing.fiber_per_100g * multiplier)
        if ing.sugar_per_100g:
             total_stats["sugar"] += (ing.sugar_per_100g * multiplier)

    # 3. Update Recipe
    recipe.total_calories = round(total_stats["calories"], 1)
    recipe.total_protein = round(total_stats["protein"], 1)
    recipe.total_carbs = round(total_stats["carbs"], 1)
    recipe.total_fat = round(total_stats["fat"], 1)
    recipe.total_fiber = round(total_stats["fiber"], 1)
    recipe.total_sugar = round(total_stats["sugar"], 1)

    db.session.commit()
    return total_stats
