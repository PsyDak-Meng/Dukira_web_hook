"""
Test configuration and fixtures for the Dukira Webhook API.

This file contains pytest fixtures that are used across multiple test files:
- Database setup with SQLite for testing
- Test client for FastAPI application
- Mock data factories for creating test objects
- Authentication helpers
"""

import pytest
import asyncio
from typing import Generator, Dict, Any
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import Mock, AsyncMock
import tempfile
import os

from app.main import app
from app.database import get_db, Base
from app.models import Store, Product, ProductVariant, ProductImage, PlatformType, ImageStatus
from app.config import settings


# Create test database using SQLite
@pytest.fixture(scope="session")
def test_engine():
    """
    Creates a SQLite test database engine for testing.
    
    Uses SQLite in-memory database for fast, isolated tests.
    Creates all tables from the SQLAlchemy models.
    """
    # Create temporary database file
    db_fd, db_path = tempfile.mkstemp()
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    yield engine
    
    # Cleanup
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture(scope="function")
def db_session(test_engine):
    """
    Creates a database session for each test function.
    
    Provides transaction isolation - each test gets a fresh database state.
    Rolls back all changes after each test to ensure test isolation.
    """
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSessionLocal()
    
    yield session
    
    session.rollback()
    session.close()


@pytest.fixture(scope="function")
def client(db_session):
    """
    Creates a FastAPI test client with database session override.
    
    Overrides the database dependency to use the test database session.
    Returns a TestClient instance for making HTTP requests to the API.
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


# Sample data factories
@pytest.fixture
def sample_shopify_store_data():
    """
    Provides sample Shopify store data for testing OAuth and store creation.
    
    Returns a dictionary with typical Shopify store information
    that would be received during OAuth flow.
    """
    return {
        "user_id": "user123",
        "platform": PlatformType.SHOPIFY,
        "store_name": "test-shop",
        "store_url": "https://test-shop.myshopify.com",
        "access_token": "test_access_token_123",
        "platform_store_id": "test-shop",
        "platform_data": {
            "shop": "test-shop",
            "scope": "read_products,write_products"
        }
    }


@pytest.fixture
def sample_woocommerce_store_data():
    """
    Provides sample WooCommerce store data for testing OAuth and store creation.
    
    Returns a dictionary with typical WooCommerce store information
    including consumer key/secret for API authentication.
    """
    return {
        "user_id": "user123",
        "platform": PlatformType.WOOCOMMERCE,
        "store_name": "test-woo-store.com",
        "store_url": "https://test-woo-store.com",
        "access_token": "ck_test_consumer_key_123",
        "refresh_token": "cs_test_consumer_secret_123",
        "platform_store_id": "key_id_123",
        "platform_data": {
            "consumer_key": "ck_test_consumer_key_123",
            "consumer_secret": "cs_test_consumer_secret_123",
            "key_id": "key_id_123"
        }
    }


@pytest.fixture
def sample_product_data():
    """
    Provides sample product data that matches Shopify API response format.
    
    Used for testing product sync operations and data transformation.
    Includes typical product fields like title, description, variants, and images.
    """
    return {
        "id": "123456789",
        "title": "Test Product",
        "body_html": "<p>This is a test product description</p>",
        "vendor": "Test Vendor",
        "product_type": "Test Type",
        "tags": "test, sample, product",
        "handle": "test-product",
        "status": "active",
        "variants": [
            {
                "id": "987654321",
                "title": "Default Title",
                "sku": "TEST-SKU-001",
                "price": "19.99",
                "inventory_quantity": 100,
                "weight": "0.5",
                "option1": "Default"
            }
        ],
        "images": [
            {
                "id": "111222333",
                "src": "https://example.com/image1.jpg",
                "alt": "Test product image",
                "position": 1,
                "width": 800,
                "height": 600
            },
            {
                "id": "444555666",
                "src": "https://example.com/image2.jpg",
                "alt": "Test product image 2",
                "position": 2,
                "width": 800,
                "height": 600
            }
        ]
    }


@pytest.fixture
def created_store(db_session, sample_shopify_store_data):
    """
    Creates a test store in the database for use in other tests.
    
    Provides a pre-created store instance that can be used
    for testing operations that require an existing store.
    """
    store = Store(**sample_shopify_store_data)
    db_session.add(store)
    db_session.commit()
    db_session.refresh(store)
    return store


@pytest.fixture
def created_product(db_session, created_store):
    """
    Creates a test product with variants and images in the database.
    
    Provides a complete product setup for testing operations
    that require existing product data.
    """
    # Create product
    product = Product(
        store_id=created_store.id,
        platform_product_id="123456789",
        title="Test Product",
        description="Test product description",
        vendor="Test Vendor",
        product_type="Test Type",
        published=True
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    
    # Create variant
    variant = ProductVariant(
        product_id=product.id,
        platform_variant_id="987654321",
        title="Default Title",
        sku="TEST-SKU-001",
        price="19.99"
    )
    db_session.add(variant)
    db_session.commit()
    
    # Create images
    image1 = ProductImage(
        product_id=product.id,
        platform_image_id="111222333",
        src="https://example.com/image1.jpg",
        alt_text="Test image 1",
        position=1,
        status=ImageStatus.APPROVED
    )
    image2 = ProductImage(
        product_id=product.id,
        platform_image_id="444555666",
        src="https://example.com/image2.jpg",
        alt_text="Test image 2",
        position=2,
        status=ImageStatus.PENDING
    )
    db_session.add_all([image1, image2])
    db_session.commit()
    
    return product


# Mock external services
@pytest.fixture
def mock_shopify_api():
    """
    Provides mocked Shopify API responses for testing without external calls.
    
    Returns a mock object that simulates Shopify API endpoints
    like product retrieval, webhook creation, etc.
    """
    mock = Mock()
    mock.get_products = AsyncMock(return_value=[
        {
            "id": "123456789",
            "title": "Test Product",
            "body_html": "Test description",
            "vendor": "Test Vendor",
            "variants": [],
            "images": []
        }
    ])
    mock.get_product = AsyncMock(return_value={
        "id": "123456789",
        "title": "Test Product"
    })
    mock.get_product_count = AsyncMock(return_value=1)
    mock.create_webhook = AsyncMock(return_value={
        "id": "webhook123",
        "topic": "products/create"
    })
    return mock


@pytest.fixture
def mock_ai_service():
    """
    Provides mocked AI service responses for testing image processing.
    
    Returns a mock that simulates AI model responses for image quality assessment.
    Includes configurable scores and analysis results.
    """
    mock = Mock()
    mock.process_image = AsyncMock(return_value={
        "score": 0.85,
        "analysis": {
            "quality": "high",
            "clarity": 0.9,
            "lighting": 0.8,
            "composition": 0.7,
            "background": "clean",
            "product_focus": True
        }
    })
    return mock


@pytest.fixture
def mock_gcs_service():
    """
    Provides mocked Google Cloud Storage service for testing file uploads.
    
    Returns a mock that simulates GCS operations like upload, delete, and URL generation
    without actually connecting to Google Cloud Storage.
    """
    mock = Mock()
    mock.upload_image = AsyncMock(return_value=True)
    mock.delete_image = AsyncMock(return_value=True)
    mock.get_image_url = AsyncMock(return_value="https://storage.googleapis.com/bucket/image.jpg")
    mock.health_check = Mock(return_value=True)
    return mock


@pytest.fixture
def mock_httpx():
    """
    Provides mocked HTTP client for testing external API calls.
    
    Returns a mock httpx client that can simulate responses from
    e-commerce platforms without making actual HTTP requests.
    """
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    mock_response.content = b"fake_image_data"
    mock_response.headers = {"content-type": "image/jpeg"}
    mock_response.raise_for_status.return_value = None
    
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.post.return_value = mock_response
    
    return mock_client


# Authentication helpers
@pytest.fixture
def auth_headers():
    """
    Provides authentication headers for testing protected endpoints.
    
    Returns headers that would be used for API authentication
    in a real application scenario.
    """
    return {
        "Authorization": "Bearer test_token",
        "Content-Type": "application/json"
    }


@pytest.fixture
def webhook_headers_shopify():
    """
    Provides Shopify webhook headers for testing webhook verification.
    
    Returns headers that Shopify would send with webhook requests
    including HMAC signature for verification.
    """
    return {
        "X-Shopify-Topic": "products/create",
        "X-Shopify-Shop-Domain": "test-shop.myshopify.com",
        "X-Shopify-Hmac-Sha256": "test_hmac_signature",
        "Content-Type": "application/json"
    }


@pytest.fixture
def webhook_headers_woocommerce():
    """
    Provides WooCommerce webhook headers for testing webhook verification.
    
    Returns headers that WooCommerce would send with webhook requests
    including signature for verification.
    """
    return {
        "X-WC-Webhook-Event": "created",
        "X-WC-Webhook-Resource": "product",
        "X-WC-Webhook-Signature": "test_signature",
        "Content-Type": "application/json"
    }


# Event loop fixture for async tests
@pytest.fixture(scope="session")
def event_loop():
    """
    Creates event loop for async tests.
    
    Provides a consistent event loop for all async test functions
    to ensure proper async test execution.
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# Test data cleanup
@pytest.fixture(autouse=True)
def cleanup_test_data(db_session):
    """
    Automatically cleans up test data after each test.
    
    Ensures that each test starts with a clean database state
    by removing any data created during the test.
    """
    yield
    # Cleanup happens in db_session fixture rollback