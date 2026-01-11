import sys
import os
from sqlalchemy import text

# Add parent directory to path to import app and models
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from database.models import Ingredient, Recipe, Chef, User

def verify_data():
    with app.app_context():
        print(f"--- Connecting to: {app.config.get('SQLALCHEMY_DATABASE_URI', 'Unknown')} ---")
        
        try:
            user_count = db.session.query(User).count()
            chef_count = db.session.query(Chef).count()
            ingredient_count = db.session.query(Ingredient).count()
            recipe_count = db.session.query(Recipe).count()
            
            print(f"Users: {user_count}")
            print(f"Chefs: {chef_count}")
            print(f"Ingredients: {ingredient_count}")
            print(f"Recipes: {recipe_count}")
            
        except Exception as e:
            print(f"Error connecting/querying: {e}")

if __name__ == "__main__":
    verify_data()
