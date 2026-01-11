import sys
import os
import getpass
from sqlalchemy import select

# Add parent directory to path to import app and models
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from database.models import User

def create_admin():
    with app.app_context():
        print("--- Create Admin User ---")
        email = input("Email: ").strip()
        
        if not email:
            print("Error: Email is required.")
            return

        stmt = select(User).where(User.email == email)
        user = db.session.execute(stmt).scalar_one_or_none()

        if user:
            print(f"User {email} already exists.")
            update = input("Do you want to update the password/admin status? (y/n): ").lower()
            if update != 'y':
                return
        else:
            user = User(email=email)
            print(f"Creating new user: {email}")

        password = getpass.getpass("Password: ")
        confirm_password = getpass.getpass("Confirm Password: ")

        if password != confirm_password:
            print("Error: Passwords do not match.")
            return
            
        user.set_password(password)
        user.is_admin = True
        
        if not user.id:
            db.session.add(user)
            
        db.session.commit()
        print(f"Successfully created/updated admin user: {email}")

if __name__ == "__main__":
    create_admin()
