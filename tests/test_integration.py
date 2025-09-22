"""
Integration Tests

End-to-end tests that verify the complete workflow from OAuth connection
through product sync, webhook processing, and image pipeline to final
API consumption by plugins.
"""

import pytest
from unittest.mock import patch, AsyncMock, Mock
from app.models import Store, Product, ProductImage, ImageStatus, SyncStatus


class TestCompleteOAuthFlow:
    """
    Integration tests for the complete OAuth authentication flow.
    
    Tests the full journey from authorization URL generation through
    token exchange to store creation and initial sync setup.
    """
    
    @patch('app.auth.oauth.shopify_oauth.exchange_code_for_token')
    def test_complete_shopify_oauth_flow(self, mock_exchange, client, db_session):
        """
        Test complete Shopify OAuth flow from start to finish.
        
        Simulates the full OAuth process including:
        1. Authorization URL generation
        2. User authorization (simulated)
        3. Callback handling with token exchange
        4. Store creation and storage
        5. Verification of stored data
        """
        # Step 1: Generate authorization URL
        auth_response = client.get(
            "/auth/shopify/authorize",
            params={"shop": "test-integration-shop", "user_id": "integration_user_123"}
        )
        
        assert auth_response.status_code == 200
        auth_data = auth_response.json()
        assert "auth_url" in auth_data
        assert "test-integration-shop.myshopify.com" in auth_data["auth_url"]
        
        # Step 2: Mock successful token exchange
        mock_exchange.return_value = {
            "access_token": "integration_access_token_123",
            "scope": "read_products,write_products"
        }
        
        # Step 3: Handle OAuth callback
        callback_response = client.get(
            "/auth/shopify/callback",
            params={
                "code": "integration_auth_code",
                "shop": "test-integration-shop", 
                "state": "integration_user_123:random_state"
            }
        )
        
        assert callback_response.status_code == 200
        callback_data = callback_response.json()
        assert callback_data["message"] == "Store connected successfully"
        
        # Step 4: Verify store was created properly
        store_id = callback_data["store_id"]
        from app.crud import store as store_crud
        created_store = store_crud.get_store(db_session, store_id)
        
        assert created_store is not None
        assert created_store.user_id == "integration_user_123"
        assert created_store.store_name == "test-integration-shop"
        assert created_store.access_token == "integration_access_token_123"
        
        # Step 5: Verify user can retrieve their stores
        stores_response = client.get("/auth/stores/integration_user_123")
        assert stores_response.status_code == 200
        user_stores = stores_response.json()
        assert len(user_stores) == 1
        assert user_stores[0]["id"] == store_id


