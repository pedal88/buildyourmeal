
import os
import json
import difflib
from google import genai
from google.genai import types
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
cleanup_data = load_json("cleanup_factors.json")['cleanup_scale']

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

            print(f"WARNING: Ingredient '{v}' is not in the pantry. Allowing for import.")
            return v_norm
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
    difficulty: str # Relaxed from Literal
    cleanup_factor: int = Field(..., ge=1, le=5, description="Score 1-5 for cleanup effort")
    protein_type: str
    meal_types: List[str] = Field(default_factory=list)
    ingredient_groups: List[IngredientGroupSchema]
    instructions: List[InstructionSchema]

    @field_validator('protein_type')
    @classmethod
    def validate_protein_type(cls, v: str) -> str:
        v_lower = v.lower()
        if v_lower not in valid_proteins:
            print(f"WARNING: Invalid protein_type '{v}'. Falling back to 'Vegetarian'.")
            # Heuristic: if it looks like meat, maybe 'Chicken'? But 'Vegetarian' is the safest neutral bucket if we don't know.
            # actually better to just check if 'other' is allowed? 
            # I'll just return "Vegetarian" as a safe fallback 
            return "Vegetarian"
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
             if v.title() in cuisines_data:
                 return v.title()
             # Fallback instead of failing
             print(f"WARNING: Invalid cuisine '{v}'. Falling back to 'Other'.")
             return "Other" # Ensure 'Other' is in cuisines.json or handle it
        return v
    
    @field_validator('diet')
    @classmethod
    def validate_diet(cls, v: str) -> str:
        # Handle case sensitivity (Pescatarian -> pescatarian)
        v_lower = v.lower()
        if v_lower not in diets_data:
             print(f"WARNING: Invalid diet '{v}'. Falling back to 'omnivore'.")
             return "omnivore"
        return v_lower

    @field_validator('difficulty')
    @classmethod
    def validate_difficulty(cls, v: str) -> str:
        # Map common terms to our internal "Simplistic, Moderate, Elevated"
        v_clean = v.title()
        if v_clean in ["Simplistic", "Moderate", "Elevated"]:
             return v_clean
        
        # Fuzzy map
        if "Easy" in v_clean or "Simple" in v_clean:
             return "Simplistic"
        if "Medium" in v_clean or "Hard" in v_clean: # Mapping Hard to Moderate for safety, or Elevated?
             return "Moderate"
        if "Complex" in v_clean or "Advanced" in v_clean or "Chef" in v_clean:
             return "Elevated"
        
        print(f"WARNING: Invalid difficulty '{v}'. Falling back to 'Moderate'.")
        return "Moderate"

# Load Chefs Data
chefs_data = load_json("chefs.json")['chefs']
chef_map = {c['id']: c for c in chefs_data}

def build_chef_prompt(chef):
    c = chef.get('constraints', {})
    ds = chef.get('diet_preferences', [])
    cs = chef.get('cooking_style', {})
    il = chef.get('ingredient_logic', {})
    ins = chef.get('instruction_style', {})
    
    # helper for range constraints
    def fmt_range(key):
        r = c.get(key, {})
        return f"{r.get('min', '?')}-{r.get('max', '?')}"
    
    prompt = f"""
    ROLE: {chef.get('name')} ({chef.get('archetype')})
    DESCRIPTION: {chef.get('description')}
    
    PHILOSOPHY & CONSTRAINTS:
    - Taste Priority: {fmt_range('taste_range')} / 5
    - Speed Priority: {fmt_range('speed_range')} / 5
    - Complexity Target: {fmt_range('complexity_range')} / 3 ({c.get('complexity_range',{}).get('note','')})
    - Cleanup Limit: {fmt_range('cleanup_range')} / 5
    - Richness Target: {fmt_range('richness_range')} / 5
    
    DIET PREFERENCES:
    """
    for d in ds:
        prompt += f"- {d.get('action').upper()} {d.get('diet_id')}\n"
        
    prompt += f"""
    COOKING STYLE:
    - Preferred Tools: {', '.join(cs.get('preferred_tools', []))}
    - Avoid Tools: {', '.join(cs.get('avoid_tools', []))}
    - Preferred Methods: {', '.join(cs.get('preferred_methods', []))}
    
    INGREDIENT LOGIC:
    - Staples: {', '.join(il.get('staples', []))}
    - Banned: {', '.join(il.get('banned_ingredients', []))}
    - Low Carb Strategy: {il.get('low_carb_strategy')}
    
    INSTRUCTION STYLE:
    - Tone: {ins.get('tone')}
    - Example Phrase: "{ins.get('example_phrase')}"
    """
    return prompt


