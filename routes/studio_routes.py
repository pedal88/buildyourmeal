import os
import re
import json
import shutil
import uuid
from datetime import datetime
from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required
from utils.decorators import admin_required
from jinja2 import Environment, FileSystemLoader

# Import Services for Test Runner
import ai_engine
from services.vertex_image_service import VertexImageGenerator
from services.podcast_service import PodcastGenerator

prompts_bp = Blueprint('prompts', __name__, url_prefix='/admin/prompts')

PROMPTS_DIR = os.path.join(os.getcwd(), 'data', 'prompts')
BACKUP_DIR = os.path.join(PROMPTS_DIR, 'backups')

# Ensure directories exist
os.makedirs(PROMPTS_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)

@prompts_bp.route('/')
@login_required
@admin_required
def studio_ui():
    """Render the Studio UI."""
    return current_app.jinja_env.get_template('studio/prompt_ide.html').render()

@prompts_bp.route('/api/prompts', methods=['GET'])
@login_required
@admin_required
def list_prompts():
    """List all .jinja2 files in the prompts directory (recursively)."""
    try:
        files = []
        for root, _, filenames in os.walk(PROMPTS_DIR):
            for filename in filenames:
                if filename.endswith('.jinja2'):
                    # Get relative path
                    rel_dir = os.path.relpath(root, PROMPTS_DIR)
                    if rel_dir == '.':
                        files.append(filename)
                    else:
                        files.append(os.path.join(rel_dir, filename))
        
        files.sort()
        return jsonify({'success': True, 'files': files})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

META_FILE = os.path.join(PROMPTS_DIR, 'meta.json')

def load_meta():
    if not os.path.exists(META_FILE): return {}
    try:
        with open(META_FILE, 'r') as f: return json.load(f)
    except: return {}

def save_meta_data(data):
    with open(META_FILE, 'w') as f: json.dump(data, f, indent=2)

