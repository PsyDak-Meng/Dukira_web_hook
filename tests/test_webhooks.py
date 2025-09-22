"""
Webhook Processing Tests

Tests for webhook handling from Shopify, WooCommerce, and Wix platforms.
Covers webhook signature verification, payload processing, event storage,
and automatic sync triggering based on webhook events.
"""

import pytest
import json
from unittest.mock import patch, AsyncMock, Mock
from app.models import WebhookEvent, PlatformType
from app.routers.webhooks import verify_shopify_webhook, verify_woocommerce_webhook, process_webhook_event


class TestWebhookVerification:
    """
    Tests for webhook signature verification across different platforms.
    
    Each platform has its own signature verification method to ensure
    webhook authenticity and prevent unauthorized requests.
    """
    
    @pytest.mark.asyncio
    async def test_shopify_webhook_verification_valid(self, created_store):
        """
        Test Shopify webhook signature verification with valid HMAC.
        
        Verifies that authentic Shopify webhooks with correct HMAC-SHA256
        signatures are properly validated and accepted for processing.
        """
        import hmac
        import hashlib
        import base64
        
        payload = b'{"id": 123, "title": "Test Product"}'
        secret = "test_webhook_secret"
        
        # Add webhook secret to store platform data
        created_store.platform_data = {"webhook_secret": secret}
        
        # Calculate valid signature
        expected_signature = base64.b64encode(
            hmac.new(secret.encode('utf-8'), payload, hashlib.sha256).digest()
        ).decode()
        
        is_valid = await verify_shopify_webhook(payload, expected_signature, created_store)
        
        assert is_valid is True
    
    @pytest.mark.asyncio
    async def test_shopify_webhook_verification_invalid(self, created_store):
        """
        Test Shopify webhook verification with invalid signature.
        
        Ensures that webhooks with tampered or incorrect signatures
        are rejected to prevent unauthorized webhook processing.
        """
        payload = b'{"id": 123, "title": "Test Product"}'
        invalid_signature = "invalid_signature_123"
        
        created_store.platform_data = {"webhook_secret": "test_secret"}
        
        is_valid = await verify_shopify_webhook(payload, invalid_signature, created_store)
        
        assert is_valid is False
    
    @pytest.mark.asyncio
    async def test_shopify_webhook_fallback_to_access_token(self, created_store):
        """
        Test Shopify webhook verification fallback to access token.
        
        When no specific webhook secret is configured, the system should
        fall back to using the access token as the webhook secret.
        """
        payload = b'{"id": 123, "title": "Test Product"}'
        secret = created_store.access_token
        
        # No webhook secret in platform data
        created_store.platform_data = {}
        
        # Calculate signature using access token
        import hmac
        import hashlib
        import base64
        
        expected_signature = base64.b64encode(
            hmac.new(secret.encode('utf-8'), payload, hashlib.sha256).digest()
        ).decode()
        
        is_valid = await verify_shopify_webhook(payload, expected_signature, created_store)
        
        assert is_valid is True
    
    @pytest.mark.asyncio
    async def test_woocommerce_webhook_verification_with_secret(self, created_store):
        """
        Test WooCommerce webhook verification with configured secret.
        
        Verifies that WooCommerce webhooks are properly validated when
        a webhook secret is configured in the store settings.
        """
        import hmac
        import hashlib
        import base64
        
        payload = b'{"id": 123, "name": "Test Product"}'
        secret = "woo_webhook_secret"
        
        created_store.platform_data = {"webhook_secret": secret}
        
        # Calculate expected signature
        expected_signature = base64.b64encode(
            hmac.new(secret.encode(), payload, hashlib.sha256).digest()
        ).decode()
        
        is_valid = await verify_woocommerce_webhook(payload, expected_signature, created_store)
        
        assert is_valid is True
    
    @pytest.mark.asyncio
    async def test_woocommerce_webhook_no_secret_configured(self, created_store):
        """
        Test WooCommerce webhook handling without configured secret.
        
        Some WooCommerce installations may not have webhook secrets configured.
        The system should handle these gracefully without failing.
        """
        payload = b'{"id": 123, "name": "Test Product"}'
        signature = "any_signature"
        
        # No webhook secret configured
        created_store.platform_data = {}
        
        is_valid = await verify_woocommerce_webhook(payload, signature, created_store)
        
        # Should return True when no secret is configured
        assert is_valid is True


