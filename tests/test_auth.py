"""
OAuth Authentication Tests

Tests for OAuth flows with Shopify, WooCommerce, and Wix platforms.
Covers authorization URL generation, callback handling, token storage,
and store connection management.
"""

import pytest
from unittest.mock import patch, AsyncMock
from app.auth.oauth import shopify_oauth, woocommerce_oauth, wix_oauth
from app.models import Store, PlatformType
from app.crud import store as store_crud


class TestShopifyOAuth:
    """
    Tests for Shopify OAuth implementation.
    
    Covers the complete Shopify OAuth flow including:
    - Authorization URL generation with proper scopes
    - Access token exchange with authorization code
    - Webhook signature verification
    """
    
    def test_generate_auth_url_with_default_scopes(self):
        """
        Test that Shopify OAuth generates correct authorization URL with default scopes.
        
        Verifies that the generated URL contains:
        - Correct Shopify domain
        - Default product-related scopes
        - Client ID and redirect URI
        - State parameter for security
        """
        shop = "test-shop"
        state = "test_state_123"
        
        auth_url = shopify_oauth.generate_auth_url(shop=shop, state=state)
        
        # Verify URL structure
        assert f"https://{shop}.myshopify.com/admin/oauth/authorize" in auth_url
        assert "client_id=" in auth_url
        assert "scope=read_products,read_product_listings,write_products" in auth_url
        assert f"state={state}" in auth_url
        assert "redirect_uri=" in auth_url
    
    def test_generate_auth_url_with_custom_scopes(self):
        """
        Test Shopify OAuth URL generation with custom scopes.
        
        Verifies that custom scopes are properly included in the authorization URL
        and that multiple scopes are comma-separated as required by Shopify.
        """
        shop = "test-shop"
        custom_scopes = ["read_orders", "write_customers"]
        
        auth_url = shopify_oauth.generate_auth_url(
            shop=shop, 
            scopes=custom_scopes
        )
        
        assert "scope=read_orders,write_customers" in auth_url
    
    @pytest.mark.asyncio
    async def test_exchange_code_for_token_success(self):
        """
        Test successful token exchange with Shopify OAuth.
        
        Mocks the Shopify token endpoint response and verifies:
        - Correct API call to Shopify's token endpoint
        - Proper handling of successful response
        - Access token extraction from response
        """
        shop = "test-shop"
        code = "test_auth_code"
        expected_token = "test_access_token_123"
        
        # Mock successful Shopify API response
        mock_response = {
            "access_token": expected_token,
            "scope": "read_products,write_products"
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value.json.return_value = mock_response
            mock_instance.post.return_value.raise_for_status.return_value = None
            mock_client.return_value.__aenter__.return_value = mock_instance
            
            result = await shopify_oauth.exchange_code_for_token(code=code, shop=shop)
            
            assert result["access_token"] == expected_token
            assert result["scope"] == "read_products,write_products"
            
            # Verify API call was made correctly
            mock_instance.post.assert_called_once()
            call_args = mock_instance.post.call_args
            assert f"https://{shop}.myshopify.com/admin/oauth/access_token" in str(call_args)
    
    @pytest.mark.asyncio
    async def test_verify_webhook_signature_valid(self):
        """
        Test Shopify webhook signature verification with valid signature.
        
        Verifies that the HMAC-SHA256 signature verification correctly
        validates authentic Shopify webhook requests.
        """
        payload = b'{"id": 123, "title": "Test Product"}'
        secret = "test_webhook_secret"
        
        # Calculate expected signature
        import hmac
        import hashlib
        import base64
        
        expected_signature = base64.b64encode(
            hmac.new(secret.encode('utf-8'), payload, hashlib.sha256).digest()
        ).decode()
        
        is_valid = await shopify_oauth.verify_webhook(payload, expected_signature, secret)
        
        assert is_valid is True
    
    @pytest.mark.asyncio
    async def test_verify_webhook_signature_invalid(self):
        """
        Test Shopify webhook signature verification with invalid signature.
        
        Ensures that tampered or incorrect webhook signatures are properly rejected
        to prevent unauthorized webhook processing.
        """
        payload = b'{"id": 123, "title": "Test Product"}'
        secret = "test_webhook_secret"
        invalid_signature = "invalid_signature_123"
        
        is_valid = await shopify_oauth.verify_webhook(payload, invalid_signature, secret)
        
        assert is_valid is False


class TestWooCommerceOAuth:
    """
    Tests for WooCommerce OAuth implementation.
    
    WooCommerce uses a different OAuth flow than Shopify,
    providing consumer keys directly in the callback.
    """
    
    def test_generate_auth_url_structure(self):
        """
        Test WooCommerce OAuth authorization URL generation.
        
        Verifies that the generated URL follows WooCommerce's OAuth format
        with proper app name, scopes, and return URL parameters.
        """
        store_url = "https://test-store.com"
        state = "test_state_123"
        
        auth_url = woocommerce_oauth.generate_auth_url(store_url=store_url, state=state)
        
        assert store_url in auth_url
        assert "/wc-auth/v1/authorize" in auth_url
        assert "app_name=Dukira+Webhook+Integration" in auth_url
        assert "scope=read,write" in auth_url
        assert f"user_id={state}" in auth_url
    
    def test_generate_auth_url_custom_scopes(self):
        """
        Test WooCommerce OAuth URL with custom scopes.
        
        Verifies that custom permission scopes are properly included
        in the WooCommerce authorization URL.
        """
        store_url = "https://test-store.com"
        custom_scopes = ["read_only"]
        
        auth_url = woocommerce_oauth.generate_auth_url(
            store_url=store_url, 
            scopes=custom_scopes
        )
        
        assert "scope=read_only" in auth_url
    
    @pytest.mark.asyncio
    async def test_exchange_code_for_token(self):
        """
        Test WooCommerce token exchange handling.
        
        WooCommerce provides consumer keys directly in the callback,
        so this tests the handling of that callback data.
        """
        callback_data = {
            "consumer_key": "ck_test_key_123",
            "consumer_secret": "cs_test_secret_123",
            "key_id": "key_123"
        }
        
        result = await woocommerce_oauth.exchange_code_for_token(**callback_data)
        
        assert result == callback_data


class TestWixOAuth:
    """
    Tests for Wix OAuth implementation.
    
    Covers Wix's standard OAuth 2.0 flow with authorization codes
    and access token exchange.
    """
    
    def test_generate_auth_url_structure(self):
        """
        Test Wix OAuth authorization URL generation.
        
        Verifies that the URL follows OAuth 2.0 standards with
        proper response type, client ID, and scope parameters.
        """
        state = "test_state_123"
        
        auth_url = wix_oauth.generate_auth_url(state=state)
        
        assert "https://www.wix.com/oauth/authorize" in auth_url
        assert "response_type=code" in auth_url
        assert "client_id=" in auth_url
        assert "scope=offline_access" in auth_url
        assert f"state={state}" in auth_url
    
    @pytest.mark.asyncio
    async def test_exchange_code_for_token_success(self):
        """
        Test successful Wix access token exchange.
        
        Mocks the Wix token endpoint and verifies proper handling
        of the OAuth 2.0 authorization code grant flow.
        """
        code = "test_auth_code"
        expected_response = {
            "access_token": "wix_access_token_123",
            "refresh_token": "wix_refresh_token_123",
            "token_type": "Bearer",
            "expires_in": 3600
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value.json.return_value = expected_response
            mock_instance.post.return_value.raise_for_status.return_value = None
            mock_client.return_value.__aenter__.return_value = mock_instance
            
            result = await wix_oauth.exchange_code_for_token(code=code)
            
            assert result["access_token"] == "wix_access_token_123"
            assert result["refresh_token"] == "wix_refresh_token_123"
            
            # Verify correct API endpoint was called
            mock_instance.post.assert_called_once()
            call_args = mock_instance.post.call_args
            assert "https://www.wix.com/oauth/access_token" in str(call_args)


class TestAuthEndpoints:
    """
    Integration tests for authentication API endpoints.
    
    Tests the complete OAuth flow through the FastAPI endpoints
    including authorization initiation and callback handling.
    """
    
    def test_shopify_authorize_endpoint(self, client):
        """
        Test the Shopify authorization endpoint.
        
        Verifies that the endpoint returns a proper authorization URL
        and maintains state for security verification.
        """
        response = client.get(
            "/auth/shopify/authorize",
            params={"shop": "test-shop", "user_id": "user123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "auth_url" in data
        assert "state" in data
        assert "shop" in data
        assert "test-shop.myshopify.com" in data["auth_url"]
        assert data["shop"] == "test-shop"
    
    @patch('app.auth.oauth.shopify_oauth.exchange_code_for_token')
    def test_shopify_callback_endpoint_success(self, mock_exchange, client, db_session):
        """
        Test successful Shopify OAuth callback handling.
        
        Mocks the token exchange and verifies that:
        - Store is created or updated in database
        - Proper response is returned with store information
        - Access token is securely stored
        """
        # Mock successful token exchange
        mock_exchange.return_value = {
            "access_token": "test_access_token_123",
            "scope": "read_products,write_products"
        }
        
        response = client.get(
            "/auth/shopify/callback",
            params={
                "code": "test_auth_code",
                "shop": "test-shop",
                "state": "user123:random_state"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["message"] == "Store connected successfully"
        assert "store_id" in data
        assert data["store_name"] == "test-shop"
        
        # Verify store was created in database
        store = store_crud.get_store(db_session, data["store_id"])
        assert store is not None
        assert store.platform == PlatformType.SHOPIFY
        assert store.access_token == "test_access_token_123"
    
    def test_woocommerce_authorize_endpoint(self, client):
        """
        Test the WooCommerce authorization endpoint.
        
        Verifies proper authorization URL generation for WooCommerce stores
        with the specific WooCommerce OAuth format.
        """
        response = client.get(
            "/auth/woocommerce/authorize",
            params={
                "store_url": "https://test-store.com",
                "user_id": "user123"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "auth_url" in data
        assert "test-store.com" in data["auth_url"]
        assert "/wc-auth/v1/authorize" in data["auth_url"]
    
    def test_get_user_stores(self, client, created_store):
        """
        Test retrieval of all stores connected by a user.
        
        Verifies that the endpoint returns all stores associated
        with a specific user ID across all platforms.
        """
        response = client.get(f"/auth/stores/{created_store.user_id}")
        
        assert response.status_code == 200
        stores = response.json()
        
        assert len(stores) == 1
        assert stores[0]["id"] == created_store.id
        assert stores[0]["platform"] == created_store.platform.value
    
    def test_disconnect_store(self, client, created_store):
        """
        Test store disconnection functionality.
        
        Verifies that stores can be properly disconnected and removed
        from the database while maintaining data integrity.
        """
        store_id = created_store.id
        
        response = client.delete(f"/auth/stores/{store_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Store disconnected successfully"
        
        # Verify store was deleted
        response = client.get(f"/auth/stores/{created_store.user_id}")
        stores = response.json()
        assert len(stores) == 0
    
    def test_invalid_callback_parameters(self, client):
        """
        Test OAuth callback with invalid or missing parameters.
        
        Ensures proper error handling when OAuth callbacks
        contain invalid or malformed data.
        """
        # Missing required parameters
        response = client.get("/auth/shopify/callback")
        assert response.status_code == 422  # Validation error
        
        # Invalid state format
        response = client.get(
            "/auth/shopify/callback",
            params={
                "code": "test_code",
                "shop": "test-shop",
                "state": "invalid_state_format"
            }
        )
        assert response.status_code == 400


class TestStoreOperations:
    """
    Tests for store-related database operations and business logic.
    
    Covers store creation, updates, token management, and multi-platform support.
    """
    
    def test_create_store_all_platforms(self, db_session):
        """
        Test store creation for all supported platforms.
        
        Verifies that stores can be created for Shopify, WooCommerce,
        and Wix with platform-specific data structures.
        """
        platforms_data = [
            {
                "user_id": "user123",
                "platform": PlatformType.SHOPIFY,
                "store_name": "shopify-store",
                "access_token": "shopify_token",
                "platform_store_id": "shopify-store"
            },
            {
                "user_id": "user123", 
                "platform": PlatformType.WOOCOMMERCE,
                "store_name": "woo-store.com",
                "access_token": "woo_consumer_key",
                "refresh_token": "woo_consumer_secret"
            },
            {
                "user_id": "user123",
                "platform": PlatformType.WIX,
                "store_name": "wix-store",
                "access_token": "wix_access_token"
            }
        ]
        
        created_stores = []
        for store_data in platforms_data:
            store = store_crud.create_store(db_session, store_data)
            created_stores.append(store)
            
            assert store.user_id == "user123"
            assert store.platform == store_data["platform"]
            assert store.access_token == store_data["access_token"]
        
        # Verify all stores were created
        user_stores = store_crud.get_stores_by_user(db_session, "user123")
        assert len(user_stores) == 3
        
        # Verify each platform is represented
        platforms = {store.platform for store in user_stores}
        assert platforms == {PlatformType.SHOPIFY, PlatformType.WOOCOMMERCE, PlatformType.WIX}
    
    def test_update_store_tokens(self, db_session, created_store):
        """
        Test updating store authentication tokens.
        
        Verifies that access tokens and refresh tokens can be updated
        for token refresh scenarios and OAuth renewals.
        """
        new_access_token = "new_access_token_123"
        new_refresh_token = "new_refresh_token_123"
        
        updated_store = store_crud.refresh_token(
            db_session,
            created_store.id,
            new_access_token,
            new_refresh_token
        )
        
        assert updated_store.access_token == new_access_token
        assert updated_store.refresh_token == new_refresh_token
        assert updated_store.updated_at is not None
    
    def test_store_sync_time_tracking(self, db_session, created_store):
        """
        Test tracking of store synchronization timestamps.
        
        Verifies that last sync times are properly recorded
        and updated when sync operations are performed.
        """
        # Initially no sync time
        assert created_store.last_sync is None
        
        # Update sync time
        updated_store = store_crud.update_store_sync_time(db_session, created_store.id)
        
        assert updated_store.last_sync is not None
        assert updated_store.updated_at is not None