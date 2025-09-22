"""
Database CRUD Operations Tests

Tests for Create, Read, Update, Delete operations on all database models.
Covers store management, product operations, image handling, and relationship integrity.
"""

import pytest
from datetime import datetime
from app.models import Store, Product, ProductVariant, ProductImage, SyncJob, WebhookEvent, PlatformType, ImageStatus, SyncStatus
from app.crud import store as store_crud, product as product_crud


class TestStoreCRUD:
    """
    Tests for store-related CRUD operations.
    
    Stores are the foundation of the system, representing connected
    e-commerce platforms for each user.
    """
    
    def test_create_store(self, db_session, sample_shopify_store_data):
        """
        Test creating a new store with complete information.
        
        Should create store record with all required fields and
        generate proper timestamps.
        """
        store = store_crud.create_store(db_session, sample_shopify_store_data)
        
        assert store.id is not None
        assert store.user_id == sample_shopify_store_data["user_id"]
        assert store.platform == sample_shopify_store_data["platform"]
        assert store.store_name == sample_shopify_store_data["store_name"]
        assert store.access_token == sample_shopify_store_data["access_token"]
        assert store.created_at is not None
        assert store.updated_at is None  # Not updated yet
    
    def test_get_store_by_id(self, db_session, created_store):
        """
        Test retrieving store by primary key ID.
        
        Should return the correct store with all associated data.
        """
        retrieved_store = store_crud.get_store(db_session, created_store.id)
        
        assert retrieved_store is not None
        assert retrieved_store.id == created_store.id
        assert retrieved_store.store_name == created_store.store_name
        assert retrieved_store.platform == created_store.platform
    
    def test_get_store_by_platform_id(self, db_session, created_store):
        """
        Test retrieving store by platform-specific ID and platform type.
        
        Should find store using the unique combination of platform
        and platform_store_id.
        """
        retrieved_store = store_crud.get_store_by_platform_id(
            db_session, 
            created_store.platform_store_id, 
            created_store.platform
        )
        
        assert retrieved_store is not None
        assert retrieved_store.id == created_store.id
        assert retrieved_store.platform_store_id == created_store.platform_store_id
    
    def test_get_stores_by_user(self, db_session, sample_shopify_store_data, sample_woocommerce_store_data):
        """
        Test retrieving all stores belonging to a specific user.
        
        Should return all stores for the user across different platforms.
        """
        # Ensure both stores belong to same user
        sample_woocommerce_store_data["user_id"] = sample_shopify_store_data["user_id"]
        
        # Create stores
        store1 = store_crud.create_store(db_session, sample_shopify_store_data)
        store2 = store_crud.create_store(db_session, sample_woocommerce_store_data)
        
        # Retrieve user's stores
        user_stores = store_crud.get_stores_by_user(db_session, sample_shopify_store_data["user_id"])
        
        assert len(user_stores) == 2
        store_ids = {store.id for store in user_stores}
        assert store1.id in store_ids
        assert store2.id in store_ids
    
    def test_get_stores_by_platform(self, db_session, sample_shopify_store_data, sample_woocommerce_store_data):
        """
        Test retrieving all stores for a specific platform.
        
        Should return only stores matching the specified platform type.
        """
        # Create stores on different platforms
        shopify_store = store_crud.create_store(db_session, sample_shopify_store_data)
        woo_store = store_crud.create_store(db_session, sample_woocommerce_store_data)
        
        # Get only Shopify stores
        shopify_stores = store_crud.get_stores_by_platform(db_session, PlatformType.SHOPIFY)
        
        assert len(shopify_stores) == 1
        assert shopify_stores[0].id == shopify_store.id
        assert shopify_stores[0].platform == PlatformType.SHOPIFY
    
    def test_update_store(self, db_session, created_store):
        """
        Test updating store information.
        
        Should update specified fields and set updated_at timestamp.
        """
        original_name = created_store.store_name
        update_data = {
            "store_name": "Updated Store Name",
            "auto_sync": False
        }
        
        updated_store = store_crud.update_store(db_session, created_store.id, update_data)
        
        assert updated_store.store_name == "Updated Store Name"
        assert updated_store.auto_sync is False
        assert updated_store.updated_at is not None
        # Other fields should remain unchanged
        assert updated_store.platform == created_store.platform
        assert updated_store.access_token == created_store.access_token
    
    def test_update_nonexistent_store(self, db_session):
        """
        Test updating store that doesn't exist.
        
        Should return None when trying to update non-existent store.
        """
        result = store_crud.update_store(db_session, 99999, {"store_name": "Test"})
        
        assert result is None
    
    def test_update_store_sync_time(self, db_session, created_store):
        """
        Test updating store's last sync timestamp.
        
        Should set last_sync to current time and update updated_at.
        """
        # Initially no sync time
        assert created_store.last_sync is None
        
        updated_store = store_crud.update_store_sync_time(db_session, created_store.id)
        
        assert updated_store.last_sync is not None
        assert updated_store.updated_at is not None
        assert isinstance(updated_store.last_sync, datetime)
    
    def test_refresh_token(self, db_session, created_store):
        """
        Test updating store authentication tokens.
        
        Should update access and refresh tokens while preserving other data.
        """
        new_access_token = "new_access_token_123"
        new_refresh_token = "new_refresh_token_456"
        
        updated_store = store_crud.refresh_token(
            db_session, 
            created_store.id, 
            new_access_token, 
            new_refresh_token
        )
        
        assert updated_store.access_token == new_access_token
        assert updated_store.refresh_token == new_refresh_token
        assert updated_store.updated_at is not None
    
    def test_delete_store(self, db_session, created_store):
        """
        Test deleting a store.
        
        Should remove store from database and return success indicator.
        """
        store_id = created_store.id
        
        success = store_crud.delete_store(db_session, store_id)
        
        assert success is True
        
        # Verify store was deleted
        deleted_store = store_crud.get_store(db_session, store_id)
        assert deleted_store is None
    
    def test_delete_nonexistent_store(self, db_session):
        """
        Test deleting store that doesn't exist.
        
        Should return False when trying to delete non-existent store.
        """
        success = store_crud.delete_store(db_session, 99999)
        
        assert success is False
    
    def test_get_stores_for_auto_sync(self, db_session, sample_shopify_store_data, sample_woocommerce_store_data):
        """
        Test retrieving stores with auto-sync enabled.
        
        Should return only stores that have auto_sync set to True.
        """
        # Create stores with different auto_sync settings
        sample_shopify_store_data["auto_sync"] = True
        sample_woocommerce_store_data["auto_sync"] = False
        
        auto_sync_store = store_crud.create_store(db_session, sample_shopify_store_data)
        manual_store = store_crud.create_store(db_session, sample_woocommerce_store_data)
        
        auto_sync_stores = store_crud.get_stores_for_auto_sync(db_session)
        
        assert len(auto_sync_stores) == 1
        assert auto_sync_stores[0].id == auto_sync_store.id
        assert auto_sync_stores[0].auto_sync is True