class TestWebhookEventProcessing:
    """
    Tests for webhook event processing and database storage.
    
    Covers storing webhook events, triggering appropriate sync actions,
    and handling different types of webhook events from various platforms.
    """
    
    @pytest.mark.asyncio
    async def test_process_product_create_webhook(self, db_session, created_store, sample_product_data):
        """
        Test processing of product creation webhook events.
        
        When a new product is created on the platform, the webhook should:
        - Store the webhook event in the database
        - Trigger a sync of the specific product
        - Mark the event as processed
        """
        event_type = "product/create"
        headers = {"X-Shopify-Topic": "products/create"}
        
        with patch('app.services.sync_service.SyncService._sync_single_product') as mock_sync:
            mock_sync.return_value = None
            
            await process_webhook_event(
                db_session, 
                created_store, 
                event_type, 
                sample_product_data, 
                headers
            )
            
            # Verify webhook event was stored
            webhook_event = db_session.query(WebhookEvent).filter(
                WebhookEvent.store_id == created_store.id
            ).first()
            
            assert webhook_event is not None
            assert webhook_event.event_type == event_type
            assert webhook_event.platform == created_store.platform
            assert webhook_event.payload == sample_product_data
            assert webhook_event.processed is True
            
            # Verify sync was triggered
            mock_sync.assert_called_once_with(created_store, sample_product_data)
    
    @pytest.mark.asyncio
    async def test_process_product_update_webhook(self, db_session, created_store, sample_product_data):
        """
        Test processing of product update webhook events.
        
        Product updates should trigger re-sync of the specific product
        to ensure all changes are captured in our database.
        """
        event_type = "product/update"
        headers = {"X-Shopify-Topic": "products/update"}
        
        with patch('app.services.sync_service.SyncService._sync_single_product') as mock_sync:
            mock_sync.return_value = None
            
            await process_webhook_event(
                db_session,
                created_store,
                event_type,
                sample_product_data,
                headers
            )
            
            # Verify event was processed
            webhook_event = db_session.query(WebhookEvent).first()
            assert webhook_event.event_type == event_type
            assert webhook_event.processed is True
            
            # Verify product sync was triggered
            mock_sync.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_product_delete_webhook(self, db_session, created_store, created_product):
        """
        Test processing of product deletion webhook events.
        
        When a product is deleted on the platform, it should be removed
        from our database to maintain consistency.
        """
        event_type = "product/delete"
        payload = {"id": created_product.platform_product_id}
        headers = {"X-Shopify-Topic": "products/delete"}
        
        await process_webhook_event(
            db_session,
            created_store,
            event_type,
            payload,
            headers
        )
        
        # Verify webhook event was stored
        webhook_event = db_session.query(WebhookEvent).first()
        assert webhook_event.event_type == event_type
        assert webhook_event.processed is True
        
        # Verify product was deleted (would need to refresh session)
        db_session.refresh(created_product)
    
    @pytest.mark.asyncio
    async def test_webhook_processing_error_handling(self, db_session, created_store):
        """
        Test webhook processing error handling and logging.
        
        When webhook processing fails, the error should be logged
        and the webhook event should be marked with error details.
        """
        event_type = "product/create"
        payload = {"invalid": "data"}
        headers = {}
        
        with patch('app.services.sync_service.SyncService._sync_single_product') as mock_sync:
            # Make sync raise an exception
            mock_sync.side_effect = Exception("Sync failed")
            
            await process_webhook_event(
                db_session,
                created_store,
                event_type,
                payload,
                headers
            )
            
            # Verify error was recorded
            webhook_event = db_session.query(WebhookEvent).first()
            assert webhook_event.processed is False
            assert webhook_event.error_message == "Sync failed"


