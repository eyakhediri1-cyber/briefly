"""
GCS Service — Google Cloud Storage for file uploads.
Falls back to local filesystem when GCS is not configured.
"""

import logging
import os
import uuid
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


class GCSService:
    """Service to upload files to Google Cloud Storage or local disk fallback."""

    def __init__(self):
        self.bucket_name = settings.GCS_BUCKET_NAME
        self.project = settings.GOOGLE_CLOUD_PROJECT
        self.credentials_path = settings.GOOGLE_APPLICATION_CREDENTIALS
        self.client = None

        if self.bucket_name and settings.gcp_enabled:
            try:
                from google.cloud import storage
                if self.credentials_path and os.path.exists(self.credentials_path):
                    self.client = storage.Client.from_service_account_json(self.credentials_path)
                else:
                    self.client = storage.Client(project=self.project)
                logger.info("GCS client initialized successfully.")
            except Exception as e:
                logger.warning(f"Could not initialize GCS client: {e}. Falling back to local storage.")
        else:
            logger.info("GCS bucket or project not configured. Using local storage fallback.")

    async def upload_file(self, file_content: bytes, filename: str) -> str:
        """
        Upload file content to GCS or local filesystem as fallback.
        
        Returns the path or URI of the stored file.
        """
        unique_filename = f"{uuid.uuid4()}_{filename}"

        if self.client:
            try:
                bucket = self.client.bucket(self.bucket_name)
                blob = bucket.blob(unique_filename)
                blob.upload_from_string(file_content)
                logger.info(f"File {filename} uploaded to GCS bucket {self.bucket_name} as {unique_filename}")
                return f"gs://{self.bucket_name}/{unique_filename}"
            except Exception as e:
                logger.error(f"Failed to upload to GCS: {e}. Falling back to local filesystem.")

        # Local fallback
        local_dir = settings.upload_dir
        os.makedirs(local_dir, exist_ok=True)
        local_path = os.path.join(local_dir, unique_filename)
        
        with open(local_path, "wb") as f:
            f.write(file_content)
            
        logger.info(f"File {filename} stored locally at {local_path}")
        return local_path

    async def download_file(self, file_path: str) -> bytes:
        """Download file content from GCS or local filesystem."""
        if file_path.startswith("gs://") and self.client:
            try:
                path_parts = file_path[5:].split("/", 1)
                bucket_name = path_parts[0]
                blob_name = path_parts[1]
                bucket = self.client.bucket(bucket_name)
                blob = bucket.blob(blob_name)
                return blob.download_as_bytes()
            except Exception as e:
                logger.error(f"Failed to download from GCS: {e}")

        # Local fallback
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                return f.read()
        raise FileNotFoundError(f"File not found at {file_path}")


gcs_service = GCSService()
