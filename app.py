import os
import uuid
from flask import Flask, render_template, request, redirect, url_for, flash
from database.models import db, Ingredient, Recipe, Instruction, RecipeIngredient
from services.pantry_service import get_slim_pantry_context
from ai_engine import generate_recipe_ai, get_pantry_id, chefs_data
from services.photographer_service import generate_visual_prompt, generate_actual_image, load_photographer_config
from utils.image_helpers import generate_ingredient_placeholder
import base64
from io import BytesIO
import shutil

app = Flask(__name__)

@app.template_filter('parse_chef_dna')
def parse_chef_dna(prompt):
    """Extracts sections from the system prompt for display."""
    sections = {}
    
    if not prompt: return sections
    
    # Normalize newlines
    prompt = str(prompt).replace('\\n', '\n')
    parts = prompt.split('\n')
    
    current_key = "General"
    sections[current_key] = []
    
    for line in parts:
        line = line.strip()
        if not line: continue
        
        lower_line = line.lower()
        if lower_line.startswith("role:"):
            current_key = "Role"
            sections[current_key] = [line[5:].strip()]
        elif lower_line.startswith("philosophy:"):
            current_key = "Philosophy"
            sections[current_key] = [line[11:].strip()]
        elif lower_line.startswith("tone:"):
            current_key = "Tone"
            sections[current_key] = [line[5:].strip()]
        elif lower_line.startswith("rules:"):
            current_key = "Rules"
            sections[current_key] = []
        elif current_key == "Rules" and (line[0].isdigit() or line.startswith('-')):
            sections["Rules"].append(line)
        else:
             # Append to current section
             if current_key in sections:
                sections[current_key].append(line)
             else:
                sections[current_key] = [line]
    return sections
app.config['SECRET_KEY'] = 'dev-key-secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///kitchen.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

@app.template_filter('get_protein_category')
def get_protein_category(protein_name):
    """Finds the Tier 1 category for a given protein name."""
    if not protein_name: return None
    from ai_engine import protein_data
    for category in protein_data:
        if protein_name in category['examples']:
            return category['category']
    return "Other"

db.init_app(app)

# PHOTOGRAPHER ROUTES
@app.route('/photographer', methods=['GET', 'POST'])
def photographer_studio():
    prompt = None
    recipe_text = ""
    recipe_id = None
    ingredients_list = ""
    
    config = load_photographer_config()
    
    # Check if we were sent here from a recipe page
    if request.args.get('recipe_text'):
        recipe_text = request.args.get('recipe_text')
    
    if request.args.get('recipe_id'):
        recipe_id = request.args.get('recipe_id')

    if request.args.get('ingredients_list'):
        ingredients_list = request.args.get('ingredients_list')
    
    if request.method == 'POST':
        recipe_text = request.form.get('recipe_text')
        recipe_id = request.form.get('recipe_id')
        ingredients_list = request.form.get('ingredients_list')
        
        if recipe_text:
            prompt = generate_visual_prompt(recipe_text, ingredients_list)
            
    return render_template('photographer.html', 
                         config=config, 
                         prompt=prompt, 
                         recipe_text=recipe_text,
                         recipe_id=recipe_id,
                         ingredients_list=ingredients_list)

@app.route('/photographer/snap', methods=['POST'])
def photographer_snap():
    prompt = request.form.get('visual_prompt')
    recipe_text = request.form.get('recipe_text') # Retrieve context
    recipe_id = request.form.get('recipe_id')
    ingredients_list = request.form.get('ingredients_list')
    config = load_photographer_config()

    if not prompt:
        return redirect(url_for('photographer_studio'))
        
    try:
        # Generate the Image
        img = generate_actual_image(prompt)
        
        # Save to Temp
        filename = f"temp_{uuid.uuid4().hex}.png"
        temp_path = os.path.join(app.root_path, 'static', 'temp', filename)
        img.save(temp_path, format="PNG")
        
        # Render template with the image filename AND context
        return render_template('photographer.html', 
                             config=config, 
                             prompt=prompt, 
                             recipe_text=recipe_text,
                             recipe_id=recipe_id,
                             ingredients_list=ingredients_list,
                             temp_image=filename)
                             
    except Exception as e:
        flash(f"Error generating image: {str(e)}", "error")
        # Log the full error
        print(f"Error generating image: {e}")
        return render_template('photographer.html', 
                             config=config, 
                             prompt=prompt, 
                             recipe_text=recipe_text,
                             recipe_id=recipe_id,
                             ingredients_list=ingredients_list)

