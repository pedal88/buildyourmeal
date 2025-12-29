import os
import json
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO

# Load Configuration
def load_photographer_config():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "photographer.json")
    with open(path, 'r') as f:
        return json.load(f)['photographer']

# Initialize Client
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
client = None
if GOOGLE_API_KEY:
    client = genai.Client(api_key=GOOGLE_API_KEY)

def generate_visual_prompt(recipe_text: str, ingredients_list: str = None) -> str:
    """
    Uses Gemini (Text) to act as the Food Stylist and write the detailed image prompt.
    """
    if not client:
        raise Exception("Google API Key not configured")
        
    config = load_photographer_config()
    
    ingredients_context = ""
    if ingredients_list:
        ingredients_context = f"\nStats: CRITICAL - The following ingredients MUST be visible: {ingredients_list}\n"
    
    full_prompt = f"""
    {config['system_prompt']}
    {ingredients_context}
    
    RECIPE TO ANALYZE:
    {recipe_text}
    """
    
    response = client.models.generate_content(
        model='gemini-2.0-flash-exp', # Using a fast text model
        contents=full_prompt
    )
    
    return response.text.strip()

def generate_actual_image(visual_prompt: str) -> Image.Image:
    """
    Uses Gemini (Image) to generate the actual pixel data from the prompt.
    Returns: PIL Image object
    """
    if not client:
        raise Exception("Google API Key not configured")

    # Assuming Nano Banana logic is handled by the text prompt being passed 
    # to a capable model like Imagen 3
    
    try:
        response = client.models.generate_images(
            model='imagen-4.0-generate-001',
            prompt=visual_prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio='16:9'
            )
        )
        
        # Access the first image
        if response.generated_images:
            genai_image = response.generated_images[0].image
            return Image.open(BytesIO(genai_image.image_bytes))
        else:
            raise Exception("No image returned from API")
            
    except Exception as e:
        print(f"Error generating image: {e}")
        raise e
