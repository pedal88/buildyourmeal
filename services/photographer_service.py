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
    
    from utils.prompt_manager import load_prompt
    
    ingredients_context = ""
    if ingredients_list:
        ingredients_context = f"\nStats: CRITICAL - The following ingredients MUST be visible: {ingredients_list}\n"
    
    full_prompt = load_prompt('recipe_image/visual_description.jinja2',
        system_prompt=config['system_prompt'],
        ingredients_context=ingredients_context,
        recipe_text=recipe_text
    )
    
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
    
    from utils.prompt_manager import load_prompt
    full_prompt = load_prompt('recipe_image/image_analysis.jinja2', system_prompt=config['system_prompt'])
    
    # Create the image object for Gemini
    # For new genai SDK (v1.0+), we can pass PIL images or bytes directly in contents
    image = Image.open(BytesIO(image_bytes))

    response = client.models.generate_content(
        model='gemini-2.0-flash-exp',
        contents=[full_prompt, image]
    )
    
    return response.text.strip()

def generate_actual_image(visual_prompt: str, number_of_images: int = 1) -> list[Image.Image]:
    """
    Uses Gemini (Image) to generate the actual pixel data from the prompt.
    Returns: List of PIL Image objects
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
                number_of_images=number_of_images,
                aspect_ratio='1:1'
            )
        )
        
        # Access images
        if response.generated_images:
            images = []
            for gen_img in response.generated_images:
                # Access the inner 'image' object which contains the bytes
                images.append(Image.open(BytesIO(gen_img.image.image_bytes)))
            return images
        else:
            raise Exception("No images returned from API")
            
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
        
        from utils.prompt_manager import load_prompt
        # Load the cookbook style template
        # The template expects {{ subject_description }} but generate_image_variation handles the logic of 
        # combining a subject description with a "fixed_prompt".
        # However, generate_image_variation expects a "fixed_prompt" that might contain placeholders.
        # But style_cookbook.jinja2 IS a full sentence "A professional... of {{ subject_description }}..."
        # So we need to be careful. generate_image_variation calls generate_actual_image(final_prompt).
        # We should probably use the template content AS the 'fixed_prompt' OR refactor logic.
        
        # Let's simplify: We want to use the template logic. 
        # But generate_image_variation does its own 2-step process.
        # Let's read the template RAW content (with placeholders intact) to pass as 'fixed_prompt'
        # OR we just update the text here.
        
        # ACTUALLY: The user requirement says:
        # Target: data/prompts/style_cookbook.jinja2
        # Variables: {{ subject_description }}
        # Python Change: Update function to load this style template.
        
        # So we need to get the template string itself, effectively?
        # No, we probably want to render it during the variation process?
        # But generate_image_variation is generic.
        
        # Let's assume we pass the *template name* or *pre-rendered part*?
        # "A professional ... of [Ingredient Name]..." was existing.
        # The new template is "A professional ... of {{ subject_description }}..."
        
        # In generate_image_variation, we have:
        # if "[Subject]" in fixed_prompt: ...
        
        # So sticking to the current architecture:
        # usages of generate_image_variation pass a 'fixed_prompt'.
        
        # We can load the template string, treating it as a format string for generate_image_variation?
        # Or better: We change process_external_image to do the 2 steps itself using the prompt manager?
        # No, let's keep it simple. We will load the template, and pass it.
        # But wait, PromptManager.load_prompt RENDERs it.
        # We generally want to render it AFTER we get the subject from the image.
        
        # So:
        # 1. process_external_image gets image.
        # 2. It calls generate_image_variation
        # 3. generate_image_variation gets the description.
        # 4. prompt = load_prompt('style_cookbook.jinja2', subject_description=desc)
        # 5. generate_actual_image(prompt)
        
        # But I am editing process_external_image, not generate_image_variation. 
        # And generate_image_variation is a shared utility.
        
        # Let's Modify generate_image_variation to support a 'style_template_name' arg? 
        # Or just do the logic inline here since refactoring the shared service might be risky if used elsewhere.
        # Actually, let's look at generate_image_variation again.
        
        # It's better to refactor generate_image_variation to take an optional `template_name`?
        # Or just reimplement the logic here since `process_external_image` is valid place for "Cookbook Style".
        
        # Let's reimplement step 1 & 2 here to use the proper template.
        
        # 1. Analyze Subject
        vision_prompt = "Describe the MAIN SUBJECT of this food image in one concise sentence..."
        image = Image.open(BytesIO(image_bytes))
        
        # Reuse client from outer scope
        response = client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents=[vision_prompt, image]
        )
        subject_description = response.text.strip()
        
        # 2. Render Prompt
        cookbook_prompt = load_prompt('recipe_image/style_cookbook.jinja2', subject_description=subject_description)
        
        # 3. Generate
        return generate_actual_image(cookbook_prompt)

    except Exception as e:
        print(f"Error processing external image: {e}")
        return None # Fail gracefully (user gets no image or default)
