import os
from dotenv import load_dotenv

# Load Environment Variables Forcefully BEFORE other imports might need them
load_dotenv()
print(f"--- CONFIG DEBUG: STORAGE_BACKEND={os.getenv('STORAGE_BACKEND')} ---")
print(f"--- CONFIG DEBUG: DB_BACKEND={os.getenv('DB_BACKEND', 'local')} ---")

import uuid
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from database.db_connector import configure_database
from database.models import db, Ingredient, Recipe, Instruction, RecipeIngredient, RecipeMealType, User
from utils.decorators import admin_required
from sqlalchemy import or_
from services.pantry_service import get_slim_pantry_context
from ai_engine import generate_recipe_ai, get_pantry_id, chefs_data, generate_recipe_from_web_text, analyze_ingredient_ai
from services.photographer_service import generate_visual_prompt, generate_actual_image, generate_visual_prompt_from_image, load_photographer_config, generate_image_variation, process_external_image
from services.vertex_image_service import VertexImageGenerator
from services.web_scraper_service import WebScraper
from services.storage_service import get_storage_provider
from utils.image_helpers import generate_ingredient_placeholder
import base64
from io import BytesIO
import shutil
import datetime
from sqlalchemy import func
from utils.prompt_manager import load_prompt

app = Flask(__name__)

# Register Blueprints
from routes.studio_routes import prompts_bp
app.register_blueprint(prompts_bp)


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
# Database Configuration (Local vs Cloud SQL)
configure_database(app)
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
    
    def get_recipe_image_url(recipe):
        """Generates the correct URL for a recipe image based on storage backend."""
        if not recipe or not recipe.image_filename:
            return None
        
        # If using GCS, return the public URL directly
        # We construct it manually or use storage_provider if it had a get_url method
        # But for now, we know the pattern or can assume public access for simplicity
        # The storage provider saves as "recipes/<filename>" or just "<filename>" in recipes folder?
        # Let's check storage provider usage.
        
        # Access global storage_provider
        is_gcs = isinstance(storage_provider, GoogleCloudStorageProvider)
        
        if is_gcs:
            # GCS Public URL Convention: https://storage.googleapis.com/<bucket>/<blob_path>
            # The app saves/moves items to "recipes" folder.
            return f"https://storage.googleapis.com/{storage_provider.bucket_name}/recipes/{recipe.image_filename}"
        else:
            # Local Flask Static
            return url_for('static', filename='recipes/' + recipe.image_filename)

    return dict(update_query_params=update_query_params, get_recipe_image_url=get_recipe_image_url)

db.init_app(app)

# Initialize Storage Provider
storage_provider = get_storage_provider(app.root_path)
print(f"--- STORAGE SYSTEM ACTIVE: {storage_provider.__class__.__name__} ---")

