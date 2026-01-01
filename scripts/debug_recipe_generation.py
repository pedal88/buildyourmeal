
import sys
import os
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_engine import generate_recipe_ai

print("--- STARTING DEBUG GENERATION ---")
try:
    recipe = generate_recipe_ai("Beef Bourguignon", chef_id="french_classic")
    print("\n--- GENERATION SUCCESSFUL ---")
    print(f"Title: {recipe.title}")
    print(f"Step Count: {len(recipe.instructions)}")
    
    print("\n--- INSTRUCTIONS ---")
    for step in recipe.instructions:
        print(f"[{step.phase}] {step.step_number}: {step.text}")
        
except Exception as e:
    print(f"\n--- GENERATION FAILED ---")
    print(e)
