#!/usr/bin/env python3
"""
Quick demo to show sample ingredients with images.
Useful for testing and verification.
"""

from app import app, db
from database.models import Ingredient
from pathlib import Path

def show_sample_images():
    """Display sample ingredients that have images."""
    
    with app.app_context():
        print("\n" + "="*70)
        print("SAMPLE INGREDIENTS WITH IMAGES")
        print("="*70 + "\n")
        
        # Get some ingredients with images from different categories
        categories = ["meat", "vegetables", "fruit and fruit products", "dairy and egg", "fish and seafood"]
        
        for category in categories:
            print(f"📁 {category.upper()}")
            print("-" * 70)
            
            ingredients = db.session.execute(
                db.select(Ingredient)
                .where(Ingredient.main_category == category)
                .where(Ingredient.image_url.isnot(None))
                .limit(5)
            ).scalars().all()
            
            for ing in ingredients:
                # Check if file exists
                image_path = Path(f"static/{ing.image_url}")
                status = "✅" if image_path.exists() else "❌"
                print(f"  {status} {ing.name:35} → /static/{ing.image_url}")
            
            print()
        
        print("="*70)
        print("🌐 To view images in browser:")
        print("="*70)
        print("  1. Start app: python app.py")
        print("  2. Visit: http://localhost:8000/static/pantry/000001.png")
        print("  3. Or generate a recipe to see them in context!")
        print()

if __name__ == "__main__":
    show_sample_images()
