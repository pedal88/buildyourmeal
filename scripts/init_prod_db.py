import os
import sys
from sqlalchemy import create_engine, text
from google.cloud.sql.connector import Connector, IPTypes

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_connector import get_db_connection
from database.models import db, Ingredient, Recipe # Import models to register them
from app import app, configure_database

def init_prod_db():
    print("=== Production Database Initialization ===")
    print("This script connects to Cloud SQL and creates tables if they don't exist.")
    
    # --- user-friendly enhancements: fetch connection name if missing ---
    if not os.getenv("INSTANCE_CONNECTION_NAME"):
        print("INSTANCE_CONNECTION_NAME not set. Attempting to fetch from gcloud...")
        import subprocess
        try:
            # Assumes gcloud is in PATH or alias setup. If not, catching error.
            # Using basic command to list runnable instances
            cmd = "gcloud sql instances list --format='value(connectionName)' --filter='state:RUNNABLE' --limit=1"
            conn_name = subprocess.check_output(cmd, shell=True).decode('utf-8').strip()
            if conn_name:
                print(f"Found instance: {conn_name}")
                os.environ["INSTANCE_CONNECTION_NAME"] = conn_name
            else:
                print("No running Cloud SQL instances found via gcloud.")
        except Exception as e:
            print(f"Failed to auto-detect instance: {e}")

    # Set Defaults
    if not os.getenv("DB_USER"):
        os.environ["DB_USER"] = "postgres"
    if not os.getenv("DB_NAME"):
        os.environ["DB_NAME"] = "postgres"

    # Prompt for password if missing
    if not os.getenv("DB_PASS"):
        import getpass
        print("DB_PASS not set.")
        os.environ["DB_PASS"] = getpass.getpass("Enter Database Password: ")

    # Ensure env vars are set
    required = ["INSTANCE_CONNECTION_NAME", "DB_USER", "DB_NAME", "DB_PASS"]
    missing = [k for k in required if not os.getenv(k)]
    
    if missing:
        print(f"Error: Missing environment variables: {missing}")
        print("Please export them in your shell before running this script.")
        print("Example: export INSTANCE_CONNECTION_NAME='project:region:instance'")
        sys.exit(1)

    confirm = input(f"Target: {os.getenv('INSTANCE_CONNECTION_NAME')}\nAre you sure you want to run db.create_all()? (y/n): ")
    if confirm.lower() != 'y':
        print("Aborted.")
        sys.exit(0)

    print("Connecting to Cloud SQL (via Python Connector)...")
    
    # We can reuse the app configuration logic
    # Set backend to cloudsql explicitly for this run
    os.environ['DB_BACKEND'] = 'cloudsql'
    
    # Initialize the app context
    with app.app_context():
        # Force configuration update just in case
        configure_database(app)
        
        try:
            print("Creating tables...")
            db.create_all()
            print("Success! Tables created.")
            
            # Verify
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"Tables found: {tables}")
            
        except Exception as e:
            print(f"Error initializing database: {e}")
            sys.exit(1)

if __name__ == "__main__":
    init_prod_db()
