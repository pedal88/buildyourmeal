import os
import shutil
import logging
from abc import ABC, abstractmethod
from typing import Optional
from google.cloud import storage

# Configure Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StorageProvider(ABC):
    """Abstract Base Class for Storage Providers."""
    
    @abstractmethod
    def save(self, file_bytes: bytes, filename: str, folder: str) -> str:
        """Saves bytes to storage and returns a public/accessible URL."""
        pass

    @abstractmethod
    def delete(self, filename: str, folder: str) -> bool:
        """Deletes a file from storage."""
        pass

    @abstractmethod
    def exists(self, filename: str, folder: str) -> bool:
        """Checks if a file exists."""
        pass
    
    @abstractmethod
    def copy(self, source_path: str, dest_filename: str, dest_folder: str) -> str:
        """
        Copies a file from a local source path to the storage destination.
        Returns the new URL.
        """
        pass

    @abstractmethod
    def move(self, source_filename: str, source_folder: str, dest_filename: str, dest_folder: str) -> str:
        """
        Moves a file within storage from source to destination.
        Returns the new public URL.
        """
        pass

class LocalStorageProvider(StorageProvider):
    """
    Saves files to the local /static directory.
    Useful for development.
    """
    def __init__(self, root_path: str):
        self.root_path = root_path
        self.static_url_prefix = "/static"
        logger.info(f"LocalStorageProvider initialized. Root: {self.root_path}")

    def _get_full_path(self, folder: str, filename: str) -> str:
        # Folder is like "pantry/candidates" or "recipes"
        # We assume folder is relative to static/
        return os.path.join(self.root_path, 'static', folder, filename)

    def save(self, file_bytes: bytes, filename: str, folder: str) -> str:
        full_path = self._get_full_path(folder, filename)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        with open(full_path, 'wb') as f:
            f.write(file_bytes)
            
        return f"{self.static_url_prefix}/{folder}/{filename}"

    def delete(self, filename: str, folder: str) -> bool:
        full_path = self._get_full_path(folder, filename)
        if os.path.exists(full_path):
            os.remove(full_path)
            return True
        return False

    def exists(self, filename: str, folder: str) -> bool:
        return os.path.exists(self._get_full_path(folder, filename))

    def copy(self, source_path: str, dest_filename: str, dest_folder: str) -> str:
        full_dest_path = self._get_full_path(dest_folder, dest_filename)
        os.makedirs(os.path.dirname(full_dest_path), exist_ok=True)
        
        shutil.copy2(source_path, full_dest_path)
        return f"{self.static_url_prefix}/{dest_folder}/{dest_filename}"

    def move(self, source_filename: str, source_folder: str, dest_filename: str, dest_folder: str) -> str:
        full_source_path = self._get_full_path(source_folder, source_filename)
        full_dest_path = self._get_full_path(dest_folder, dest_filename)
        
        os.makedirs(os.path.dirname(full_dest_path), exist_ok=True)
        
        if os.path.exists(full_source_path):
            shutil.move(full_source_path, full_dest_path)
            return f"{self.static_url_prefix}/{dest_folder}/{dest_filename}"
        else:
            raise FileNotFoundError(f"Source file not found: {full_source_path}")


class GoogleCloudStorageProvider(StorageProvider):
    """
    Saves files to a Google Cloud Storage Bucket.
    Used for production.
    """
    def __init__(self, bucket_name: str):
        self.bucket_name = bucket_name
        logger.info(f"GoogleCloudStorageProvider initializing for bucket: {self.bucket_name}")
        
        # This will raise DefaultCredentialsError if creds are missing.
        # We want this to fail fast per requirements.
        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)

    def save(self, file_bytes: bytes, filename: str, folder: str) -> str:
        blob_path = f"{folder}/{filename}"
        blob = self.bucket.blob(blob_path)
        
        # Upload with Cache-Control
        blob.upload_from_string(
            file_bytes, 
            content_type=self._guess_content_type(filename)
        )
        blob.cache_control = "public, max-age=31536000"
        blob.patch()

        return blob.public_url

    def delete(self, filename: str, folder: str) -> bool:
        blob_path = f"{folder}/{filename}"
        blob = self.bucket.blob(blob_path)
        if blob.exists():
            blob.delete()
            return True
        return False

    def exists(self, filename: str, folder: str) -> bool:
        blob_path = f"{folder}/{filename}"
        return self.bucket.blob(blob_path).exists()

    def copy(self, source_path: str, dest_filename: str, dest_folder: str) -> str:
        # Upload local file to GCS
        with open(source_path, 'rb') as f:
            return self.save(f.read(), dest_filename, dest_folder)

    def move(self, source_filename: str, source_folder: str, dest_filename: str, dest_folder: str) -> str:
        source_blob_path = f"{source_folder}/{source_filename}"
        dest_blob_path = f"{dest_folder}/{dest_filename}"
        
        source_blob = self.bucket.blob(source_blob_path)
        
        if not source_blob.exists():
             raise FileNotFoundError(f"Source blob not found: {source_blob_path}")

        # Rename (Copy + Delete)
        # Note: rename returns the new blob
        new_blob = self.bucket.rename_blob(source_blob, dest_blob_path)
        
        return new_blob.public_url

    def _guess_content_type(self, filename: str) -> str:
        if filename.endswith('.png'): return 'image/png'
        if filename.endswith('.jpg') or filename.endswith('.jpeg'): return 'image/jpeg'
        if filename.endswith('.mp3'): return 'audio/mpeg'
        if filename.endswith('.json'): return 'application/json'
        # Default fallback
        return 'application/octet-stream'

def get_storage_provider(root_path: Optional[str] = None) -> StorageProvider:
    """Factory to get the configured storage provider."""
    backend = os.getenv('STORAGE_BACKEND', 'local').lower()
    
    logger.info(f"Initializing Storage Provider. Backend selected: {backend}")
    
    if backend == 'gcs':
        bucket_name = os.getenv('GCS_BUCKET_NAME')
        if not bucket_name:
            raise ValueError("STORAGE_BACKEND=gcs is set, but GCS_BUCKET_NAME is missing from environment.")
        
        # Fail Fast: Initialization will crash if credentials are invalid
        return GoogleCloudStorageProvider(bucket_name)
    
    elif backend == 'local':
        return LocalStorageProvider(root_path or os.getcwd())
    
    else:
        raise ValueError(f"Unknown storage backend: {backend}. Supported backends: 'local', 'gcs'")