@prompts_bp.route('/api/prompts/<path:filename>', methods=['GET'])
@login_required
@admin_required
def get_prompt(filename):
    """Read a specific prompt file and detect variables."""
    # Security check: disallow directory traversal
    if '..' in filename or filename.startswith('/'):
        return jsonify({'success': False, 'error': 'Invalid filename'}), 400
        
    path = os.path.join(PROMPTS_DIR, filename)
    if not os.path.exists(path):
        return jsonify({'success': False, 'error': 'File not found'}), 404
        
    try:
        with open(path, 'r') as f:
            content = f.read()
            
        # Detect Variables: {{ variable_name }}
        # Detect Variables: {{ variable_name }}
        pattern = r'\{\{\s*([a-zA-Z0-9_]+)\s*\}\}'
        all_vars = set(re.findall(pattern, content))
        # Filter out system variables (starting with _)
        variables = [v for v in all_vars if not v.startswith('_')]
        variables.sort()
        
        # Load Description from Meta
        meta = load_meta()
        description = meta.get(filename, "")
        
        return jsonify({
            'success': True, 
            'content': content,
            'variables': variables,
            'description': description
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@prompts_bp.route('/api/prompts/save', methods=['POST'])
@login_required
@admin_required
def save_prompt():
    """Backup current file and overwrite with new content."""
    try:
        data = request.get_json()
        filename = data.get('filename')
        content = data.get('content')
        description = data.get('description', '')
        
        if not filename:
            return jsonify({'success': False, 'error': 'Missing filename'}), 400

        # Security check
        if '..' in filename or filename.startswith('/'):
             return jsonify({'success': False, 'error': 'Invalid filename'}), 400

        path = os.path.join(PROMPTS_DIR, filename)
        
        # 1. Backup if exists
        if os.path.exists(path):
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_name = f"{filename}.{timestamp}.bak"
            # Ensure backup dir exists for nested files
            backup_full_path = os.path.join(BACKUP_DIR, backup_name)
            os.makedirs(os.path.dirname(backup_full_path), exist_ok=True)
            shutil.copy2(path, backup_full_path)
            
        # 2. Save New Content (if provided - maybe user just saved description)
        if content is not None:
            with open(path, 'w') as f:
                f.write(content)
            
        # 3. Save Description
        meta = load_meta()
        meta[filename] = description
        save_meta_data(meta)

        return jsonify({'success': True})
        
    except Exception as e:
        print(e)
        return jsonify({'success': False, 'error': str(e)}), 500

@prompts_bp.route('/api/prompts/test', methods=['POST'])
@login_required
@admin_required
def test_prompt():
    """Test the prompt with a specific runner."""
    try:
        data = request.get_json()
        filename = data.get('filename')
        variables = data.get('variables', {})
        runner = data.get('runner', 'unknown')
        
        if not filename:
             return jsonify({'success': False, 'error': 'Filename required'}), 400

        # 1. Render Template in Memory to debug input
        env = Environment(loader=FileSystemLoader(PROMPTS_DIR))
        template = env.get_template(filename)
        rendered_prompt = template.render(**variables)
        
        # 2. Runner Logic
        result = None
        
        if runner == 'gemini_text':
            # Call Gemini via AI Engine's client (Raw call)
            # We assume user wants raw text output
            model = 'gemini-2.0-flash-exp' # Default to Flash for speed
            
            print(f"DEBUG: Testing Gemini Text with prompt: {rendered_prompt[:100]}...")
            
            response = ai_engine.client.models.generate_content(
                model=model,
                contents=rendered_prompt
            )
            result = response.text

        elif runner == 'gemini_json':
            # Call Gemini with JSON structure forced
            model = 'gemini-2.0-flash-exp'
            
            print(f"DEBUG: Testing Gemini JSON with prompt: {rendered_prompt[:100]}...")
            
            response = ai_engine.client.models.generate_content(
                model=model,
                contents=rendered_prompt,
                config={
                    'response_mime_type': 'application/json'
                }
            )
            result = response.text
            # Try to parse to ensure it's valid JSON for display
            try:
                json_res = json.loads(result)
                result = json_res # Return object to be stringified by frontend
            except:
                pass # Return text if parse fails
            
        elif runner == 'vertex_image':
            # Call Vertex Image Service (Ingredient Image)
            # This service returns a dict {success, image_url} or similar
            # Use a dummy ingredient name for the file if not provided
            ing_name = variables.get('ingredient_name', 'test_ingredient')
            
            # Use injected storage provider
            storage_provider = prompts_bp.storage_provider
            gen = VertexImageGenerator(storage_provider=storage_provider, root_path=os.getcwd())
            
            # We pass the rendered prompt directly
            # Note: generate_candidate wants (ingredient_name, prompt)
            res = gen.generate_candidate(ing_name, rendered_prompt)
            
            if res.get('success'):
                # Return image tag markup or just the url
                result = f'<img src="{res["image_url"]}" class="max-w-full h-auto rounded shadow" />'
            else:
                result = f"Error: {res.get('error')}"
                


        elif runner == 'article_generator':
            # 1. Load Library Context (Simplified)
            resources_path = os.path.join(os.getcwd(), 'data', 'resources.json')
            existing_slugs = []
            try:
                with open(resources_path, 'r') as f:
                    data = json.load(f)
                    existing_slugs = [{'title': item['title'], 'slug': item['slug']} for item in data]
            except:
                pass # First run

            # 2. Render Prompt with Context
            if not variables.get('user_description'):
                return jsonify({'success': False, 'error': 'Please provide a "user_description" for the article.'}), 400

            variables['_existing_library_context'] = json.dumps(existing_slugs)
            rendered_prompt = template.render(**variables)

            # 3. Generate Text (Article JSON)
            print(f"DEBUG: Generating Article...")
            model = 'gemini-2.0-flash-exp'
            response = ai_engine.client.models.generate_content(
                model=model,
                contents=rendered_prompt,
                config={'response_mime_type': 'application/json'}
            )
            article_json = json.loads(response.text)

            # 4. Generate Image (Vertex)
            image_prompt = article_json.get('image_prompt', 'A delicious food image')
            print(f"DEBUG: Generating Article Image for prompt: {image_prompt}")
            
            storage_provider = prompts_bp.storage_provider
            gen = VertexImageGenerator(storage_provider=storage_provider, root_path=os.getcwd())
            
            # Use 'studio' context or similar for consistent style if needed
            res = gen.generate_candidate(article_json.get('slug', 'temp'), image_prompt)
            
            if res.get('success'):
                # Attach temp image url to the result so frontend can see/save it
                article_json['temp_image_url'] = res['image_url']
                # For Phase 2, remove local_path dependency if possible or map appropriately
                article_json['temp_image_path'] = res.get('local_path', res['image_url'])
            
            result = article_json

        elif runner == 'podcast_ingredient':
            # 1. Generate Script (Gemini JSON)
            print("DEBUG: Generating Podcast Script...")
            model = 'gemini-2.0-flash-exp'
            rendered_prompt = template.render(**variables)
            
            response = ai_engine.client.models.generate_content(
                model=model,
                contents=rendered_prompt,
                config={'response_mime_type': 'application/json'}
            )
            
            script_json = []
            try:
                script_json = json.loads(response.text)
            except:
                script_json = [{"speaker": "System", "text": "Error parsing JSON script."}]
                
            # 2. Synthesize Audio
            print("DEBUG: Synthesizing Audio...")
            storage_provider = prompts_bp.storage_provider
            gen = PodcastGenerator(storage_provider=storage_provider)
            
            if gen.client:
                slug = "test_podcast"
                filename = f"{slug}_{uuid.uuid4().hex[:6]}.mp3"
                
                try:
                    # Save via Storage Service (generates directly to storage)
                    # Use a temp folder or just podcasts/temp?
                    public_url = gen.generate_and_save(script_json, filename, "podcasts/temp")
                    
                    result = {
                        "audio_url": public_url,
                        "temp_path": public_url, # Identifier for later saving/moving
                        "script": script_json
                    }
                except Exception as e:
                     result = {
                        "error": str(e),
                        "script": script_json
                    }
            else:
                result = {
                    "error": "TTS Client not available (check logs/creds).",
                    "script": script_json
                }

        else:
            return jsonify({'success': False, 'error': f'Unknown runner: {runner}'}), 400

        return jsonify({
            'success': True,
            'rendered_prompt': rendered_prompt,
            'result': result
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@prompts_bp.route('/api/resources/save', methods=['POST'])
@login_required
@admin_required
def save_resource():
    try:
        article_data = request.get_json()
        if not article_data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        # 1. Handle Image Move (Temp -> Static/Resources)
        temp_path = article_data.get('temp_image_path')
        final_image_filename = None
        
        storage_provider = prompts_bp.storage_provider
        
        if temp_path:
            # Generate new filename
            ext = ".png" # Assume png from Vertex service
            if temp_path.endswith('.jpg'): ext = ".jpg"
            
            new_filename = f"{article_data.get('slug', 'resource')}_{uuid.uuid4().hex[:6]}{ext}"
            
            # USE COPY from storage provider
            # Note: "temp_path" here is actually the URL from previous step in our new flow
            # If it's local URL: /static/pantry/candidates/foo.png
            # If it's GCS URL: https://storage.../pantry/candidates/foo.png
            
            # The StorageService.copy expects a SOURCE PATH.
            # Local: full path. GCS: ?
            
            # HACK: For consistency in Phase 2, we assume `temp_path` allows us to find the source.
            # If we are Local, we can resolve it.
            # If we are GCS, we should ideally simply copy object to object.
            # Our current interface is limited.
            
            # Let's rely on the fact that `VertexImageGenerator` put it in `pantry/candidates`.
            # We want to move it to `resources`.
            
            # Extract filename from URL/Path
            source_filename = os.path.basename(temp_path)
            
            # This is fragile but works for the current "Local" impl which expects full path.
            # We construct the source key.
            pass
            
            # Check if valid source for Copy
            # For LocalStorageProvider, `copy` takes a source_path (absolute).
            # We need to resolve `temp_path` (which might be a URL) to an absolute path IF local.
            
            real_source_path = temp_path
            if isinstance(storage_provider, type(storage_provider).__bases__[0]): # Is Local? No easy check without imports
                 # Simple check: if it starts with /static, map it
                 if temp_path.startswith('/static'):
                     real_source_path = os.path.join(os.getcwd(), temp_path.lstrip('/'))
            
            # Try copy
            # Dest folder: resources
            try:
                final_image_filename = storage_provider.copy(real_source_path, new_filename, "resources")
            except Exception as e:
                print(f"Error copying image: {e}")
                final_image_filename = article_data.get('image_filename') # Fallback

        # 2. Prepare Resource Object
        new_resource = {
            "id": article_data.get('slug'), # Use slug as ID for simplicity or generate UUID
            "slug": article_data.get('slug'),
            "title": article_data.get('title'),
            "summary": article_data.get('summary'),
            "content_markdown": article_data.get('content_markdown'),
            "tags": article_data.get('tags', []),
            "image_filename": final_image_filename,
            "related_slugs": article_data.get('related_slugs', []),
            "meta": article_data.get('meta', {})
        }

        # 3. Save to JSON Store
        resources_path = os.path.join(os.getcwd(), 'data', 'resources.json')
        current_resources = []
        if os.path.exists(resources_path):
            with open(resources_path, 'r') as f:
                current_resources = json.load(f)
        
        # Append
        current_resources.append(new_resource)
        
        with open(resources_path, 'w') as f:
            json.dump(current_resources, f, indent=4)

        return jsonify({'success': True})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@prompts_bp.route('/api/podcasts/save', methods=['POST'])
@login_required
@admin_required
def save_podcast():
    try:
        data = request.get_json()
        temp_path = data.get('temp_path') # This is the URL now
        ingredient_name = data.get('ingredient_name', 'audio')
        
        storage_provider = prompts_bp.storage_provider
        
        if not temp_path:
             return jsonify({'success': False, 'error': 'Temp path missing'}), 400

        slug = re.sub(r'[^a-z0-9]+', '-', ingredient_name.lower()).strip('-')
        filename = f"{slug}_{uuid.uuid4().hex[:6]}.mp3"
        
        # Resolve Source
        real_source_path = temp_path
        if temp_path.startswith('/static'):
             real_source_path = os.path.join(os.getcwd(), temp_path.lstrip('/'))

        final_url = storage_provider.copy(real_source_path, filename, "podcasts")
        
        return jsonify({'success': True, 'path': final_url})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
