
import os
import json
import difflib
from google import genai
from pydantic import BaseModel, Field, field_validator
from typing import List, Literal, Optional
from dotenv import load_dotenv

load_dotenv()

# Load Data
def load_json(filename):
    path = os.path.join(os.path.dirname(__file__), "data", filename)
    with open(path, 'r') as f:
        return json.load(f)

pantry_map = {}
pantry_names = set()

def set_pantry_memory(slim_context):
    global pantry_map, pantry_names
    pantry_map.clear()
    pantry_names.clear()
    for item in slim_context:
        # item keys: i=id, n=name, c=category, u=unit, t=tags
        name = item['n']
        fid = item['i']
        pantry_map[name.lower()] = fid
        pantry_names.add(name.lower())

cuisines_data = load_json("cuisines.json")['cuisines']
diets_data = load_json("diets_tag.json")['diets']
difficulty_data = load_json("difficulty_tag.json")['difficulty']
protein_data = load_json("protein_types.json")['protein_types']
meal_types_data = load_json("meal_types.json")['meal_classification']

# Flatten valid specific proteins (Tier 2)
valid_proteins = set()
for category in protein_data:
    for example in category['examples']:
        valid_proteins.add(example.lower())

# Flatten valid meal tags
valid_meal_tags = set()
for category, tags in meal_types_data.items():
    for tag in tags:
        valid_meal_tags.add(tag)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if GOOGLE_API_KEY:
    client = genai.Client(api_key=GOOGLE_API_KEY)
else:
    client = None
    print("Warning: GOOGLE_API_KEY not found in environment.")

# Pydantic Models for Validation
class IngredientSchema(BaseModel):
    name: str
    amount: float
    unit: str

    @field_validator('name')
    @classmethod
    def validate_ingredient_name(cls, v: str) -> str:
        v_norm = v.lower().strip()
        if v_norm not in pantry_names:
            # 1. Try fuzzy match
            matches = difflib.get_close_matches(v_norm, pantry_names, n=1, cutoff=0.6)
            if matches:
                 print(f"DEBUG: Fuzzy matched '{v}' to '{matches[0]}'")
                 return matches[0]
            
            # 2. Try substring match (e.g. "pork" in "minced pork")
            for p_name in pantry_names:
                if v_norm in p_name or p_name in v_norm:
                     print(f"DEBUG: Substring matched '{v}' to '{p_name}'")
                     return p_name

            raise ValueError(f"Ingredient '{v}' is not in the pantry.")
        return v_norm

class IngredientGroupSchema(BaseModel):
    component: str
    ingredients: List[IngredientSchema]

class InstructionSchema(BaseModel):
    phase: str
    step_number: int
    text: str

    @field_validator('phase')
    @classmethod
    def validate_phase(cls, v: str) -> str:
        # Normalize strictly to Prep, Cook, Serve
        v_clean = v.strip().title()
        if v_clean in ["Prep", "Cook", "Serve"]:
            return v_clean
        
        # Fuzzy match if AI gets creative (e.g. "Cook Salmon")
        v_lower = v.lower()
        if "prep" in v_lower:
            return "Prep"
        if "cook" in v_lower or "heat" in v_lower or "bake" in v_lower or "fry" in v_lower:
            return "Cook"
        if "serve" in v_lower or "plate" in v_lower or "assembl" in v_lower:
            return "Serve"
            
        # Default fallback
        return "Cook"

class RecipeSchema(BaseModel):
    title: str
    cuisine: str
    diet: str
    difficulty: Literal["Simplistic", "Moderate", "Elevated"]
    protein_type: str
    meal_types: List[str] = Field(default_factory=list)
    ingredient_groups: List[IngredientGroupSchema]
    instructions: List[InstructionSchema]

    @field_validator('protein_type')
    @classmethod
    def validate_protein_type(cls, v: str) -> str:
        v_lower = v.lower()
        if v_lower not in valid_proteins:
            # Try fuzzy match against valid_proteins if needed, or just error
            # For now, simplistic validation
            raise ValueError(f"Protein type '{v}' is not valid. Must be one of: {sorted(list(valid_proteins))}")
        return v.title()

    @field_validator('meal_types')
    @classmethod
    def validate_meal_types(cls, v: List[str]) -> List[str]:
        validated = []
        for tag in v:
            # Simple check against flattened tags
            if tag in valid_meal_tags:
                validated.append(tag)
        return validated

    @field_validator('cuisine')
    @classmethod
    def validate_cuisine(cls, v: str) -> str:
        if v not in cuisines_data:
             # Basic fuzzy handle or error? Let's try to capitalize or just error
             if v.title() in cuisines_data:
                 return v.title()
             raise ValueError(f"Cuisine '{v}' is not valid. Valid options: {cuisines_data}")
        return v
    
    @field_validator('diet')
    @classmethod
    def validate_diet(cls, v: str) -> str:
        # Handle case sensitivity (Pescatarian -> pescatarian)
        v_lower = v.lower()
        if v_lower not in diets_data:
             raise ValueError(f"Diet '{v}' is not valid. Valid options: {diets_data}")
        return v_lower

