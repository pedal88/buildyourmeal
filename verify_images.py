#!/usr/bin/env python3
"""
Verification script to show which ingredients now have actual images
vs which will use the grey fallback.
"""

import os
from pathlib import Path
from app import app, db
from database.models import Ingredient

def verify_ingredient_images():
    """Check which ingredients have actual image files."""
    
    static_pantry = Path("static/pantry")
    
    with app.app_context():
        print("\n" + "="*70)
        print("INGREDIENT IMAGE VERIFICATION")
        print("="*70 + "\n")
        
        # Get all ingredients
        all_ingredients = db.session.execute(
            db.select(Ingredient).order_by(Ingredient.food_id)
        ).scalars().all()
        
        # Categorize ingredients
        with_images = []
        without_images = []
        
        for ing in all_ingredients:
            if ing.image_url:
                # Check if actual file exists
                image_path = static_pantry / f"{ing.food_id}.png"
                if image_path.exists():
                    with_images.append(ing)
                else:
                    without_images.append(ing)
            else:
                without_images.append(ing)
        
        # Show samples with images
        print("✅ INGREDIENTS WITH ACTUAL IMAGES (showing first 20):")
        print("-" * 70)
        for ing in with_images[:20]:
            print(f"  📸 {ing.food_id} - {ing.name:40} [{ing.main_category}]")
        
        if len(with_images) > 20:
            print(f"  ... and {len(with_images) - 20} more\n")
        else:
            print()
        
        # Show samples without images
        print("⬜ INGREDIENTS WITH GREY FALLBACK (showing first 20):")
        print("-" * 70)
        for ing in without_images[:20]:
            print(f"  🔲 {ing.food_id} - {ing.name:40} [{ing.main_category}]")
        
        if len(without_images) > 20:
            print(f"  ... and {len(without_images) - 20} more\n")
        else:
            print()
        
        # Statistics
        total = len(all_ingredients)
        with_count = len(with_images)
        without_count = len(without_images)
        
        print("="*70)
        print("STATISTICS")
        print("="*70)
        print(f"  Total ingredients:       {total}")
        print(f"  With actual images:      {with_count} ({with_count/total*100:.1f}%)")
        print(f"  With grey fallback:      {without_count} ({without_count/total*100:.1f}%)")
        
        # Category breakdown
        print("\n📊 COVERAGE BY CATEGORY:")
        print("-" * 70)
        
        categories = {}
        for ing in all_ingredients:
            cat = ing.main_category or "uncategorized"
            if cat not in categories:
                categories[cat] = {"total": 0, "with_images": 0}
            categories[cat]["total"] += 1
            if ing in with_images:
                categories[cat]["with_images"] += 1
        
        for cat in sorted(categories.keys()):
            stats = categories[cat]
            coverage = (stats["with_images"] / stats["total"] * 100) if stats["total"] > 0 else 0
            print(f"  {cat:20} {stats['with_images']:3}/{stats['total']:3} ({coverage:5.1f}%)")
        
        print("\n" + "="*70)
        print("✨ Verification complete!")
        print("="*70 + "\n")
        
        print("🎨 VISUAL PREVIEW:")
        print("  • Ingredients with images will show actual photos")
        print("  • Ingredients without images will show grey squares with names")
        print("\n🚀 Ready to test! Run: python app.py\n")

if __name__ == "__main__":
    verify_ingredient_images()
