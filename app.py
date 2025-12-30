import os
import uuid
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from database.models import db, Ingredient, Recipe, Instruction, RecipeIngredient
from sqlalchemy import or_
from services.pantry_service import get_slim_pantry_context
from ai_engine import generate_recipe_ai, get_pantry_id, chefs_data
from services.photographer_service import generate_visual_prompt, generate_actual_image, generate_visual_prompt_from_image, load_photographer_config
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
@app.context_processor
def utility_processor():
    def update_query_params(**kwargs):
        args = request.args.copy()
        for key, value in kwargs.items():
            args[key] = value
        return url_for(request.endpoint, **args)
    return dict(update_query_params=update_query_params)

db.init_app(app)

# PHOTOGRAPHER ROUTES

@app.route('/studio', methods=['GET', 'POST'])
def studio_view():
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
        
        # Check for Image Upload (Option 1B)
        if 'reference_image' in request.files and request.files['reference_image'].filename != '':
            file = request.files['reference_image']
            image_bytes = file.read()
            prompt = generate_visual_prompt_from_image(image_bytes)
            
        # Fallback to Text (Option 1A)
        elif recipe_text:
            prompt = generate_visual_prompt(recipe_text, ingredients_list)
            
            
    return render_template('studio.html', 
                         config=config, 
                         prompt=prompt, 
                         recipe_text=recipe_text,
                         recipe_id=recipe_id,
                         ingredients_list=ingredients_list)

