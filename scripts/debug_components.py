import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.models import Recipe, RecipeIngredient, Instruction
from app import app

with app.app_context():
    r = Recipe.query.order_by(Recipe.id.desc()).first()
    print(f'Recipe: {r.title}\n')
    
    print('Ingredient Components:')
    ing_components = set()
    for ing in r.ingredients:
        if ing.component not in ing_components:
            ing_components.add(ing.component)
            print(f'  - {ing.component}')
    
    print('\nInstruction Components:')
    instr_components = set()
    for instr in r.instructions:
        if instr.component not in instr_components:
            instr_components.add(instr.component)
            print(f'  - {instr.component}')
    
    print('\nMismatch?', ing_components != instr_components)
    if ing_components != instr_components:
        print(f'Missing in instructions: {ing_components - instr_components}')
        print(f'Missing in ingredients: {instr_components - ing_components}')
