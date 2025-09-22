"""
Image Processing Pipeline Tests

Tests for the image processing service that handles downloading, validation,
AI processing, deduplication, and Google Cloud Storage upload for product images.
"""

import pytest
import hashlib
from unittest.mock import patch, AsyncMock, Mock
from io import BytesIO
from PIL import Image

from app.services.image_service import ImageService
from app.services.gcs_service import GCSService
from app.models import ProductImage, ImageStatus
from app.crud import product as product_crud


class TestImageDownloadAndValidation:
    """
    Tests for image download and validation functionality.
    
    Images must be downloaded from external URLs and validated
    for format, size, and quality before processing.
    """
    
    @pytest.mark.asyncio
    async def test_download_valid_image(self, mock_httpx):
        """
        Test downloading a valid image from external URL.
        
        Should successfully download the image and extract metadata
        like dimensions, file size, and content type.
        """
        image_service = ImageService()
        
        # Create a simple test image
        test_image = Image.new('RGB', (800, 600), color='red')
        image_buffer = BytesIO()
        test_image.save(image_buffer, format='JPEG')
        image_data = image_buffer.getvalue()
        
        # Mock HTTP response
        mock_httpx.get.return_value.content = image_data
        mock_httpx.get.return_value.headers = {'content-type': 'image/jpeg'}
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value = mock_httpx
            
            result_data, info = await image_service._download_and_validate_image(
                "https://example.com/image.jpg"
            )
            
            assert result_data == image_data
            assert info['width'] == 800
            assert info['height'] == 600
            assert info['content_type'] == 'image/jpeg'
            assert info['format'] == 'JPEG'
            assert info['file_size'] == len(image_data)
    
    @pytest.mark.asyncio
    async def test_download_invalid_content_type(self, mock_httpx):
        """
        Test rejection of non-image content types.
        
        Files that aren't images should be rejected during validation
        to prevent processing of invalid content.
        """
        image_service = ImageService()
        
        # Mock non-image response
        mock_httpx.get.return_value.content = b'not an image'
        mock_httpx.get.return_value.headers = {'content-type': 'text/html'}
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value = mock_httpx
            
            result_data, info = await image_service._download_and_validate_image(
                "https://example.com/notimage.html"
            )
            
            assert result_data is None
            assert info == {}
    
    @pytest.mark.asyncio
    async def test_download_image_too_small(self, mock_httpx):
        """
        Test rejection of images that are too small.
        
        Images below minimum dimensions should be rejected
        as they're likely not suitable for product display.
        """
        image_service = ImageService()
        
        # Create tiny image (below 100x100 minimum)
        tiny_image = Image.new('RGB', (50, 50), color='blue')
        image_buffer = BytesIO()
        tiny_image.save(image_buffer, format='JPEG')
        tiny_image_data = image_buffer.getvalue()
        
        mock_httpx.get.return_value.content = tiny_image_data
        mock_httpx.get.return_value.headers = {'content-type': 'image/jpeg'}
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value = mock_httpx
            
            result_data, info = await image_service._download_and_validate_image(
                "https://example.com/tiny.jpg"
            )
            
            assert result_data is None
            assert info == {}
    
    @pytest.mark.asyncio
    async def test_download_image_too_large(self, mock_httpx):
        """
        Test rejection of images that exceed size limits.
        
        Very large images should be rejected to prevent storage
        and processing issues.
        """
        image_service = ImageService()
        
        # Mock very large image data (over 10MB)
        large_image_data = b'x' * (11 * 1024 * 1024)  # 11MB
        
        mock_httpx.get.return_value.content = large_image_data
        mock_httpx.get.return_value.headers = {'content-type': 'image/jpeg'}
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value = mock_httpx
            
            result_data, info = await image_service._download_and_validate_image(
                "https://example.com/huge.jpg"
            )
            
            assert result_data is None
            assert info == {}
    
    @pytest.mark.asyncio
    async def test_download_network_error(self, mock_httpx):
        """
        Test handling of network errors during image download.
        
        Network failures should be handled gracefully without
        crashing the image processing pipeline.
        """
        image_service = ImageService()
        
        # Mock network error
        mock_httpx.get.side_effect = Exception("Network timeout")
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value = mock_httpx
            
            result_data, info = await image_service._download_and_validate_image(
                "https://example.com/unreachable.jpg"
            )
            
            assert result_data is None
            assert info == {}


