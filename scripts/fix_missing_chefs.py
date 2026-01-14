import sys
import os
import logging
from sqlalchemy import text

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from database.models import Chef

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_missing_chefs():
    basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    target_db = os.path.join(basedir, 'instance', 'kitchen.db')
    
    # Force the app to use the correct database (the one with 600KB data)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{target_db}'

    with app.app_context():
        logger.info(f"Checking database: {app.config.get('SQLALCHEMY_DATABASE_URI')}")
        
        # 1. Gourmet (The default AI Chef)
        gourmet = db.session.get(Chef, 'gourmet')
        if not gourmet:
            logger.info("Adding missing chef: 'gourmet'...")
            c = Chef(
                id='gourmet',
                name='The Gourmet',
                archetype='System Default',
                description='The default AI chef for general recipe generation.',
                image_filename='gourmet.jpg', # Placeholder
                constraints='{}',
                diet_preferences='[]',
                cooking_style='{}',
                ingredient_logic='{}',
                instruction_style='{}'
            )
            db.session.add(c)
        else:
            logger.info("Chef 'gourmet' already exists.")

        # 2. Moribyan (Legacy/Imported)
        moribyan = db.session.get(Chef, 'Moribyan')
        if not moribyan:
            logger.info("Adding missing chef: 'Moribyan'...")
            c = Chef(
                id='Moribyan',
                name='Moribyan',
                archetype='Imported',
                description='Imported chef profile.',
                image_filename='moribyan.jpg', # Placeholder
                constraints='{}',
                diet_preferences='[]',
                cooking_style='{}',
                ingredient_logic='{}',
                instruction_style='{}'
            )
            db.session.add(c)
        else:
            logger.info("Chef 'Moribyan' already exists.")

        try:
            db.session.commit()
            logger.info("Fix applied successfully!")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to commit fix: {e}")

if __name__ == "__main__":
    fix_missing_chefs()
