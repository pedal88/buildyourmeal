#!/usr/bin/env python3
"""
Demo script to show how the ingredient image system works.
Creates a sample ingredient with and without an image to demonstrate fallback.
"""

from app import app, db
from database.models import Ingredient

def demo_image_system():
    with app.app_context():
        print("\n" + "="*60)
        print("INGREDIENT IMAGE SYSTEM DEMO")
        print("="*60 + "\n")
        
        # Show some ingredients with images
        print("📸 Ingredients WITH image URLs:")
        print("-" * 60)
        ingredients_with_images = db.session.execute(
            db.select(Ingredient).where(Ingredient.image_url.isnot(None)).limit(5)
        ).scalars().all()
        
        for ing in ingredients_with_images:
            print(f"  ✓ {ing.name:30} → {ing.image_url}")
        
        # Show some ingredients without images (if any)
        print("\n❌ Ingredients WITHOUT image URLs:")
        print("-" * 60)
        ingredients_without_images = db.session.execute(
            db.select(Ingredient).where(Ingredient.image_url.is_(None)).limit(5)
        ).scalars().all()
        
        if ingredients_without_images:
            for ing in ingredients_without_images:
                print(f"  ✗ {ing.name:30} → Will show grey fallback")
        else:
            print("  (None found - all ingredients have image URLs!)")
        
        # Statistics
        print("\n📊 Statistics:")
        print("-" * 60)
        total = db.session.execute(db.select(db.func.count(Ingredient.id))).scalar()
        with_images = db.session.execute(
            db.select(db.func.count(Ingredient.id)).where(Ingredient.image_url.isnot(None))
        ).scalar()
        
        print(f"  Total ingredients: {total}")
        print(f"  With image URLs:   {with_images}")
        print(f"  Without images:    {total - with_images}")
        print(f"  Coverage:          {(with_images/total*100):.1f}%")
        
        # How to test
        print("\n🧪 How to Test:")
        print("-" * 60)
        print("  1. Run the app:  python app.py")
        print("  2. Go to:        http://localhost:8000")
        print("  3. Generate a recipe (e.g., 'Make me a beef stir-fry')")
        print("  4. View the recipe to see ingredient images")
        print("\n  📝 Note: Images will show as grey squares with names")
        print("           until you add actual .png files to static/pantry/")
        
        # API endpoint demo
        print("\n🔗 API Endpoints:")
        print("-" * 60)
        if ingredients_with_images:
            sample = ingredients_with_images[0]
            print(f"  Static image:      /static/{sample.image_url}")
            print(f"  SVG placeholder:   /api/placeholder/ingredient/{sample.food_id}")
        
        print("\n" + "="*60)
        print("Demo complete! Your image system is ready to use.")
        print("="*60 + "\n")

if __name__ == "__main__":
    demo_image_system()
