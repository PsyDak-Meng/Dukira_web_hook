"""
API Endpoints Tests

Tests for all FastAPI endpoints including product retrieval, search,
synchronization triggers, and plugin integration endpoints.
"""

import pytest
from unittest.mock import patch, Mock
from app.models import ProductImage, ImageStatus


class TestProductEndpoints:
    """
    Tests for product-related API endpoints.
    
    These endpoints provide product data for frontend applications
    and plugin integrations.
    """
    
    def test_get_store_products(self, client, created_store, created_product):
        """
        Test retrieval of all products for a specific store.
        
        Should return paginated list of products with basic information
        for store management and overview purposes.
        """
        response = client.get(f"/products/store/{created_store.id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "store" in data
        assert "products" in data
        assert "total" in data
        assert data["store"]["id"] == created_store.id
        assert len(data["products"]) == 1
        assert data["products"][0]["id"] == created_product.id
        assert data["products"][0]["title"] == created_product.title
    
    def test_get_store_products_pagination(self, client, db_session, created_store):
        """
        Test product retrieval with pagination parameters.
        
        Large product catalogs should be properly paginated for
        efficient loading and better user experience.
        """
        from app.models import Product
        
        # Create multiple products for pagination testing
        products = []
        for i in range(15):
            product = Product(
                store_id=created_store.id,
                platform_product_id=f"product_{i}",
                title=f"Test Product {i}",
                published=True
            )
            products.append(product)
            db_session.add(product)
        
        db_session.commit()
        
        # Test first page
        response = client.get(
            f"/products/store/{created_store.id}",
            params={"skip": 0, "limit": 5}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["products"]) == 5
        assert data["skip"] == 0
        assert data["limit"] == 5
        
        # Test second page
        response = client.get(
            f"/products/store/{created_store.id}",
            params={"skip": 5, "limit": 5}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["products"]) == 5
    
    def test_get_store_products_nonexistent_store(self, client):
        """
        Test product retrieval for non-existent store.
        
        Should return 404 error when requesting products for a store
        that doesn't exist in the database.
        """
        response = client.get("/products/store/99999")
        
        assert response.status_code == 404
        assert "Store not found" in response.json()["detail"]
    
    def test_get_single_product(self, client, created_product, created_store):
        """
        Test retrieval of a single product with full details.
        
        Should return complete product information including variants,
        approved images, and store details for detailed product view.
        """
        response = client.get(f"/products/{created_product.id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "product" in data
        assert "approved_images" in data
        assert "store" in data
        
        product_data = data["product"]
        assert product_data["id"] == created_product.id
        assert product_data["title"] == created_product.title
        
        store_data = data["store"]
        assert store_data["id"] == created_store.id
    
    def test_get_single_product_nonexistent(self, client):
        """
        Test retrieval of non-existent product.
        
        Should return 404 error when requesting a product that
        doesn't exist in the database.
        """
        response = client.get("/products/99999")
        
        assert response.status_code == 404
        assert "Product not found" in response.json()["detail"]
    
    def test_get_product_images(self, client, db_session, created_product):
        """
        Test retrieval of approved images for a product.
        
        Should return only approved and stored images, excluding
        pending, processing, or rejected images.
        """
        # Create images in different states
        approved_image = ProductImage(
            product_id=created_product.id,
            platform_image_id="approved_123",
            src="https://example.com/approved.jpg",
            status=ImageStatus.STORED,
            position=1
        )
        
        rejected_image = ProductImage(
            product_id=created_product.id,
            platform_image_id="rejected_456",
            src="https://example.com/rejected.jpg",
            status=ImageStatus.REJECTED,
            position=2
        )
        
        db_session.add_all([approved_image, rejected_image])
        db_session.commit()
        
        response = client.get(f"/products/{created_product.id}/images")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "images" in data
        assert data["product_id"] == created_product.id
        assert len(data["images"]) == 1  # Only approved image
        assert data["images"][0]["platform_image_id"] == "approved_123"
    
    @patch('app.services.gcs_service.GCSService.get_image_url')
    def test_get_product_images_with_signed_urls(self, mock_get_url, client, db_session, created_product):
        """
        Test retrieval of product images with signed URLs.
        
        When requested, should include signed URLs for secure access
        to images stored in Google Cloud Storage.
        """
        # Mock GCS signed URL generation
        mock_get_url.return_value = "https://storage.googleapis.com/signed-url"
        
        # Create approved image with GCS path
        approved_image = ProductImage(
            product_id=created_product.id,
            platform_image_id="with_url_123",
            src="https://example.com/image.jpg",
            status=ImageStatus.STORED,
            gcs_path="products/1/images/123.jpg"
        )
        db_session.add(approved_image)
        db_session.commit()
        
        response = client.get(
            f"/products/{created_product.id}/images",
            params={"include_urls": "true"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify signed URL was generated
        mock_get_url.assert_called_once_with("products/1/images/123.jpg")
    
    def test_search_products(self, client, db_session, created_store):
        """
        Test product search functionality.
        
        Should return products matching search query in title,
        description, or vendor fields.
        """
        from app.models import Product
        
        # Create products with different content
        products_data = [
            ("Laptop Computer", "High-performance laptop", "TechCorp"),
            ("Gaming Mouse", "Precision gaming mouse", "GameGear"),
            ("Wireless Keyboard", "Bluetooth keyboard", "TechCorp"),
            ("Monitor Stand", "Adjustable monitor stand", "OfficeMax")
        ]
        
        for title, description, vendor in products_data:
            product = Product(
                store_id=created_store.id,
                platform_product_id=f"search_{title.replace(' ', '_').lower()}",
                title=title,
                description=description,
                vendor=vendor,
                published=True
            )
            db_session.add(product)
        
        db_session.commit()
        
        # Search by title
        response = client.get("/products/search", params={"q": "laptop"})
        assert response.status_code == 200
        data = response.json()
        assert len(data["products"]) == 1
        assert "Laptop" in data["products"][0]["title"]
        
        # Search by vendor
        response = client.get("/products/search", params={"q": "TechCorp"})
        assert response.status_code == 200
        data = response.json()
        assert len(data["products"]) == 2  # Laptop and Keyboard
        
        # Search by description
        response = client.get("/products/search", params={"q": "gaming"})
        assert response.status_code == 200
        data = response.json()
        assert len(data["products"]) == 1
        assert "Gaming Mouse" in data["products"][0]["title"]
    
    def test_search_products_with_store_filter(self, client, db_session, created_store, sample_woocommerce_store_data):
        """
        Test product search filtered by specific store.
        
        Search should only return products from the specified store
        when store_id filter is applied.
        """
        from app.models import Product
        from app.crud import store as store_crud
        
        # Create second store
        second_store = store_crud.create_store(db_session, sample_woocommerce_store_data)
        
        # Create products in both stores
        product1 = Product(
            store_id=created_store.id,
            platform_product_id="search_test_1",
            title="Test Product Store 1",
            published=True
        )
        
        product2 = Product(
            store_id=second_store.id,
            platform_product_id="search_test_2", 
            title="Test Product Store 2",
            published=True
        )
        
        db_session.add_all([product1, product2])
        db_session.commit()
        
        # Search without store filter (should find both)
        response = client.get("/products/search", params={"q": "Test Product"})
        assert response.status_code == 200
        assert len(response.json()["products"]) == 2
        
        # Search with store filter (should find only one)
        response = client.get(
            "/products/search",
            params={"q": "Test Product", "store_id": created_store.id}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["products"]) == 1
        assert data["products"][0]["store_id"] == created_store.id
    
    def test_search_products_validation(self, client):
        """
        Test search endpoint input validation.
        
        Should validate search query length and other parameters
        to prevent abuse and ensure good performance.
        """
        # Query too short
        response = client.get("/products/search", params={"q": "a"})
        assert response.status_code == 422  # Validation error
        
        # Missing query
        response = client.get("/products/search")
        assert response.status_code == 422


class TestUserProductEndpoints:
    """
    Tests for user-specific product endpoints.
    
    These endpoints aggregate products across all stores
    belonging to a specific user.
    """
    
    def test_get_user_products(self, client, db_session, created_store, created_product, sample_woocommerce_store_data):
        """
        Test retrieval of all products for a user across multiple stores.
        
        Should return products from all stores belonging to the user
        with store information included for context.
        """
        from app.models import Product
        from app.crud import store as store_crud
        
        # Create second store for same user
        sample_woocommerce_store_data["user_id"] = created_store.user_id
        second_store = store_crud.create_store(db_session, sample_woocommerce_store_data)
        
        # Create product in second store
        second_product = Product(
            store_id=second_store.id,
            platform_product_id="user_product_2",
            title="Product from Second Store",
            published=True
        )
        db_session.add(second_product)
        db_session.commit()
        
        response = client.get(f"/products/user/{created_store.user_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["user_id"] == created_store.user_id
        assert len(data["products"]) == 2
        assert data["stores"] == 2
        
        # Verify store info is included
        for product in data["products"]:
            assert "store_info" in product
            assert "id" in product["store_info"]
            assert "platform" in product["store_info"]
    
    def test_get_user_products_with_images(self, client, db_session, created_store, created_product):
        """
        Test user product retrieval with approved images included.
        
        When requested, should include approved images for each product
        to provide complete product information.
        """
        # Create approved image
        approved_image = ProductImage(
            product_id=created_product.id,
            platform_image_id="user_image_123",
            src="https://example.com/user_product.jpg",
            status=ImageStatus.STORED
        )
        db_session.add(approved_image)
        db_session.commit()
        
        response = client.get(
            f"/products/user/{created_store.user_id}",
            params={"include_images": "true"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["products"]) == 1
        product = data["products"][0]
        assert "approved_images" in product
        assert len(product["approved_images"]) == 1
    
    def test_get_user_products_no_stores(self, client):
        """
        Test user product retrieval when user has no connected stores.
        
        Should return empty product list gracefully without errors.
        """
        response = client.get("/products/user/nonexistent_user")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["user_id"] == "nonexistent_user"
        assert data["products"] == []
        assert data["total"] == 0


class TestProductDisplayEndpoint:
    """
    Tests for the product display endpoint optimized for plugin use.
    
    This endpoint provides product data specifically formatted
    for frontend plugins and widgets.
    """
    
    @patch('app.services.gcs_service.GCSService.get_image_url')
    def test_get_product_for_display(self, mock_get_url, client, db_session, created_product, created_store):
        """
        Test product display endpoint with complete product information.
        
        Should return product data optimized for display with signed URLs
        for images and formatted data structure.
        """
        # Mock signed URL generation
        mock_get_url.return_value = "https://storage.googleapis.com/signed-url"
        
        # Create approved image with GCS path
        approved_image = ProductImage(
            product_id=created_product.id,
            platform_image_id="display_123",
            src="https://example.com/display.jpg",
            status=ImageStatus.STORED,
            gcs_path="products/1/images/display.jpg",
            alt_text="Display image",
            position=1,
            width=800,
            height=600
        )
        db_session.add(approved_image)
        db_session.commit()
        
        response = client.get(f"/products/display/{created_product.id}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify product structure
        assert "product" in data
        assert "store" in data
        assert "images" in data
        assert "variants" in data
        
        product_data = data["product"]
        assert product_data["id"] == created_product.id
        assert product_data["title"] == created_product.title
        
        # Verify image URLs were generated
        assert len(data["images"]) == 1
        image = data["images"][0]
        assert image["url"] == "https://storage.googleapis.com/signed-url"
        assert image["alt_text"] == "Display image"
        assert image["width"] == 800
        assert image["height"] == 600
        
        mock_get_url.assert_called_once()
    
    def test_get_product_for_display_with_variant(self, client, db_session, created_product):
        """
        Test product display endpoint filtered by specific variant.
        
        When variant_id is specified, should filter images to show
        only those associated with the specific variant.
        """
        from app.models import ProductVariant
        
        # Create variant
        variant = ProductVariant(
            product_id=created_product.id,
            platform_variant_id="display_variant_123",
            title="Red Large",
            sku="PROD-RED-L"
        )
        db_session.add(variant)
        db_session.commit()
        db_session.refresh(variant)
        
        # Create variant-specific image
        variant_image = ProductImage(
            product_id=created_product.id,
            variant_id=variant.id,
            platform_image_id="variant_image_123",
            src="https://example.com/variant.jpg",
            status=ImageStatus.STORED,
            gcs_path="products/1/variants/1/images/variant.jpg"
        )
        
        # Create general product image
        general_image = ProductImage(
            product_id=created_product.id,
            variant_id=None,
            platform_image_id="general_image_123",
            src="https://example.com/general.jpg",
            status=ImageStatus.STORED,
            gcs_path="products/1/images/general.jpg"
        )
        
        db_session.add_all([variant_image, general_image])
        db_session.commit()
        
        # Mock GCS service
        with patch('app.services.gcs_service.GCSService.get_image_url') as mock_get_url:
            mock_get_url.return_value = "https://storage.googleapis.com/signed-url"
            
            response = client.get(
                f"/products/display/{created_product.id}",
                params={"variant_id": variant.id}
            )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should only show variant-specific image
        assert len(data["images"]) == 1
        assert "variant" in data
        assert data["variant"]["id"] == variant.id
    
    def test_get_product_for_display_nonexistent(self, client):
        """
        Test product display endpoint for non-existent product.
        
        Should return 404 error appropriately.
        """
        response = client.get("/products/display/99999")
        
        assert response.status_code == 404
        assert "Product not found" in response.json()["detail"]


class TestSyncEndpoints:
    """
    Tests for product synchronization trigger endpoints.
    
    These endpoints allow manual triggering of sync operations
    for stores and products.
    """
    
    @patch('app.routers.products.sync_store_task.delay')
    def test_trigger_store_sync(self, mock_delay, client, created_store):
        """
        Test manual triggering of store product synchronization.
        
        Should queue a background sync job and return confirmation
        with job details.
        """
        mock_delay.return_value = Mock(id="task_123")
        
        response = client.post(f"/products/sync/{created_store.id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "Sync job queued" in data["message"]
        assert data["store_id"] == created_store.id
        assert data["job_type"] == "full_sync"  # default
        
        # Verify Celery task was queued
        mock_delay.assert_called_once_with(created_store.id, "full_sync")
    
    @patch('app.routers.products.sync_store_task.delay')
    def test_trigger_incremental_sync(self, mock_delay, client, created_store):
        """
        Test triggering incremental sync with specific job type.
        
        Should support different sync types like incremental sync
        for faster updates.
        """
        response = client.post(
            f"/products/sync/{created_store.id}",
            params={"job_type": "incremental"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["job_type"] == "incremental"
        
        mock_delay.assert_called_once_with(created_store.id, "incremental")
    
    def test_trigger_sync_nonexistent_store(self, client):
        """
        Test sync trigger for non-existent store.
        
        Should return 404 error when trying to sync a store
        that doesn't exist.
        """
        response = client.post("/products/sync/99999")
        
        assert response.status_code == 404
        assert "Store not found" in response.json()["detail"]


class TestProductStatsEndpoint:
    """
    Tests for product and image statistics endpoints.
    
    These endpoints provide insights into store product status
    and image processing progress.
    """
    
    def test_get_store_product_stats(self, client, db_session, created_store, created_product):
        """
        Test retrieval of product and image statistics for a store.
        
        Should provide counts of products, variants, and images
        in different states for monitoring and dashboard purposes.
        """
        from app.models import Product, ProductVariant, ProductImage
        
        # Create additional products and variants
        for i in range(3):
            product = Product(
                store_id=created_store.id,
                platform_product_id=f"stats_product_{i}",
                title=f"Stats Product {i}",
                published=i < 2  # 2 published, 1 draft
            )
            db_session.add(product)
            db_session.commit()
            
            # Add variant
            variant = ProductVariant(
                product_id=product.id,
                platform_variant_id=f"stats_variant_{i}",
                title=f"Variant {i}"
            )
            db_session.add(variant)
            
            # Add images in different states
            for j, status in enumerate([ImageStatus.PENDING, ImageStatus.STORED, ImageStatus.REJECTED]):
                image = ProductImage(
                    product_id=product.id,
                    platform_image_id=f"stats_image_{i}_{j}",
                    src=f"https://example.com/stats_{i}_{j}.jpg",
                    status=status
                )
                db_session.add(image)
        
        db_session.commit()
        
        response = client.get(f"/products/stats/{created_store.id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["store_id"] == created_store.id
        assert data["store_name"] == created_store.store_name
        
        # Verify product counts (3 new + 1 existing)
        assert data["products"]["total"] == 4
        assert data["products"]["published"] == 3  # 2 new published + 1 existing
        assert data["products"]["draft"] == 1
        
        # Verify image counts
        assert data["images"]["pending"] == 3
        assert data["images"]["stored"] == 3
        assert data["images"]["rejected"] == 3
    
    def test_get_stats_nonexistent_store(self, client):
        """
        Test statistics retrieval for non-existent store.
        
        Should return 404 error appropriately.
        """
        response = client.get("/products/stats/99999")
        
        assert response.status_code == 404
        assert "Store not found" in response.json()["detail"]


class TestHealthAndInfoEndpoints:
    """
    Tests for application health and information endpoints.
    
    These endpoints provide system status and application metadata
    for monitoring and integration purposes.
    """
    
    def test_root_endpoint(self, client):
        """
        Test the root API endpoint.
        
        Should return basic application information and status.
        """
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["message"] == "Dukira Webhook API"
        assert data["version"] == "1.0.0"
        assert data["status"] == "operational"
    
    @patch('app.main.GCSService.health_check')
    def test_health_check_healthy(self, mock_gcs_health, client, db_session):
        """
        Test health check endpoint when all services are healthy.
        
        Should return healthy status when database and GCS are accessible.
        """
        mock_gcs_health.return_value = True
        
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        assert data["gcs"] == "connected"
    
    @patch('app.main.GCSService.health_check')
    def test_health_check_gcs_unavailable(self, mock_gcs_health, client, db_session):
        """
        Test health check when GCS is unavailable.
        
        Should still return healthy status if only GCS is unavailable
        since it's not critical for basic operations.
        """
        mock_gcs_health.return_value = False
        
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        assert data["gcs"] == "disconnected"
    
    def test_app_info_endpoint(self, client):
        """
        Test application information endpoint.
        
        Should return comprehensive application metadata including
        supported platforms, features, and endpoint information.
        """
        response = client.get("/info")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "app_name" in data
        assert "version" in data
        assert "supported_platforms" in data
        assert "features" in data
        assert "endpoints" in data
        
        # Verify supported platforms
        assert "shopify" in data["supported_platforms"]
        assert "woocommerce" in data["supported_platforms"]
        assert "wix" in data["supported_platforms"]
        
        # Verify features
        features = data["features"]
        assert features["oauth_authentication"] is True
        assert features["webhook_processing"] is True
        assert features["product_sync"] is True
        assert features["image_processing"] is True
        assert features["cloud_storage"] is True
        
        # Verify endpoints
        endpoints = data["endpoints"]
        assert endpoints["auth"] == "/auth"
        assert endpoints["webhooks"] == "/webhooks"
        assert endpoints["products"] == "/products"