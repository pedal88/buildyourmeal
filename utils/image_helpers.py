from flask import Response
import urllib.parse

def generate_ingredient_placeholder(name, width=200, height=200):
    """
    Generate an SVG placeholder for ingredients without images.
    Returns an SVG with the ingredient name centered on a grey background.
    
    Args:
        name: The ingredient name to display
        width: Width of the SVG (default 200)
        height: Height of the SVG (default 200)
    
    Returns:
        Flask Response object with SVG content
    """
    # Truncate long names
    display_name = name if len(name) <= 20 else name[:17] + "..."
    
    # Calculate font size based on name length
    if len(display_name) <= 8:
        font_size = 18
    elif len(display_name) <= 12:
        font_size = 16
    else:
        font_size = 14
    
    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
    <defs>
        <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" style="stop-color:#D1D5DB;stop-opacity:1" />
            <stop offset="100%" style="stop-color:#9CA3AF;stop-opacity:1" />
        </linearGradient>
    </defs>
    <rect width="{width}" height="{height}" fill="url(#grad)"/>
    <text x="50%" y="50%" 
          font-family="Inter, system-ui, sans-serif" 
          font-size="{font_size}" 
          font-weight="600"
          fill="#374151" 
          text-anchor="middle" 
          dominant-baseline="middle">
        {urllib.parse.quote(display_name)}
    </text>
</svg>'''
    
    return Response(svg, mimetype='image/svg+xml')


def get_ingredient_image_url(ingredient):
    """
    Get the image URL for an ingredient, with fallback to placeholder.
    
    Args:
        ingredient: Ingredient model instance
    
    Returns:
        URL string for the ingredient image
    """
    if ingredient.image_url:
        return f"/static/{ingredient.image_url}"
    else:
        return f"/api/placeholder/ingredient/{ingredient.food_id}"
