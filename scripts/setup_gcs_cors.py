import os
import sys
from google.cloud import storage

def configure_cors(bucket_name):
    """
    Configures CORS for the specified GCS bucket to allow access from web frontends.
    """
    print(f"--- Configuring CORS for bucket: {bucket_name} ---")

    # Check for credentials (as per user context)
    creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if not creds_path:
        print("WARNING: GOOGLE_APPLICATION_CREDENTIALS environment variable is not set.")
        print("The script will attempt to use default credentials, but this may fail if not authenticated.")
    else:
        print(f"Using credentials from: {creds_path}")

    try:
        # Initialize Client
        storage_client = storage.Client()
        
        # Get Bucket
        try:
            bucket = storage_client.get_bucket(bucket_name)
        except Exception as e:
            print(f"Error accessing bucket '{bucket_name}': {e}")
            print("Make sure the bucket exists and you have permissions.")
            sys.exit(1)

        # Define CORS Policy
        # Origins: ["*"] (Allow all for now)
        # Methods: ["GET", "HEAD", "OPTIONS"]
        # Response Headers: ["Content-Type", "Access-Control-Allow-Origin"]
        # Max Age: 3600
        cors_configuration = [
            {
                "origin": ["*"],
                "method": ["GET", "HEAD", "OPTIONS"],
                "responseHeader": ["Content-Type", "Access-Control-Allow-Origin"],
                "maxAgeSeconds": 3600
            }
        ]

        print("Applying CORS policy...")
        bucket.cors = cors_configuration
        bucket.patch()

        print("Successfully updated CORS configuration.")
        
        # Verification
        print("\n--- Current CORS Configuration ---")
        bucket.reload() # Refresh metadata
        for cors_entry in bucket.cors:
            print(cors_entry)
            
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Target Bucket Name
    TARGET_BUCKET_NAME = "buildyourmeal-assets"
    configure_cors(TARGET_BUCKET_NAME)
