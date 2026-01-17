import os
import logging
from google.cloud import storage
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def sync_recipes_to_gcs():
    """Uploads local recipe images to GCS if they don't exist."""
    
    bucket_name = os.getenv('GCS_BUCKET_NAME')
    if not bucket_name:
        logger.error("GCS_BUCKET_NAME not found in environment variables.")
        return

    logger.info(f"Connecting to GCS bucket: {bucket_name}")
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    local_recipes_dir = os.path.join(os.getcwd(), 'static', 'recipes')
    
    if not os.path.exists(local_recipes_dir):
        logger.error(f"Local recipes directory not found: {local_recipes_dir}")
        return

    files = [f for f in os.listdir(local_recipes_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    logger.info(f"Found {len(files)} image files in {local_recipes_dir}")

    uploaded_count = 0
    skipped_count = 0

    for filename in files:
        local_path = os.path.join(local_recipes_dir, filename)
        blob_path = f"recipes/{filename}"
        blob = bucket.blob(blob_path)

        if blob.exists():
            logger.info(f"Skipping {filename} (already exists in GCS)")
            skipped_count += 1
            continue

        logger.info(f"Uploading {filename}...")
        
        # Determine content type
        content_type = 'image/png' if filename.endswith('.png') else 'image/jpeg'
        
        try:
            blob.upload_from_filename(local_path, content_type=content_type)
            blob.cache_control = "public, max-age=31536000"
            blob.patch()
            uploaded_count += 1
        except Exception as e:
            logger.error(f"Failed to upload {filename}: {e}")

    logger.info(f"Sync Complete. Uploaded: {uploaded_count}, Skipped: {skipped_count}")

if __name__ == "__main__":
    sync_recipes_to_gcs()