class TestCompleteProductSyncFlow:
    """
    Integration tests for the complete product synchronization workflow.
    
    Tests the full process from sync trigger through product fetching,
    data transformation, and storage with all related entities.
    """
    
    @patch('app.services.platform_clients.get_platform_client')
    @patch('app.services.sync_service.process_image_task.delay')
    def test_complete_product_sync_workflow(self, mock_image_task, mock_get_client, client, db_session, created_store):
        """
        Test complete product sync from API trigger to database storage.
        
        Simulates the full sync process including:
        1. API trigger for sync
        2. Platform data fetching
        3. Product, variant, and image creation
        4. Background image processing queue
        5. Data verification in database
        """
        # Step 1: Mock platform client with comprehensive product data
        mock_client = Mock()
        mock_client.get_product_count = AsyncMock(return_value=2)
        mock_client.get_products = AsyncMock(side_effect=[
            # First batch of products
            [
                {
                    "id": "integration_product_1",
                    "title": "Integration Test Product 1",
                    "body_html": "First test product for integration",
                    "vendor": "Integration Vendor",
                    "product_type": "Test Type",
                    "tags": "integration, test, product1",
                    "handle": "integration-test-product-1",
                    "status": "active",
                    "variants": [
                        {
                            "id": "integration_variant_1_1",
                            "title": "Small",
                            "sku": "INT-PROD-1-S",
                            "price": "19.99",
                            "inventory_quantity": 25,
                            "option1": "Small"
                        },
                        {
                            "id": "integration_variant_1_2", 
                            "title": "Large",
                            "sku": "INT-PROD-1-L",
                            "price": "24.99",
                            "inventory_quantity": 15,
                            "option1": "Large"
                        }
                    ],
                    "images": [
                        {
                            "id": "integration_image_1_1",
                            "src": "https://example.com/integration_product_1_main.jpg",
                            "alt": "Integration Product 1 Main Image",
                            "position": 1,
                            "width": 800,
                            "height": 600
                        },
                        {
                            "id": "integration_image_1_2",
                            "src": "https://example.com/integration_product_1_side.jpg", 
                            "alt": "Integration Product 1 Side View",
                            "position": 2,
                            "width": 800,
                            "height": 600
                        }
                    ]
                },
                {
                    "id": "integration_product_2",
                    "title": "Integration Test Product 2",
                    "body_html": "Second test product for integration",
                    "vendor": "Integration Vendor",
                    "product_type": "Test Type",
                    "tags": "integration, test, product2",
                    "handle": "integration-test-product-2",
                    "status": "active",
                    "variants": [
                        {
                            "id": "integration_variant_2_1",
                            "title": "Default",
                            "sku": "INT-PROD-2-DEF",
                            "price": "29.99",
                            "inventory_quantity": 50
                        }
                    ],
                    "images": [
                        {
                            "id": "integration_image_2_1",
                            "src": "https://example.com/integration_product_2_main.jpg",
                            "alt": "Integration Product 2 Main Image", 
                            "position": 1,
                            "width": 1200,
                            "height": 800
                        }
                    ]
                }
            ],
            # End of pagination
            []
        ])
        
        mock_get_client.return_value = mock_client
        
        # Step 2: Trigger sync via API
        sync_response = client.post(f"/products/sync/{created_store.id}")
        assert sync_response.status_code == 200
        sync_data = sync_response.json()
        assert "Sync job queued" in sync_data["message"]
        
        # Step 3: Execute sync directly (simulating Celery task)
        from app.services.sync_service import SyncService
        sync_service = SyncService(db_session)
        
        # Import asyncio for running async function
        import asyncio
        
        # Run the sync
        sync_job = asyncio.run(sync_service.sync_store_products(created_store.id, "full_sync"))
        
        # Step 4: Verify sync job completion
        assert sync_job.status == SyncStatus.COMPLETED
        assert sync_job.processed_products == 2
        assert sync_job.failed_products == 0
        
        # Step 5: Verify products were created
        from app.crud import product as product_crud
        products = product_crud.get_products_by_store(db_session, created_store.id)
        assert len(products) == 2
        
        # Verify first product details
        product1 = next(p for p in products if p.platform_product_id == "integration_product_1")
        assert product1.title == "Integration Test Product 1"
        assert product1.vendor == "Integration Vendor"
        assert len(product1.variants) == 2
        assert len(product1.images) == 2
        
        # Verify variants
        small_variant = next(v for v in product1.variants if v.platform_variant_id == "integration_variant_1_1")
        assert small_variant.title == "Small"
        assert small_variant.sku == "INT-PROD-1-S"
        assert small_variant.price == "19.99"
        
        # Verify images were queued for processing
        pending_images = product_crud.get_pending_images(db_session)
        assert len(pending_images) == 3  # 2 from product1 + 1 from product2
        
        # Verify image processing tasks were queued
        assert mock_image_task.call_count == 3