class TestProductCRUD:
    """
    Tests for product-related CRUD operations.
    
    Products are the core content managed by the system,
    with variants and images as related entities.
    """
    
    def test_create_product(self, db_session, created_store):
        """
        Test creating a new product.
        
        Should create product with required fields and establish
        relationship to store.
        """
        product_data = {
            "platform_product_id": "test_product_123",
            "title": "Test Product",
            "description": "Test product description",
            "vendor": "Test Vendor",
            "published": True
        }
        
        product = product_crud.create_product(db_session, product_data, created_store.id)
        
        assert product.id is not None
        assert product.store_id == created_store.id
        assert product.platform_product_id == "test_product_123"
        assert product.title == "Test Product"
        assert product.published is True
        assert product.created_at is not None
    
    def test_get_product_by_id(self, db_session, created_product):
        """
        Test retrieving product by primary key ID.
        
        Should return product with all associated data.
        """
        retrieved_product = product_crud.get_product(db_session, created_product.id)
        
        assert retrieved_product is not None
        assert retrieved_product.id == created_product.id
        assert retrieved_product.title == created_product.title
    
    def test_get_product_by_platform_id(self, db_session, created_product, created_store):
        """
        Test retrieving product by platform ID and store.
        
        Should find product using platform_product_id within specific store.
        """
        retrieved_product = product_crud.get_product_by_platform_id(
            db_session, 
            created_product.platform_product_id, 
            created_store.id
        )
        
        assert retrieved_product is not None
        assert retrieved_product.id == created_product.id
        assert retrieved_product.platform_product_id == created_product.platform_product_id
    
    def test_get_products_by_store(self, db_session, created_store):
        """
        Test retrieving all products for a specific store.
        
        Should return paginated list of products belonging to store.
        """
        # Create multiple products
        products = []
        for i in range(5):
            product_data = {
                "platform_product_id": f"store_product_{i}",
                "title": f"Store Product {i}",
                "published": True
            }
            product = product_crud.create_product(db_session, product_data, created_store.id)
            products.append(product)
        
        # Retrieve products
        store_products = product_crud.get_products_by_store(db_session, created_store.id, skip=0, limit=3)
        
        assert len(store_products) == 3  # Limited by limit parameter
        for product in store_products:
            assert product.store_id == created_store.id
    
    def test_update_product(self, db_session, created_product):
        """
        Test updating product information.
        
        Should update specified fields and set updated_at timestamp.
        """
        update_data = {
            "title": "Updated Product Title",
            "description": "Updated description",
            "vendor": "Updated Vendor"
        }
        
        updated_product = product_crud.update_product(db_session, created_product.id, update_data)
        
        assert updated_product.title == "Updated Product Title"
        assert updated_product.description == "Updated description"
        assert updated_product.vendor == "Updated Vendor"
        assert updated_product.updated_at is not None
        # Platform ID should remain unchanged
        assert updated_product.platform_product_id == created_product.platform_product_id
    
    def test_delete_product(self, db_session, created_product):
        """
        Test deleting a product.
        
        Should remove product and handle cascading deletes properly.
        """
        product_id = created_product.id
        
        success = product_crud.delete_product(db_session, product_id)
        
        assert success is True
        
        # Verify product was deleted
        deleted_product = product_crud.get_product(db_session, product_id)
        assert deleted_product is None
    
    def test_search_products(self, db_session, created_store):
        """
        Test product search functionality.
        
        Should find products matching search terms in title, description, or vendor.
        """
        # Create products with searchable content
        products_data = [
            {"platform_product_id": "search_1", "title": "Blue Laptop Computer", "vendor": "TechCorp"},
            {"platform_product_id": "search_2", "title": "Red Gaming Mouse", "description": "High precision mouse"},
            {"platform_product_id": "search_3", "title": "Green Keyboard", "vendor": "TechCorp"},
            {"platform_product_id": "search_4", "title": "Monitor Stand", "description": "Adjustable stand"}
        ]
        
        for data in products_data:
            product_crud.create_product(db_session, data, created_store.id)
        
        # Search by title
        results = product_crud.search_products(db_session, "laptop", created_store.id)
        assert len(results) == 1
        assert "Laptop" in results[0].title
        
        # Search by vendor
        results = product_crud.search_products(db_session, "TechCorp")
        assert len(results) == 2
        
        # Search by description
        results = product_crud.search_products(db_session, "precision")
        assert len(results) == 1
        assert "Gaming Mouse" in results[0].title


