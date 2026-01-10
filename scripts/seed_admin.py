import sys
import os
import argparse
from getpass import getpass

# Add parent directory to path to allow imports from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from database.models import db, User

def seed_admin():
    """
    Create or update an admin user. Can be interactive or via arguments.
    """
    parser = argparse.ArgumentParser(description="Seed Admin User")
    parser.add_argument("--email", help="Admin email")
    parser.add_argument("--password", help="Admin password")
    args = parser.parse_args()

    print("--- Create Admin User ---")
    
    # Get Email
    if args.email:
        email = args.email
    else:
        email = input("Enter Email: ").strip()
    
    if not email:
        print("Email is required.")
        return

    # Get Password
    if args.password:
        password = args.password
    else:
        password = getpass("Enter Password: ").strip()
    
    if not password:
        print("Password is required.")
        return

    with app.app_context():
        # Ensure tables exist
        db.create_all()
        
        # Check for existing user
        user = db.session.execute(db.select(User).where(User.email == email)).scalar()
        
        if user:
            print(f"User '{email}' already exists.")
            if args.password:
                 # Force update if provided via CLI
                 confirm = 'y'
            else:
                 confirm = input("Update password and ensure admin access? (y/n): ")
            
            if confirm.lower() == 'y':
                user.set_password(password)
                user.is_admin = True
                db.session.commit()
                print("User updated successfully.")
            else:
                print("Operation cancelled.")
        else:
            # Create new user
            new_user = User(email=email, is_admin=True)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            print(f"Admin user '{email}' created successfully.")

if __name__ == '__main__':
    seed_admin()