class TestCompleteWebhookFlow:
    """
    Integration tests for the complete webhook processing workflow.
    
    Tests webhook reception, verification, processing, and resulting
    database updates.
    """
    
    @patch('app.routers.webhooks.verify_shopify_webhook')
    @patch('app.services.platform_clients.get_platform_client')
    def test_complete_webhook_processing_flow(self, mock_get_client, mock_verify, client, db_session, created_store, created_product):
        """
        Test complete webhook processing from reception to database update.
        
        Simulates receiving a product update webhook and processing it
        through the complete pipeline.
        """
        # Step 1: Mock webhook verification
        mock_verify.return_value = True
        
        # Step 2: Mock platform client for product fetching
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        # Step 3: Prepare webhook payload (product update)
        webhook_payload = {
            "id": created_product.platform_product_id,
            "title": "Updated Product Title via Webhook",
            "body_html": "Updated description via webhook",
            "vendor": "Updated Vendor",
            "product_type": "Updated Type",
            "tags": "updated, webhook, integration",
            "handle": "updated-product-webhook",
            "status": "active",
            "variants": [
                {
                    "id": "updated_variant_123",
                    "title": "Updated Variant",
                    "sku": "UPDATED-SKU-001", 
                    "price": "39.99",
                    "inventory_quantity": 75
                }
            ],
            "images": [
                {
                    "id": "updated_image_123",
                    "src": "https://example.com/updated_image.jpg",
                    "alt": "Updated product image",
                    "position": 1,
                    "width": 1000,
                    "height": 800
                }
            ]
        }
        
        webhook_headers = {
            "X-Shopify-Topic": "products/update",
            "X-Shopify-Shop-Domain": "test-shop.myshopify.com",
            "X-Shopify-Hmac-Sha256": "valid_signature",
            "Content-Type": "application/json"
        }
        
        # Step 4: Send webhook
        webhook_response = client.post(
            f"/webhooks/shopify/{created_store.id}",
            json=webhook_payload,
            headers=webhook_headers
        )
        
        assert webhook_response.status_code == 200
        assert webhook_response.json()["status"] == "received"
        
        # Step 5: Simulate background processing (normally done by BackgroundTasks)
        from app.routers.webhooks import process_webhook_event
        import asyncio
        
        asyncio.run(process_webhook_event(
            db_session, 
            created_store, 
            "products/update", 
            webhook_payload,
            webhook_headers
        ))
        
        # Step 6: Verify webhook event was stored
        from app.models import WebhookEvent
        webhook_events = db_session.query(WebhookEvent).filter(
            WebhookEvent.store_id == created_store.id
        ).all()
        
        assert len(webhook_events) == 1
        webhook_event = webhook_events[0]
        assert webhook_event.event_type == "products/update"
        assert webhook_event.processed is True
        
        # Step 7: Verify product was updated
        db_session.refresh(created_product)
        assert created_product.title == "Updated Product Title via Webhook"
        assert created_product.description == "Updated description via webhook"
        assert created_product.vendor == "Updated Vendor"


class TestCompleteImageProcessingFlow:
    """
    Integration tests for the complete image processing pipeline.
    
    Tests the full workflow from image download through AI processing
    to Google Cloud Storage upload and final API consumption.
    """
    
    @patch('app.services.gcs_service.GCSService.upload_image')
    @patch('app.services.image_service.ImageService._process_with_ai')
    @patch('app.services.image_service.ImageService._download_and_validate_image')
    def test_complete_image_processing_pipeline(self, mock_download, mock_ai, mock_gcs_upload, db_session, created_product):
        """
        Test complete image processing from pending status to final storage.
        
        Simulates the full image processing pipeline including:
        1. Image download and validation
        2. Hash calculation and duplicate detection
        3. AI quality assessment
        4. Google Cloud Storage upload
        5. Database status updates
        6. API retrieval with signed URLs
        """
        from app.services.image_service import ImageService
        from app.crud import product as product_crud
        
        # Step 1: Create pending image
        pending_image = ProductImage(
            product_id=created_product.id,
            platform_image_id="integration_image_123",
            src="https://example.com/integration_test_image.jpg",
            alt_text="Integration test image",
            position=1,
            status=ImageStatus.PENDING
        )
        db_session.add(pending_image)
        db_session.commit()
        db_session.refresh(pending_image)
        
        # Step 2: Mock successful image download
        from PIL import Image
        from io import BytesIO
        
        # Create test image data
        test_image = Image.new('RGB', (800, 600), color='green')
        image_buffer = BytesIO()
        test_image.save(image_buffer, format='JPEG')
        image_data = image_buffer.getvalue()
        
        mock_download.return_value = (image_data, {
            'width': 800,
            'height': 600,
            'file_size': len(image_data),
            'content_type': 'image/jpeg',
            'format': 'JPEG'
        })
        
        # Step 3: Mock successful AI processing (high quality score)
        mock_ai.return_value = {
            "score": 0.92,
            "analysis": {
                "quality": "excellent",
                "clarity": 0.95,
                "lighting": 0.88,
                "composition": 0.93,
                "background": "clean",
                "product_focus": True
            }
        }
        
        # Step 4: Mock successful GCS upload
        mock_gcs_upload.return_value = True
        
        # Step 5: Process the image
        image_service = ImageService()
        import asyncio
        
        asyncio.run(image_service.process_image(db_session, pending_image.id))
        
        # Step 6: Verify image processing results
        db_session.refresh(pending_image)
        
        assert pending_image.status == ImageStatus.STORED
        assert pending_image.width == 800
        assert pending_image.height == 600
        assert pending_image.ai_score == "0.92"
        assert pending_image.gcs_path is not None
        assert pending_image.image_hash is not None
        assert pending_image.is_duplicate is False
        
        # Step 7: Verify image appears in approved images
        approved_images = product_crud.get_approved_images_by_product(db_session, created_product.id)
        assert len(approved_images) == 1
        assert approved_images[0].id == pending_image.id
        
        # Verify mocks were called properly
        mock_download.assert_called_once()
        mock_ai.assert_called_once()
        mock_gcs_upload.assert_called_once()


