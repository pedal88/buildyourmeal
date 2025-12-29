import json
import os
from app import app, db
from database.models import Ingredient

def load_pantry():
    path = os.path.join(os.path.dirname(__file__), "data", "pantry.json")
    with open(path, 'r') as f:
        data = json.load(f)
    
    with app.app_context():
        # Create tables if they don't exist yet
        db.create_all()
        
        print(f"Seeding pantry data from {path}...")
        count = 0
        updated = 0
        
        for item in data:
            # Check if exists
            existing = db.session.execute(
                db.select(Ingredient).where(Ingredient.food_id == item['food_id'])
            ).scalar_one_or_none()
            
            # Extract nested data
            nutrition = item.get('nutrition', {})
            images = item.get('images', {})
            
            if not existing:
                # Create new ingredient with all fields
                ing = Ingredient(
                    food_id=item['food_id'],
                    name=item['food_name'],
                    main_category=item.get('main_category'),
                    sub_category=item.get('sub_category'),
                    tags=item.get('tags', ''),
                    default_unit=item.get('unit', 'g'),
                    average_g_per_unit=item.get('average_g_per_unit'),
                    
                    # Images
                    image_url=images.get('image_url'),
                    image_prompt=images.get('image_prompt'),
                    
                    # Nutrition
                    calories_per_100g=nutrition.get('calories_per_100g'),
                    kj_per_100g=nutrition.get('kj_per_100g'),
                    protein_per_100g=nutrition.get('proteins_per_100g'),
                    carbs_per_100g=nutrition.get('carbs_per_100g'),
                    fat_per_100g=nutrition.get('fat_per_100g'),
                    fat_saturated_per_100g=nutrition.get('fat_saturated_per_100g'),
                    sugar_per_100g=nutrition.get('sugar_per_100g'),
                    fiber_per_100g=nutrition.get('fiber_per_100g'),
                    sodium_mg_per_100g=nutrition.get('sodium_mg_per_100g')
                )
                db.session.add(ing)
                count += 1
            else:
                # Update existing ingredient with latest data (Images + Nutrition)
                
                # Images (preserve existing if JSON is missing it, but overwrite if JSON has it? 
                # Strategy: Only update if we have new data to offer)
                if images.get('image_url'):
                     existing.image_url = images.get('image_url')
                if images.get('image_prompt'):
                     existing.image_prompt = images.get('image_prompt')

                # Nutrition - Always sync from JSON
                existing.calories_per_100g = nutrition.get('calories_per_100g')
                existing.kj_per_100g = nutrition.get('kj_per_100g')
                existing.protein_per_100g = nutrition.get('proteins_per_100g')
                existing.carbs_per_100g = nutrition.get('carbs_per_100g')
                existing.fat_per_100g = nutrition.get('fat_per_100g')
                existing.fat_saturated_per_100g = nutrition.get('fat_saturated_per_100g')
                existing.sugar_per_100g = nutrition.get('sugar_per_100g')
                existing.fiber_per_100g = nutrition.get('fiber_per_100g')
                existing.sodium_mg_per_100g = nutrition.get('sodium_mg_per_100g')
                
                updated += 1
        
        db.session.commit()
        print(f"Pantry seeded successfully. Added {count} new ingredients, updated {updated} existing.")

if __name__ == "__main__":
    load_pantry()