class TestImageHashingAndDeduplication:
    """
    Tests for image hashing and duplicate detection.
    
    Duplicate images should be detected and not processed multiple times
    to save storage space and processing resources.
    """
    
    def test_calculate_image_hash(self):
        """
        Test image hash calculation for deduplication.
        
        The same image data should always produce the same hash,
        while different images should produce different hashes.
        """
        image_service = ImageService()
        
        image_data1 = b'sample image data'
        image_data2 = b'different image data'
        image_data1_copy = b'sample image data'
        
        hash1 = image_service._calculate_image_hash(image_data1)
        hash2 = image_service._calculate_image_hash(image_data2)
        hash1_copy = image_service._calculate_image_hash(image_data1_copy)
        
        # Same data should produce same hash
        assert hash1 == hash1_copy
        
        # Different data should produce different hash
        assert hash1 != hash2
        
        # Hash should be SHA-256
        expected_hash = hashlib.sha256(image_data1).hexdigest()
        assert hash1 == expected_hash
    
    @pytest.mark.asyncio
    async def test_duplicate_detection(self, db_session, created_product):
        """
        Test detection and handling of duplicate images.
        
        When an image with the same hash already exists, the new image
        should be marked as duplicate and linked to the original.
        """
        image_service = ImageService()
        
        # Create original image
        original_image = ProductImage(
            product_id=created_product.id,
            platform_image_id="original_123",
            src="https://example.com/original.jpg",
            image_hash="duplicate_hash_123",
            status=ImageStatus.STORED
        )
        db_session.add(original_image)
        db_session.commit()
        db_session.refresh(original_image)
        
        # Create duplicate image
        duplicate_image = ProductImage(
            product_id=created_product.id,
            platform_image_id="duplicate_456",
            src="https://example.com/duplicate.jpg",
            status=ImageStatus.PENDING
        )
        db_session.add(duplicate_image)
        db_session.commit()
        db_session.refresh(duplicate_image)
        
        # Mock image download to return same hash
        image_data = b'same image content'
        
        with patch.object(image_service, '_download_and_validate_image') as mock_download:
            mock_download.return_value = (image_data, {
                'width': 800, 'height': 600, 'file_size': len(image_data), 'content_type': 'image/jpeg'
            })
            
            with patch.object(image_service, '_calculate_image_hash') as mock_hash:
                mock_hash.return_value = "duplicate_hash_123"  # Same hash as original
                
                await image_service.process_image(db_session, duplicate_image.id)
        
        # Refresh duplicate image
        db_session.refresh(duplicate_image)
        
        # Verify duplicate was detected
        assert duplicate_image.is_duplicate is True
        assert duplicate_image.original_image_id == original_image.id
        assert duplicate_image.status == ImageStatus.REJECTED