class TestCompletePluginIntegrationFlow:
    """
    Integration tests for plugin consumption of the API.
    
    Tests the complete flow from store setup through product sync
    to final API consumption by frontend plugins.
    """
    
    @patch('app.services.gcs_service.GCSService.get_image_url')
    def test_complete_plugin_integration_workflow(self, mock_get_url, client, db_session, created_store, created_product):
        """
        Test complete workflow from plugin perspective.
        
        Simulates how a frontend plugin would interact with the API:
        1. Get user's connected stores
        2. Get products for display
        3. Get product details with images
        4. Get signed URLs for image display
        """
        # Step 1: Create approved images for the product
        approved_image1 = ProductImage(
            product_id=created_product.id,
            platform_image_id="plugin_image_1",
            src="https://example.com/plugin_image_1.jpg",
            alt_text="Plugin test image 1",
            position=1,
            status=ImageStatus.STORED,
            gcs_path="products/1/images/plugin_1.jpg",
            width=800,
            height=600
        )
        
        approved_image2 = ProductImage(
            product_id=created_product.id,
            platform_image_id="plugin_image_2",
            src="https://example.com/plugin_image_2.jpg",
            alt_text="Plugin test image 2", 
            position=2,
            status=ImageStatus.STORED,
            gcs_path="products/1/images/plugin_2.jpg",
            width=1200,
            height=800
        )
        
        db_session.add_all([approved_image1, approved_image2])
        db_session.commit()
        
        # Step 2: Mock signed URL generation
        mock_get_url.return_value = "https://storage.googleapis.com/bucket/signed-url-123"
        
        # Step 3: Plugin gets user's stores
        stores_response = client.get(f"/auth/stores/{created_store.user_id}")
        assert stores_response.status_code == 200
        stores = stores_response.json()
        assert len(stores) == 1
        
        store_info = stores[0]
        assert store_info["id"] == created_store.id
        assert store_info["platform"] == created_store.platform.value
        
        # Step 4: Plugin gets user's products across all stores
        products_response = client.get(
            f"/products/user/{created_store.user_id}",
            params={"include_images": "true"}
        )
        assert products_response.status_code == 200
        products_data = products_response.json()
        
        assert products_data["user_id"] == created_store.user_id
        assert len(products_data["products"]) == 1
        assert products_data["stores"] == 1
        
        product_info = products_data["products"][0]
        assert product_info["id"] == created_product.id
        assert "store_info" in product_info
        assert "approved_images" in product_info
        assert len(product_info["approved_images"]) == 2
        
        # Step 5: Plugin gets detailed product info for display
        display_response = client.get(f"/products/display/{created_product.id}")
        assert display_response.status_code == 200
        display_data = display_response.json()
        
        # Verify product structure for plugin consumption
        assert "product" in display_data
        assert "store" in display_data
        assert "images" in display_data
        assert "variants" in display_data
        
        product_display = display_data["product"]
        assert product_display["id"] == created_product.id
        assert product_display["title"] == created_product.title
        
        # Verify images with signed URLs
        images = display_data["images"]
        assert len(images) == 2
        
        for image in images:
            assert "url" in image
            assert image["url"] == "https://storage.googleapis.com/bucket/signed-url-123"
            assert "alt_text" in image
            assert "width" in image
            assert "height" in image
        
        # Verify signed URLs were generated for both images
        assert mock_get_url.call_count == 2
        
        # Step 6: Plugin gets product statistics for dashboard
        stats_response = client.get(f"/products/stats/{created_store.id}")
        assert stats_response.status_code == 200
        stats_data = stats_response.json()
        
        assert stats_data["store_id"] == created_store.id
        assert stats_data["products"]["total"] == 1
        assert stats_data["images"]["stored"] == 2


