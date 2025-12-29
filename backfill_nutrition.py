from app import app, db
from database.models import Recipe
from services.nutrition_service import calculate_nutritional_totals

def backfill_nutrition():
    print("Starting nutrition backfill...")
    with app.app_context():
        # Get all recipe IDs
        recipes = db.session.execute(db.select(Recipe)).scalars().all()
        total = len(recipes)
        print(f"Found {total} recipes to process.")
        
        for i, recipe in enumerate(recipes):
            print(f"Processing {i+1}/{total}: {recipe.title}")
            stats = calculate_nutritional_totals(recipe.id)
            if stats:
                print(f"  -> Calories: {stats['calories']:.1f}, Protein: {stats['protein']:.1f}g")
            else:
                print("  -> Skipped (Not found or error)")
                
    print("Backfill complete!")

if __name__ == "__main__":
    backfill_nutrition()