@app.route('/studio/snap', methods=['POST'])
def studio_snap():
    prompt = request.form.get('visual_prompt')
    recipe_text = request.form.get('recipe_text') # Retrieve context
    recipe_id = request.form.get('recipe_id')
    ingredients_list = request.form.get('ingredients_list')
    config = load_photographer_config()

    if not prompt:
        return redirect(url_for('studio_view'))
        
    try:
        # Generate the Image
        img = generate_actual_image(prompt)
        
        # Save to Temp
        filename = f"temp_{uuid.uuid4().hex}.png"
        temp_path = os.path.join(app.root_path, 'static', 'temp', filename)
        img.save(temp_path, format="PNG")
        
        # Render template with the image filename AND context
        return render_template('studio.html', 
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
        return render_template('studio.html', 
                             config=config, 
                             prompt=prompt, 
                             recipe_text=recipe_text,
                             recipe_id=recipe_id,
                             ingredients_list=ingredients_list)

@app.route('/studio/save', methods=['POST'])
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

def load_json_option(filename, key):
    data_dir = os.path.join(app.root_path, 'data')
    try:
        with open(os.path.join(data_dir, filename), 'r') as f:
            return json.load(f).get(key, [])
    except:
        return []

@app.route('/chefs')
def chefs_list():
    diets_data = load_json_option('diets_tag.json', 'diets')
    
    # Load Cooking Methods (Grouped)
    methods_data_raw = load_json_option('cooking_methods.json', 'cooking_methods')
    grouped_methods = {}
    for m in methods_data_raw:
        cat = m['category']
        if cat not in grouped_methods:
            grouped_methods[cat] = []
        grouped_methods[cat].append(m['method'])
    
    # Sort keys
    grouped_methods = dict(sorted(grouped_methods.items()))
    
    return render_template('chefs.html', chefs=chefs_data, diets_list=diets_data, grouped_methods=grouped_methods)

@app.route('/chefs/save', methods=['POST'])
def save_chefs_json():
    try:
        data = request.get_json()
        if not data or 'chefs' not in data:
            return jsonify({'success': False, 'error': 'Invalid JSON structure'}), 400
        
        new_chefs = data['chefs']
        
        # Validate/Persist
        json_path = os.path.join(os.path.dirname(__file__), "data", "chefs.json")
        
        # We replace the entire list with the new data from UI
        # But we should preserve structure wrappers if any
        full_data = {"chefs": new_chefs}
        
        with open(json_path, 'w') as f:
            json.dump(full_data, f, indent=2)
            
        # Update in-memory reference
        global chefs_data
        chefs_data = new_chefs
        
        # Also need to update cache in ai_engine if it's imported there
        # Since ai_engine loads on import, we might need a reload mechanism 
        # or just let the app restart handle it. 
        # For this dev server, a restart is often best, but let's try to update the reference if shared.
        import ai_engine
        ai_engine.chefs_data = new_chefs
        ai_engine.chef_map = {c['id']: c for c in new_chefs}

        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Error saving chefs: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/recipes')
def recipes_list():
    # 1. Load Filter Data Options
    # Use global load_json_option helper

    cuisine_options = load_json_option('cuisines.json', 'cuisines')
    diet_options = load_json_option('diets_tag.json', 'diets')
    difficulty_options = load_json_option('difficulty_tag.json', 'difficulty')
    
    # Protein Types (List of Dicts -> List of Strings)
    pt_data = load_json_option('protein_types.json', 'protein_types')
    protein_options = []
    for p in pt_data:
        if 'examples' in p:
            protein_options.extend(p['examples'])
    protein_options = sorted(list(set(protein_options)))
    
    # Meal Types (Dict of Lists -> Flattened List)
    mt_data = load_json_option('meal_types.json', 'meal_classification')
    meal_type_options = []
    if isinstance(mt_data, dict):
        for category_list in mt_data.values():
            if isinstance(category_list, list):
                meal_type_options.extend(category_list)
    meal_type_options = sorted(list(set(meal_type_options)))

    # 2. Handle Query Params (multi-select)
    # Default to ALL options if not specified (First load behavior)
    selected_cuisines = request.args.getlist('cuisine')
    if not selected_cuisines and 'cuisine' not in request.args:
        selected_cuisines = cuisine_options
        
    selected_diets = request.args.getlist('diet')
    if not selected_diets and 'diet' not in request.args:
        selected_diets = diet_options

    selected_meal_types = request.args.getlist('meal_type')
    if not selected_meal_types and 'meal_type' not in request.args:
        selected_meal_types = meal_type_options
    
    selected_difficulties = request.args.getlist('difficulty')
    selected_proteins = request.args.getlist('protein_type')

    # 3. Build Filtered Query
    stmt = db.select(Recipe).order_by(Recipe.id.desc())

    if selected_cuisines:
        stmt = stmt.where(Recipe.cuisine.in_(selected_cuisines))
    
    if selected_diets:
        stmt = stmt.where(Recipe.diet.in_(selected_diets))

    if selected_difficulties:
        stmt = stmt.where(Recipe.difficulty.in_(selected_difficulties))

    if selected_proteins:
        # Filter by INGREDIENTS that match the selected protein names
        # We join to RecipeIngredient -> Ingredient and check for partial matches
        # or exact matches to the protein examples.
        # Since 'Beef' might match 'Ground Beef', ILIKE is good.
        clauses = []
        for p in selected_proteins:
            clauses.append(Recipe.ingredients.any(
                RecipeIngredient.ingredient.has(Ingredient.name.ilike(f'%{p}%'))
            ))
        if clauses:
             stmt = stmt.where(or_(*clauses))

    if selected_meal_types:
        # JSON list contains check. We want recipes that match ANY of the selected types.
        clauses = [Recipe.meal_types.like(f'%"{m}"%') for m in selected_meal_types]
        if clauses:
            stmt = stmt.where(or_(*clauses))

    recipes = db.session.execute(stmt).scalars().all()

    return render_template('recipes_list.html', 
                         recipes=recipes,
                         cuisine_options=sorted(cuisine_options),
                         diet_options=sorted(diet_options),
                         difficulty_options=difficulty_options,
                         protein_options=sorted(protein_options),
                         meal_type_options=meal_type_options,
                         # Selected State
                         selected_cuisines=selected_cuisines,
                         selected_diets=selected_diets,
                         selected_meal_types=selected_meal_types,
                         selected_difficulties=selected_difficulties,
                         selected_proteins=selected_proteins)

@app.route('/recipes_list')
def recipes_table_view():
    # 1. Load Filter Data Options
    # Use global load_json_option helper

    cuisine_options = load_json_option('cuisines.json', 'cuisines')
    diet_options = load_json_option('diets_tag.json', 'diets')
    difficulty_options = load_json_option('difficulty_tag.json', 'difficulty')
    
    pt_data = load_json_option('protein_types.json', 'protein_types')
    protein_options = []
    for p in pt_data:
        if 'examples' in p:
            protein_options.extend(p['examples'])
    protein_options = sorted(list(set(protein_options)))
    
    mt_data = load_json_option('meal_types.json', 'meal_classification')
    meal_type_options = []
    if isinstance(mt_data, dict):
        for category_list in mt_data.values():
            if isinstance(category_list, list):
                meal_type_options.extend(category_list)
    meal_type_options = sorted(list(set(meal_type_options)))

    # 2. Handle Query Params
    selected_cuisines = request.args.getlist('cuisine')
    selected_diets = request.args.getlist('diet')
    selected_meal_types = request.args.getlist('meal_type')
    selected_difficulties = request.args.getlist('difficulty')
    selected_proteins = request.args.getlist('protein_type')

    # Sorting
    sort_col = request.args.get('sort', 'id')
    sort_dir = request.args.get('dir', 'desc')

    # 3. Build Query
    stmt = db.select(Recipe)

    if selected_cuisines:
        stmt = stmt.where(Recipe.cuisine.in_(selected_cuisines))
    if selected_diets:
        stmt = stmt.where(Recipe.diet.in_(selected_diets))
    if selected_difficulties:
        stmt = stmt.where(Recipe.difficulty.in_(selected_difficulties))
    if selected_proteins:
        clauses = []
        for p in selected_proteins:
            clauses.append(Recipe.ingredients.any(
                RecipeIngredient.ingredient.has(Ingredient.name.ilike(f'%{p}%'))
            ))
        if clauses:
             stmt = stmt.where(or_(*clauses))
    if selected_meal_types:
        clauses = [Recipe.meal_types.like(f'%"{m}"%') for m in selected_meal_types]
        if clauses:
            stmt = stmt.where(or_(*clauses))

    # Apply Sorting
    valid_cols = {
        'id': Recipe.id,
        'title': Recipe.title,
        'cuisine': Recipe.cuisine,
        'diet': Recipe.diet,
        'difficulty': Recipe.difficulty,
        'protein_type': Recipe.protein_type,
        'total_calories': Recipe.total_calories,
        'total_protein': Recipe.total_protein,
        'total_carbs': Recipe.total_carbs,
        'total_fat': Recipe.total_fat,
        'total_fiber': Recipe.total_fiber,
        'total_sugar': Recipe.total_sugar
    }
    
    sort_attr = valid_cols.get(sort_col, Recipe.id)
    if sort_dir == 'asc':
        stmt = stmt.order_by(sort_attr.asc())
    else:
        stmt = stmt.order_by(sort_attr.desc())

    recipes = db.session.execute(stmt).scalars().all()

    return render_template('recipes_table.html', 
                         recipes=recipes,
                         cuisine_options=sorted(cuisine_options),
                         diet_options=sorted(diet_options),
                         difficulty_options=difficulty_options,
                         protein_options=sorted(protein_options),
                         meal_type_options=meal_type_options,
                         selected_cuisines=selected_cuisines,
                         selected_diets=selected_diets,
                         selected_difficulties=selected_difficulties,
                         selected_proteins=selected_proteins,
                         selected_meal_types=selected_meal_types,
                         current_sort=sort_col,
                         current_dir=sort_dir)

@app.route('/ingredients')
def pantry_list():
    # Fetch all ingredients for the visual pantry grid
    ingredients = db.session.execute(db.select(Ingredient).order_by(Ingredient.name)).scalars().all()
    
    # Get unique categories for the filter dropdown
    categories = db.session.execute(db.select(Ingredient.main_category).distinct()).scalars().all()
    categories = [c for c in categories if c] # Filter None
    
    return render_template('pantry.html', ingredients=ingredients, categories=sorted(categories))

@app.route('/pantry')
def pantry_management():
    # Fetch all ingredients
    ingredients = db.session.execute(db.select(Ingredient).order_by(Ingredient.main_category, Ingredient.name)).scalars().all()
    
    # Group by category for the view
    grouped = {}
    for ing in ingredients:
        cat = ing.main_category or "Other"
        if cat not in grouped:
            grouped[cat] = []
        grouped[cat].append(ing)
    
    # Sort categories
    sorted_grouped = dict(sorted(grouped.items()))
    
    return render_template('pantry_management.html', grouped_ingredients=sorted_grouped)

@app.route('/api/ingredient/<int:id>/toggle_basic', methods=['POST'])
def toggle_basic_ingredient(id):
    ing = db.session.get(Ingredient, id)
    if not ing:
        return jsonify({'success': False, 'error': 'Ingredient not found'}), 404
    
    # Toggle
    ing.is_basic_ingredient = not ing.is_basic_ingredient
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'new_status': ing.is_basic_ingredient,
        'id': ing.id,
        'name': ing.name
    })

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
            
            # 4. Calculate Nutrition
            from services.nutrition_service import calculate_nutritional_totals
            calculate_nutritional_totals(new_recipe.id)
            
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


