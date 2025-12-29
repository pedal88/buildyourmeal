from app import app, db
from database.models import Ingredient

with app.app_context():
    count = db.session.query(Ingredient).count()
    print(f"Ingredient count: {count}")
