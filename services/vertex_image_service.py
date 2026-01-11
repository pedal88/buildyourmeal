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
    def __init__(self, storage_provider, root_path=None):
        self.storage = storage_provider
        self.root_path = root_path or os.getcwd()
        self.pantry_file = os.path.join(self.root_path, 'data', 'constraints', 'pantry.json')
        
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
                # We can save bytes directly
                image_bytes = genai_image.image_bytes
                
                # Save via Storage Provider
                # Folder: pantry/candidates
                public_url = self.storage.save(image_bytes, filename, "pantry/candidates")
                
                # For local dev, we might need the absolute path for some operations, but
                # optimally we just return the URL. The previous code returned 'local_path'.
                # We'll return the URL as the primary identifier now.
                
                return {
                    'success': True,
                    'image_url': public_url,
                    'local_path': public_url # Backwards compat: use URL as path identifier
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
        # target_relative_path is likely "pantry/000001.png" or "/static/pantry/000001.png"
        clean_target = target_relative_path
        if clean_target.startswith("/static/"):
            clean_target = clean_target.replace("/static/", "")
        
        # Now we have something like "pantry/000001.png"
        # We need to extract folder and filename
        if "/" in clean_target:
            dest_folder = os.path.dirname(clean_target)
            dest_filename = os.path.basename(clean_target)
        else:
            dest_folder = "pantry" # Default
            dest_filename = clean_target

        try:
            print(f"Approving: Moving Candidate -> {dest_folder}/{dest_filename}")
            
            # Since candidate is already in storage, we need a "move/copy" operation.
            # However, our current StorageProvider only has `copy` from LOCAL source.
            # If we are in GCS, we'd want a bucket-to-bucket copy.
            # For Phase 2, let's assume valid flow is:
            # 1. Candidate is in "pantry/candidates/{filename}"
            # 2. We want to move it to "{dest_folder}/{dest_filename}"
            
            # Simplification: READ bytes -> WRITE bytes -> DELETE old
            # This is inefficient for GCS but universal.
            # Better: Add `move` to StorageProvider later.
            
            # For now, we will rely on `approve_candidate` being used mostly for metadata updates
            # OR we implement a simple read-and-write. 
            pass 
            # WAIT: The storage interface doesn't have a generic "read" or "move". 
            # The prompt asked for `copy(source_path, ...)` but defined source_path as local.
            # Current `LocalStorageProvider` supports `copy` from local path.
            # `GoogleCloudStorageProvider` assumes receiving local path too and uploading.
            
            # CRITICAL: `approve_candidate` logic relies on the file being present to move it.
            # If we are strictly using StorageProvider, we should probably just re-generate 
            # or expect the caller to handle the bytes.
            # BUT, the `copy` method I implemented in `GoogleCloudStorageProvider` does `open(source_path)`.
            
            # For this specific refactor, since we changed `generate_candidate` to return a URL,
            # `approve_candidate` is tricky without direct file access.
            # Let's Modify StorageProvider to include `move` or just omit this feature for now?
            # User requirement: "Refactor... Inject StorageProvider... Replace all local save logic".
            
            # Let's assume for now that `approve_candidate` needs to know the source.
            # Since `generate_candidate` saves via storage, we can't easily "move" it if we don't have a "move" method.
            # Let's add a TODO and return success for now to unblock, 
            # or implemented a specific hack?
            # Actually, `approve_candidate` was reading `candidates_dir` locally. 
            # If we are on GCS, `candidates_dir` doesn't exist locally.
            
            return {'success': False, 'error': "Approve functionality pending update for Cloud Storage."}

        except Exception as e:
            return {'success': False, 'error': f"Error moving file: {str(e)}"}