# Helper: Extract JSON from mixed text
def extract_json_from_text(text: str):
    """
    Robustly extract JSON object from a string that might contain other text.
    Finds the first '{' and the last '}'.
    """
    try:
        # 1. Simple Case: It's clean JSON
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Markdown Strip Case
    clean_text = text.replace('```json', '').replace('```', '').strip()
    try:
        return json.loads(clean_text)
    except json.JSONDecodeError:
        pass

    # 3. Brute Force Substring Case (Find first { and last })
    start = text.find('{')
    end = text.rfind('}')
    
    if start != -1 and end != -1 and end > start:
        json_str = text[start : end + 1]
        try:
             return json.loads(json_str)
        except json.JSONDecodeError:
             # Last ditch: try to fix common trailing comma or newlines? 
             # For now, just fail.
             pass
             
    raise ValueError(f"Could not extract valid JSON from response: {text[:100]}...")

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
    print(f"DEBUG IN: Requested Chef ID: '{chef_id}'")
    
    fallback_chef = chef_map.get("french_classic") 
    if not fallback_chef:
         fallback_chef = list(chef_map.values())[0]

    selected_chef = chef_map.get(chef_id, fallback_chef)
    print(f"DEBUG OUT: Selected Chef: {selected_chef.get('name')} (ID: {selected_chef.get('id')})")
    
    chef_system_prompt = build_chef_prompt(selected_chef)
    
    # Build Cleanup Guide String
    cleanup_guide = "\n    CLEANUP FACTOR GUIDE (1-5):"
    for item in cleanup_data:
        cleanup_guide += f"\n    - {item['value']}: {item['description']}"

    prompt = f"""
    USER REQUEST: "{query}"

    {chef_system_prompt}
    
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
    7. Cleanup Factor: Assign a score 1-5 based on this guide: {cleanup_guide}
    
    Return the output as a valid JSON object matching this schema (no markdown formatting):
    {{
        "title": "Clean, Simple Title",
        "cuisine": "Valid Cuisine",
        "diet": "Valid Diet",
        "difficulty": "Valid Difficulty",
        "cleanup_factor": 1,
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
        data = extract_json_from_text(response.text)
        return RecipeSchema(**data)
    except Exception as e:
        raise ValueError(f"Validation failed: {e}. Raw response: {response.text[:200]}")

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
        
    # Select Chef Logic
    fallback_chef = chef_map.get("french_classic") 
    if not fallback_chef:
         fallback_chef = list(chef_map.values())[0]

    selected_chef = chef_map.get(chef_id, fallback_chef)
    
    chef_system_prompt = build_chef_prompt(selected_chef)

    # Build Cleanup Guide String
    cleanup_guide = "\n    CLEANUP FACTOR GUIDE (1-5):"
    for item in cleanup_data:
        cleanup_guide += f"\n    - {item['value']}: {item['description']}"

    prompt = f"""
    VIDEO ANALYSIS REQUEST. 
    Caption: "{caption}"

    {chef_system_prompt}
    
    TASK: Watch this cooking video and extract the recipe. 
    Indentify what is being cooked and how.
    MATCH ingredients to my available pantry list where possible: 
    {pantry_str}

    CRITICAL: YOU MUST ESTIMATE AMOUNTS.
    - Resulting amounts MUST be specific numbers (e.g. 200.0, not 0).
    - If the video doesn't state the amount, USE YOUR CHEF KNOWLEDGE to estimate a reasonable quantity for 2 servings.
    - Do not output "to taste" or 0 for main ingredients (meat, veg, carbs).

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
    7. Cleanup Factor: Assign a score 1-5 based on this guide: {cleanup_guide}
    
    Return the output as a valid JSON object matching this schema:
    {{
        "title": "Clean, Simple Title",
        "cuisine": "Valid Cuisine",
        "diet": "Valid Diet",
        "difficulty": "Valid Difficulty",
        "cleanup_factor": 1,
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
        data = extract_json_from_text(response.text)
        return RecipeSchema(**data)
        
    except Exception as e:
        raise ValueError(f"AI Generation failed: {e}")


def generate_recipe_from_web_text(raw_text: str, pantry_context: str) -> RecipeSchema:
    """
    Extracts a structured recipe from raw webpage text.
    PERFORMS SILENT INGREDIENT SWAPS based on pantry availability.
    """
    if not client:
        return None
        
    prompt = f"""
    You are an expert chef and data engineer.
    
    1. EXTRACT: Analyze the following disorganized webpage text and extract the main recipe.
    2. ADAPT (CRITICAL): The user has a specific pantry. Compare the recipe's required ingredients against this Pantry List:
    {pantry_context}
    
    RULE: If the recipe calls for an ingredient the user DOES NOT have, but they have a valid, reasonable substitute in the pantry, SILENTLY SWAP it in your output.
    - Example: Recipe needs "Buttermilk". Pantry has "Milk" and "Lemon". Swap to "Milk and Lemon".
    - Example: Recipe needs "Shallots". Pantry has "Red Onion". Swap to "Red Onion".
    - If no substitute exists, keep the original ingredient.
    - Do NOT mention that a swap occurred. Just output the recipe as if it was written that way.
    
    3. FORMAT: Output the result strictly as a valid JSON object matching the RecipeSchema.
    
    WEBPAGE TEXT:
    {raw_text}
    """
    
    try:
        print("DEBUG: Sending prompt to GenAI...")
        response = client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type='application/json',
                response_schema=RecipeSchema
            )
        )
        print("DEBUG: GenAI response received.")
        parsed = response.parsed
        
        # If SDK auto-parsing fails (sometimes returns None even if text is valid JSON)
        if parsed is None and response.text:
             print("DEBUG: Auto-parsing failed. Attempting manual extraction.")
             data = extract_json_from_text(response.text)
             return RecipeSchema(**data)
             
        return parsed
    except Exception as e:
        print(f"Error extracting recipe from web: {e}")
        try:
             # Last ditch effort if structured generation failed completely
             # (Sometimes 400 errors or schema violations cause exceptions)
             pass
        except:
             pass
        return None
