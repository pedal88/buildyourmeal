import os
import re
import json
import shutil
from datetime import datetime
from flask import Blueprint, jsonify, request, current_app
from jinja2 import Environment, FileSystemLoader

# Import Services for Test Runner
import ai_engine
from services.vertex_image_service import VertexImageGenerator

studio_bp = Blueprint('studio', __name__, url_prefix='/studio')

PROMPTS_DIR = os.path.join(os.getcwd(), 'data', 'prompts')
BACKUP_DIR = os.path.join(PROMPTS_DIR, 'backups')

# Ensure directories exist
os.makedirs(PROMPTS_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)

@studio_bp.route('/prompts')
def studio_ui():
    """Render the Studio UI."""
    return current_app.jinja_env.get_template('studio/prompts.html').render()

@studio_bp.route('/api/prompts', methods=['GET'])
def list_prompts():

    """List all .jinja2 files in the prompts directory."""
    try:
        files = [f for f in os.listdir(PROMPTS_DIR) if f.endswith('.jinja2')]
        files.sort()
        return jsonify({'success': True, 'files': files})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@studio_bp.route('/api/prompts/<filename>', methods=['GET'])
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
        # Pattern handles simple variable names
        pattern = r'\{\{\s*([a-zA-Z0-9_]+)\s*\}\}'
        variables = list(set(re.findall(pattern, content)))
        variables.sort()
        
        return jsonify({
            'success': True, 
            'content': content,
            'variables': variables
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@studio_bp.route('/api/prompts/save', methods=['POST'])
def save_prompt():
    """Backup current file and overwrite with new content."""
    try:
        data = request.get_json()
        filename = data.get('filename')
        content = data.get('content')
        
        if not filename or not content:
            return jsonify({'success': False, 'error': 'Missing filename or content'}), 400

        # Security check
        if '..' in filename or filename.startswith('/'):
             return jsonify({'success': False, 'error': 'Invalid filename'}), 400

        path = os.path.join(PROMPTS_DIR, filename)
        
        # 1. Backup if exists
        if os.path.exists(path):
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_name = f"{filename}.{timestamp}.bak"
            backup_path = os.path.join(BACKUP_DIR, backup_name)
            shutil.copy2(path, backup_path)
            
        # 2. Save New Content
        with open(path, 'w') as f:
            f.write(content)
            
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@studio_bp.route('/api/prompts/test', methods=['POST'])
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
            model = 'gemini-flash-latest' # Default to Flash for speed
            
            print(f"DEBUG: Testing Gemini Text with prompt: {rendered_prompt[:100]}...")
            
            response = ai_engine.client.models.generate_content(
                model=model,
                contents=rendered_prompt
            )
            result = response.text
            
        elif runner == 'vertex_image':
            # Call Vertex Image Service (Ingredient Image)
            # This service returns a dict {success, image_url} or similar
            # Use a dummy ingredient name for the file if not provided
            ing_name = variables.get('ingredient_name', 'test_ingredient')
            
            gen = VertexImageGenerator(root_path=os.getcwd())
            
            # We pass the rendered prompt directly
            # Note: generate_candidate wants (ingredient_name, prompt)
            res = gen.generate_candidate(ing_name, rendered_prompt)
            
            if res.get('success'):
                # Return image tag markup or just the url
                result = f'<img src="{res["image_url"]}" class="max-w-full h-auto rounded shadow" />'
            else:
                result = f"Error: {res.get('error')}"
                
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
