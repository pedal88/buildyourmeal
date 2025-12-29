from database.models import db, Ingredient

def get_slim_pantry_context():
    """
    Provides the AI with the ingredient definition, including tags for filtering.
    Returns a minified list of dictionaries with abbreviated keys to save tokens.
    
    Keys:
    i: food_id
    n: name
    c: main_category
    u: default_unit
    t: tags
    """
    stmt = db.select(
        Ingredient.food_id,
        Ingredient.name,
        Ingredient.main_category,
        Ingredient.default_unit,
        Ingredient.tags
    )
    results = db.session.execute(stmt).all()
    
    slim_context = []
    for row in results:
        slim_context.append({
            "i": row.food_id,
            "n": row.name,
            "c": row.main_category if row.main_category else "",
            "u": row.default_unit if row.default_unit else "",
            "t": row.tags if row.tags else ""
        })
        
    return slim_context
