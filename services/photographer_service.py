import requests
import os
import json
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO

# Load Configuration
def load_photographer_config():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "agents", "photographer.json")
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
    
    style_guide = """
    STYLE GUIDELINE:
    - Vibe: Professional, High-End, Cookbook.
    - Description: Hyper-realistic photography with perfect studio lighting. The ingredient is the hero.
    - Constraint: Isolated on a pure white background.
    - Output Format: Write a single, concise image generation prompt. Do not write a list.
    """
    
    full_prompt = f"""
    {config['system_prompt']}
    {style_guide}
    {ingredients_context}
    
    RECIPE / IDEA TO ANALYZE:
    {recipe_text}
    
    Task: Convert the above idea into a professional image generation prompt following the style guideline.
    """
    
    response = client.models.generate_content(
        model='gemini-2.0-flash-exp', # Using a fast text model
        contents=full_prompt
    )
    
    return response.text.strip()

def generate_visual_prompt_from_image(image_bytes: bytes) -> str:
    """
    Uses Gemini Vision to analyze an uploaded image and write a prompt to recreate it.
    """
    if not client:
        raise Exception("Google API Key not configured")
        
    config = load_photographer_config()
    
    full_prompt = f"""
    {config['system_prompt']}
    
    TASK: Analyze the provided food image. Write a highly detailed visual prompt that would allow an AI model to recreate this exact dish, lighting, styling, and composition.
    Focus on:
    1. The textures and ingredient visibility.
    2. The lighting setup (direction, hardness, color).
    3. The plating and background.
    """
    
    # Create the image object for Gemini
    # For new genai SDK (v1.0+), we can pass PIL images or bytes directly in contents
    image = Image.open(BytesIO(image_bytes))

    response = client.models.generate_content(
        model='gemini-2.0-flash-exp',
        contents=[full_prompt, image]
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

def generate_image_variation(image_bytes: bytes, fixed_prompt: str) -> Image.Image:
    """
    Simulates an 'Image Variation' or 'Remix' by:
    1. Using Gemini Vision to describe the input image content/subject.
    2. combining that description with the 'fixed_prompt' (Enhancer).
    3. Generating a entirely new image based on the combined prompt.
    """
    if not client:
        raise Exception("Google API Key not configured")

    # 1. Analyze the input image to get the core subject
    vision_prompt = """
    Describe the MAIN SUBJECT of this food image in one concise sentence. 
    Focus only on the food items and key ingredients.
    IMPORTANT: IGNORE any text, labels, logos, or watermarks superimposed on the image. Describe only the food itself as if the text wasn't there.
    Example: 'A stack of pancakes with syrup' (even if the image says 'Good Morning' on it).
    """
    
    try:
        image = Image.open(BytesIO(image_bytes))
        response = client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents=[vision_prompt, image]
        )
        subject_description = response.text.strip()
        
        # 2. Combine with Fixed Prompt (Enhancer)
        # The fixed prompt provides the "Style", the vision provides the "Subject".
        # We support a template format "[Subject]" to insert the description naturally.
        if "[Subject]" in fixed_prompt:
            final_prompt = fixed_prompt.replace("[Subject]", subject_description)
        elif "[Ingredient Name]" in fixed_prompt:
            final_prompt = fixed_prompt.replace("[Ingredient Name]", subject_description)
        else:
            final_prompt = f"Subject: {subject_description}. \nStyle & Execution: {fixed_prompt}"
        
        # 3. Generate
        return generate_actual_image(final_prompt)

    except Exception as e:
        print(f"Error in variation generation: {e}")
        raise e

def process_external_image(image_url: str) -> Image.Image:
    """
    Downloads an image from a URL and "Re-Imagines" it using our style.
    Returns: PIL Image object of the NEW AI generated image.
    """
    if not image_url:
        return None
        
    try:
        # 1. Download Content
        response = requests.get(image_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        response.raise_for_status()
        
        image_bytes = response.content
        
        # 2. Re-Imagine (Use Cookbook Style)
        # We reuse the generate_image_variation which specifically cleans up text and applies our style
        config = load_photographer_config()
        # "Cookbook Style" is not in config, so we use the best template we created for Studio
        # Actually, let's reuse generate_image_variation directly with a strong fixed prompt
        
        cookbook_prompt = "A professional close-up food photography shot of [Ingredient Name]. Studio lighting, soft shadows, sharp focus, isolated on a pure white background. 8k resolution, highly detailed texture, appetizing."
        
        return generate_image_variation(image_bytes, cookbook_prompt)

    except Exception as e:
        print(f"Error processing external image: {e}")
        return None # Fail gracefully (user gets no image or default)
