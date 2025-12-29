#!/usr/bin/env python3
"""
Script to copy ingredient images from temp folder to static/pantry/
and verify matches with database.
"""

import os
import shutil
from pathlib import Path
from app import app, db
from database.models import Ingredient

def copy_ingredient_images():
    """Copy images from temp folder to static/pantry and report matches."""
    
    # Paths
    source_dir = Path("temp_ingredients_for_Mapping")
    target_dir = Path("static/pantry")
    
    # Ensure target directory exists
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Get all PNG files (excluding _default versions)
    source_images = sorted([
        f for f in source_dir.glob("*.png") 
        if not f.name.endswith("_default.png")
    ])
    
    print("\n" + "="*70)
    print("INGREDIENT IMAGE IMPORT")
    print("="*70 + "\n")
    
    print(f"📁 Source: {source_dir}")
    print(f"📁 Target: {target_dir}")
    print(f"📸 Found {len(source_images)} images to import\n")
    
    # Track statistics
    copied = 0
    updated = 0
    new_images = 0
    matched = 0
    unmatched = []
    
    with app.app_context():
        # Get all ingredient food_ids from database
        all_ingredients = db.session.execute(
            db.select(Ingredient.food_id, Ingredient.name)
        ).all()
        
        db_food_ids = {ing.food_id for ing in all_ingredients}
        
        print("🔄 Copying images...\n")
        
        for source_file in source_images:
            # Extract food_id from filename (e.g., "000001.png" -> "000001")
            food_id = source_file.stem  # Gets filename without extension
            target_file = target_dir / source_file.name
            
            # Check if file already exists
            already_exists = target_file.exists()
            
            # Copy the file
            shutil.copy2(source_file, target_file)
            
            if already_exists:
                updated += 1
            else:
                new_images += 1
            
            copied += 1
            
            # Check if this food_id exists in database
            if food_id in db_food_ids:
                matched += 1
                # Get ingredient name for reporting
                ing_name = next(
                    (ing.name for ing in all_ingredients if ing.food_id == food_id),
                    "Unknown"
                )
                if matched <= 10:  # Show first 10 matches
                    print(f"  ✓ {food_id}.png → {ing_name}")
            else:
                unmatched.append(food_id)
        
        if matched > 10:
            print(f"  ... and {matched - 10} more matches")
        
        # Summary
        print("\n" + "="*70)
        print("SUMMARY")
        print("="*70)
        print(f"  📸 Total images copied:  {copied}")
        print(f"  ✨ New images added:     {new_images}")
        print(f"  🔄 Existing updated:     {updated}")
        print(f"  ✅ Matched in database:  {matched}")
        print(f"  ❌ Not in database:      {len(unmatched)}")
        print(f"  📊 Match rate:           {(matched/copied*100):.1f}%")
        
        # Show database coverage
        total_ingredients = len(db_food_ids)
        coverage = (matched / total_ingredients * 100)
        print(f"\n  🎯 Database coverage:    {matched}/{total_ingredients} ({coverage:.1f}%)")
        
        # Show unmatched if any
        if unmatched and len(unmatched) <= 20:
            print(f"\n  ⚠️  Unmatched food_ids: {', '.join(unmatched)}")
        elif unmatched:
            print(f"\n  ⚠️  Unmatched food_ids: {', '.join(unmatched[:20])}... and {len(unmatched)-20} more")
        
        print("\n" + "="*70)
        print("✨ Import complete! Images are now in static/pantry/")
        print("="*70 + "\n")
        
        # Next steps
        print("🚀 NEXT STEPS:")
        print("  1. Run the app: python app.py")
        print("  2. Generate a recipe")
        print("  3. View the recipe to see ingredient images!")
        print(f"\n  💡 {matched} ingredients will now show actual images")
        print(f"  💡 {total_ingredients - matched} ingredients will show grey fallback\n")

if __name__ == "__main__":
    copy_ingredient_images()
