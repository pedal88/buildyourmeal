import os
import shutil
import json
import re
from typing import Optional
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO

# Load Credentials (Assuming Environment Variables or default Auth)
# Project ID and Location are usually required for Vertex AI
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "your-project-id") 
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

class VertexImageGenerator:
    def __init__(self, root_path=None):
        self.root_path = root_path or os.getcwd()
        self.candidates_dir = os.path.join(self.root_path, 'static', 'pantry', 'candidates')
        self.production_dir = os.path.join(self.root_path, 'static', 'pantry')
        self.pantry_file = os.path.join(self.root_path, 'data', 'constraints', 'pantry.json')
        
        # Ensure candidates dir exists
        os.makedirs(self.candidates_dir, exist_ok=True)
        
        # Initialize GenAI Client
        api_key = os.getenv("GOOGLE_API_KEY")
        if api_key:
            self.client = genai.Client(api_key=api_key)
        else:
            self.client = None
            print("WARNING: GOOGLE_API_KEY not set. VertexImageGenerator will fail.")
            
        # Initialize Jinja2 Env
        try:
            from jinja2 import Environment, FileSystemLoader
            self.jinja_env = Environment(loader=FileSystemLoader(os.path.join(self.root_path, 'data', 'prompts')))
        except Exception as e:
            print(f"Warning: Jinja2 initialization failed: {e}")
            self.jinja_env = None

    def get_prompt(self, ingredient_name, visual_details=""):
        if not self.jinja_env:
            return f"A professional studio food photography shot of {ingredient_name}. {visual_details}"
            
        try:
            template = self.jinja_env.get_template('ingredient_image/ingredient_image.jinja2')
            return template.render(ingredient_name=ingredient_name, visual_details=visual_details)
        except Exception as e:
            print(f"Error rendering prompt: {e}")
            return f"A professional studio food photography shot of {ingredient_name}."


    def _get_safe_filename(self, name: str) -> str:
        """Converts ingredient name to safe filename: 'Beef Ribeye' -> 'beef_ribeye.png'"""
        safe_name = re.sub(r'[^a-zA-Z0-9]', '_', name.lower())
        safe_name = re.sub(r'_+', '_', safe_name).strip('_')
        return f"{safe_name}.png"
    
    def generate_candidate(self, ingredient_name: str, prompt: str) -> dict:
        """
        Generates an image using Imagen 3 and saves it to the candidates folder.
        Returns: { 'success': bool, 'image_url': str, 'error': str }
        """
        if not self.client:
            return {'success': False, 'error': "Google API Key not configured"}

        try:
            filename = self._get_safe_filename(ingredient_name)
            output_path = os.path.join(self.candidates_dir, filename)
            
            print(f"Generating candidate for {ingredient_name} using Prompt: {prompt[:50]}...")
            
            # Call Imagen 4 (via Gemini API wrapper)
            response = self.client.models.generate_images(
                model='imagen-4.0-generate-001',
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio='1:1' # Square for ingredients
                )
            )
            
            if response.generated_images:
                genai_image = response.generated_images[0].image
                img = Image.open(BytesIO(genai_image.image_bytes))
                
                # Resize/Optimize if needed (keeping original for now)
                img.save(output_path, format="PNG")
                
                return {
                    'success': True,
                    'image_url': f"/static/pantry/candidates/{filename}",
                    'local_path': output_path
                }
            else:
                 return {'success': False, 'error': "No image returned from API"}

        except Exception as e:
            print(f"Error generating candidate: {e}")
            return {'success': False, 'error': str(e)}

    def approve_candidate(self, ingredient_name: str) -> dict:
        """
        Approves a candidate image by overwriting the production image.
        1. Finds candidate file.
        2. Looks up target filename from pantry.json.
        3. Overwrites target file.
        4. Deletes candidate.
        """
        candidate_filename = self._get_safe_filename(ingredient_name)
        candidate_path = os.path.join(self.candidates_dir, candidate_filename)
        
        if not os.path.exists(candidate_path):
            return {'success': False, 'error': f"Candidate file not found: {candidate_filename}"}
        
        # Look up target in pantry.json
        target_relative_path = None
        try:
            with open(self.pantry_file, 'r') as f:
                pantry_data = json.load(f)
                
            # Search for ingredient (case-insensitive)
            # pantry_data is a list of objects
            for item in pantry_data:
                if item.get('food_name', '').lower() == ingredient_name.lower():
                    # found it
                    if 'images' in item and 'image_url' in item['images']:
                        target_relative_path = item['images']['image_url']
                    break
            
            if not target_relative_path:
                 return {'success': False, 'error': f"Ingredient '{ingredient_name}' not found in pantry.json or has no image_url defined."}
                 
        except Exception as e:
             return {'success': False, 'error': f"Error reading pantry.json: {str(e)}"}

        # Perform Overwrite
        # target_relative_path is likely "pantry/000001.png"
        # We need to strip "pantry/" if it exists because our production_dir is 'static/pantry'
        # OR we just construct full path carefully.
        
        # Validating path structure
        if target_relative_path.startswith("pantry/"):
             clean_target = target_relative_path.replace("pantry/", "")
             target_path = os.path.join(self.production_dir, clean_target)
        elif target_relative_path.startswith("/static/pantry/"):
             clean_target = target_relative_path.replace("/static/pantry/", "")
             target_path = os.path.join(self.production_dir, clean_target)
        else:
             # Assume it's just a filename
             target_path = os.path.join(self.production_dir, os.path.basename(target_relative_path))
             
        try:
            print(f"Approving: Moving {candidate_path} -> {target_path}")
            shutil.copy2(candidate_path, target_path) # Copy metadata + data
            os.remove(candidate_path) # Cleanup
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': f"Error moving file: {str(e)}"}