@app.route('/photographer/save', methods=['POST'])
def save_recipe_image():
    filename = request.form.get('filename')
    recipe_id = request.form.get('recipe_id')
    
    if not filename or not recipe_id:
        flash("Missing data to save image", "error")
        return redirect(url_for('index'))
        
    try:
        # Move file from temp to recipes
        src = os.path.join(app.root_path, 'static', 'temp', filename)
        
        # Create cleaner permanent filename
        new_filename = f"recipe_{recipe_id}_{uuid.uuid4().hex[:8]}.png"
        dst = os.path.join(app.root_path, 'static', 'recipes', new_filename)
        
        shutil.move(src, dst)
        
        # Update DB
        recipe = db.session.get(Recipe, int(recipe_id))
        if recipe:
            recipe.image_filename = new_filename
            db.session.commit()
            flash("Image saved to recipe!", "success")
            return redirect(url_for('recipe_detail', recipe_id=recipe_id))
        else:
             flash("Recipe not found", "error")
             return redirect(url_for('index'))

    except Exception as e:
        print(f"DEBUG SAVE ERROR: {e}")
        flash(f"Error saving image: {str(e)}", "error")
        return redirect(url_for('index')) 


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        query = request.form.get('query')
        chef_id = request.form.get('chef_id', 'gourmet')
        if query:
            return redirect(url_for('generate', query=query, chef_id=chef_id))
    
    # Get recent recipes
    recent_recipes = db.session.execute(db.select(Recipe).order_by(Recipe.id.desc()).limit(10)).scalars().all()
    return render_template('index.html', recipes=recent_recipes, chefs=chefs_data)

import json

@app.route('/chefs')
def chefs_list():
    return render_template('chefs.html', chefs=chefs_data)

@app.route('/chefs/save', methods=['POST'])
def save_chef_prompt():
    chef_id = request.form.get('chef_id')
    
    # Check if we are saving via raw prompt OR individual fields
    if request.form.get('system_prompt'):
        new_prompt = request.form.get('system_prompt')
    else:
        # Reconstruct from fields
        role = request.form.get('role', '').strip()
        philosophy = request.form.get('philosophy', '').strip()
        tone = request.form.get('tone', '').strip()
        rules = request.form.get('rules', '').strip()
        
        # Ensure proper formatting
        new_prompt = f"ROLE: {role}\nPHILOSOPHY: {philosophy}\n\nTONE: {tone}\n\nRULES:\n{rules}"
    
    if not chef_id:
        flash("Missing chef ID", "error")
        return redirect(url_for('chefs_list'))
        
    # 1. Update In-Memory Data
    target_chef = next((c for c in chefs_data if c['id'] == chef_id), None)
    if target_chef:
        target_chef['system_prompt'] = new_prompt
        
        # 2. Persist to JSON
        json_path = os.path.join(os.path.dirname(__file__), "data", "chefs.json")
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
            
            # Find in JSON structure
            for chef in data['chefs']:
                if chef['id'] == chef_id:
                    chef['system_prompt'] = new_prompt
                    break
            
            with open(json_path, 'w') as f:
                json.dump(data, f, indent=4)
                
            flash(f"Updated persona for {target_chef['name']}", "success")
        except Exception as e:
             flash(f"Error saving to disk: {e}", "error")
    else:
        flash("Chef not found", "error")
        
    return redirect(url_for('chefs_list'))

@app.route('/recipes')
def recipes_list():
    recipes = db.session.execute(db.select(Recipe).order_by(Recipe.id.desc())).scalars().all()
    return render_template('recipes_list.html', recipes=recipes)

@app.route('/ingredients')
def pantry_list():
    # Fetch all ingredients for the visual pantry grid
    ingredients = db.session.execute(db.select(Ingredient).order_by(Ingredient.name)).scalars().all()
    
    # Get unique categories for the filter dropdown
    categories = db.session.execute(db.select(Ingredient.main_category).distinct()).scalars().all()
    categories = [c for c in categories if c] # Filter None
    
    return render_template('pantry.html', ingredients=ingredients, categories=sorted(categories))