# Inject storage provider into blueprint context
# Note: Blueprints are registered earlier, but we can attach attributes to the object
prompts_bp.storage_provider = storage_provider

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# AUTH ROUTES
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
         return redirect(url_for('studio_view'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = db.session.execute(db.select(User).where(User.email == email)).scalar()
        
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('studio_view'))
        
        flash('Invalid email or password', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('studio_view'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not email or not password or not confirm_password:
             flash('Please fill in all fields', 'error')
             return render_template('register.html')

        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('register.html')
            
        # Check if user exists
        user_exists = db.session.execute(db.select(User).where(User.email == email)).scalar()
        if user_exists:
            flash('Email already registered', 'error')
            return render_template('register.html')
            
        # Create user
        new_user = User(email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
        
    return render_template('register.html')

# PHOTOGRAPHER ROUTES

@app.route('/admin/studio', methods=['GET', 'POST'])
@login_required
@admin_required
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

@app.route('/admin/studio/snap', methods=['POST'])
@login_required
@admin_required
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
        
        # Save to Temp via Storage Provider
        filename = f"temp_{uuid.uuid4().hex}.png"
        
        # Convert PIL to Bytes
        img_byte_arr = BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_bytes = img_byte_arr.getvalue()
        
        public_url = storage_provider.save(img_bytes, filename, "temp")
        
        # Render template with the image filename/URL AND context
        # Note: 'temp_image' variable now expects just the filename for some logic 
        # OR the URL? The template uses `url_for('static', filename='temp/'+temp_image)` usually.
        # If we return a URL from GCS, we can't wrap it in `url_for('static')`.
        # We need to pass the FULL URL.
        # But let's check studio.html usage later. unique filename is safer for now if local.
        # If local, storage.save returns "/static/temp/filename.png"
        # If GCS, it returns "https://..."
        
        # Let's pass the full URL to the template as 'temp_image_url' and update template?
        # OR keep 'temp_image' as filename, and 'temp_image_full_url' as the public url.
        
        return render_template('studio.html', 
                             config=config, 
                             prompt=prompt, 
                             recipe_text=recipe_text,
                             recipe_id=recipe_id,
                             ingredients_list=ingredients_list,
                             temp_image=filename,
                             temp_image_url=public_url) # New variable
                             
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

@app.route('/admin/studio/save', methods=['POST'])
@login_required
@admin_required
def save_recipe_image():
    filename = request.form.get('filename')
    recipe_id = request.form.get('recipe_id')
    
    if not filename or not recipe_id:
        flash("Missing data to save image", "error")
        return redirect(url_for('index'))
        
    try:
        # Move file from temp to recipes
        # Use simple storage abstraction
        new_filename = f"recipe_{recipe_id}_{uuid.uuid4().hex[:8]}.png"
        
        # Move: Temp -> Recipes
        storage_provider.move(filename, "temp", new_filename, "recipes")
        
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


@app.route('/admin/studio/analyze', methods=['POST'])
@login_required
@admin_required
def studio_analyze():
    try:
        # A1: Text Input -> Generate Prompt
        text_a1 = request.form.get('text_a1', '')
        prompt_b1 = ""
        if text_a1:
            prompt_b1 = generate_visual_prompt(text_a1)
        
        # A2: Image Input (for Image-to-Prompt)
        prompt_a2 = ""
        if 'image_a2' in request.files and request.files['image_a2'].filename != '':
            file = request.files['image_a2']
            image_bytes = file.read()
            prompt_a2 = generate_visual_prompt_from_image(image_bytes)
            
        # A3: Image Input (for Remix) - We just confirm it's valid/received, 
        # but the prompt is fixed.
        # Maybe we could do a quick check? 
        
        # Get Fixed Prompt from Config
        config = load_photographer_config()
        # Create a specific "Enhancer" prompt or just use the system prompt
        # User requested: "Cookbook Style" with Template
        prompt_b3 = load_prompt('recipe_image/style_remix.jinja2', ingredient_name='[Ingredient Name]')

        return jsonify({
            'success': True,
            'row1': prompt_b1, 
            'row2': prompt_a2,
            'row3': prompt_b3
        })

    except Exception as e:
        print(f"Analyze Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/studio/generate', methods=['POST'])
@login_required
@admin_required
def studio_generate():
    try:
        # B1: Text-to-Image
        prompt_b1 = request.form.get('prompt_b1')
        img_c1_url = None
        if prompt_b1:
            img = generate_actual_image(prompt_b1)[0]
            filename = f"studio_a_{uuid.uuid4().hex}.png"
            
            # Save via Storage
            img_byte_arr = BytesIO()
            img.save(img_byte_arr, format='PNG')
            img_c1_url = storage_provider.save(img_byte_arr.getvalue(), filename, "temp")

        # B2: Image-to-Prompt-to-Image
        prompt_b2 = request.form.get('prompt_b2')
        img_c2_url = None
        if prompt_b2:
            img = generate_actual_image(prompt_b2)[0]
            filename = f"studio_b_{uuid.uuid4().hex}.png"
            
            # Save via Storage
            img_byte_arr = BytesIO()
            img.save(img_byte_arr, format='PNG')
            img_c2_url = storage_provider.save(img_byte_arr.getvalue(), filename, "temp")
            
        # B3: Mix (Image + Fixed Prompt)
        prompt_b3 = request.form.get('prompt_b3')
        img_c3_url = None
        
        # We need the image from A3 again. 
        # NOTE: Ideally we would have saved it to a temp path in /analyze and passed the path.
        # But for this stateless implementation, we expect the frontend to re-send the file 
        # OR we rely on the file being present in request.files if the user selected it.
        if 'image_a3' in request.files and request.files['image_a3'].filename != '' and prompt_b3:
            file = request.files['image_a3']
            image_bytes = file.read()
            # Variation Generation
            img = generate_image_variation(image_bytes, prompt_b3)
            filename = f"studio_c_{uuid.uuid4().hex}.png"
            
            # Save via Storage
            img_byte_arr = BytesIO()
            img.save(img_byte_arr, format='PNG')
            img_c3_url = storage_provider.save(img_byte_arr.getvalue(), filename, "temp")

        return jsonify({
            'success': True,
            'image_c1': img_c1_url,
            'image_c2': img_c2_url,
            'image_c3': img_c3_url
        })

    except Exception as e:
        print(f"Generate Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# RECIPE IMAGE GENERATION FLOW
@app.route('/recipe-image-generation')
def recipe_image_generation_view():
    recipe_id = request.args.get('recipe_id')
    if not recipe_id:
        flash("Recipe ID required", "error")
        return redirect(url_for('index'))
    
    recipe = db.session.get(Recipe, int(recipe_id))
    if not recipe:
        flash("Recipe not found", "error")
        return redirect(url_for('index'))
        
    return render_template('recipe_photographer.html', recipe=recipe)

@app.route('/recipe-image-generation/prompt', methods=['POST'])
def recipe_image_generation_prompt():
    try:
        data = request.get_json()
        recipe_id = data.get('recipe_id')
        recipe = db.session.get(Recipe, int(recipe_id))
        
        if not recipe:
            return jsonify({'success': False, 'error': 'Recipe not found'})
            
        # Reconstruct Context for AI
        ingredients_list = ", ".join([ri.ingredient.name for ri in recipe.ingredients])
        
        recipe_text = f"Title: {recipe.title}\n"
        recipe_text += f"Cuisine: {recipe.cuisine}\n"
        recipe_text += f"Diet: {recipe.diet}\n"
        
        # Generate Prompt
        prompt = generate_visual_prompt(recipe_text, ingredients_list)
        
        return jsonify({'success': True, 'prompt': prompt})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/recipe-image-generation/generate', methods=['POST'])
def recipe_image_generation_create():
    try:
        data = request.get_json()
        prompt = data.get('prompt')
        
        if not prompt:
            return jsonify({'success': False, 'error': 'Prompt required'})
            
        # Generate Image
        try:
            # Check if using Vertex or Photographer Service
            # For now, assuming generate_actual_image returns a list of PIL images
            images = generate_actual_image(prompt)
            if not images:
                 return jsonify({'success': False, 'error': 'No image generated'})
            img = images[0]
        except Exception as e:
             print(f"Error calling AI generation: {e}")
             return jsonify({'success': False, 'error': f"Generation failed: {str(e)}"})
             
        # Save to Temp
        filename = f"temp_{uuid.uuid4().hex}.png"
        
        # Save via Storage
        img_byte_arr = BytesIO()
        img.save(img_byte_arr, format='PNG')
        file_url = storage_provider.save(img_byte_arr.getvalue(), filename, "temp")
        
        return jsonify({'success': True, 'filename': filename, 'url': file_url})
        
    except Exception as e:
        print(f"Gen Error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/recipe-image-generation/save', methods=['POST'])
def recipe_image_generation_save():
    try:
        data = request.get_json()
        filename = data.get('filename')
        recipe_id = data.get('recipe_id')
        
        if not filename or not recipe_id:
            return jsonify({'success': False, 'error': 'Missing data'})
            
        # Move file using Storage Provider (Abstracts Local vs Cloud)
        new_filename = f"recipe_{recipe_id}_{uuid.uuid4().hex[:8]}.png"
        
        try:
            # Move from 'temp' to 'recipes'
            storage_provider.move(filename, "temp", new_filename, "recipes")
            
            # Update DB
            recipe = db.session.get(Recipe, int(recipe_id))
            recipe.image_filename = new_filename
            db.session.commit()
            
            return jsonify({'success': True})
            
        except FileNotFoundError:
             return jsonify({'success': False, 'error': 'Temp file not found or expired'})
            
    except Exception as e:
        print(f"Save Logic Error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/new-recipe', methods=['GET', 'POST'])
def new_recipe():
    if request.method == 'POST':
        query = request.form.get('query')
        chef_id = request.form.get('chef_id', 'gourmet')
        if query:
            return redirect(url_for('generate', query=query, chef_id=chef_id))
    
    # Get recent recipes (Still passed but template might not use them if removed)
    recent_recipes = db.session.execute(db.select(Recipe).order_by(Recipe.id.desc()).limit(10)).scalars().all()
    return render_template('index.html', recipes=recent_recipes, chefs=chefs_data)

@app.route('/')
def index():
    # Load Recent Recipes
    recent_recipes = db.session.execute(db.select(Recipe).order_by(Recipe.id.desc()).limit(8)).scalars().all()
    
    # Load Resources
    resources = load_resources()
    
    return render_template('landing.html', recipes=recent_recipes, resources=resources)

def load_resources():
    try:
        data_dir = os.path.join(app.root_path, 'data')
        with open(os.path.join(data_dir, 'resources.json'), 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading resources: {e}")
        return []

@app.route('/become-a-chef')
def resources_list():
    resources = load_resources()
    return render_template('resources.html', resources=resources)

@app.route('/become-a-chef/<slug>')
def resource_detail(slug):
    resources = load_resources()
    resource = next((r for r in resources if r.get('slug') == slug or r.get('id') == slug), None)
    
    if not resource:
        flash("Article not found", "error")
        return redirect(url_for('resources_list'))
    
    # Resolve Related Articles
    related_resources = []
    if 'related_slugs' in resource:
        for r_slug in resource['related_slugs']:
             rel = next((r for r in resources if r.get('slug') == r_slug), None)
             if rel:
                 related_resources.append(rel)
        
    return render_template('resource_detail.html', resource=resource, related_resources=related_resources)

import json

def load_json_option(filename, key):
    data_dir = os.path.join(app.root_path, 'data')
    try:
        with open(os.path.join(data_dir, filename), 'r') as f:
            return json.load(f).get(key, [])
    except:
        return []

@app.route('/admin/chefs')
@login_required
@admin_required
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

@app.route('/admin/chefs/save', methods=['POST'])
@login_required
@admin_required
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
        # Filter by related RecipeMealType
        # We want recipes that have ANY of the selected tags
        stmt = stmt.where(Recipe.meal_types.any(RecipeMealType.meal_type.in_(selected_meal_types)))

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

    cuisine_options = load_json_option('post_processing/cuisines.json', 'cuisines')
    diet_options = load_json_option('constraints/diets.json', 'diets')
    difficulty_options = load_json_option('constraints/difficulty.json', 'difficulty')
    
    pt_data = load_json_option('constraints/main_protein.json', 'protein_types')
    protein_options = []
    for p in pt_data:
        if 'examples' in p:
            protein_options.extend(p['examples'])
    protein_options = sorted(list(set(protein_options)))
    
    mt_data = load_json_option('constraints/meal_types.json', 'meal_classification')
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
        stmt = stmt.where(Recipe.meal_types.any(RecipeMealType.meal_type.in_(selected_meal_types)))

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
def pantry_management():
    # Fetch all ingredients sorted by Category then Name
    ingredients = db.session.execute(db.select(Ingredient).order_by(Ingredient.main_category, Ingredient.name)).scalars().all()
    
    # Load constraints for dependent filtering
    data_dir = os.path.join(app.root_path, 'data', 'constraints')
    sub_categories_map = {}
    try:
        with open(os.path.join(data_dir, 'categories.json'), 'r') as f:
            data = json.load(f)
            sub_categories_map = data.get('sub_categories', {})
    except Exception as e:
        print(f"Error loading categories: {e}")

    return render_template('pantry_management.html', ingredients=ingredients, sub_categories_map=sub_categories_map)

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

# --- New Ingredient Workflow ---

@app.route('/new-ingredient', methods=['GET'])
@app.route('/new-ingredient', methods=['GET'])
def new_ingredient_view():
    # Load categories for the dropdown in the template (manually or via API)
    # We can pass them to the template
    data_dir = os.path.join(app.root_path, 'data', 'constraints')
    with open(os.path.join(data_dir, 'categories.json'), 'r') as f:
        category_data = json.load(f)
        
    return render_template('new_ingredient.html', 
                         main_categories=category_data.get('main_categories', []),
                         sub_categories_map=category_data.get('sub_categories', {}))

@app.route('/api/search-ingredients', methods=['POST'])
def search_ingredients_api():
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        
        if not query or len(query) < 2:
            return jsonify({'success': True, 'results': []})
            
        # Search for name matches (ILIKE)
        results = db.session.execute(
            db.select(Ingredient)
            .where(Ingredient.name.ilike(f"%{query}%"))
            .order_by(Ingredient.name)
            .limit(10)
        ).scalars().all()
        
        # Serialize results
        items = [{
            'id': i.id,
            'name': i.name, 
            'category': i.main_category,
            'food_id': i.food_id
        } for i in results]
        
        return jsonify({'success': True, 'results': items})
        
    except Exception as e:
        print(f"Search API Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analyze-ingredient', methods=['POST'])
def analyze_ingredient_api():
    try:
        data = request.get_json()
        prompt = data.get('prompt')
        
        if not prompt:
            return jsonify({'success': False, 'error': 'Prompt is required'})
            
        # Load validation constraints
        data_dir = os.path.join(app.root_path, 'data', 'constraints')
        with open(os.path.join(data_dir, 'categories.json'), 'r') as f:
            valid_categories = json.load(f)
            
        # Call AI Engine
        analysis = analyze_ingredient_ai(prompt, valid_categories)
        
        return jsonify({'success': True, 'data': analysis})
        
    except Exception as e:
        print(f"Analysis API Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/generate-ingredient-image', methods=['POST'])
def generate_ingredient_image_api():
    try:
        data = request.get_json()
        prompt = data.get('prompt')
        if not prompt:
            return jsonify({'success': False, 'error': 'No prompt provided'})

        # Generate 4 Images
        images_list = generate_actual_image(prompt, number_of_images=4)
        
        results = []
        temp_dir = os.path.join(app.root_path, 'static', 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        
        for img in images_list:
            filename = f"ing_temp_{uuid.uuid4().hex}.png"
            img.save(os.path.join(temp_dir, filename))
            results.append({
                'url': url_for('static', filename=f'temp/{filename}'),
                'filename': filename
            })
        
        return jsonify({
            'success': True, 
            'images': results
        })
        
    except Exception as e:
        print(f"Image Gen Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ingredient/<int:id>', methods=['GET'])
def get_ingredient_details_api(id):
    try:
        ingredient = db.session.get(Ingredient, id)
        if not ingredient:
            return jsonify({'success': False, 'error': 'Ingredient not found'}), 404
            
        return jsonify({
            'success': True,
            'id': ingredient.id,
            'name': ingredient.name,
            'image_prompt': ingredient.image_prompt or "No prompt available.",
            'main_category': ingredient.main_category,
            'sub_category': ingredient.sub_category,
            'unit': ingredient.default_unit,
            'average_g_per_unit': ingredient.average_g_per_unit,
            'calories_per_100g': ingredient.calories_per_100g,
            'protein_per_100g': ingredient.protein_per_100g,
            'fat_per_100g': ingredient.fat_per_100g,
            'carbs_per_100g': ingredient.carbs_per_100g,
            'sugar_per_100g': ingredient.sugar_per_100g,
            'fiber_per_100g': ingredient.fiber_per_100g,
            'fat_saturated_per_100g': ingredient.fat_saturated_per_100g,
            'sodium_mg_per_100g': ingredient.sodium_mg_per_100g,
            'kj_per_100g': ingredient.kj_per_100g
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ingredient/<int:id>', methods=['DELETE'])
def delete_ingredient_api(id):
    try:
        ingredient = db.session.get(Ingredient, id)
        if not ingredient:
            return jsonify({'success': False, 'error': 'Ingredient not found'}), 404
            
        # Check usage in recipes
        if ingredient.recipe_ingredients:
            force = request.args.get('force') == 'true'
            if not force:
                recipes = [ri.recipe.title for ri in ingredient.recipe_ingredients]
                return jsonify({
                    'success': False, 
                    'requires_confirmation': True,
                    'message': f"Used in {len(recipes)} recipes: {', '.join(recipes)}. Delete anyway?",
                    'recipes': recipes
                }), 409

            # Explicitly delete associations if forcing
            for ri in ingredient.recipe_ingredients:
                db.session.delete(ri)
            
        db.session.delete(ingredient)
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/update-ingredient-image', methods=['POST'])
def update_ingredient_image_api():
    try:
        data = request.get_json()
        ing_id = data.get('id')
        temp_filename = data.get('temp_filename')
        image_prompt = data.get('image_prompt')
        
        if not ing_id or not temp_filename:
            return jsonify({'success': False, 'error': 'Missing ID or Image'}), 400
            
        ingredient = db.session.get(Ingredient, ing_id)
        if not ingredient:
            return jsonify({'success': False, 'error': 'Ingredient not found'}), 404

        # Create new unique name to bust cache
        new_filename = f"{ingredient.food_id}_{uuid.uuid4().hex[:8]}.png"
        
        # Use storage provider to move from temp to pantry
        # This works for both local and GCS storage
        try:
            new_url = storage_provider.move(temp_filename, "temp", new_filename, "pantry")
        except FileNotFoundError:
            return jsonify({'success': False, 'error': 'Temp image not found'}), 404
        
        # Update DB with the new image URL
        # For GCS, this will be the full public URL
        # For local, this will be /static/pantry/{filename}
        if new_url.startswith('http'):
            # GCS - store full URL
            ingredient.image_url = new_url
        else:
            # Local - store relative path
            ingredient.image_url = f"pantry/{new_filename}"
            
        if image_prompt:
            ingredient.image_prompt = image_prompt
            
        db.session.commit()
        
        return jsonify({
            'success': True,
            'new_image_url': new_url
        })

    except Exception as e:
        print(f"Update Image Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/save-ingredient', methods=['POST'])
def save_new_ingredient_api():
    try:
        data = request.get_json()
        
        # 1. Generate Unique ID
        all_ids = db.session.execute(db.select(Ingredient.food_id)).scalars().all()
        max_id = 0
        for fid in all_ids:
            if fid.isdigit():
                val = int(fid)
                if val > max_id:
                    max_id = val
        
        new_id_int = max_id + 1
        new_food_id = f"{new_id_int:06d}" 
        
        # 2. Handle Image
        image_url = None
        temp_filename = data.get('temp_image_filename')
        if temp_filename:
            # Move from temp to pantry
            src = os.path.join(app.root_path, 'static', 'temp', temp_filename)
            if os.path.exists(src):
                # We use the food_id for the filename: 000123.png
                new_filename = f"{new_food_id}.png"
                dst_dir = os.path.join(app.root_path, 'static', 'pantry')
                os.makedirs(dst_dir, exist_ok=True)
                
                dst = os.path.join(dst_dir, new_filename)
                shutil.move(src, dst) # Keep this line
                
                image_url = f"pantry/{new_filename}"

        # 3. Create Object
        new_ing = Ingredient(
            food_id=new_food_id,
            name=data.get('name'),
            main_category=data.get('main_category'),
            sub_category=data.get('sub_category'),
            default_unit=data.get('unit'),
            average_g_per_unit=data.get('average_g_per_unit'),
            
            # Nutrition
            calories_per_100g=data.get('calories_per_100g'),
            protein_per_100g=data.get('protein_per_100g'),
            fat_per_100g=data.get('fat_per_100g'),
            carbs_per_100g=data.get('carbs_per_100g'),
            sugar_per_100g=data.get('sugar_per_100g'),
            fiber_per_100g=data.get('fiber_per_100g'),
            sodium_mg_per_100g=data.get('sodium_mg_per_100g'),
            fat_saturated_per_100g=data.get('fat_saturated_per_100g'),
            
            # Metadata
            image_prompt=data.get('image_prompt'),
            image_url=image_url,
            is_original=False,
            created_at=datetime.datetime.now().isoformat()
        )
        
        db.session.add(new_ing)
        db.session.commit()
        
        return jsonify({'success': True, 'id': new_ing.id}) # Changed 'food_id' to 'id'
        
    except Exception as e:
        db.session.rollback() # Added rollback
        print(f"Save Ing Error: {e}") # Changed print message
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/quick-add-ingredient', methods=['POST'])
def quick_add_ingredient_api():
    try:
        data = request.get_json()
        name = data.get('name')
        
        if not name:
            return jsonify({'success': False, 'error': 'Name is required'}), 400
            
        # 1. Load Categories via Constraints
        data_dir = os.path.join(app.root_path, 'data', 'constraints')
        with open(os.path.join(data_dir, 'categories.json'), 'r') as f:
            category_data = json.load(f)
            
        # 2. Analyze
        analysis = analyze_ingredient_ai(name, category_data)
        
        # 3. Generate Unique ID
        all_ids = db.session.execute(db.select(Ingredient.food_id)).scalars().all()
        max_id = 0
        for fid in all_ids:
             # Ensure we parse only numeric IDs
             if fid.isdigit():
                val = int(fid)
                if val > max_id:
                    max_id = val
        
        new_id_int = max_id + 1
        new_food_id = f"{new_id_int:06d}"
        
        # 4. Create Object (No Image for Quick Add - can regenerate later)
        new_ing = Ingredient(
            food_id=new_food_id,
            name=analysis.get('name', name), # Use analyzed name if available
            main_category=analysis.get('main_category'),
            sub_category=analysis.get('sub_category'),
            default_unit=analysis.get('unit'),
            average_g_per_unit=analysis.get('average_g_per_unit'),
            
            # Nutrition
            calories_per_100g=analysis.get('calories_per_100g'),
            protein_per_100g=analysis.get('protein_per_100g'),
            fat_per_100g=analysis.get('fat_per_100g'),
            carbs_per_100g=analysis.get('carbs_per_100g'),
            sugar_per_100g=analysis.get('sugar_per_100g'),
            fiber_per_100g=analysis.get('fiber_per_100g'),
            sodium_mg_per_100g=analysis.get('sodium_mg_per_100g'),
            fat_saturated_per_100g=analysis.get('fat_saturated_per_100g'),
            kj_per_100g=analysis.get('kj_per_100g'),
            
            # Metadata
            image_prompt=analysis.get('image_prompt'),
            is_original=False,
            created_at=datetime.datetime.now().isoformat()
        )
        
        db.session.add(new_ing)
        db.session.commit()
        
        # Update cache/map if needed?
        # Typically the app gets context from DB on request, 
        # but generate_recipe_ai uses a "slim_context" passed to it.
        # We assume the user RE-SUBMITS the generation request, which will fetch fresh context.
        
        return jsonify({
            'success': True, 
            'ingredient': {
                'id': new_ing.id,
                'name': new_ing.name
            }
        })

    except Exception as e:
        db.session.rollback()
        print(f"Quick Add Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/update-ingredient-data', methods=['POST'])
def update_ingredient_data_api():
    try:
        data = request.get_json()
        ing_id = data.get('id')
        
        if not ing_id:
             return jsonify({'success': False, 'error': 'ID is required'}), 400
             
        ingredient = db.session.get(Ingredient, ing_id)
        if not ingredient:
             return jsonify({'success': False, 'error': 'Ingredient not found'}), 404
             
        # Update Fields
        ingredient.name = data.get('name')
        ingredient.main_category = data.get('main_category')
        ingredient.sub_category = data.get('sub_category')
        ingredient.default_unit = data.get('unit')
        ingredient.average_g_per_unit = data.get('average_g_per_unit')
        
        ingredient.calories_per_100g = data.get('calories_per_100g')
        ingredient.kj_per_100g = data.get('kj_per_100g', 0)
        ingredient.protein_per_100g = data.get('protein_per_100g')
        ingredient.fat_per_100g = data.get('fat_per_100g')
        ingredient.carbs_per_100g = data.get('carbs_per_100g')
        ingredient.sugar_per_100g = data.get('sugar_per_100g')
        ingredient.fiber_per_100g = data.get('fiber_per_100g')
        ingredient.fat_saturated_per_100g = data.get('fat_saturated_per_100g')
        ingredient.sodium_mg_per_100g = data.get('sodium_mg_per_100g')
        
        if data.get('image_prompt'):
            ingredient.image_prompt = data.get('image_prompt')
            
        # Handle New Image if provided
        temp_filename = data.get('temp_image_filename')
        if temp_filename:
            src = os.path.join(app.root_path, 'static', 'temp', temp_filename)
            if os.path.exists(src):
                # Use existing food_id + random to bust cache
                new_filename = f"{ingredient.food_id}_{uuid.uuid4().hex[:6]}.png"
                dst_dir = os.path.join(app.root_path, 'static', 'pantry')
                os.makedirs(dst_dir, exist_ok=True)
                
                dst = os.path.join(dst_dir, new_filename)
                shutil.move(src, dst)
                
                ingredient.image_url = f"pantry/{new_filename}"
        
        db.session.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        print(f"Update Ing Data Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/merge-ingredients', methods=['POST'])
def merge_ingredients_api():
    try:
        data = request.get_json()
        source_id = data.get('source_id')
        target_id = data.get('target_id')
        
        if not source_id or not target_id:
            return jsonify({'success': False, 'error': 'Source and Target IDs required'}), 400
        
        if source_id == target_id:
            return jsonify({'success': False, 'error': 'Cannot merge ingredient into itself'}), 400

        source = db.session.get(Ingredient, source_id)
        target = db.session.get(Ingredient, target_id)
        
        if not source or not target:
             return jsonify({'success': False, 'error': 'One or both ingredients not found'}), 404
             
        # Begin Merge
        # 1. Get all usages of source
        usages = list(source.recipe_ingredients) 
        
        count_updated = 0
        count_conflicts = 0
        
        for usage in usages:
            recipe = usage.recipe
            
            # Check if recipe already has target
            conflict = next((ri for ri in recipe.ingredients if ri.ingredient_id == target.id), None)
            
            if conflict:
                # Recipe uses both. Remove source usage (redundant).
                db.session.delete(usage)
                count_conflicts += 1
            else:
                # No conflict, just reassign
                usage.ingredient = target
                db.session.add(usage)
                count_updated += 1
        
        # Flush changes to DB so Foreign Keys are updated/deleted
        db.session.flush()
        
        # Refresh source to ensure it knows it has no more associated ingredients
        # preventing SQLAlchemy from trying to SET NULL on delete
        db.session.refresh(source)
        
        # 2. Delete the Source Ingredient
        db.session.delete(source)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f"Merged '{source.name}' into '{target.name}'. Updated {count_updated} recipes, resolved {count_conflicts} conflicts."
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Merge Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/generate/web', methods=['POST'])
def generate_web_recipe():
    blog_url = request.form.get('blog_url')
    
    if not blog_url:
        return redirect(url_for('home')) # Or show error
    
    try:
        # 1. Scrape Content
        scraper = WebScraper()
        scraped_data = scraper.scrape_url(blog_url)
        
        if not scraped_data or not scraped_data['text']:
            return "Could not extract text from this URL", 400
            
        # 2. Extract Recipe with Silent Swaps
        slim_context = get_slim_pantry_context()
        try:
             import json
             pantry_str = json.dumps(slim_context)
        except:
             pantry_str = "[]"
             
        recipe_data = generate_recipe_from_web_text(scraped_data['text'], pantry_str)
        
        if not recipe_data:
             return "AI could not extract a valid recipe from the page.", 400
             
        # 3. Process Image (Parallel-ish)
        # We re-imagine the hero image from the blog
        image_url = scraped_data.get('image_url')
        print(f"Scraped Image URL: {image_url}")
        
        final_image_filename = None
        if image_url:
            try:
                # Process external -> New AI Image
                generated_pil = process_external_image(image_url)
                if generated_pil:
                     # Save it
                     unique_filename = f"web_import_{uuid.uuid4()}.png"
                     save_path = os.path.join(app.root_path, 'static', 'recipe_images', unique_filename)
                     generated_pil.save(save_path)
                     final_image_filename = unique_filename
            except Exception as e:
                print(f"Image processing failed: {e}")
                # Continue without image
        
        # 4. Save to DB (Reusing existing logic logic would be better but simple copy for now)
        with app.app_context():
            new_recipe = Recipe(
                title=recipe_data.title,
                cuisine=recipe_data.cuisine,
                diet=recipe_data.diet,
                difficulty=recipe_data.difficulty,
                cleanup_factor=recipe_data.cleanup_factor or 3,
                protein_type=recipe_data.protein_type,
                image_filename=final_image_filename,
                # meal_types=json.dumps(recipe_data.meal_types) # DEPRECATED
                chef_id=recipe_data.chef_id,
                taste_level=recipe_data.taste_level,
                prep_time_mins=recipe_data.prep_time_mins
            )
            db.session.add(new_recipe)
            db.session.flush()
            
            # Save Meal Types
            if recipe_data.meal_types:
                for mt in recipe_data.meal_types:
                    db.session.add(RecipeMealType(recipe_id=new_recipe.id, meal_type=mt))
            
            # Save Instructions
            for component in recipe_data.components:
                for step in component.steps:
                    instr = Instruction(
                        recipe_id=new_recipe.id,
                        step_number=step.step_number,
                        text=step.text,
                        phase=step.phase,
                        component=component.name
                    )
                    db.session.add(instr)

            # Save Ingredients
            for group in recipe_data.ingredient_groups:
                for ing in group.ingredients:
                     # Match to existing ingredients? or Create?
                     # Simple logic: check existing name, else create
                     db_ing = Ingredient.query.filter(Ingredient.name.ilike(ing.name)).first()
                     if not db_ing:
                         # Create new ingredient entry (auto-add to pantry? maybe not)
                         # Need a dummy food_id since it's required and unique. Using UUID or "IMP-{randint}"
                         dummy_id = f"IMP-{uuid.uuid4().hex[:6]}"
                         db_ing = Ingredient(name=ing.name, food_id=dummy_id, main_category="Imported", default_unit=ing.unit)
                         db.session.add(db_ing)
                         db.session.flush()
                     
                     ri = RecipeIngredient(
                         recipe_id=new_recipe.id,
                         ingredient_id=db_ing.id,
                         amount=ing.amount,
                         unit=ing.unit,
                         component=group.component
                     )
                     db.session.add(ri)
            
            db.session.commit()
            return redirect(url_for('recipe_detail', recipe_id=new_recipe.id))

    except Exception as e:
        print(f"Web Import Error: {e}")
        return f"Error processing web import: {e}", 500

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
            # meal_types=json.dumps(recipe_data.meal_types) # DEPRECATED
            chef_id=recipe_data.chef_id,
            taste_level=recipe_data.taste_level,
            prep_time_mins=recipe_data.prep_time_mins,
            cleanup_factor=recipe_data.cleanup_factor
        )
        db.session.add(new_recipe)
        db.session.flush() # Get ID
        
        # Save Meal Types
        if recipe_data.meal_types:
            for mt in recipe_data.meal_types:
                db.session.add(RecipeMealType(recipe_id=new_recipe.id, meal_type=mt))
        
        # Validate Ingredients - Step 1: Check for Missing Items
        missing_ingredients = []
        for group in recipe_data.ingredient_groups:
            for ing in group.ingredients:
                food_id_str = get_pantry_id(ing.name)
                if not food_id_str:
                     # Check if we already added it to missing list to avoid duplicates
                     if not any(m['name'] == ing.name for m in missing_ingredients):
                        missing_ingredients.append({
                            'name': ing.name,
                            'amount': ing.amount,
                            'unit': ing.unit,
                            'component': group.component
                        })
        
        # If we have missing ingredients, STOP and ask user to resolve
        if missing_ingredients:
            # Load categories for the resolution UI dropdowns
            data_dir = os.path.join(app.root_path, 'data', 'constraints')
            with open(os.path.join(data_dir, 'categories.json'), 'r') as f:
                cat_data = json.load(f)
                
            return render_template('missing_ingredients_resolution.html', 
                                 missing_items=missing_ingredients,
                                 query=query,
                                 chef_id=chef_id,
                                 main_categories=cat_data.get('main_categories', []),
                                 sub_categories_map=cat_data.get('sub_categories', {}))

        # Step 2: Save to DB (All ingredients detected)
        for group in recipe_data.ingredient_groups:
            for ing in group.ingredients:
                # ing.name is validated name from pantry
                # get_pantry_id returns the food_id string (e.g. "000322")
                food_id_str = get_pantry_id(ing.name)
                
                if not food_id_str:
                     # Should not happen if logic above works, unless race condition
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
            
        # Instructions (NOW NESTED IN COMPONENTS)
        for comp in recipe_data.components:
            for step in comp.steps:
                new_instr = Instruction(
                    recipe_id=new_recipe.id,
                    phase=step.phase,
                    component=comp.name,  # NEW: Save component name
                    step_number=step.step_number,
                    text=step.text
                )
                db.session.add(new_instr)
        
        # Commit AFTER all instructions are added
        db.session.commit()
        
        # 4. Calculate Nutrition
        from services.nutrition_service import calculate_nutritional_totals
        calculate_nutritional_totals(new_recipe.id)
        
        # 5. AUTO-GENERATE RECIPE IMAGE
        try:
            print(f"🎨 Auto-generating image for: {recipe_data.title}")
            
            # Create visual prompt from recipe title and cuisine
            visual_context = f"{recipe_data.title} - {recipe_data.cuisine} cuisine"
            visual_prompt = generate_visual_prompt(visual_context)
            
            # Generate actual image
            img = generate_actual_image(visual_prompt)[0]
            
            # Save to static/recipes/
            import uuid
            unique_suffix = str(uuid.uuid4())[:8]
            filename = f"recipe_{new_recipe.id}_{unique_suffix}.png"
            filepath = os.path.join('static', 'recipes', filename)
            
            img.save(filepath, 'PNG')
            
            # Update recipe with image filename
            new_recipe.image_filename = filename
            db.session.commit()
            
            print(f"✅ Image saved: {filename}")
            
        except Exception as img_error:
            print(f"⚠️  Image generation failed (non-critical): {img_error}")
            # Continue without image - don't block recipe creation
        
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
        flash("Recipe not found.", "error")
        return redirect(url_for('index'))
    
    # Group instructions by phase for display
    instructions = Instruction.query.filter_by(recipe_id=recipe_id).order_by(Instruction.component, Instruction.phase, Instruction.step_number).all()
    
    steps_by_phase = {
        'Prep': [i for i in instructions if i.phase == 'Prep'],
        'Cook': [i for i in instructions if i.phase == 'Cook'],
        'Serve': [i for i in instructions if i.phase == 'Serve']
    }
    
    # NEW: Group instructions by component for multi-component display
    from itertools import groupby
    steps_by_component = []
    for component_name, steps in groupby(instructions, key=lambda x: x.component):
        steps_by_component.append((component_name, list(steps)))
    
    # Group ingredients by component
    ingredients_by_component = {}
    for recipe_ing in recipe.ingredients:
        comp = recipe_ing.component
        if comp not in ingredients_by_component:
            ingredients_by_component[comp] = []
        ingredients_by_component[comp].append(recipe_ing)

    return render_template('recipe.html', recipe=recipe, steps_by_phase=steps_by_phase, ingredients_by_component=ingredients_by_component, steps_by_component=steps_by_component)

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
            for component in recipe_data.components:
                for step in component.steps:
                    new_instr = Instruction(
                        recipe_id=new_recipe.id,
                        phase=step.phase,
                        step_number=step.step_number,
                        text=step.text,
                        component=component.name
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


# --- INGREDIENT DASHBOARD ROUTES ---
@app.route('/ingredient-images')
def ingredient_dashboard():
    # 1. Load Pantry
    pantry_path = os.path.join(app.root_path, 'data', 'constraints', 'pantry.json')
    with open(pantry_path, 'r') as f:
        pantry_items = json.load(f)
    
    # 2. Check for Candidates
    generator = VertexImageGenerator(root_path=app.root_path)
    # We populate the candidate status for each item
    for item in pantry_items:
        safe_name = generator._get_safe_filename(item['food_name'])
        candidate_path = os.path.join(generator.candidates_dir, safe_name)
        item['has_candidate'] = os.path.exists(candidate_path)
        item['candidate_url'] = f"/static/pantry/candidates/{safe_name}" if item['has_candidate'] else None
        
        # Ensure image_url is fully qualified for display if it's relative
        if 'images' in item and item['images'].get('image_url'):
             if not item['images']['image_url'].startswith('/'):
                 item['images']['image_url'] = f"/static/{item['images']['image_url']}"
                 
        # 3. Check for Originals (Locked Assets)
        # We assume original filename matches current filename (based on migration strategy)
        if 'images' in item and item['images'].get('image_url'):
            current_url = item['images']['image_url'] # e.g. /static/pantry/000001.png
            basename = os.path.basename(current_url)
            original_path = os.path.join(app.root_path, 'static', 'pantry', 'originals', basename)
            if os.path.exists(original_path):
                item['original_url'] = f"/static/pantry/originals/{basename}"
            else:
                 item['original_url'] = None

    return render_template('ingredient_dashboard.html', ingredients=pantry_items)

@app.route('/api/generate-ingredient-image', methods=['POST'])
def generate_ingredient_image():
    data = request.json
    ingredient_name = data.get('ingredient_name')
    # The frontend text box value, treated as details if name exists, or raw prompt if not
    user_input = data.get('prompt') 
    
    if not ingredient_name and not user_input:
        return jsonify({'success': False, 'error': 'Missing name or details'})
        
    generator = VertexImageGenerator(root_path=app.root_path)

    if ingredient_name:
        # STRATEGY A: Use the Studio Template (Preferred)
        # We treat the user's input as the 'visual_details' variable
        final_prompt = generator.get_prompt(ingredient_name, visual_details=user_input or "")
        print(f"DEBUG: Generating image for '{ingredient_name}' using Template. Final Prompt: {final_prompt[:50]}...")
        result = generator.generate_candidate(ingredient_name, final_prompt)
    elif user_input:
        # STRATEGY B: Fallback (Raw Mode) - generate a temp name
        temp_name = f"unknown_{uuid.uuid4().hex[:6]}"
        print(f"DEBUG: Generating raw image using Prompt: {user_input[:50]}...")
        result = generator.generate_candidate(temp_name, user_input)
    else:
         return jsonify({'success': False, 'error': 'Missing name or prompt'})

    return jsonify(result)

@app.route('/api/approve-ingredient-image', methods=['POST'])
def approve_ingredient_image():
    data = request.json
    ingredient_name = data.get('ingredient_name')
    
    if not ingredient_name:
        return jsonify({'success': False, 'error': 'Missing ingredient name'})
        
    generator = VertexImageGenerator(root_path=app.root_path)
    result = generator.approve_candidate(ingredient_name)
    
    return jsonify(result)

if __name__ == '__main__':
    with app.app_context():
        db.create_all() # Ensure tables exist
    app.run(debug=True, port=8000)
