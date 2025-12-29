"""Quick script to check if ingredient images are loaded in the database"""
from app import app, db
from database.models import Ingredient

with app.app_context():
    # Get first 5 ingredients
    ingredients = db.session.execute(
        db.select(Ingredient).limit(5)
    ).scalars().all()
    
    print("\n=== Checking Ingredient Images ===\n")
    for ing in ingredients:
        print(f"ID: {ing.food_id}")
        print(f"Name: {ing.name}")
        print(f"Image URL: {ing.image_url or 'NO IMAGE'}")
        print(f"Category: {ing.main_category}")
        print("-" * 50)
