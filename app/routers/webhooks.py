from fastapi import APIRouter, Depends, HTTPException, Request, Header, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
import hmac
import hashlib
import base64
import json
import logging

from ..database import get_db
from ..models import Store, WebhookEvent, PlatformType
from ..crud import store as store_crud
from ..services.sync_service import SyncService
from ..auth.oauth import shopify_oauth

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)


async def verify_shopify_webhook(payload: bytes, signature: str, store: Store) -> bool:
    """Verify Shopify webhook signature"""
    webhook_secret = store.platform_data.get('webhook_secret') if store.platform_data else None
    if not webhook_secret:
        # Fallback to using access token as secret (not recommended for production)
        webhook_secret = store.access_token
    
    return await shopify_oauth.verify_webhook(payload, signature, webhook_secret)


async def verify_woocommerce_webhook(payload: bytes, signature: str, store: Store) -> bool:
    """Verify WooCommerce webhook signature"""
    webhook_secret = store.platform_data.get('webhook_secret') if store.platform_data else None
    if not webhook_secret:
        return True  # WooCommerce webhooks might not always have secrets
    
    expected_signature = base64.b64encode(
        hmac.new(webhook_secret.encode(), payload, hashlib.sha256).digest()
    ).decode()
    
    return hmac.compare_digest(expected_signature, signature)


async def process_webhook_event(
    db: Session, 
    store: Store, 
    event_type: str, 
    payload: Dict[str, Any],
    headers: Dict[str, str]
):
    """Process webhook event and trigger appropriate sync actions"""
    # Store webhook event
    webhook_event = WebhookEvent(
        store_id=store.id,
        platform=store.platform,
        event_type=event_type,
        platform_event_id=payload.get('id'),
        payload=payload,
        headers=headers
    )
    db.add(webhook_event)
    db.commit()
    
    # Determine sync action based on event type
    sync_service = SyncService(db)
    
    try:
        if event_type in ['product/create', 'product/update', 'product.created', 'product.updated']:
            # Sync specific product
            product_id = str(payload.get('id'))
            if product_id:
                await sync_service._sync_single_product(store, payload)
        
        elif event_type in ['product/delete', 'product.deleted']:
            # Handle product deletion
            product_id = str(payload.get('id'))
            if product_id:
                from ..crud import product as product_crud
                existing_product = product_crud.get_product_by_platform_id(
                    db, product_id, store.id
                )
                if existing_product:
                    product_crud.delete_product(db, existing_product.id)
        
        # Mark webhook as processed
        webhook_event.processed = True
        webhook_event.processed_at = db.utcnow()
        db.commit()
        
    except Exception as e:
        logger.error(f"Failed to process webhook {webhook_event.id}: {str(e)}")
        webhook_event.error_message = str(e)
        db.commit()