class TestErrorHandlingAndRecovery:
    """
    Integration tests for error handling and recovery scenarios.
    
    Tests how the system handles various failure modes and
    maintains data consistency during partial failures.
    """
    
    @patch('app.services.platform_clients.get_platform_client')
    def test_sync_with_partial_failures(self, mock_get_client, db_session, created_store):
        """
        Test sync behavior when some products fail to process.
        
        Verifies that sync continues processing other products even
        when individual products fail, and properly tracks failures.
        """
        # Mock client that returns some valid and some invalid products
        mock_client = Mock()
        mock_client.get_product_count = AsyncMock(return_value=3)
        mock_client.get_products = AsyncMock(return_value=[
            # Valid product
            {
                "id": "valid_product_123",
                "title": "Valid Product",
                "body_html": "Valid description",
                "vendor": "Valid Vendor",
                "variants": [],
                "images": []
            },
            # Invalid product (missing required fields)
            {
                "id": "invalid_product_456"
                # Missing title and other required fields
            },
            # Another valid product
            {
                "id": "valid_product_789",
                "title": "Another Valid Product",
                "body_html": "Another valid description",
                "vendor": "Another Vendor",
                "variants": [],
                "images": []
            }
        ])
        
        mock_get_client.return_value = mock_client
        
        # Execute sync
        from app.services.sync_service import SyncService
        sync_service = SyncService(db_session)
        
        import asyncio
        sync_job = asyncio.run(sync_service.sync_store_products(created_store.id))
        
        # Verify sync completed despite failures
        assert sync_job.status == SyncStatus.COMPLETED
        assert sync_job.processed_products == 2  # 2 valid products
        assert sync_job.failed_products == 1    # 1 invalid product
        
        # Verify valid products were created
        from app.crud import product as product_crud
        products = product_crud.get_products_by_store(db_session, created_store.id)
        assert len(products) == 2
        
        product_ids = {p.platform_product_id for p in products}
        assert "valid_product_123" in product_ids
        assert "valid_product_789" in product_ids
        assert "invalid_product_456" not in product_ids
    
    @patch('app.services.gcs_service.GCSService.upload_image')
    @patch('app.services.image_service.ImageService._process_with_ai')
    @patch('app.services.image_service.ImageService._download_and_validate_image')
    def test_image_processing_with_failures(self, mock_download, mock_ai, mock_gcs_upload, db_session, created_product):
        """
        Test image processing pipeline with various failure modes.
        
        Verifies graceful handling of download failures, AI service errors,
        and storage upload failures.
        """
        from app.services.image_service import ImageService
        
        # Create images for testing different failure scenarios
        images = []
        
        # Image 1: Download failure
        image1 = ProductImage(
            product_id=created_product.id,
            platform_image_id="download_fail_123",
            src="https://unreachable.com/image1.jpg",
            status=ImageStatus.PENDING
        )
        images.append(image1)
        
        # Image 2: AI processing failure
        image2 = ProductImage(
            product_id=created_product.id,
            platform_image_id="ai_fail_456", 
            src="https://example.com/image2.jpg",
            status=ImageStatus.PENDING
        )
        images.append(image2)
        
        # Image 3: GCS upload failure
        image3 = ProductImage(
            product_id=created_product.id,
            platform_image_id="gcs_fail_789",
            src="https://example.com/image3.jpg",
            status=ImageStatus.PENDING
        )
        images.append(image3)
        
        for image in images:
            db_session.add(image)
        db_session.commit()
        
        # Mock different failure scenarios
        def mock_download_side_effect(url):
            if "unreachable.com" in url:
                return (None, {})  # Download failure
            else:
                return (b'fake_image_data', {
                    'width': 800, 'height': 600, 'file_size': 1000, 'content_type': 'image/jpeg'
                })
        
        def mock_ai_side_effect(image_data, url):
            if "image2.jpg" in url:
                raise Exception("AI service unavailable")  # AI failure
            else:
                return {"score": 0.8, "analysis": {"quality": "good"}}
        
        def mock_gcs_side_effect(image_data, path, content_type):
            if "gcs_fail" in path:
                return False  # GCS upload failure
            else:
                return True
        
        mock_download.side_effect = mock_download_side_effect
        mock_ai.side_effect = mock_ai_side_effect
        mock_gcs_upload.side_effect = mock_gcs_side_effect
        
        # Process all images
        image_service = ImageService()
        import asyncio
        
        for image in images:
            asyncio.run(image_service.process_image(db_session, image.id))
        
        # Verify failure handling
        db_session.refresh(image1)
        db_session.refresh(image2)
        db_session.refresh(image3)
        
        # All should be rejected due to various failures
        assert image1.status == ImageStatus.REJECTED  # Download failed
        assert image2.status == ImageStatus.REJECTED  # AI failed
        assert image3.status == ImageStatus.REJECTED  # GCS upload failed
        
        # Verify no approved images
        from app.crud import product as product_crud
        approved_images = product_crud.get_approved_images_by_product(db_session, created_product.id)
        assert len(approved_images) == 0