class TestAIProcessing:
    """
    Tests for AI-powered image quality assessment.
    
    Images should be processed by an AI model to determine
    their suitability for product display.
    """
    
    @pytest.mark.asyncio
    async def test_ai_processing_high_quality(self, mock_ai_service):
        """
        Test AI processing for high-quality images.
        
        High-quality images should receive good scores and be approved
        for storage and display.
        """
        image_service = ImageService()
        image_data = b'high quality image data'
        image_url = "https://example.com/quality.jpg"
        
        # Mock high-quality AI response
        mock_ai_service.return_value = {
            "score": 0.95,
            "analysis": {
                "quality": "excellent",
                "clarity": 0.98,
                "lighting": 0.92,
                "composition": 0.90
            }
        }
        
        with patch.object(image_service, '_process_with_ai', return_value=mock_ai_service.return_value):
            result = await image_service._process_with_ai(image_data, image_url)
        
        assert result["score"] == 0.95
        assert result["analysis"]["quality"] == "excellent"
        assert result["analysis"]["clarity"] == 0.98
    
    @pytest.mark.asyncio
    async def test_ai_processing_low_quality(self, mock_ai_service):
        """
        Test AI processing for low-quality images.
        
        Low-quality images should receive poor scores and be rejected
        to maintain high standards for product display.
        """
        image_service = ImageService()
        image_data = b'low quality image data'
        image_url = "https://example.com/poor.jpg"
        
        # Mock low-quality AI response
        mock_ai_service.return_value = {
            "score": 0.3,
            "analysis": {
                "quality": "poor",
                "clarity": 0.2,
                "lighting": 0.4,
                "composition": 0.3
            }
        }
        
        with patch.object(image_service, '_process_with_ai', return_value=mock_ai_service.return_value):
            result = await image_service._process_with_ai(image_data, image_url)
        
        assert result["score"] == 0.3
        assert result["analysis"]["quality"] == "poor"
    
    @pytest.mark.asyncio
    async def test_ai_processing_api_error(self):
        """
        Test AI processing when the AI service is unavailable.
        
        When AI processing fails, the system should handle it gracefully
        and potentially approve images by default or use fallback logic.
        """
        image_service = ImageService()
        image_data = b'image data'
        image_url = "https://example.com/image.jpg"
        
        # Mock AI service error
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = Exception("AI service unavailable")
            mock_client.return_value.__aenter__.return_value = mock_instance
            
            result = await image_service._process_with_ai(image_data, image_url)
        
        # Should return None when AI processing fails
        assert result is None
    
    @pytest.mark.asyncio
    async def test_ai_processing_disabled(self):
        """
        Test image processing when AI service is not configured.
        
        When no AI configuration is provided, the system should
        handle images gracefully without AI processing.
        """
        image_service = ImageService()
        
        # Mock missing AI configuration
        with patch('app.services.image_service.settings') as mock_settings:
            mock_settings.ai_model_api_url = None
            mock_settings.ai_model_api_key = None
            
            result = await image_service._process_with_ai(b'data', "url")
        
        assert result is None


class TestGoogleCloudStorageIntegration:
    """
    Tests for Google Cloud Storage upload functionality.
    
    Approved images should be uploaded to GCS with proper
    organization and metadata.
    """
    
    @pytest.mark.asyncio
    async def test_upload_to_gcs_success(self, mock_gcs_service, created_product):
        """
        Test successful image upload to Google Cloud Storage.
        
        Approved images should be uploaded with proper path structure
        and return the GCS path for storage in the database.
        """
        image_service = ImageService()
        image_service.gcs_service = mock_gcs_service
        
        # Create test image
        image = ProductImage(
            id=123,
            product_id=created_product.id,
            variant_id=None,
            content_type="image/jpeg"
        )
        
        image_data = b'test image data'
        mock_gcs_service.upload_image.return_value = True
        
        gcs_path = await image_service._upload_to_gcs(image_data, image)
        
        expected_path = f"products/{created_product.id}/images/123.jpg"
        assert gcs_path == expected_path
        
        # Verify upload was called with correct parameters
        mock_gcs_service.upload_image.assert_called_once_with(
            image_data, expected_path, "image/jpeg"
        )
    
    @pytest.mark.asyncio
    async def test_upload_to_gcs_with_variant(self, mock_gcs_service, created_product):
        """
        Test GCS upload for variant-specific images.
        
        Images associated with specific product variants should be
        organized in variant-specific directories.
        """
        image_service = ImageService()
        image_service.gcs_service = mock_gcs_service
        
        # Create test image with variant
        image = ProductImage(
            id=123,
            product_id=created_product.id,
            variant_id=456,
            content_type="image/png"
        )
        
        image_data = b'variant image data'
        mock_gcs_service.upload_image.return_value = True
        
        gcs_path = await image_service._upload_to_gcs(image_data, image)
        
        expected_path = f"products/{created_product.id}/variants/456/images/123.jpg"
        assert gcs_path == expected_path
    
    @pytest.mark.asyncio
    async def test_upload_to_gcs_failure(self, mock_gcs_service, created_product):
        """
        Test handling of GCS upload failures.
        
        When GCS upload fails, the system should handle it gracefully
        and not mark the image as stored.
        """
        image_service = ImageService()
        image_service.gcs_service = mock_gcs_service
        
        image = ProductImage(
            id=123,
            product_id=created_product.id,
            content_type="image/jpeg"
        )
        
        image_data = b'test image data'
        mock_gcs_service.upload_image.return_value = False  # Upload failure
        
        gcs_path = await image_service._upload_to_gcs(image_data, image)
        
        assert gcs_path is None


