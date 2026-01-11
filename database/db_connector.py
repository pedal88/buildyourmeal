import os
import logging
from google.cloud.sql.connector import Connector, IPTypes

logger = logging.getLogger(__name__)

# Global connector instance to be reused
_connector = None

def get_db_connection():
    """
    Creator function for Cloud SQL connection.
    Reference: https://cloud.google.com/sql/docs/postgres/connect-connectors#python_1
    """
    global _connector
    
    instance_connection_name = os.getenv("INSTANCE_CONNECTION_NAME")
    db_user = os.getenv("DB_USER")
    db_pass = os.getenv("DB_PASS") # Optional if using IAM
    db_name = os.getenv("DB_NAME")
    
    # Initialize connector if not exists (lazy load)
    if _connector is None:
        _connector = Connector()

    # Cloud Run default is usually Public Access to Cloud SQL via Connector.
    # The connector handles the secure tunnel (Proxy) on public IP.
    logger.info(f"Connecting to Cloud SQL Instance: {instance_connection_name}")

    conn = _connector.connect(
        instance_connection_name,
        "pg8000",
        user=db_user,
        password=db_pass,
        db=db_name,
        ip_type=IPTypes.PUBLIC  # Explicitly set
    )
    return conn

def configure_database(app):
    """
    Configures the Flask app's database settings based on DB_BACKEND.
    """
    backend = os.getenv('DB_BACKEND', 'local').lower()
    
    if backend == 'local':
        logger.info("Using Local SQLite Database")
        basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        db_path = os.path.join(basedir, 'kitchen.db')
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
        
    elif backend == 'cloudsql':
        logger.info("Using Google Cloud SQL (Postgres)")
        
        # Validation
        required_vars = ["INSTANCE_CONNECTION_NAME", "DB_USER", "DB_NAME"]
        missing = [v for v in required_vars if not os.getenv(v)]
        if missing:
             raise ValueError(f"DB_BACKEND=cloudsql but missing env vars: {missing}")

        # For Cloud SQL with connector, we use the 'postgresql+pg8000://' driver
        # and pass the connection creator function via engine options.
        app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql+pg8000://"
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            "creator": get_db_connection
        }
    else:
        raise ValueError(f"Unknown DB_BACKEND: {backend}")
