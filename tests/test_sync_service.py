"""
Product Sync Service Tests

Tests for the product synchronization service that fetches data from
e-commerce platforms. Covers full sync, incremental sync, data transformation,
and background job processing with Celery.
"""

import pytest
from unittest.mock import patch, AsyncMock, Mock
from datetime import datetime

from app.services.sync_service import SyncService, sync_store_task
from app.models import Store, Product, ProductVariant, ProductImage, SyncJob, SyncStatus, ImageStatus, PlatformType
from app.crud import store as store_crud, product as product_crud


class TestSyncService:
    """
    Tests for the core SyncService functionality.
    
    The SyncService handles fetching product data from e-commerce platforms
    and transforming it into our internal data structure.
    """
    
    @pytest.mark.asyncio
    async def test_sync_store_products_full_sync(self, db_session, created_store, mock_shopify_api):
        """
        Test full product synchronization for a store.
        
        A full sync should:
        - Create a sync job with proper tracking
        - Fetch all products from the platform
        - Transform and store product data
        - Update sync job status and timestamps
        - Update store's last sync time
        """
        sync_service = SyncService(db_session)
        
        # Mock platform client
        with patch('app.services.sync_service.get_platform_client') as mock_client:
            mock_client.return_value = mock_shopify_api
            
            # Mock product data from platform
            mock_shopify_api.get_products.return_value = [
                {
                    "id": "123456789",
                    "title": "Test Product 1",
                    "body_html": "Description 1",
                    "vendor": "Test Vendor",
                    "variants": [],
                    "images": []
                },
                {
                    "id": "987654321", 
                    "title": "Test Product 2",
                    "body_html": "Description 2",
                    "vendor": "Test Vendor",
                    "variants": [],
                    "images": []
                }
            ]
            
            # Execute sync
            sync_job = await sync_service.sync_store_products(created_store.id, "full_sync")
            
            # Verify sync job was created and completed
            assert sync_job.store_id == created_store.id
            assert sync_job.job_type == "full_sync"
            assert sync_job.status == SyncStatus.COMPLETED
            assert sync_job.processed_products == 2
            assert sync_job.failed_products == 0
            assert sync_job.started_at is not None
            assert sync_job.completed_at is not None
            
            # Verify products were created
            products = product_crud.get_products_by_store(db_session, created_store.id)
            assert len(products) == 2
            
            # Verify product data transformation
            product1 = next(p for p in products if p.platform_product_id == "123456789")
            assert product1.title == "Test Product 1"
            assert product1.description == "Description 1"
            assert product1.vendor == "Test Vendor"
            
            # Verify store last sync was updated
            db_session.refresh(created_store)
            assert created_store.last_sync is not None
    
    @pytest.mark.asyncio
    async def test_sync_with_product_count_tracking(self, db_session, created_store, mock_shopify_api):
        """
        Test sync progress tracking using product count.
        
        When the platform supports product count API, the sync should
        track progress by setting total_products on the sync job.
        """
        sync_service = SyncService(db_session)
        
        with patch('app.services.sync_service.get_platform_client') as mock_client:
            mock_client.return_value = mock_shopify_api
            mock_shopify_api.get_product_count.return_value = 5
            mock_shopify_api.get_products.return_value = []  # Empty for simplicity
            
            sync_job = await sync_service.sync_store_products(created_store.id)
            
            # Verify total product count was set
            assert sync_job.total_products == 5
    
    @pytest.mark.asyncio
    async def test_sync_single_product_new_product(self, db_session, created_store):
        """
        Test syncing a single new product.
        
        When a product doesn't exist in our database, it should be created
        with all its variants and images properly processed.
        """
        sync_service = SyncService(db_session)
        
        product_data = {
            "id": "new_product_123",
            "title": "New Product",
            "body_html": "New product description",
            "vendor": "New Vendor",
            "product_type": "New Type",
            "tags": "new, product",
            "handle": "new-product",
            "status": "active",
            "variants": [
                {
                    "id": "variant_123",
                    "title": "Default",
                    "sku": "NEW-SKU-001",
                    "price": "29.99",
                    "inventory_quantity": 50
                }
            ],
            "images": [
                {
                    "id": "image_123",
                    "src": "https://example.com/new-product.jpg",
                    "alt": "New product image",
                    "position": 1
                }
            ]
        }
        
        await sync_service._sync_single_product(created_store, product_data)
        
        # Verify product was created
        product = product_crud.get_product_by_platform_id(
            db_session, "new_product_123", created_store.id
        )
        assert product is not None
        assert product.title == "New Product"
        assert product.vendor == "New Vendor"
        assert product.tags == ["new", "product"]
        
        # Verify variant was created
        assert len(product.variants) == 1
        variant = product.variants[0]
        assert variant.platform_variant_id == "variant_123"
        assert variant.sku == "NEW-SKU-001"
        assert variant.price == "29.99"
        
        # Verify image was created and queued for processing
        assert len(product.images) == 1
        image = product.images[0]
        assert image.platform_image_id == "image_123"
        assert image.src == "https://example.com/new-product.jpg"
        assert image.status == ImageStatus.PENDING
    
    @pytest.mark.asyncio
    async def test_sync_single_product_update_existing(self, db_session, created_store, created_product):
        """
        Test syncing an existing product with updates.
        
        When a product already exists, the sync should update its data
        while preserving the internal database ID and relationships.
        """
        sync_service = SyncService(db_session)
        
        # Updated product data
        updated_product_data = {
            "id": created_product.platform_product_id,
            "title": "Updated Product Title",
            "body_html": "Updated description",
            "vendor": "Updated Vendor",
            "product_type": "Updated Type",
            "tags": "updated, product",
            "status": "active",
            "variants": [],
            "images": []
        }
        
        await sync_service._sync_single_product(created_store, updated_product_data)
        
        # Refresh product from database
        db_session.refresh(created_product)
        
        # Verify product was updated
        assert created_product.title == "Updated Product Title"
        assert created_product.description == "Updated description"
        assert created_product.vendor == "Updated Vendor"
        assert created_product.tags == ["updated", "product"]
        assert created_product.updated_at is not None
    
    @pytest.mark.asyncio
    async def test_sync_error_handling(self, db_session, created_store):
        """
        Test sync error handling and failure tracking.
        
        When sync operations fail, errors should be properly logged
        and the sync job should be marked as failed with error details.
        """
        sync_service = SyncService(db_session)
        
        with patch('app.services.sync_service.get_platform_client') as mock_client:
            # Make platform client raise an exception
            mock_client.side_effect = Exception("Platform API error")
            
            sync_job = await sync_service.sync_store_products(created_store.id)
            
            # Verify sync job was marked as failed
            assert sync_job.status == SyncStatus.FAILED
            assert sync_job.error_message == "Platform API error"
            assert sync_job.completed_at is not None
    
    def test_extract_shopify_product_data(self, db_session, created_store):
        """
        Test Shopify product data extraction and transformation.
        
        Verifies that raw Shopify API data is properly transformed
        into our internal product data structure.
        """
        sync_service = SyncService(db_session)
        
        shopify_data = {
            "id": "123456789",
            "title": "Shopify Product",
            "body_html": "<p>Rich HTML description</p>",
            "vendor": "Shopify Vendor",
            "product_type": "Shopify Type",
            "tags": "tag1, tag2, tag3",
            "handle": "shopify-product",
            "status": "active"
        }
        
        extracted = sync_service._extract_product_data(shopify_data, "shopify")
        
        assert extracted["platform_product_id"] == "123456789"
        assert extracted["title"] == "Shopify Product"
        assert extracted["description"] == "<p>Rich HTML description</p>"
        assert extracted["vendor"] == "Shopify Vendor"
        assert extracted["product_type"] == "Shopify Type"
        assert extracted["tags"] == ["tag1", "tag2", "tag3"]
        assert extracted["handle"] == "shopify-product"
        assert extracted["published"] is True
        assert extracted["platform_data"] == shopify_data
    
    def test_extract_woocommerce_product_data(self, db_session, created_store):
        """
        Test WooCommerce product data extraction and transformation.
        
        WooCommerce has a different API structure than Shopify,
        so data extraction must handle these differences.
        """
        sync_service = SyncService(db_session)
        
        woocommerce_data = {
            "id": 123,
            "name": "WooCommerce Product",
            "description": "WooCommerce description",
            "type": "simple",
            "tags": [
                {"name": "tag1"},
                {"name": "tag2"}
            ],
            "slug": "woocommerce-product",
            "status": "publish"
        }
        
        extracted = sync_service._extract_product_data(woocommerce_data, "woocommerce")
        
        assert extracted["platform_product_id"] == "123"
        assert extracted["title"] == "WooCommerce Product"
        assert extracted["description"] == "WooCommerce description"
        assert extracted["product_type"] == "simple"
        assert extracted["tags"] == ["tag1", "tag2"]
        assert extracted["handle"] == "woocommerce-product"
        assert extracted["published"] is True
    
    def test_extract_wix_product_data(self, db_session, created_store):
        """
        Test Wix product data extraction and transformation.
        
        Wix has its own unique API structure that requires
        specific data transformation logic.
        """
        sync_service = SyncService(db_session)
        
        wix_data = {
            "id": "wix_product_123",
            "name": "Wix Product",
            "description": "Wix product description",
            "productType": "physical"
        }
        
        extracted = sync_service._extract_product_data(wix_data, "wix")
        
        assert extracted["platform_product_id"] == "wix_product_123"
        assert extracted["title"] == "Wix Product"
        assert extracted["description"] == "Wix product description"
        assert extracted["product_type"] == "physical"
        assert extracted["published"] is True
    
    def test_extract_variant_data_shopify(self, db_session, created_store):
        """
        Test Shopify variant data extraction.
        
        Shopify variants contain pricing, inventory, and option data
        that needs to be properly extracted and stored.
        """
        sync_service = SyncService(db_session)
        
        shopify_variant = {
            "id": "variant_123",
            "title": "Medium / Blue",
            "sku": "SHIRT-M-BLUE",
            "barcode": "123456789012",
            "price": "25.99",
            "compare_at_price": "29.99",
            "inventory_quantity": 15,
            "weight": "0.2",
            "option1": "Medium",
            "option2": "Blue",
            "option3": None
        }
        
        extracted = sync_service._extract_variant_data(shopify_variant, "shopify")
        
        assert extracted["platform_variant_id"] == "variant_123"
        assert extracted["title"] == "Medium / Blue"
        assert extracted["sku"] == "SHIRT-M-BLUE"
        assert extracted["price"] == "25.99"
        assert extracted["compare_at_price"] == "29.99"
        assert extracted["inventory_quantity"] == 15
        assert extracted["option1"] == "Medium"
        assert extracted["option2"] == "Blue"
    
    def test_extract_image_data_shopify(self, db_session, created_store):
        """
        Test Shopify image data extraction.
        
        Shopify images include URL, alt text, position, and dimensions
        that need to be captured for our image processing pipeline.
        """
        sync_service = SyncService(db_session)
        
        shopify_image = {
            "id": "image_123",
            "src": "https://cdn.shopify.com/image.jpg",
            "alt": "Product image",
            "position": 1,
            "width": 800,
            "height": 600
        }
        
        extracted = sync_service._extract_image_data(shopify_image, "shopify")
        
        assert extracted["platform_image_id"] == "image_123"
        assert extracted["src"] == "https://cdn.shopify.com/image.jpg"
        assert extracted["alt_text"] == "Product image"
        assert extracted["position"] == 1
        assert extracted["width"] == 800
        assert extracted["height"] == 600
        assert extracted["status"] == ImageStatus.PENDING