@app.route('/generate')
def generate():
    query = request.args.get('query')
    chef_id = request.args.get('chef_id', 'gourmet')
    if not query:
        return redirect(url_for('index'))
    
    try:
        # Get Context for AI
        pantry_context = get_slim_pantry_context()
        
        # Call AI with context
        recipe_data = generate_recipe_ai(query, pantry_context, chef_id=chef_id)
        
        # Save to DB
        new_recipe = Recipe(
            title=recipe_data.title,
            cuisine=recipe_data.cuisine,
            diet=recipe_data.diet,
            difficulty=recipe_data.difficulty,
            protein_type=recipe_data.protein_type,
            meal_types=json.dumps(recipe_data.meal_types)
        )
        db.session.add(new_recipe)
        db.session.flush() # Get ID
        
        # Ingredients
        # Ingredients
        for group in recipe_data.ingredient_groups:
            for ing in group.ingredients:
                # ing.name is validated name from pantry
                # get_pantry_id returns the food_id string (e.g. "000322")
                food_id_str = get_pantry_id(ing.name)
                
                if not food_id_str:
                     raise ValueError(f"System error: ID not found for validated ingredient {ing.name}")
                
                # Find the internal Integer ID (PK) for this food_id
                ingredient_record = db.session.execute(
                    db.select(Ingredient).where(Ingredient.food_id == food_id_str)
                ).scalar_one_or_none()
                
                if not ingredient_record:
                    raise ValueError(f"Database consistency error: Ingredient {ing.name} ({food_id_str}) not found in DB.")

                recipe_ing = RecipeIngredient(
                    recipe_id=new_recipe.id,
                    ingredient_id=ingredient_record.id, # Use Integer PK
                    amount=ing.amount,
                    unit=ing.unit,
                    component=group.component
                )
                db.session.add(recipe_ing)
            
        # Instructions
        for instr in recipe_data.instructions:
            new_instr = Instruction(
                recipe_id=new_recipe.id,
                phase=instr.phase,
                step_number=instr.step_number,
                text=instr.text
            )
            db.session.add(new_instr)
            
        db.session.commit()
        return redirect(url_for('recipe_detail', recipe_id=new_recipe.id))
        
    except ValueError as ve:
         flash(f"Validation Error: {str(ve)}", "error")
         return redirect(url_for('index'))
    except Exception as e:
        db.session.rollback()
        flash(f"Error generating recipe: {str(e)}", "error")
        # In production, log the full traceback
        return redirect(url_for('index'))

@app.route('/recipe/<int:recipe_id>')
def recipe_detail(recipe_id):
    recipe = db.session.get(Recipe, recipe_id)
    if not recipe:
        return "Recipe not found", 404
        
    # Group instructions by phase
    steps_by_phase = {"Prep": [], "Cook": [], "Serve": []}
    for step in recipe.instructions:
        if step.phase in steps_by_phase:
            steps_by_phase[step.phase].append(step)
    
    # Sort steps in each phase
    for phase in steps_by_phase:
        steps_by_phase[phase].sort(key=lambda x: x.step_number)

    # Group ingredients by component
    ingredients_by_component = {}
    for recipe_ing in recipe.ingredients:
        comp = recipe_ing.component
        if comp not in ingredients_by_component:
            ingredients_by_component[comp] = []
        ingredients_by_component[comp].append(recipe_ing)

    return render_template('recipe.html', recipe=recipe, steps_by_phase=steps_by_phase, ingredients_by_component=ingredients_by_component)

@app.route('/api/placeholder/ingredient/\u003cfood_id\u003e')
def ingredient_placeholder(food_id):
    """Generate a dynamic SVG placeholder for an ingredient without an image."""
    ingredient = db.session.execute(
        db.select(Ingredient).where(Ingredient.food_id == food_id)
    ).scalar_one_or_none()
    
    if ingredient:
        return generate_ingredient_placeholder(ingredient.name)
    else:
        return generate_ingredient_placeholder("Unknown")


if __name__ == '__main__':
    with app.app_context():
        db.create_all() # Ensure tables exist
    app.run(debug=True, port=8000)
