from google.cloud import storage
from google.oauth2 import service_account
import asyncio
from typing import Optional, List
import logging
from io import BytesIO

from ..config import settings

logger = logging.getLogger(__name__)


class GCSService:
    def __init__(self):
        self.client = None
        self.bucket = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Google Cloud Storage client"""
        try:
            if settings.google_application_credentials:
                # Use service account credentials file
                credentials = service_account.Credentials.from_service_account_file(
                    settings.google_application_credentials
                )
                self.client = storage.Client(
                    credentials=credentials,
                    project=settings.google_cloud_project_id
                )
            else:
                # Use default credentials (environment-based)
                self.client = storage.Client(project=settings.google_cloud_project_id)
            
            self.bucket = self.client.bucket(settings.google_cloud_bucket_name)
            logger.info(f"GCS client initialized for bucket: {settings.google_cloud_bucket_name}")
        
        except Exception as e:
            logger.error(f"Failed to initialize GCS client: {str(e)}")
            self.client = None
            self.bucket = None
    
    async def upload_image(self, image_data: bytes, gcs_path: str, content_type: str = "image/jpeg") -> bool:
        """Upload image to Google Cloud Storage"""
        if not self.bucket:
            logger.error("GCS client not initialized")
            return False
        
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                None, 
                self._upload_blob, 
                image_data, 
                gcs_path, 
                content_type
            )
            return success
        
        except Exception as e:
            logger.error(f"Failed to upload image to GCS: {str(e)}")
            return False
    
    def _upload_blob(self, image_data: bytes, gcs_path: str, content_type: str) -> bool:
        """Upload blob to GCS (blocking operation)"""
        try:
            blob = self.bucket.blob(gcs_path)
            
            # Set metadata
            blob.content_type = content_type
            blob.cache_control = "public, max-age=31536000"  # 1 year cache
            
            # Upload data
            blob.upload_from_file(BytesIO(image_data), content_type=content_type)
            
            logger.info(f"Successfully uploaded image to gs://{settings.google_cloud_bucket_name}/{gcs_path}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to upload blob: {str(e)}")
            return False
    
    async def delete_image(self, gcs_path: str) -> bool:
        """Delete image from Google Cloud Storage"""
        if not self.bucket:
            logger.error("GCS client not initialized")
            return False
        
        try:
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                None, 
                self._delete_blob, 
                gcs_path
            )
            return success
        
        except Exception as e:
            logger.error(f"Failed to delete image from GCS: {str(e)}")
            return False
    
    def _delete_blob(self, gcs_path: str) -> bool:
        """Delete blob from GCS (blocking operation)"""
        try:
            blob = self.bucket.blob(gcs_path)
            blob.delete()
            
            logger.info(f"Successfully deleted image from gs://{settings.google_cloud_bucket_name}/{gcs_path}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to delete blob: {str(e)}")
            return False
    
    async def get_image_url(self, gcs_path: str, expiration_hours: int = 24) -> Optional[str]:
        """Generate signed URL for image access"""
        if not self.bucket:
            logger.error("GCS client not initialized")
            return None
        
        try:
            from datetime import timedelta
            
            loop = asyncio.get_event_loop()
            url = await loop.run_in_executor(
                None, 
                self._generate_signed_url, 
                gcs_path, 
                expiration_hours
            )
            return url
        
        except Exception as e:
            logger.error(f"Failed to generate signed URL: {str(e)}")
            return None
    
    def _generate_signed_url(self, gcs_path: str, expiration_hours: int) -> Optional[str]:
        """Generate signed URL (blocking operation)"""
        try:
            from datetime import timedelta
            
            blob = self.bucket.blob(gcs_path)
            
            # Generate signed URL
            url = blob.generate_signed_url(
                expiration=timedelta(hours=expiration_hours),
                method='GET'
            )
            
            return url
        
        except Exception as e:
            logger.error(f"Failed to generate signed URL: {str(e)}")
            return None
    
    async def get_public_url(self, gcs_path: str) -> str:
        """Get public URL for image (if bucket is public)"""
        return f"https://storage.googleapis.com/{settings.google_cloud_bucket_name}/{gcs_path}"
    
    async def list_images(self, prefix: str = "", limit: int = 100) -> List[str]:
        """List images in GCS bucket with optional prefix"""
        if not self.bucket:
            logger.error("GCS client not initialized")
            return []
        
        try:
            loop = asyncio.get_event_loop()
            image_paths = await loop.run_in_executor(
                None, 
                self._list_blobs, 
                prefix, 
                limit
            )
            return image_paths
        
        except Exception as e:
            logger.error(f"Failed to list images: {str(e)}")
            return []
    
    def _list_blobs(self, prefix: str, limit: int) -> List[str]:
        """List blobs (blocking operation)"""
        try:
            blobs = self.bucket.list_blobs(prefix=prefix, max_results=limit)
            return [blob.name for blob in blobs]
        
        except Exception as e:
            logger.error(f"Failed to list blobs: {str(e)}")
            return []
    
    async def get_image_metadata(self, gcs_path: str) -> Optional[dict]:
        """Get metadata for an image in GCS"""
        if not self.bucket:
            logger.error("GCS client not initialized")
            return None
        
        try:
            loop = asyncio.get_event_loop()
            metadata = await loop.run_in_executor(
                None, 
                self._get_blob_metadata, 
                gcs_path
            )
            return metadata
        
        except Exception as e:
            logger.error(f"Failed to get image metadata: {str(e)}")
            return None
    
    def _get_blob_metadata(self, gcs_path: str) -> Optional[dict]:
        """Get blob metadata (blocking operation)"""
        try:
            blob = self.bucket.blob(gcs_path)
            blob.reload()
            
            return {
                "name": blob.name,
                "size": blob.size,
                "content_type": blob.content_type,
                "created": blob.time_created,
                "updated": blob.updated,
                "etag": blob.etag,
                "md5_hash": blob.md5_hash,
                "public_url": blob.public_url
            }
        
        except Exception as e:
            logger.error(f"Failed to get blob metadata: {str(e)}")
            return None
    
    async def copy_image(self, source_gcs_path: str, destination_gcs_path: str) -> bool:
        """Copy image from one GCS path to another"""
        if not self.bucket:
            logger.error("GCS client not initialized")
            return False
        
        try:
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                None, 
                self._copy_blob, 
                source_gcs_path, 
                destination_gcs_path
            )
            return success
        
        except Exception as e:
            logger.error(f"Failed to copy image: {str(e)}")
            return False
    
    def _copy_blob(self, source_gcs_path: str, destination_gcs_path: str) -> bool:
        """Copy blob (blocking operation)"""
        try:
            source_blob = self.bucket.blob(source_gcs_path)
            destination_blob = self.bucket.blob(destination_gcs_path)
            
            # Copy the blob
            destination_blob.rewrite(source_blob)
            
            logger.info(f"Successfully copied image from {source_gcs_path} to {destination_gcs_path}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to copy blob: {str(e)}")
            return False
    
    def health_check(self) -> bool:
        """Check if GCS client is properly configured and accessible"""
        if not self.client or not self.bucket:
            return False
        
        try:
            # Try to access bucket
            self.bucket.reload()
            return True
        except Exception as e:
            logger.error(f"GCS health check failed: {str(e)}")
            return False