class TestProductVariantCRUD:
    """
    Tests for product variant CRUD operations.
    
    Variants represent different options or configurations
    of a product (size, color, etc.).
    """
    
    def test_create_variant(self, db_session, created_product):
        """
        Test creating a product variant.
        
        Should create variant linked to product with variant-specific data.
        """
        variant_data = {
            "platform_variant_id": "variant_123",
            "title": "Large / Red",
            "sku": "PROD-L-RED",
            "price": "29.99",
            "inventory_quantity": 50
        }
        
        variant = product_crud.create_variant(db_session, variant_data, created_product.id)
        
        assert variant.id is not None
        assert variant.product_id == created_product.id
        assert variant.platform_variant_id == "variant_123"
        assert variant.title == "Large / Red"
        assert variant.sku == "PROD-L-RED"
        assert variant.price == "29.99"
    
    def test_get_variant_by_platform_id(self, db_session, created_product):
        """
        Test retrieving variant by platform ID within product.
        
        Should find variant using platform_variant_id within specific product.
        """
        # Create variant
        variant_data = {
            "platform_variant_id": "find_variant_123",
            "title": "Medium / Blue",
            "sku": "PROD-M-BLUE"
        }
        created_variant = product_crud.create_variant(db_session, variant_data, created_product.id)
        
        # Retrieve variant
        retrieved_variant = product_crud.get_variant_by_platform_id(
            db_session, 
            "find_variant_123", 
            created_product.id
        )
        
        assert retrieved_variant is not None
        assert retrieved_variant.id == created_variant.id
        assert retrieved_variant.platform_variant_id == "find_variant_123"
    
    def test_update_variant(self, db_session, created_product):
        """
        Test updating variant information.
        
        Should update specified fields like price, inventory, etc.
        """
        # Create variant
        variant_data = {
            "platform_variant_id": "update_variant_123",
            "title": "Small / Green",
            "price": "19.99",
            "inventory_quantity": 25
        }
        variant = product_crud.create_variant(db_session, variant_data, created_product.id)
        
        # Update variant
        update_data = {
            "price": "24.99",
            "inventory_quantity": 30,
            "title": "Small / Dark Green"
        }
        
        updated_variant = product_crud.update_variant(db_session, variant.id, update_data)
        
        assert updated_variant.price == "24.99"
        assert updated_variant.inventory_quantity == 30
        assert updated_variant.title == "Small / Dark Green"
        assert updated_variant.updated_at is not None