class TestCeleryTasks:
    """
    Tests for Celery background tasks.
    
    These tasks handle heavy sync operations asynchronously
    to avoid blocking the main application.
    """
    
    @patch('app.services.sync_service.SyncService.sync_store_products')
    @patch('app.services.sync_service.SessionLocal')
    def test_sync_store_task(self, mock_session, mock_sync):
        """
        Test the Celery task for store synchronization.
        
        Verifies that the Celery task properly:
        - Creates a database session
        - Initializes the sync service
        - Executes the sync operation
        - Handles cleanup properly
        """
        # Mock database session
        mock_db = Mock()
        mock_session.return_value = mock_db
        
        # Mock sync result
        mock_sync_job = Mock()
        mock_sync_job.id = 123
        mock_sync.return_value = mock_sync_job
        
        # Execute task
        result = sync_store_task(1, "full_sync")
        
        # Verify task execution
        assert result == 123
        mock_sync.assert_called_once_with(1, "full_sync")
        mock_db.close.assert_called_once()
    
    @patch('app.services.sync_service.store_crud.get_stores_for_auto_sync')
    @patch('app.services.sync_service.sync_store_task.delay')
    @patch('app.services.sync_service.SessionLocal')
    def test_auto_sync_all_stores_task(self, mock_session, mock_delay, mock_get_stores):
        """
        Test the automatic sync task for all stores.
        
        This task runs periodically to sync all stores that have
        auto-sync enabled, ensuring data stays up to date.
        """
        from app.services.sync_service import auto_sync_all_stores
        
        # Mock stores with auto-sync enabled
        mock_stores = [
            Mock(id=1, auto_sync=True),
            Mock(id=2, auto_sync=True),
            Mock(id=3, auto_sync=True)
        ]
        mock_get_stores.return_value = mock_stores
        
        mock_db = Mock()
        mock_session.return_value = mock_db
        
        # Execute task
        auto_sync_all_stores()
        
        # Verify all stores were queued for sync
        assert mock_delay.call_count == 3
        calls = mock_delay.call_args_list
        assert calls[0][0] == (1, "incremental")
        assert calls[1][0] == (2, "incremental")
        assert calls[2][0] == (3, "incremental")