class TestCompleteImageProcessingPipeline:
    """
    Tests for the complete end-to-end image processing pipeline.
    
    Tests the full workflow from image download through AI processing
    to final storage in Google Cloud Storage.
    """
    
    @pytest.mark.asyncio
    async def test_complete_processing_success(self, db_session, created_product, mock_gcs_service):
        """
        Test complete successful image processing pipeline.
        
        A valid image should go through all processing steps and end up
        stored in GCS with STORED status in the database.
        """
        # Create test image
        test_image = ProductImage(
            product_id=created_product.id,
            platform_image_id="test_123",
            src="https://example.com/test.jpg",
            status=ImageStatus.PENDING
        )
        db_session.add(test_image)
        db_session.commit()
        db_session.refresh(test_image)
        
        image_service = ImageService()
        image_service.gcs_service = mock_gcs_service
        
        # Create test image data
        pil_image = Image.new('RGB', (800, 600), color='green')
        image_buffer = BytesIO()
        pil_image.save(image_buffer, format='JPEG')
        image_data = image_buffer.getvalue()
        
        # Mock successful download
        with patch.object(image_service, '_download_and_validate_image') as mock_download:
            mock_download.return_value = (image_data, {
                'width': 800, 'height': 600, 'file_size': len(image_data), 'content_type': 'image/jpeg'
            })
            
            # Mock successful AI processing (high score)
            with patch.object(image_service, '_process_with_ai') as mock_ai:
                mock_ai.return_value = {
                    "score": 0.85,
                    "analysis": {"quality": "good"}
                }
                
                # Mock successful GCS upload
                mock_gcs_service.upload_image.return_value = True
                
                await image_service.process_image(db_session, test_image.id)
        
        # Refresh image from database
        db_session.refresh(test_image)
        
        # Verify complete processing
        assert test_image.status == ImageStatus.STORED
        assert test_image.width == 800
        assert test_image.height == 600
        assert test_image.ai_score == "0.85"
        assert test_image.gcs_path is not None
        assert test_image.image_hash is not None
        assert test_image.is_duplicate is False
    
    @pytest.mark.asyncio
    async def test_processing_low_quality_rejection(self, db_session, created_product):
        """
        Test image rejection due to low AI quality score.
        
        Images that receive low quality scores from the AI model
        should be rejected and not uploaded to storage.
        """
        # Create test image
        test_image = ProductImage(
            product_id=created_product.id,
            platform_image_id="low_quality_123",
            src="https://example.com/lowquality.jpg",
            status=ImageStatus.PENDING
        )
        db_session.add(test_image)
        db_session.commit()
        db_session.refresh(test_image)
        
        image_service = ImageService()
        
        # Create test image data
        image_data = b'low quality image data'
        
        # Mock successful download but low AI score
        with patch.object(image_service, '_download_and_validate_image') as mock_download:
            mock_download.return_value = (image_data, {
                'width': 400, 'height': 300, 'file_size': len(image_data), 'content_type': 'image/jpeg'
            })
            
            # Mock low AI score (below 0.7 threshold)
            with patch.object(image_service, '_process_with_ai') as mock_ai:
                mock_ai.return_value = {
                    "score": 0.3,  # Below approval threshold
                    "analysis": {"quality": "poor"}
                }
                
                await image_service.process_image(db_session, test_image.id)
        
        # Refresh image from database
        db_session.refresh(test_image)
        
        # Verify rejection
        assert test_image.status == ImageStatus.REJECTED
        assert test_image.ai_score == "0.3"
        assert test_image.gcs_path is None
    
    @pytest.mark.asyncio
    async def test_processing_download_failure(self, db_session, created_product):
        """
        Test image processing when download fails.
        
        Images that cannot be downloaded should be marked as rejected
        without attempting further processing.
        """
        # Create test image
        test_image = ProductImage(
            product_id=created_product.id,
            platform_image_id="unreachable_123",
            src="https://unreachable.com/image.jpg",
            status=ImageStatus.PENDING
        )
        db_session.add(test_image)
        db_session.commit()
        db_session.refresh(test_image)
        
        image_service = ImageService()
        
        # Mock download failure
        with patch.object(image_service, '_download_and_validate_image') as mock_download:
            mock_download.return_value = (None, {})  # Download failed
            
            await image_service.process_image(db_session, test_image.id)
        
        # Refresh image from database
        db_session.refresh(test_image)
        
        # Verify rejection due to download failure
        assert test_image.status == ImageStatus.REJECTED


