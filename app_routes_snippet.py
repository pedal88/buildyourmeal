
# RECIPE IMAGE GENERATION FLOW
@app.route('/recipe-image-generation')
def recipe_image_generation_view():
    recipe_id = request.args.get('recipe_id')
    if not recipe_id:
        flash("Recipe ID required", "error")
        return redirect(url_for('index'))
    
    recipe = db.session.get(Recipe, int(recipe_id))
    if not recipe:
        flash("Recipe not found", "error")
        return redirect(url_for('index'))
        
    return render_template('recipe_photographer.html', recipe=recipe)

@app.route('/recipe-image-generation/prompt', methods=['POST'])
def recipe_image_generation_prompt():
    try:
        data = request.get_json()
        recipe_id = data.get('recipe_id')
        recipe = db.session.get(Recipe, int(recipe_id))
        
        if not recipe:
            return jsonify({'success': False, 'error': 'Recipe not found'})
            
        # Reconstruct Context for AI
        ingredients_list = ", ".join([ri.ingredient.name for ri in recipe.ingredients])
        
        recipe_text = f"Title: {recipe.title}\n"
        recipe_text += f"Cuisine: {recipe.cuisine}\n"
        recipe_text += f"Diet: {recipe.diet}\n"
        
        # Generate Prompt
        prompt = generate_visual_prompt(recipe_text, ingredients_list)
        
        return jsonify({'success': True, 'prompt': prompt})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/recipe-image-generation/generate', methods=['POST'])
def recipe_image_generation_create():
    try:
        data = request.get_json()
        prompt = data.get('prompt')
        
        if not prompt:
            return jsonify({'success': False, 'error': 'Prompt required'})
            
        # Generate Image
        img = generate_actual_image(prompt)
        
        # Save to Temp
        filename = f"temp_{uuid.uuid4().hex}.png"
        temp_path = os.path.join(app.root_path, 'static', 'temp', filename)
        
        # Ensure temp dir exists
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        
        img.save(temp_path, format="PNG")
        
        return jsonify({'success': True, 'filename': filename})
        
    except Exception as e:
        print(f"Gen Error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/recipe-image-generation/save', methods=['POST'])
def recipe_image_generation_save():
    try:
        data = request.get_json()
        filename = data.get('filename')
        recipe_id = data.get('recipe_id')
        
        if not filename or not recipe_id:
            return jsonify({'success': False, 'error': 'Missing data'})
            
        # Move file
        src = os.path.join(app.root_path, 'static', 'temp', filename)
        new_filename = f"recipe_{recipe_id}_{uuid.uuid4().hex[:8]}.png"
        dst = os.path.join(app.root_path, 'static', 'recipes', new_filename)
        
        if os.path.exists(src):
            shutil.move(src, dst)
            
            # Update DB
            recipe = db.session.get(Recipe, int(recipe_id))
            recipe.image_filename = new_filename
            db.session.commit()
            
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Temp file not found'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
