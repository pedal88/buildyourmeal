import sys
import os
import logging
from google.cloud import storage

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from database.models import Ingredient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def sync_images():
    """
    Iterates through local static/pantry images, uploads them to GCS,
    and updates the database records with the new GCS URLs.
    """
    
    # Check Environment
    bucket_name = os.getenv('GCS_BUCKET_NAME')
    if not bucket_name:
        logger.error("GCS_BUCKET_NAME environment variable not set.")
        return

    # Initialize GCS Client
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
    except Exception as e:
        logger.error(f"Failed to initialize GCS client: {e}")
        return

    # Local Pantry Directory
    local_pantry_dir = os.path.join(app.root_path, 'static', 'pantry')
    if not os.path.exists(local_pantry_dir):
        logger.error(f"Local pantry directory not found: {local_pantry_dir}")
        return

    logger.info(f"Scanning {local_pantry_dir} for images...")

    with app.app_context():
        # Get all ingredients to match files against
        ingredients = db.session.execute(db.select(Ingredient)).scalars().all()
        ing_map = {ing.food_id: ing for ing in ingredients}
        
        count_uploaded = 0
        count_updated = 0

        for filename in os.listdir(local_pantry_dir):
            if not filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                continue

            file_path = os.path.join(local_pantry_dir, filename)
            
            # Destination path in GCS
            blob_path = f"pantry/{filename}"
            blob = bucket.blob(blob_path)

            try:
                # 1. Upload File
                if not blob.exists():
                    logger.info(f"Uploading {filename} to gs://{bucket_name}/{blob_path}...")
                    blob.upload_from_filename(file_path)
                    blob.cache_control = "public, max-age=31536000"
                    blob.patch()
                    count_uploaded += 1
                else:
                    logger.info(f"Skipping {filename} (already exists in GCS)")

                # 2. Update Database
                # Determine which ingredient this belongs to.
                # Filename format: "{food_id}.png" or "{food_id}_{uuid}.png"
                # We try to extract the food_id prefix.
                parts = filename.split('_')
                food_id_candidate = parts[0].split('.')[0] # handle "000123.png" case too
                
                # If filename is like "000123.png", parts=['000123.png'], split leads to '000123'
                # If filename is "000123_uuid.png", parts=['000123', 'uuid.png'], first is '000123'
                
                ing = ing_map.get(food_id_candidate)
                if ing:
                    # New Public URL
                    public_url = blob.public_url
                    
                    # Update if different
                    if ing.image_url != public_url:
                        logger.info(f"Updating DB for {ing.name} ({ing.food_id}): {ing.image_url} -> {public_url}")
                        ing.image_url = public_url
                        count_updated += 1
                else:
                    logger.warning(f"Could not find ingredient for file: {filename} (Extracted ID: {food_id_candidate})")

            except Exception as e:
                logger.error(f"Error processing {filename}: {e}")

        # Commit changes
        if count_updated > 0:
            logger.info(f"Committing {count_updated} database updates...")
            db.session.commit()
        else:
            logger.info("No database updates needed.")

    logger.info(f"Sync Complete. Uploaded: {count_uploaded}. Updated DB: {count_updated}.")

if __name__ == "__main__":
    sync_images()