class TestIncrementalSync:
    """
    Tests for incremental synchronization functionality.
    
    Incremental syncs only fetch products that have been updated
    since the last sync, improving efficiency for large stores.
    """
    
    @pytest.mark.asyncio
    async def test_incremental_sync_with_since_parameter(self, db_session, created_store, mock_shopify_api):
        """
        Test incremental sync using 'since_id' parameter.
        
        Incremental syncs should only fetch products that were created
        or updated after a specific product ID (pagination cursor).
        """
        sync_service = SyncService(db_session)
        
        with patch('app.services.sync_service.get_platform_client') as mock_client:
            mock_client.return_value = mock_shopify_api
            
            # Mock incremental product fetch
            mock_shopify_api.get_products.side_effect = [
                # First batch
                [{"id": "100", "title": "Product 100", "variants": [], "images": []}],
                # Second batch (empty - end of pagination)
                []
            ]
            
            sync_job = await sync_service.sync_store_products(created_store.id, "incremental")
            
            # Verify incremental sync completed
            assert sync_job.job_type == "incremental"
            assert sync_job.status == SyncStatus.COMPLETED
            assert sync_job.processed_products == 1
            
            # Verify pagination was used
            calls = mock_shopify_api.get_products.call_args_list
            assert len(calls) == 2
            # Second call should use since_id from first batch
            assert calls[1][1]["since_id"] == "100"