# Load Chefs Data
chefs_data = load_json("chefs.json")['chefs']
chef_map = {c['id']: c for c in chefs_data}

def generate_recipe_ai(query: str, slim_context: List[dict] = None, chef_id: str = "gourmet") -> RecipeSchema:
    if not client:
        raise Exception("Gemini API key not configured")

    if slim_context:
        # Use provided slim context
        pantry_str = json.dumps(slim_context)
        # We ensure memory is synced for validation
        set_pantry_memory(slim_context)
    else:
        # Fallback to whatever is in memory or empty
        pantry_str = "[]" 
    
    # Select Chef Logic
    selected_chef = chef_map.get(chef_id, chef_map["gourmet"]) # Default to Marco
    
    prompt = f"""
    USER REQUEST: "{query}"

    {selected_chef['system_prompt']}
    
    TASK: Create a recipe that satisfies the USER REQUEST using only available ingredients.

    COMPONENT ARCHITECTURE RULES:
    1. DEFAULT TO SINGLE COMPONENT: Cohesive dishes (Pasta, Pizza, Burgers, Salads, Soups) must be ONE component.
       - Invalid: "Pasta Base", "Pasta Sauce", "Pasta Garnish".
       - Valid: "Spaghetti Carbonara" (Everything included).
    
    2. SPLIT ONLY FOR DISTINCT MODULES: Create separate components ONLY if they are prepared completely independently and combined at the end.
       - Valid (2 Components): "Steak" (Main) + "Fries" (Side).
       - Valid (2 Components): "Sourdough Toast" (Base) + "Scrambled Eggs" (Topping).
       - Valid (3 Components): "Schnitzel" (Main) + "Potato Salad" (Side) + "Lingonberry Jam" (Condiment).
       
    3. NO "MICRO-COMPONENTS": Seasonings, simple garnishes, or "frying fats" are NOT separate components. They belong to the Main.

    INGREDIENT RULES:
    1. Use ONLY ingredients from the available list below.
    2. {pantry_str}
    
    INSTRUCTION PHASING RULES:
    - PREP: Preliminary tasks only. Chopping, measuring, grating, and organizing tools. NO application of heat.
    - COOK: The application of heat OR the final assembly logic for cold dishes (salads, etc.). This is where the dish is "transformed."
    - SERVE: Final presentation and immediate serving tips.

    JSON RULES:
    1. Valid Cuisines: {", ".join(cuisines_data)}
    2. Valid Diets: {", ".join(diets_data)}
    3. Valid Difficulties: {", ".join(difficulty_data)}
    4. Valid Protein Types (Tier 2): {", ".join([p.title() for p in valid_proteins])}
    5. Valid Meal Types (Select 1-3 that apply): {", ".join(valid_meal_tags)}
    6. Exact pantry names (n) required.
    
    Return the output as a valid JSON object matching this schema (no markdown formatting):
    {{
        "title": "Clean, Simple Title",
        "cuisine": "Valid Cuisine",
        "diet": "Valid Diet",
        "difficulty": "Valid Difficulty",
        "protein_type": "Valid Specific Protein",
        "meal_types": ["Tag 1", "Tag 2"],
        "ingredient_groups": [
            {{
                "component": "Main",
                "ingredients": [
                    {{"name": "n name", "amount": 0.0, "unit": "u"}}
                ]
            }}
        ],
        "instructions": [
            {{"phase": "Prep", "step_number": 1, "text": "Friendly, short step description."}},
            {{"phase": "Cook", "step_number": 2, "text": "Friendly, short step description."}},
            {{"phase": "Serve", "step_number": 3, "text": "Friendly, short step description."}}
        ]
    }}
    """
    
    response = client.models.generate_content(
        model='gemini-flash-latest',
        contents=prompt
    )
    
    try:
        text = response.text.replace('```json', '').replace('```', '').strip()
        data = json.loads(text)
        return RecipeSchema(**data)
    except json.JSONDecodeError:
        raise ValueError(f"AI returned invalid JSON: {response.text}")
    except Exception as e:
        raise ValueError(f"Validation failed: {e}")

def get_pantry_id(name: str):
    return pantry_map.get(name.lower())