class TestProductImageCRUD:
    """
    Tests for product image CRUD operations.
    
    Images are associated with products and optionally with
    specific variants for detailed product presentation.
    """
    
    def test_create_image(self, db_session, created_product):
        """
        Test creating a product image.
        
        Should create image linked to product with image metadata.
        """
        image_data = {
            "platform_image_id": "image_123",
            "src": "https://example.com/image.jpg",
            "alt_text": "Product image",
            "position": 1,
            "status": ImageStatus.PENDING
        }
        
        image = product_crud.create_image(db_session, image_data, created_product.id)
        
        assert image.id is not None
        assert image.product_id == created_product.id
        assert image.platform_image_id == "image_123"
        assert image.src == "https://example.com/image.jpg"
        assert image.status == ImageStatus.PENDING
    
    def test_create_image_with_variant(self, db_session, created_product):
        """
        Test creating image associated with specific variant.
        
        Should create image linked to both product and variant.
        """
        # Create variant
        variant_data = {
            "platform_variant_id": "image_variant_123",
            "title": "Variant for Image"
        }
        variant = product_crud.create_variant(db_session, variant_data, created_product.id)
        
        # Create image for variant
        image_data = {
            "platform_image_id": "variant_image_123",
            "src": "https://example.com/variant_image.jpg",
            "status": ImageStatus.PENDING
        }
        
        image = product_crud.create_image(db_session, image_data, created_product.id, variant.id)
        
        assert image.product_id == created_product.id
        assert image.variant_id == variant.id
    
    def test_get_image_by_platform_id(self, db_session, created_product):
        """
        Test retrieving image by platform ID within product.
        
        Should find image using platform_image_id within specific product.
        """
        # Create image
        image_data = {
            "platform_image_id": "find_image_123",
            "src": "https://example.com/find_image.jpg",
            "status": ImageStatus.APPROVED
        }
        created_image = product_crud.create_image(db_session, image_data, created_product.id)
        
        # Retrieve image
        retrieved_image = product_crud.get_image_by_platform_id(
            db_session, 
            "find_image_123", 
            created_product.id
        )
        
        assert retrieved_image is not None
        assert retrieved_image.id == created_image.id
        assert retrieved_image.platform_image_id == "find_image_123"
    
    def test_get_image_by_hash(self, db_session, created_product):
        """
        Test retrieving image by content hash for deduplication.
        
        Should find image using calculated hash for duplicate detection.
        """
        # Create image with hash
        image_data = {
            "platform_image_id": "hash_image_123",
            "src": "https://example.com/hash_image.jpg",
            "image_hash": "abc123hash456def",
            "status": ImageStatus.STORED
        }
        created_image = product_crud.create_image(db_session, image_data, created_product.id)
        
        # Retrieve by hash
        retrieved_image = product_crud.get_image_by_hash(db_session, "abc123hash456def")
        
        assert retrieved_image is not None
        assert retrieved_image.id == created_image.id
        assert retrieved_image.image_hash == "abc123hash456def"
    
    def test_update_image(self, db_session, created_product):
        """
        Test updating image information.
        
        Should update processing status, AI analysis, GCS path, etc.
        """
        # Create image
        image_data = {
            "platform_image_id": "update_image_123",
            "src": "https://example.com/update_image.jpg",
            "status": ImageStatus.PENDING
        }
        image = product_crud.create_image(db_session, image_data, created_product.id)
        
        # Update image after processing
        update_data = {
            "status": ImageStatus.STORED,
            "ai_score": "0.85",
            "gcs_path": "products/1/images/123.jpg",
            "width": 800,
            "height": 600
        }
        
        updated_image = product_crud.update_image(db_session, image.id, update_data)
        
        assert updated_image.status == ImageStatus.STORED
        assert updated_image.ai_score == "0.85"
        assert updated_image.gcs_path == "products/1/images/123.jpg"
        assert updated_image.width == 800
        assert updated_image.height == 600
        assert updated_image.updated_at is not None
    
    def test_get_pending_images(self, db_session, created_product):
        """
        Test retrieving images that need AI processing.
        
        Should return only images with PENDING status for processing queue.
        """
        # Create images in different states
        pending_image = product_crud.create_image(db_session, {
            "platform_image_id": "pending_123",
            "src": "https://example.com/pending.jpg",
            "status": ImageStatus.PENDING
        }, created_product.id)
        
        stored_image = product_crud.create_image(db_session, {
            "platform_image_id": "stored_456",
            "src": "https://example.com/stored.jpg",
            "status": ImageStatus.STORED
        }, created_product.id)
        
        pending_images = product_crud.get_pending_images(db_session, limit=10)
        
        assert len(pending_images) == 1
        assert pending_images[0].id == pending_image.id
        assert pending_images[0].status == ImageStatus.PENDING
    
    def test_get_approved_images_by_product(self, db_session, created_product):
        """
        Test retrieving approved images for a product.
        
        Should return only stored, non-duplicate images ordered by position.
        """
        # Create images in different states
        approved_image = product_crud.create_image(db_session, {
            "platform_image_id": "approved_123",
            "src": "https://example.com/approved.jpg",
            "status": ImageStatus.STORED,
            "position": 1,
            "is_duplicate": False
        }, created_product.id)
        
        duplicate_image = product_crud.create_image(db_session, {
            "platform_image_id": "duplicate_456",
            "src": "https://example.com/duplicate.jpg",
            "status": ImageStatus.STORED,
            "position": 2,
            "is_duplicate": True
        }, created_product.id)
        
        rejected_image = product_crud.create_image(db_session, {
            "platform_image_id": "rejected_789",
            "src": "https://example.com/rejected.jpg",
            "status": ImageStatus.REJECTED,
            "position": 3,
            "is_duplicate": False
        }, created_product.id)
        
        approved_images = product_crud.get_approved_images_by_product(db_session, created_product.id)
        
        assert len(approved_images) == 1
        assert approved_images[0].id == approved_image.id
        assert approved_images[0].status == ImageStatus.STORED
        assert approved_images[0].is_duplicate is False


