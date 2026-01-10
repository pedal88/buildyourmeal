
import os
import json
import uuid
import typing_extensions as typing # For TypedDict compatibility
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load Environment
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    raise ValueError("GOOGLE_API_KEY is not set in .env")

client = genai.Client(api_key=api_key)

# --- Pydantic/TypedDict Schema Definitions ---
# Using TypedDict as requested for Gemini response_schema

class Ingredient(typing.TypedDict):
    name: str
    amount: float
    unit: str

class IngredientGroup(typing.TypedDict):
    component: str
    ingredients: list[Ingredient]

class Instruction(typing.TypedDict):
    step_number: int
    phase: str # 'Prep', 'Cook', 'Serve'
    text: str

class ComponentSchema(typing.TypedDict):
    name: str # e.g., "The Steak", "Garlic Butter Sauce", "Main Dish"
    steps: list[Instruction]

class RecipeSchema(typing.TypedDict):
    title: str
    cuisine: str
    diet: str
    difficulty: str
    protein_type: str
    meal_types: list[str]
    chef_id: str
    # Numeric metadata (Critical for App Compatibility)
    cleanup_factor: int 
    taste_level: int
    prep_time_mins: int
    
    ingredient_groups: list[IngredientGroup]
    components: list[ComponentSchema]  # CHANGED: From instructions to components
    chef_note: str

class IngredientAnalysisSchema(typing.TypedDict):
    name: str # The standardized name
    main_category: str
    sub_category: str
    amount: float # Default amount for context
    unit: str # Default unit
    average_g_per_unit: float
    calories_per_100g: float
    kj_per_100g: float
    protein_per_100g: float
    fat_per_100g: float
    carbs_per_100g: float
    sugar_per_100g: float
    fiber_per_100g: float
    sodium_mg_per_100g: float
    fat_saturated_per_100g: float
    image_prompt: str

# --- Helper Classes for Application Compatibility ---
# The app expects object access (recipe.title), not dict access (recipe['title'])
class RecipeObj:
    def __init__(self, **entries):
        self.__dict__.update(entries)
        # Handle nested objects for dot access
        if 'ingredient_groups' in entries:
            self.ingredient_groups = [
                RecipeObj(**g) if isinstance(g, dict) else g 
                for g in entries['ingredient_groups']
            ]
            for group in self.ingredient_groups:
                if hasattr(group, 'ingredients'):
                    group.ingredients = [RecipeObj(**i) if isinstance(i, dict) else i for i in group.ingredients]
        
        # Handle NEW nested components
        if 'components' in entries:
            self.components = [RecipeObj(**c) if isinstance(c, dict) else c for c in entries['components']]
            for comp in self.components:
                if hasattr(comp, 'steps'):
                    comp.steps = [RecipeObj(**s) if isinstance(s, dict) else s for s in comp.steps]

# --- Data Loading (Retaining Pantry/Chef Context) ---
def load_json(path):
    with open(path, 'r') as f:
        return json.load(f)

try:
    pantry_data = load_json("data/constraints/pantry.json")
    pantry_map = {item['name'].lower(): item['id'] for item in pantry_data['ingredients']}
except Exception:
    pantry_map = {}

# --- RESTORED EXPORTS FOR APP COMPATIBILITY ---
try:
    chefs_data = load_json("data/agents/chefs.json")['chefs']
except Exception:
    chefs_data = []

try:
    protein_data = load_json("data/constraints/main_protein.json")['protein_types']
except Exception:
    protein_data = []

def generate_recipe_from_web_text(text: str, source_url: str) -> RecipeObj:
    """
    Generates a recipe from raw text (e.g. from a website extract).
    """
    prompt = f"""
    ROLE: Data Engineer.
    TASK: Extract a structured recipe from this text content.
    SOURCE URL: {source_url}
    CONTENT:
    {text[:15000]} # Limit context
    
    CRITICAL:
    1. Extract the title, cuisine, diet, etc.
    2. Infer numeric values for taste_level, prep_time_mins, etc.
    3. Map ingredients to the best fit.
    4. Structure instructions into Prep/Cook/Serve phases.
    """
    
    print(f"DEBUG: Generating from Web Text via 'gemini-flash-latest'")
    response = client.models.generate_content(
        model='gemini-flash-latest',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=RecipeSchema
        )
    )

    try:
        if response.parsed:
             return RecipeObj(**response.parsed)
        # import json # REMOVED: Redundant

        data = json.loads(response.text)
        return RecipeObj(**data)
    except Exception as e:
        print(f"ERROR: Web Generation failed. Raw output: {response.text[:200]}")
        raise ValueError(f"AI Generation failed: {e}")

def get_pantry_id(name: str):
    # 1. Try Exact Match
    n_lower = name.lower()
    if n_lower in pantry_map:
        return pantry_map[n_lower]
    
    # 2. Try 'exact word' match (e.g. "thyme" in "fresh thyme")
    # We prefer short keys matching parts of the query (pantry="thyme", query="fresh thyme")
    for key, pid in pantry_map.items():
        # Check if pantry item is inside the query (e.g. key="thyme" in name="fresh thyme")
        if key in n_lower: 
            return pid
            
    # 3. Try query inside pantry item (e.g. name="beef" in key="beef chuck")
    for key, pid in pantry_map.items():
        if n_lower in key:
            return pid
            
    return None