from services.social_media_service import SocialMediaExtractor
from ai_engine import generate_recipe_ai, get_pantry_id, chefs_data, generate_recipe_from_video



@app.route('/generate/video', methods=['POST'])
def generate_from_video():
    video_url = request.form.get('video_url')
    
    if not video_url:
        flash("Please provide a video URL", "error")
        return redirect(url_for('index'))
        
    try:
        # 1. Download Video
        extract_result = SocialMediaExtractor.download_video(video_url)
        video_path = extract_result['video_path']
        caption = extract_result['caption']
        
        try:
            # 2. Analyze with AI
            pantry_context = get_slim_pantry_context()
            recipe_data = generate_recipe_from_video(video_path, caption, pantry_context)
            
            # 3. Save to DB (reusing logic from generate route - ideally refactor to service)
            # Create Recipe Record
            new_recipe = Recipe(
                title=recipe_data.title,
                cuisine=recipe_data.cuisine,
                diet=recipe_data.diet,
                difficulty=recipe_data.difficulty,
                protein_type=recipe_data.protein_type,
                meal_types=json.dumps(recipe_data.meal_types)
            )
            db.session.add(new_recipe)
            db.session.flush()

            # Create Ingredients
            for group in recipe_data.ingredient_groups:
                for ing in group.ingredients:
                    food_id_str = get_pantry_id(ing.name)
                    if not food_id_str:
                         raise ValueError(f"System error: ID not found for validated ingredient {ing.name}")
                    
                    ingredient_record = db.session.execute(
                        db.select(Ingredient).where(Ingredient.food_id == food_id_str)
                    ).scalar_one_or_none()
                    
                    if not ingredient_record:
                        raise ValueError(f"Database consistency error: Ingredient {ing.name} not found.")

                    recipe_ing = RecipeIngredient(
                        recipe_id=new_recipe.id,
                        ingredient_id=ingredient_record.id,
                        amount=ing.amount,
                        unit=ing.unit,
                        component=group.component
                    )
                    db.session.add(recipe_ing)
            
            # Create Instructions
            for instr in recipe_data.instructions:
                new_instr = Instruction(
                    recipe_id=new_recipe.id,
                    phase=instr.phase,
                    step_number=instr.step_number,
                    text=instr.text
                )
                db.session.add(new_instr)

            db.session.commit()
            
            # 4. Calculate Nutrition
            from services.nutrition_service import calculate_nutritional_totals
            calculate_nutritional_totals(new_recipe.id)
            
            # Success!
            return redirect(url_for('recipe_detail', recipe_id=new_recipe.id))
            
        finally:
            # Always cleanup the video file
            SocialMediaExtractor.cleanup(video_path)
            
    except Exception as e:
        db.session.rollback()
        # In case of error (and file still exists), cleanup provided it was downloaded
        # video_path scope check? It's inside try, but if download fails it won't be set.
        # If download succeeds but AI fails, we catch here.
        flash(f"Error processing video: {str(e)}", "error")
        return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all() # Ensure tables exist
    app.run(debug=True, port=8000)