@router.post("/shopify/{store_id}")
async def shopify_webhook(
    store_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    x_shopify_hmac_sha256: Optional[str] = Header(None),
    x_shopify_topic: Optional[str] = Header(None),
    x_shopify_shop_domain: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Handle Shopify webhooks
    """
    # Get store
    store = store_crud.get_store(db, store_id)
    if not store or store.platform != PlatformType.SHOPIFY:
        raise HTTPException(status_code=404, detail="Store not found")
    
    # Get request body
    body = await request.body()
    
    # Verify webhook signature
    if x_shopify_hmac_sha256:
        is_valid = await verify_shopify_webhook(body, x_shopify_hmac_sha256, store)
        if not is_valid:
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
    
    # Parse payload
    try:
        payload = json.loads(body.decode('utf-8'))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    
    # Get headers
    headers = {
        "x-shopify-topic": x_shopify_topic,
        "x-shopify-shop-domain": x_shopify_shop_domain,
        "x-shopify-hmac-sha256": x_shopify_hmac_sha256
    }
    
    # Process webhook in background
    background_tasks.add_task(
        process_webhook_event,
        db, store, x_shopify_topic or "unknown", payload, headers
    )
    
    return {"status": "received"}


@router.post("/woocommerce/{store_id}")
async def woocommerce_webhook(
    store_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    x_wc_webhook_signature: Optional[str] = Header(None),
    x_wc_webhook_event: Optional[str] = Header(None),
    x_wc_webhook_resource: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Handle WooCommerce webhooks
    """
    # Get store
    store = store_crud.get_store(db, store_id)
    if not store or store.platform != PlatformType.WOOCOMMERCE:
        raise HTTPException(status_code=404, detail="Store not found")
    
    # Get request body
    body = await request.body()
    
    # Verify webhook signature (if provided)
    if x_wc_webhook_signature:
        is_valid = await verify_woocommerce_webhook(body, x_wc_webhook_signature, store)
        if not is_valid:
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
    
    # Parse payload
    try:
        payload = json.loads(body.decode('utf-8'))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    
    # Get headers
    headers = {
        "x-wc-webhook-event": x_wc_webhook_event,
        "x-wc-webhook-resource": x_wc_webhook_resource,
        "x-wc-webhook-signature": x_wc_webhook_signature
    }
    
    # Construct event type
    event_type = f"{x_wc_webhook_resource}.{x_wc_webhook_event}" if x_wc_webhook_resource and x_wc_webhook_event else "unknown"
    
    # Process webhook in background
    background_tasks.add_task(
        process_webhook_event,
        db, store, event_type, payload, headers
    )
    
    return {"status": "received"}


@router.post("/wix/{store_id}")
async def wix_webhook(
    store_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    x_wix_event_type: Optional[str] = Header(None),
    x_wix_instance_id: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Handle Wix webhooks
    """
    # Get store
    store = store_crud.get_store(db, store_id)
    if not store or store.platform != PlatformType.WIX:
        raise HTTPException(status_code=404, detail="Store not found")
    
    # Get request body
    body = await request.body()
    
    # Parse payload
    try:
        payload = json.loads(body.decode('utf-8'))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    
    # Get headers
    headers = {
        "x-wix-event-type": x_wix_event_type,
        "x-wix-instance-id": x_wix_instance_id
    }
    
    # Process webhook in background
    background_tasks.add_task(
        process_webhook_event,
        db, store, x_wix_event_type or "unknown", payload, headers
    )
    
    return {"status": "received"}


@router.get("/{store_id}/events")
async def get_webhook_events(
    store_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Get webhook events for a store
    """
    store = store_crud.get_store(db, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    events = db.query(WebhookEvent).filter(
        WebhookEvent.store_id == store_id
    ).order_by(WebhookEvent.created_at.desc()).offset(skip).limit(limit).all()
    
    return events


@router.post("/{store_id}/setup")
async def setup_webhooks(store_id: int, db: Session = Depends(get_db)):
    """
    Set up webhooks for a store
    """
    store = store_crud.get_store(db, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    from ..services.platform_clients import get_platform_client
    from ..config import settings
    
    client = get_platform_client(store)
    webhook_url = f"https://your-domain.com/webhooks/{store.platform.value}/{store_id}"
    
    try:
        if store.platform == PlatformType.SHOPIFY:
            # Set up Shopify webhooks
            topics = ['products/create', 'products/update', 'products/delete']
            created_webhooks = []
            
            for topic in topics:
                webhook = await client.create_webhook(topic, webhook_url)
                created_webhooks.append(webhook)
            
            return {"message": "Webhooks created successfully", "webhooks": created_webhooks}
        
        elif store.platform == PlatformType.WOOCOMMERCE:
            # Set up WooCommerce webhooks
            topics = ['product.created', 'product.updated', 'product.deleted']
            created_webhooks = []
            
            for topic in topics:
                webhook = await client.create_webhook(topic, webhook_url)
                created_webhooks.append(webhook)
            
            return {"message": "Webhooks created successfully", "webhooks": created_webhooks}
        
        else:
            return {"message": "Webhook setup not implemented for this platform"}
    
    except Exception as e:
        logger.error(f"Failed to setup webhooks for store {store_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to setup webhooks: {str(e)}")