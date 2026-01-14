import os
import google.auth
from dotenv import load_dotenv

# Load .env (as app.py does)
load_dotenv()

print(f"GOOGLE_APPLICATION_CREDENTIALS via env: {os.getenv('GOOGLE_APPLICATION_CREDENTIALS')}")
print(f"GOOGLE_CLOUD_PROJECT via env: {os.getenv('GOOGLE_CLOUD_PROJECT')}")

try:
    credentials, project = google.auth.default()
    print(f"Loaded Credentials Type: {type(credentials)}")
    print(f"Loaded Project: {project}")
    
    if hasattr(credentials, 'service_account_email'):
         print(f"Service Account Email: {credentials.service_account_email}")
    elif hasattr(credentials, 'signer_email'):
         print(f"Signer Email: {credentials.signer_email}")
    else:
         print("User Credentials (likely ADC)")
         
    # Check if scopes allow SQL Admin
    # (Note: ADC usually has broad scopes, but let's see)
    
except Exception as e:
    print(f"Error loading defaults: {e}")
