import httpx
import hashlib
from PIL import Image
import io
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
import logging
import asyncio
from datetime import datetime

from ..models import ProductImage, ImageStatus
from ..crud import product as product_crud
from ..config import settings
from .gcs_service import GCSService
from .test_model import TestModel

logger = logging.getLogger(__name__)


class ImageService:
    def __init__(self):
        self.gcs_service = GCSService()
        self.test_model = TestModel() if settings.use_test_model else None
    
    async def process_image(self, db: Session, image_id: int):
        """Process a single image through the complete pipeline"""
        image = db.query(ProductImage).filter(ProductImage.id == image_id).first()
        if not image:
            logger.error(f"Image {image_id} not found")
            return
        
        try:
            # Update status to processing
            image.status = ImageStatus.PROCESSING
            db.commit()
            
            # Step 1: Download and validate image
            image_data, image_info = await self._download_and_validate_image(image.src)
            if not image_data:
                image.status = ImageStatus.REJECTED
                db.commit()
                return
            
            # Step 2: Calculate hash for deduplication
            image_hash = self._calculate_image_hash(image_data)
            image.image_hash = image_hash
            
            # Check for duplicates
            existing_image = product_crud.get_image_by_hash(db, image_hash)
            if existing_image and existing_image.id != image.id:
                image.is_duplicate = True
                image.original_image_id = existing_image.id
                image.status = ImageStatus.REJECTED
                db.commit()
                return
            
            # Step 3: Update image metadata
            image.width = image_info.get('width')
            image.height = image_info.get('height')
            image.file_size = image_info.get('file_size')
            image.content_type = image_info.get('content_type')
            db.commit()
            
            # Step 4: AI processing
            ai_result = await self._process_with_ai(image_data, image.src)
            if ai_result:
                image.ai_score = str(ai_result.get('score', 0))
                image.ai_analysis = ai_result.get('analysis', {})
                
                # Determine if image is approved based on AI score
                score = ai_result.get('score', 0)
                if score >= 0.7:  # Configurable threshold
                    image.status = ImageStatus.APPROVED
                else:
                    image.status = ImageStatus.REJECTED
                    db.commit()
                    return
            else:
                # If AI processing fails, approve by default (or configure differently)
                image.status = ImageStatus.APPROVED
            
            db.commit()
            
            # Step 5: Upload to Google Cloud Storage if approved
            if image.status == ImageStatus.APPROVED:
                gcs_path = await self._upload_to_gcs(image_data, image)
                if gcs_path:
                    image.gcs_path = gcs_path
                    image.status = ImageStatus.STORED
                    db.commit()
                else:
                    image.status = ImageStatus.REJECTED
                    db.commit()
        
        except Exception as e:
            logger.error(f"Failed to process image {image_id}: {str(e)}")
            image.status = ImageStatus.REJECTED
            db.commit()
    
    async def _download_and_validate_image(self, image_url: str) -> Tuple[Optional[bytes], Dict[str, Any]]:
        """Download image and extract basic information"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(image_url, timeout=30.0)
                response.raise_for_status()
                
                image_data = response.content
                content_type = response.headers.get('content-type', '')
                
                # Validate it's an image
                if not content_type.startswith('image/'):
                    logger.warning(f"Invalid content type: {content_type}")
                    return None, {}
                
                # Validate with PIL
                try:
                    image = Image.open(io.BytesIO(image_data))
                    width, height = image.size
                    
                    # Basic validation
                    if width < 100 or height < 100:
                        logger.warning(f"Image too small: {width}x{height}")
                        return None, {}
                    
                    if len(image_data) > 10 * 1024 * 1024:  # 10MB limit
                        logger.warning(f"Image too large: {len(image_data)} bytes")
                        return None, {}
                    
                    return image_data, {
                        'width': width,
                        'height': height,
                        'file_size': len(image_data),
                        'content_type': content_type,
                        'format': image.format
                    }
                
                except Exception as e:
                    logger.error(f"Invalid image data: {str(e)}")
                    return None, {}
        
        except Exception as e:
            logger.error(f"Failed to download image {image_url}: {str(e)}")
            return None, {}
    
    def _calculate_image_hash(self, image_data: bytes) -> str:
        """Calculate SHA-256 hash of image data for deduplication"""
        return hashlib.sha256(image_data).hexdigest()
    
    async def _process_with_ai(self, image_data: bytes, image_url: str) -> Optional[Dict[str, Any]]:
        """Process image with AI model for quality assessment"""
        # Use test model if configured
        if settings.use_test_model and self.test_model:
            logger.info("Using TestModel for image analysis")
            return await self.test_model.analyze_image(image_data, image_url)
        
        if not settings.ai_model_api_url or not settings.ai_model_api_key:
            logger.warning("AI model not configured, skipping AI processing")
            return None
        
        try:
            # Convert image to base64 for API call (common format)
            import base64
            image_b64 = base64.b64encode(image_data).decode('utf-8')
            
            # Prepare API request
            payload = {
                "image": image_b64,
                "url": image_url,
                "analysis_type": "product_image_quality"
            }
            
            headers = {
                "Authorization": f"Bearer {settings.ai_model_api_key}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    settings.ai_model_api_url,
                    json=payload,
                    headers=headers,
                    timeout=60.0
                )
                response.raise_for_status()
                
                result = response.json()
                
                # Expected response format:
                # {
                #   "score": 0.85,
                #   "analysis": {
                #     "quality": "high",
                #     "clarity": 0.9,
                #     "lighting": 0.8,
                #     "composition": 0.7,
                #     "background": "clean",
                #     "product_focus": true
                #   }
                # }
                
                return result
        
        except Exception as e:
            logger.error(f"AI processing failed: {str(e)}")
            return None
    
    async def _upload_to_gcs(self, image_data: bytes, image: ProductImage) -> Optional[str]:
        """Upload image to Google Cloud Storage"""
        try:
            # Generate GCS path: products/{product_id}/variants/{variant_id}/images/{image_id}.jpg
            if image.variant_id:
                gcs_path = f"products/{image.product_id}/variants/{image.variant_id}/images/{image.id}.jpg"
            else:
                gcs_path = f"products/{image.product_id}/images/{image.id}.jpg"
            
            success = await self.gcs_service.upload_image(image_data, gcs_path, image.content_type)
            
            if success:
                return gcs_path
            else:
                return None
        
        except Exception as e:
            logger.error(f"Failed to upload image to GCS: {str(e)}")
            return None
    
    async def process_pending_images(self, db: Session, batch_size: int = 10):
        """Process a batch of pending images"""
        pending_images = product_crud.get_pending_images(db, limit=batch_size)
        
        if not pending_images:
            return
        
        # Process images concurrently
        tasks = [
            self.process_image(db, image.id) 
            for image in pending_images
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    def get_image_stats(self, db: Session) -> Dict[str, int]:
        """Get image processing statistics"""
        from sqlalchemy import func
        
        stats = db.query(
            ProductImage.status,
            func.count(ProductImage.id).label('count')
        ).group_by(ProductImage.status).all()
        
        return {status.value: count for status, count in stats}
    
    async def reprocess_failed_images(self, db: Session, limit: int = 50):
        """Reprocess images that failed processing"""
        failed_images = db.query(ProductImage).filter(
            ProductImage.status == ImageStatus.REJECTED
        ).limit(limit).all()
        
        for image in failed_images:
            # Reset status and retry
            image.status = ImageStatus.PENDING
            db.commit()
            
            await self.process_image(db, image.id)
    
    def cleanup_duplicate_images(self, db: Session):
        """Clean up images marked as duplicates"""
        duplicate_images = db.query(ProductImage).filter(
            ProductImage.is_duplicate == True
        ).all()
        
        for image in duplicate_images:
            # Optionally delete GCS file if it exists
            if image.gcs_path:
                asyncio.create_task(self.gcs_service.delete_image(image.gcs_path))
            
            # Delete from database
            db.delete(image)
        
        db.commit()
        return len(duplicate_images)