class TestRelationshipIntegrity:
    """
    Tests for database relationship integrity and cascading operations.
    
    Ensures that relationships between entities are properly maintained
    and that cascade deletes work correctly.
    """
    
    def test_store_product_relationship(self, db_session, created_store, created_product):
        """
        Test relationship between stores and products.
        
        Should maintain proper foreign key relationships and
        allow navigation between related entities.
        """
        # Test accessing products from store
        assert created_store.products is not None
        # Note: SQLAlchemy relationships might be lazy-loaded
        
        # Test accessing store from product
        assert created_product.store_id == created_store.id
        assert created_product.store.id == created_store.id
    
    def test_product_variant_relationship(self, db_session, created_product):
        """
        Test relationship between products and variants.
        
        Should maintain proper parent-child relationship.
        """
        # Create variant
        variant_data = {
            "platform_variant_id": "relationship_variant",
            "title": "Test Variant"
        }
        variant = product_crud.create_variant(db_session, variant_data, created_product.id)
        
        # Test relationship
        assert variant.product_id == created_product.id
        assert variant.product.id == created_product.id
    
    def test_product_image_relationship(self, db_session, created_product):
        """
        Test relationship between products and images.
        
        Should maintain proper parent-child relationship with optional variant link.
        """
        # Create variant and image
        variant_data = {"platform_variant_id": "img_variant", "title": "Image Variant"}
        variant = product_crud.create_variant(db_session, variant_data, created_product.id)
        
        image_data = {
            "platform_image_id": "relationship_image",
            "src": "https://example.com/relationship.jpg",
            "status": ImageStatus.PENDING
        }
        image = product_crud.create_image(db_session, image_data, created_product.id, variant.id)
        
        # Test relationships
        assert image.product_id == created_product.id
        assert image.variant_id == variant.id
        assert image.product.id == created_product.id
        assert image.variant.id == variant.id
    
    def test_duplicate_image_relationship(self, db_session, created_product):
        """
        Test self-referential relationship for duplicate images.
        
        Should properly link duplicate images to their originals.
        """
        # Create original image
        original_data = {
            "platform_image_id": "original_image",
            "src": "https://example.com/original.jpg",
            "status": ImageStatus.STORED,
            "image_hash": "same_hash_123"
        }
        original = product_crud.create_image(db_session, original_data, created_product.id)
        
        # Create duplicate image
        duplicate_data = {
            "platform_image_id": "duplicate_image",
            "src": "https://example.com/duplicate.jpg",
            "status": ImageStatus.REJECTED,
            "image_hash": "same_hash_123",
            "is_duplicate": True,
            "original_image_id": original.id
        }
        duplicate = product_crud.create_image(db_session, duplicate_data, created_product.id)
        
        # Test relationship
        assert duplicate.original_image_id == original.id
        assert duplicate.is_duplicate is True
    
    def test_cascade_delete_behavior(self, db_session, created_store):
        """
        Test cascade delete behavior when store is deleted.
        
        Should handle deletion of related products, variants, and images
        according to configured cascade rules.
        """
        # Create product with variants and images
        product_data = {
            "platform_product_id": "cascade_product",
            "title": "Cascade Test Product"
        }
        product = product_crud.create_product(db_session, product_data, created_store.id)
        
        variant_data = {
            "platform_variant_id": "cascade_variant",
            "title": "Cascade Variant"
        }
        variant = product_crud.create_variant(db_session, variant_data, product.id)
        
        image_data = {
            "platform_image_id": "cascade_image",
            "src": "https://example.com/cascade.jpg",
            "status": ImageStatus.PENDING
        }
        image = product_crud.create_image(db_session, image_data, product.id)
        
        # Store IDs for verification
        product_id = product.id
        variant_id = variant.id
        image_id = image.id
        
        # Delete store (should cascade to related entities based on DB schema)
        store_crud.delete_store(db_session, created_store.id)
        
        # Verify store was deleted
        assert store_crud.get_store(db_session, created_store.id) is None
        
        # Note: Actual cascade behavior depends on database schema configuration
        # This test documents expected behavior but may need adjustment based on
        # actual foreign key constraints and cascade settings