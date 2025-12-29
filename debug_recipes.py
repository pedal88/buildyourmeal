from app import app, db
from database.models import Recipe

def get_recipe_details():
    with app.app_context():
        recipes = db.session.execute(db.select(Recipe).limit(2)).scalars().all()
        
        examples = []
        for r in recipes:
            # Build a dictionary of the recipe data
            data = {
                "Metadata (Fields)": {
                    "id": r.id,
                    "title": r.title,
                    "cuisine": r.cuisine,
                    "diet": r.diet,
                    "difficulty": r.difficulty,
                    "protein_type": r.protein_type,
                    "meal_types_raw": r.meal_types,
                    "meal_types_parsed": r.meal_types_list,
                    "image_filename": r.image_filename
                },
                "Related Data": {
                    "Instructions": [
                        {"step": i.step_number, "phase": i.phase, "text": i.text} 
                        for i in r.instructions
                    ],
                    "Ingredients": [
                        {
                            "name": ri.ingredient.name,
                            "amount": ri.amount,
                            "unit": ri.unit,
                            "component": ri.component,
                            # Ingredient Metadata
                            "ingredient_category": ri.ingredient.main_category,
                            "ingredient_id": ri.ingredient.food_id
                        }
                        for ri in r.ingredients
                    ]
                }
            }
            examples.append(data)
            
        import json
        print(json.dumps(examples, indent=4))

if __name__ == "__main__":
    get_recipe_details()