def set_pantry_memory(slim_context):
    global pantry_map
    for item in slim_context:
        # Handle minified keys from pantry_service (n=name, i=id)
        name = item.get('n', item.get('name'))
        pantry_id = item.get('i', item.get('id'))
        
        if name and pantry_id:
            pantry_map[name.lower()] = pantry_id

# --- Core Generation Function ---
def generate_recipe_ai(query: str, slim_context: list[dict] = None, chef_id: str = "gourmet") -> RecipeObj:
    
    if slim_context:
        set_pantry_memory(slim_context)
        pantry_str = json.dumps(slim_context)
    else:
        pantry_str = "[]"

    # Chef Context
    chef_context = f"You are acting as the Chef ID: {chef_id}."

    
    # Load Template
    try:
        from jinja2 import Environment, FileSystemLoader
        env = Environment(loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), 'data', 'prompts')))
        template = env.get_template('recipe_text/recipe_generation.jinja2')
        prompt = template.render(
            chef_context=chef_context,
            query=query,
            pantry_context=pantry_str
        )
    except Exception as e:
        print(f"Error loading prompt template: {e}")
        # Fallback (Safety)
        prompt = f"""
        You are a precise Data Engineer Chef.
        {chef_context}
        GOAL: Generate a structured recipe for: "{query}" using these ingredients: {pantry_str}.
        """




    print(f"DEBUG: Using Model 'gemini-flash-latest' with Few-Shot Prompt")
    
    response = client.models.generate_content(
        model='gemini-flash-latest',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=RecipeSchema
        )
    )

    # === CRITICAL DEBUG LOGGING ===
    print("\n" + "="*80)
    print("RAW AI RESPONSE (Full JSON):")
    print("="*80)
    print(response.text)
    print("="*80 + "\n")
    
    # Parse and count instructions
    try:
        parsed_data = response.parsed if response.parsed else json.loads(response.text)
        instruction_count = len(parsed_data.get('instructions', []))
        print(f"🔍 INSTRUCTION COUNT IN AI RESPONSE: {instruction_count}")
        for idx, instr in enumerate(parsed_data.get('instructions', []), 1):
            print(f"  Step {idx}: [{instr.get('phase')}] {instr.get('text', '')[:60]}...")
        print("="*80 + "\n")
    except Exception as debug_err:
        print(f"⚠️  Debug parsing failed: {debug_err}")
    
    # Original logic
    try:
        if response.parsed:
             # Convert Dict to Object for App Compatibility
             return RecipeObj(**response.parsed)
        
        # Fallback if parsed is empty (rare with native schema)
        data = json.loads(response.text)
        return RecipeObj(**data)

    except Exception as e:
        print(f"ERROR: Generation failed. Raw output: {response.text[:200]}")
        raise ValueError(f"AI Generation failed: {e}")

# --- Video Generation (Retained for Safety) ---
def generate_recipe_from_video(video_path: str, caption: str, slim_context: list[dict] = None, chef_id: str = "gourmet"):
    # Reuse the same schema logic ideally, for now just a stub or basic version
    # Since user emphasized 'Rewrite entire file', we keep a minimal working version
    
    print(f"🎬 Uploading video to Gemini: {video_path}")
    file_ref = client.files.upload(file=video_path)
    
    import time
    while True:
        file_info = client.files.get(name=file_ref.name)
        if file_info.state == "ACTIVE":
            break
        elif file_info.state == "FAILED":
            raise ValueError("Video processing failed")
        time.sleep(2)

    prompt = f"""
    Watch this video and create a structured recipe.
    Caption: {caption}
    Chef ID: {chef_id}
    
    CRITICAL: Follow the same strict multi-step rules:
    1. At least 5 distinct steps.
    2. Prep, Cook, Serve phases.
    3. Estimate numeric amounts for ingredients.
    """
    
    response = client.models.generate_content(
        model='gemini-flash-latest',
        contents=[file_ref, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=RecipeSchema
        )
    )
    
    if response.parsed:
        return RecipeObj(**response.parsed)
    return RecipeObj(**json.loads(response.text))

# --- Ingredient Analysis ---
def analyze_ingredient_ai(prompt: str, valid_categories: dict) -> dict:
    
    print(f"DEBUG: Analyzing ingredient '{prompt}' via 'gemini-flash-latest'")
    
    # Load prompt from studio template
    from utils.prompt_manager import load_prompt
    
    system_prompt = load_prompt('ingredient_text/ingredient_analysis.jinja2', 
        user_input=prompt,
        valid_categories_json=json.dumps(valid_categories['main_categories']),
        valid_subcategories_json=json.dumps(valid_categories['sub_categories'])
    )

    try:
        response = client.models.generate_content(
            model='gemini-flash-latest',
            contents=system_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=IngredientAnalysisSchema
            )
        )
        
        if response.parsed:
            return response.parsed
        return json.loads(response.text)
        
    except Exception as e:
        print(f"ERROR: Ingredient Analysis failed: {e}")
        raise ValueError(f"AI Analysis failed: {e}")