class TestSyncJobTracking:
    """
    Tests for sync job progress tracking and monitoring.
    
    Sync jobs provide visibility into long-running sync operations
    and help with debugging sync issues.
    """
    
    @pytest.mark.asyncio
    async def test_sync_job_progress_tracking(self, db_session, created_store, mock_shopify_api):
        """
        Test that sync jobs properly track progress during execution.
        
        Progress tracking helps monitor large sync operations and
        provides feedback to users about sync status.
        """
        sync_service = SyncService(db_session)
        
        with patch('app.services.sync_service.get_platform_client') as mock_client:
            mock_client.return_value = mock_shopify_api
            
            # Mock multiple batches of products
            products_batch_1 = [
                {"id": f"product_{i}", "title": f"Product {i}", "variants": [], "images": []}
                for i in range(1, 6)  # 5 products
            ]
            products_batch_2 = [
                {"id": f"product_{i}", "title": f"Product {i}", "variants": [], "images": []}
                for i in range(6, 11)  # 5 more products
            ]
            
            mock_shopify_api.get_products.side_effect = [
                products_batch_1,
                products_batch_2,
                []  # End pagination
            ]
            
            sync_job = await sync_service.sync_store_products(created_store.id)
            
            # Verify final progress tracking
            assert sync_job.processed_products == 10
            assert sync_job.failed_products == 0
    
    @pytest.mark.asyncio
    async def test_sync_job_partial_failure_tracking(self, db_session, created_store, mock_shopify_api):
        """
        Test sync job tracking when some products fail to sync.
        
        Even when individual products fail, the sync should continue
        and track both successful and failed product counts.
        """
        sync_service = SyncService(db_session)
        
        with patch('app.services.sync_service.get_platform_client') as mock_client:
            mock_client.return_value = mock_shopify_api
            
            # Mock products where some will fail to sync
            mock_products = [
                {"id": "valid_product", "title": "Valid Product", "variants": [], "images": []},
                {"id": "invalid_product"},  # Missing required fields
                {"id": "another_valid", "title": "Another Valid", "variants": [], "images": []}
            ]
            mock_shopify_api.get_products.return_value = mock_products
            
            # Patch _sync_single_product to fail for invalid product
            original_sync = sync_service._sync_single_product
            async def mock_sync_single_product(store, product_data):
                if product_data.get("id") == "invalid_product":
                    raise Exception("Invalid product data")
                return await original_sync(store, product_data)
            
            with patch.object(sync_service, '_sync_single_product', side_effect=mock_sync_single_product):
                sync_job = await sync_service.sync_store_products(created_store.id)
            
            # Verify partial failure tracking
            assert sync_job.status == SyncStatus.COMPLETED  # Still completes despite failures
            assert sync_job.processed_products == 2  # 2 successful
            assert sync_job.failed_products == 1    # 1 failed