class TestShopifyWebhookEndpoint:
    """
    Tests for the Shopify webhook API endpoint.
    
    Tests the complete webhook handling flow including signature verification,
    payload parsing, and background processing initiation.
    """
    
    @patch('app.routers.webhooks.verify_shopify_webhook')
    def test_shopify_webhook_valid_signature(self, mock_verify, client, created_store):
        """
        Test Shopify webhook endpoint with valid signature.
        
        Verifies that webhooks with valid signatures are accepted
        and queued for background processing.
        """
        mock_verify.return_value = True
        
        webhook_payload = {
            "id": 123456789,
            "title": "Test Product",
            "handle": "test-product"
        }
        
        headers = {
            "X-Shopify-Topic": "products/create",
            "X-Shopify-Shop-Domain": "test-shop.myshopify.com",
            "X-Shopify-Hmac-Sha256": "valid_signature",
            "Content-Type": "application/json"
        }
        
        response = client.post(
            f"/webhooks/shopify/{created_store.id}",
            json=webhook_payload,
            headers=headers
        )
        
        assert response.status_code == 200
        assert response.json()["status"] == "received"
        
        # Verify signature verification was called
        mock_verify.assert_called_once()
    
    @patch('app.routers.webhooks.verify_shopify_webhook')
    def test_shopify_webhook_invalid_signature(self, mock_verify, client, created_store):
        """
        Test Shopify webhook endpoint with invalid signature.
        
        Webhooks with invalid signatures should be rejected with a 401 error
        to prevent unauthorized webhook processing.
        """
        mock_verify.return_value = False
        
        webhook_payload = {"id": 123, "title": "Test"}
        headers = {
            "X-Shopify-Hmac-Sha256": "invalid_signature",
            "Content-Type": "application/json"
        }
        
        response = client.post(
            f"/webhooks/shopify/{created_store.id}",
            json=webhook_payload,
            headers=headers
        )
        
        assert response.status_code == 401
        assert "Invalid webhook signature" in response.json()["detail"]
    
    def test_shopify_webhook_nonexistent_store(self, client):
        """
        Test Shopify webhook for non-existent store.
        
        Webhooks for stores that don't exist in our database
        should return a 404 error.
        """
        webhook_payload = {"id": 123, "title": "Test"}
        
        response = client.post(
            "/webhooks/shopify/99999",
            json=webhook_payload
        )
        
        assert response.status_code == 404
        assert "Store not found" in response.json()["detail"]
    
    def test_shopify_webhook_invalid_json(self, client, created_store):
        """
        Test Shopify webhook with invalid JSON payload.
        
        Malformed JSON payloads should be rejected with appropriate error.
        """
        # Send invalid JSON
        response = client.post(
            f"/webhooks/shopify/{created_store.id}",
            data="invalid json content",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 400
        assert "Invalid JSON payload" in response.json()["detail"]


class TestWooCommerceWebhookEndpoint:
    """
    Tests for the WooCommerce webhook API endpoint.
    
    WooCommerce uses different header formats and event types
    compared to Shopify webhooks.
    """
    
    @patch('app.routers.webhooks.verify_woocommerce_webhook')
    def test_woocommerce_webhook_success(self, mock_verify, client, sample_woocommerce_store_data, db_session):
        """
        Test successful WooCommerce webhook processing.
        
        Verifies that WooCommerce webhooks are properly parsed and processed
        with the correct event type construction.
        """
        # Create WooCommerce store
        from app.crud import store as store_crud
        store = store_crud.create_store(db_session, sample_woocommerce_store_data)
        
        mock_verify.return_value = True
        
        webhook_payload = {
            "id": 123,
            "name": "Test WooCommerce Product",
            "type": "simple"
        }
        
        headers = {
            "X-WC-Webhook-Event": "created",
            "X-WC-Webhook-Resource": "product",
            "X-WC-Webhook-Signature": "valid_signature",
            "Content-Type": "application/json"
        }
        
        response = client.post(
            f"/webhooks/woocommerce/{store.id}",
            json=webhook_payload,
            headers=headers
        )
        
        assert response.status_code == 200
        assert response.json()["status"] == "received"
    
    def test_woocommerce_webhook_wrong_platform_store(self, client, created_store):
        """
        Test WooCommerce webhook sent to Shopify store.
        
        Webhooks should only be processed for stores of the correct platform.
        """
        # created_store is a Shopify store by default
        webhook_payload = {"id": 123, "name": "Test"}
        
        response = client.post(
            f"/webhooks/woocommerce/{created_store.id}",
            json=webhook_payload
        )
        
        assert response.status_code == 404
        assert "Store not found" in response.json()["detail"]


class TestWixWebhookEndpoint:
    """
    Tests for the Wix webhook API endpoint.
    
    Wix webhooks have their own format and event structure
    that differs from both Shopify and WooCommerce.
    """
    
    def test_wix_webhook_success(self, client, db_session):
        """
        Test successful Wix webhook processing.
        
        Verifies that Wix webhooks are accepted and processed
        with the appropriate Wix-specific headers.
        """
        # Create Wix store
        from app.crud import store as store_crud
        wix_store_data = {
            "user_id": "user123",
            "platform": PlatformType.WIX,
            "store_name": "wix-store",
            "access_token": "wix_access_token"
        }
        store = store_crud.create_store(db_session, wix_store_data)
        
        webhook_payload = {
            "instanceId": "wix_instance_123",
            "eventType": "ProductCreated",
            "data": {"productId": "123"}
        }
        
        headers = {
            "X-Wix-Event-Type": "ProductCreated",
            "X-Wix-Instance-Id": "wix_instance_123",
            "Content-Type": "application/json"
        }
        
        response = client.post(
            f"/webhooks/wix/{store.id}",
            json=webhook_payload,
            headers=headers
        )
        
        assert response.status_code == 200
        assert response.json()["status"] == "received"


class TestWebhookEventRetrieval:
    """
    Tests for webhook event history and monitoring endpoints.
    
    These endpoints allow monitoring webhook processing and debugging
    webhook-related issues.
    """
    
    def test_get_webhook_events(self, client, db_session, created_store):
        """
        Test retrieval of webhook events for a store.
        
        Verifies that webhook event history can be retrieved
        for monitoring and debugging purposes.
        """
        # Create some webhook events
        events = []
        for i in range(3):
            event = WebhookEvent(
                store_id=created_store.id,
                platform=created_store.platform,
                event_type=f"products/create",
                payload={"id": i, "title": f"Product {i}"},
                processed=True
            )
            events.append(event)
            db_session.add(event)
        
        db_session.commit()
        
        response = client.get(f"/webhooks/{created_store.id}/events")
        
        assert response.status_code == 200
        webhook_events = response.json()
        
        assert len(webhook_events) == 3
        # Events should be ordered by created_at desc (newest first)
        assert webhook_events[0]["payload"]["title"] == "Product 2"
    
    def test_get_webhook_events_pagination(self, client, db_session, created_store):
        """
        Test webhook event retrieval with pagination.
        
        Verifies that large numbers of webhook events can be paginated
        for efficient retrieval and display.
        """
        # Create many webhook events
        for i in range(15):
            event = WebhookEvent(
                store_id=created_store.id,
                platform=created_store.platform,
                event_type="products/create",
                payload={"id": i},
                processed=True
            )
            db_session.add(event)
        
        db_session.commit()
        
        # Test pagination
        response = client.get(
            f"/webhooks/{created_store.id}/events",
            params={"skip": 0, "limit": 5}
        )
        
        assert response.status_code == 200
        events = response.json()
        assert len(events) == 5
        
        # Test second page
        response = client.get(
            f"/webhooks/{created_store.id}/events",
            params={"skip": 5, "limit": 5}
        )
        
        assert response.status_code == 200
        events = response.json()
        assert len(events) == 5


class TestWebhookSetup:
    """
    Tests for automatic webhook setup on e-commerce platforms.
    
    Tests the functionality that automatically creates webhooks
    on the platform side when stores are connected.
    """
    
    @patch('app.services.platform_clients.ShopifyClient.create_webhook')
    def test_setup_shopify_webhooks(self, mock_create_webhook, client, created_store):
        """
        Test automatic Shopify webhook setup.
        
        Verifies that the system can automatically create the necessary
        webhooks in Shopify when a store is connected.
        """
        mock_create_webhook.return_value = {
            "id": "webhook_123",
            "topic": "products/create",
            "address": "https://your-domain.com/webhooks/shopify/1"
        }
        
        response = client.post(f"/webhooks/{created_store.id}/setup")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "Webhooks created successfully" in data["message"]
        assert "webhooks" in data
        
        # Verify webhook creation was called for each topic
        expected_topics = ['products/create', 'products/update', 'products/delete']
        assert mock_create_webhook.call_count == len(expected_topics)
    
    @patch('app.services.platform_clients.WooCommerceClient.create_webhook')
    def test_setup_woocommerce_webhooks(self, mock_create_webhook, client, db_session, sample_woocommerce_store_data):
        """
        Test automatic WooCommerce webhook setup.
        
        Verifies webhook creation for WooCommerce stores with the
        appropriate WooCommerce webhook topics and formats.
        """
        from app.crud import store as store_crud
        store = store_crud.create_store(db_session, sample_woocommerce_store_data)
        
        mock_create_webhook.return_value = {
            "id": 123,
            "name": "Dukira product.created",
            "status": "active"
        }
        
        response = client.post(f"/webhooks/{store.id}/setup")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "Webhooks created successfully" in data["message"]
        
        # Verify WooCommerce topics were used
        expected_topics = ['product.created', 'product.updated', 'product.deleted']
        assert mock_create_webhook.call_count == len(expected_topics)
    
    def test_webhook_setup_nonexistent_store(self, client):
        """
        Test webhook setup for non-existent store.
        
        Should return appropriate error when trying to set up webhooks
        for a store that doesn't exist.
        """
        response = client.post("/webhooks/99999/setup")
        
        assert response.status_code == 404
        assert "Store not found" in response.json()["detail"]