def generate_recipe_from_video(video_path: str, caption: str, slim_context: List[dict] = None, chef_id: str = "gourmet") -> RecipeSchema:
    if not client:
        raise Exception("Gemini API key not configured")
        
    print(f"🎬 Uploading video to Gemini: {video_path}")
    
    # 1. Upload File
    try:
        # Use simple upload (v1beta/genai library style)
        # Note: 'genai.files' might need import or access via client?
        # The new 'google.genai' library (v1.0+) has specific file handling.
        # Based on user's prompt they reference `genai.upload_file`.
        # Because we imported `from google import genai`, we might need to adjust.
        # BUT: The user code uses `genai.Client`. The older `google.generativeai` has `upload_file`.
        # The new `google.genai` SDK is a bit different.
        # Let's check imports. Line 5: `from google import genai`.
        # This is the NEW SDK 1.0+.
        # In new SDK: client.files.upload(...)
        
        # However, checking earlier errors in this chat history (Step 1477), the user had `import google.generativeai as genai`.
        # But `ai_engine.py` (Step 1882) shows `from google import genai`.
        # This is an important distinction. 
        # If using `google.genai` (new SDK):
        file_ref = client.files.upload(file=video_path)
    except Exception as e:
        # Fallback if using older library or mixup
        print(f"Upload failed: {e}")
        raise ValueError(f"Failed to upload video to AI: {e}")

    print(f"⏳ Waiting for video processing (File URI: {file_ref.uri})...")
    
    # 2. Wait for processing (Polling)
    import time
    while True:
        # refresh file info
        file_info = client.files.get(name=file_ref.name)
        if file_info.state == "ACTIVE":
            break
        elif file_info.state == "FAILED":
            raise ValueError("Video processing failed in Gemini Cloud.")
        time.sleep(2)
        print(".", end="", flush=True)
    print(" Ready!")

    # 3. Prepare Prompt
    if slim_context:
        set_pantry_memory(slim_context)
        pantry_str = json.dumps(slim_context)
    else:
        pantry_str = "[]"
        
    selected_chef = chef_map.get(chef_id, chef_map["gourmet"])

    prompt = f"""
    VIDEO ANALYSIS REQUEST. 
    Caption: "{caption}"

    {selected_chef['system_prompt']}
    
    TASK: Watch this cooking video and extract the recipe. 
    Indentify what is being cooked and how.
    MATCH ingredients to my available pantry list where possible: 
    {pantry_str}

    COMPONENT ARCHITECTURE RULES:
    1. DEFAULT TO SINGLE COMPONENT: Cohesive dishes (Pasta, Pizza, Burgers, Salads, Soups) must be ONE component.
       - Valid: "Spaghetti Carbonara" (Everything included).
    2. SPLIT ONLY FOR DISTINCT MODULES: "Steak" + "Fries".
    3. NO "MICRO-COMPONENTS".

    INSTRUCTION PHASING RULES:
    - PREP: Preliminary tasks.
    - COOK: Heat application or main assembly.
    - SERVE: Presentation.

    JSON RULES:
    1. Valid Cuisines: {", ".join(cuisines_data)}
    2. Valid Diets: {", ".join(diets_data)}
    3. Valid Difficulties: {", ".join(difficulty_data)}
    4. Valid Protein Types (Tier 2): {", ".join([p.title() for p in valid_proteins])}
    5. Valid Meal Types: {", ".join(valid_meal_tags)}
    6. Exact pantry names (n) required if matched.
    
    Return the output as a valid JSON object matching this schema:
    {{
        "title": "Clean, Simple Title",
        "cuisine": "Valid Cuisine",
        "diet": "Valid Diet",
        "difficulty": "Valid Difficulty",
        "protein_type": "Valid Specific Protein",
        "meal_types": ["Tag 1", "Tag 2"],
        "ingredient_groups": [
            {{
                "component": "Main",
                "ingredients": [
                    {{"name": "n name", "amount": 0.0, "unit": "u"}}
                ]
            }}
        ],
        "instructions": [
            {{"phase": "Prep", "step_number": 1, "text": "Step description."}},
            {{"phase": "Cook", "step_number": 2, "text": "Step description."}},
            {{"phase": "Serve", "step_number": 3, "text": "Step description."}}
        ]
    }}
    """
    
    # 4. Generate Content
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash', # Vision optimized
            contents=[file_ref, prompt]
        )
        
        # 5. Cleanup Cloud File
        print("🧹 Cleaning up cloud file...")
        try:
            client.files.delete(name=file_ref.name)
        except:
            pass # Non-critical

        # 6. Parse
        text = response.text.replace('```json', '').replace('```', '').strip()
        data = json.loads(text)
        return RecipeSchema(**data)
        
    except Exception as e:
        raise ValueError(f"AI Generation failed: {e}")