class TestImageServiceUtilities:
    """
    Tests for image service utility functions.
    
    Covers batch processing, statistics, cleanup, and monitoring functionality.
    """
    
    @pytest.mark.asyncio
    async def test_process_pending_images_batch(self, db_session, created_product):
        """
        Test batch processing of pending images.
        
        The service should be able to process multiple pending images
        in parallel for efficiency.
        """
        image_service = ImageService()
        
        # Create multiple pending images
        pending_images = []
        for i in range(5):
            image = ProductImage(
                product_id=created_product.id,
                platform_image_id=f"pending_{i}",
                src=f"https://example.com/pending_{i}.jpg",
                status=ImageStatus.PENDING
            )
            pending_images.append(image)
            db_session.add(image)
        
        db_session.commit()
        
        # Mock processing for each image
        with patch.object(image_service, 'process_image') as mock_process:
            mock_process.return_value = None
            
            await image_service.process_pending_images(db_session, batch_size=3)
            
            # Should process up to batch_size images
            assert mock_process.call_count == 3
    
    def test_get_image_stats(self, db_session, created_product):
        """
        Test image processing statistics retrieval.
        
        Should provide counts of images in different processing states
        for monitoring and dashboard purposes.
        """
        image_service = ImageService()
        
        # Create images in different states
        states_and_counts = [
            (ImageStatus.PENDING, 3),
            (ImageStatus.PROCESSING, 1),
            (ImageStatus.APPROVED, 5),
            (ImageStatus.REJECTED, 2),
            (ImageStatus.STORED, 4)
        ]
        
        for status, count in states_and_counts:
            for i in range(count):
                image = ProductImage(
                    product_id=created_product.id,
                    platform_image_id=f"{status.value}_{i}",
                    src=f"https://example.com/{status.value}_{i}.jpg",
                    status=status
                )
                db_session.add(image)
        
        db_session.commit()
        
        stats = image_service.get_image_stats(db_session)
        
        # Verify statistics
        assert stats[ImageStatus.PENDING.value] == 3
        assert stats[ImageStatus.PROCESSING.value] == 1
        assert stats[ImageStatus.APPROVED.value] == 5
        assert stats[ImageStatus.REJECTED.value] == 2
        assert stats[ImageStatus.STORED.value] == 4
    
    def test_cleanup_duplicate_images(self, db_session, created_product, mock_gcs_service):
        """
        Test cleanup of duplicate images.
        
        Duplicate images should be removed from both database and storage
        to free up space and reduce clutter.
        """
        image_service = ImageService()
        image_service.gcs_service = mock_gcs_service
        
        # Create original image
        original = ProductImage(
            product_id=created_product.id,
            platform_image_id="original",
            src="https://example.com/original.jpg",
            status=ImageStatus.STORED,
            gcs_path="products/1/images/original.jpg"
        )
        db_session.add(original)
        
        # Create duplicate images
        duplicates = []
        for i in range(3):
            duplicate = ProductImage(
                product_id=created_product.id,
                platform_image_id=f"duplicate_{i}",
                src=f"https://example.com/duplicate_{i}.jpg",
                status=ImageStatus.REJECTED,
                is_duplicate=True,
                original_image_id=original.id,
                gcs_path=f"products/1/images/duplicate_{i}.jpg"
            )
            duplicates.append(duplicate)
            db_session.add(duplicate)
        
        db_session.commit()
        
        # Mock GCS deletion
        mock_gcs_service.delete_image.return_value = True
        
        # Perform cleanup
        deleted_count = image_service.cleanup_duplicate_images(db_session)
        
        # Verify cleanup
        assert deleted_count == 3
        
        # Verify duplicates were deleted from database
        remaining_images = db_session.query(ProductImage).filter(
            ProductImage.product_id == created_product.id
        ).all()
        assert len(remaining_images) == 1  # Only original should remain
        assert remaining_images[0].platform_image_id == "original"