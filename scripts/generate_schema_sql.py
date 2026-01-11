import sys
import os
from sqlalchemy.schema import CreateTable
from sqlalchemy import create_mock_engine

# Add parent directory to path to import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db

def dump_node(buf, metadata, item):
    pass

def dump(sql, *multiparams, **params):
    print(sql.compile(dialect=engine.dialect))

def generate_ddl():
    # Use a mock engine to capture DDL
    def dump(sql, *multiparams, **params):
        print(f"{sql.compile(dialect=engine.dialect)};")

    # Use postgresql dialect
    engine = create_mock_engine("postgresql://", dump)

    with app.app_context():
        # This will verify the models are loaded
        from database.models import User, Recipe, Ingredient, Instruction, RecipeIngredient, RecipeMealType, Chef
        
        print("-- Auto-generated schema from SQLAlchemy Models")
        metadata = db.metadata
        metadata.create_all(engine, checkfirst=False)

if __name__ == "__main__":
    generate_ddl()