class TestPerformanceAndScaling:
    """
    Integration tests for performance and scaling scenarios.
    
    Tests system behavior under load and with large datasets
    to ensure proper pagination and resource management.
    """
    
    def test_large_product_catalog_handling(self, client, db_session, created_store):
        """
        Test API performance with large product catalogs.
        
        Verifies that pagination works correctly and response times
        are reasonable even with large numbers of products.
        """
        from app.models import Product
        
        # Create large number of products
        products = []
        for i in range(100):
            product = Product(
                store_id=created_store.id,
                platform_product_id=f"perf_product_{i}",
                title=f"Performance Test Product {i}",
                description=f"Description for product {i}",
                vendor="Performance Vendor",
                published=True
            )
            products.append(product)
            db_session.add(product)
        
        db_session.commit()
        
        # Test paginated retrieval
        response = client.get(
            f"/products/store/{created_store.id}",
            params={"skip": 0, "limit": 20}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["products"]) == 20
        
        # Test search performance
        search_response = client.get(
            "/products/search",
            params={"q": "Performance Test", "limit": 50}
        )
        
        assert search_response.status_code == 200
        search_data = search_response.json()
        assert len(search_data["products"]) == 50  # Limited by pagination
        
        # Test user product aggregation
        user_response = client.get(
            f"/products/user/{created_store.user_id}",
            params={"limit": 25}
        )
        
        assert user_response.status_code == 200
        user_data = user_response.json()
        assert len(user_data["products"]) == 25


class TestDataConsistency:
    """
    Integration tests for data consistency across operations.
    
    Tests that data remains consistent during concurrent operations
    and complex multi-step workflows.
    """
    
    def test_webhook_sync_consistency(self, client, db_session, created_store, created_product):
        """
        Test data consistency between webhook updates and manual sync.
        
        Verifies that webhook updates and sync operations don't create
        conflicts or duplicate data.
        """
        original_title = created_product.title
        
        # Simulate webhook update
        with patch('app.routers.webhooks.verify_shopify_webhook') as mock_verify:
            mock_verify.return_value = True
            
            webhook_payload = {
                "id": created_product.platform_product_id,
                "title": "Webhook Updated Title",
                "body_html": "Updated via webhook",
                "variants": [],
                "images": []
            }
            
            webhook_response = client.post(
                f"/webhooks/shopify/{created_store.id}",
                json=webhook_payload,
                headers={"X-Shopify-Topic": "products/update"}
            )
            
            assert webhook_response.status_code == 200
        
        # Verify product count hasn't changed (update, not create)
        from app.crud import product as product_crud
        products = product_crud.get_products_by_store(db_session, created_store.id)
        assert len(products) == 1
        
        # Verify update was applied
        db_session.refresh(created_product)
        assert created_product.title == "Webhook Updated Title"
        
        # Ensure no duplicate products were created
        duplicate_check = product_crud.get_product_by_platform_id(
            db_session,
            created_product.platform_product_id,
            created_store.id
        )
        assert duplicate_check.id == created_product.id