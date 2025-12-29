# Ingredient Image System

## Overview
This app implements a robust image system for pantry ingredients with automatic fallback to styled placeholders when images are not available.

## Features

### 1. **Database Integration**
- Each ingredient in the database has an `image_url` field that stores the relative path to the image
- Images are stored in `static/pantry/` directory
- The `image_prompt` field stores the AI prompt used to generate the image (for reference)

### 2. **Automatic Fallback**
When an ingredient doesn't have an image:
- **Static Fallback**: A grey gradient square displays the ingredient name
- **Dynamic SVG Fallback** (optional): Server-generated SVG with the ingredient name

### 3. **Image Display Logic**
The recipe detail page (`recipe.html`) checks for each ingredient:
```html
{% if item.ingredient.image_url %}
    <!-- Show actual image from static folder -->
    <img src="{{ url_for('static', filename=item.ingredient.image_url) }}" ...>
{% else %}
    <!-- Show grey placeholder with ingredient name -->
    <div class="bg-gradient-to-br from-gray-300 to-gray-400">
        {{ item.ingredient.name }}
    </div>
{% endif %}
```

## File Structure

```
bym2026/
├── static/
│   └── pantry/           # Ingredient images (e.g., 000001.png)
├── data/
│   └── pantry.json       # Source data with image paths
├── utils/
│   └── image_helpers.py  # SVG placeholder generator
├── templates/
│   └── recipe.html       # Displays ingredients with images
└── seed_data.py          # Loads images from pantry.json
```

## Usage

### Loading Images from pantry.json
Run the seed script to populate the database with image URLs:
```bash
python seed_data.py
```

This will:
- Create new ingredients with all fields including `image_url`
- Update existing ingredients that are missing image data
- Preserve the relative path format (e.g., `pantry/000001.png`)

### Adding New Ingredient Images

1. **Add the image file** to `static/pantry/` with the food_id as filename:
   ```
   static/pantry/000123.png
   ```

2. **Update pantry.json** with the image reference:
   ```json
   {
     "food_id": "000123",
     "food_name": "Tomato",
     "images": {
       "image_url": "pantry/000123.png",
       "image_prompt": "Professional food photography of a ripe tomato..."
     }
   }
   ```

3. **Re-run the seed script** to update the database:
   ```bash
   python seed_data.py
   ```

### Dynamic SVG Placeholders (Advanced)

For ingredients without images, you can use the API endpoint:
```
GET /api/placeholder/ingredient/{food_id}
```

This returns an SVG with:
- Gradient background (grey tones)
- Ingredient name centered
- Responsive font sizing based on name length
- Proper SVG formatting for web display

## Styling

The ingredient cards use:
- **Size**: 96x96px (w-24 h-24)
- **Border radius**: rounded-lg
- **Shadow**: hover effect for interactivity
- **Overlay**: Semi-transparent black overlay with white text for actual images
- **Fallback**: Grey gradient with dark grey text

## Example Data Structure

From `pantry.json`:
```json
{
  "food_id": "000001",
  "food_name": "beef ribeye",
  "main_category": "meat",
  "sub_category": "beef",
  "unit": "g",
  "nutrition": { ... },
  "images": {
    "image_prompt": "Professional food photography of raw beef ribeye...",
    "image_url": "pantry/000001.png"
  }
}
```

## Benefits

1. **Graceful Degradation**: App works perfectly even without images
2. **User-Friendly**: Ingredient names are always visible
3. **Scalable**: Easy to add images incrementally
4. **Consistent UX**: Uniform card sizes whether image exists or not
5. **SEO-Friendly**: Proper alt text and semantic HTML

## Future Enhancements

- [ ] Automatic image generation using AI (Gemini, DALL-E, etc.)
- [ ] Image upload interface for manual additions
- [ ] Image optimization and WebP conversion
- [ ] Lazy loading for performance
- [ ] Image caching strategy
