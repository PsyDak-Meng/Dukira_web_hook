from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from typing import Optional
import secrets

from ..database import get_db
from ..models import Store, PlatformType
from ..schemas import OAuthCallback, Store as StoreSchema
from ..auth.oauth import shopify_oauth, woocommerce_oauth, wix_oauth
from ..crud import store as store_crud

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.get("/shopify/authorize")
async def shopify_authorize(
    shop: str = Query(..., description="Shopify shop domain (without .myshopify.com)"),
    user_id: str = Query(..., description="User ID to associate with this store")
):
    """
    Generate Shopify OAuth authorization URL
    """
    state = f"{user_id}:{secrets.token_urlsafe(16)}"
    auth_url = shopify_oauth.generate_auth_url(shop=shop, state=state)
    
    return {
        "auth_url": auth_url,
        "state": state,
        "shop": shop
    }


@router.get("/shopify/callback")
async def shopify_callback(
    code: str = Query(...),
    shop: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    Handle Shopify OAuth callback
    """
    try:
        # Extract user_id from state
        user_id = state.split(':')[0]
        
        # Exchange code for access token
        token_data = await shopify_oauth.exchange_code_for_token(code=code, shop=shop)
        
        # Create or update store
        store_data = {
            "user_id": user_id,
            "platform": PlatformType.SHOPIFY,
            "store_name": shop,
            "store_url": f"https://{shop}.myshopify.com",
            "access_token": token_data["access_token"],
            "platform_store_id": shop,
            "platform_data": token_data
        }
        
        # Check if store already exists
        existing_store = store_crud.get_store_by_platform_id(
            db, platform_store_id=shop, platform=PlatformType.SHOPIFY
        )
        
        if existing_store:
            store = store_crud.update_store(db, store_id=existing_store.id, store_data=store_data)
        else:
            store = store_crud.create_store(db, store_data=store_data)
        
        return {
            "message": "Store connected successfully",
            "store_id": store.id,
            "store_name": store.store_name
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth callback failed: {str(e)}")


@router.get("/woocommerce/authorize")
async def woocommerce_authorize(
    store_url: str = Query(..., description="WooCommerce store URL"),
    user_id: str = Query(..., description="User ID to associate with this store")
):
    """
    Generate WooCommerce OAuth authorization URL
    """
    state = f"{user_id}:{secrets.token_urlsafe(16)}"
    auth_url = woocommerce_oauth.generate_auth_url(store_url=store_url, state=state)
    
    return {
        "auth_url": auth_url,
        "state": state,
        "store_url": store_url
    }


@router.get("/woocommerce/callback")
async def woocommerce_callback(
    user_id: str = Query(...),
    key_id: str = Query(...),
    consumer_key: str = Query(...),
    consumer_secret: str = Query(...),
    success: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    Handle WooCommerce OAuth callback
    """
    try:
        if success != "1":
            raise HTTPException(status_code=400, detail="OAuth authorization was denied")
        
        # WooCommerce provides consumer key/secret directly
        token_data = {
            "consumer_key": consumer_key,
            "consumer_secret": consumer_secret,
            "key_id": key_id
        }
        
        # Note: We need the store_url, which should be passed in state or stored elsewhere
        # For now, we'll require it as a parameter
        store_url = Query(..., description="Store URL from authorization")
        
        store_data = {
            "user_id": user_id,
            "platform": PlatformType.WOOCOMMERCE,
            "store_name": store_url.replace("https://", "").replace("http://", ""),
            "store_url": store_url,
            "access_token": consumer_key,  # Using consumer_key as access_token
            "refresh_token": consumer_secret,  # Using consumer_secret as refresh_token
            "platform_store_id": key_id,
            "platform_data": token_data
        }
        
        # Check if store already exists
        existing_store = store_crud.get_store_by_platform_id(
            db, platform_store_id=key_id, platform=PlatformType.WOOCOMMERCE
        )
        
        if existing_store:
            store = store_crud.update_store(db, store_id=existing_store.id, store_data=store_data)
        else:
            store = store_crud.create_store(db, store_data=store_data)
        
        return {
            "message": "Store connected successfully",
            "store_id": store.id,
            "store_name": store.store_name
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth callback failed: {str(e)}")


@router.get("/wix/authorize")
async def wix_authorize(
    user_id: str = Query(..., description="User ID to associate with this store")
):
    """
    Generate Wix OAuth authorization URL
    """
    state = f"{user_id}:{secrets.token_urlsafe(16)}"
    auth_url = wix_oauth.generate_auth_url(state=state)
    
    return {
        "auth_url": auth_url,
        "state": state
    }


@router.get("/wix/callback")
async def wix_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    Handle Wix OAuth callback
    """
    try:
        # Extract user_id from state
        user_id = state.split(':')[0]
        
        # Exchange code for access token
        token_data = await wix_oauth.exchange_code_for_token(code=code)
        
        # Get site info using the access token
        # Note: You'll need to implement Wix API calls to get site details
        
        store_data = {
            "user_id": user_id,
            "platform": PlatformType.WIX,
            "store_name": "Wix Store",  # Update with actual store name from API
            "access_token": token_data["access_token"],
            "refresh_token": token_data.get("refresh_token"),
            "platform_data": token_data
        }
        
        store = store_crud.create_store(db, store_data=store_data)
        
        return {
            "message": "Store connected successfully",
            "store_id": store.id,
            "store_name": store.store_name
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth callback failed: {str(e)}")


@router.get("/stores/{user_id}")
async def get_user_stores(user_id: str, db: Session = Depends(get_db)):
    """
    Get all stores connected by a user
    """
    stores = store_crud.get_stores_by_user(db, user_id=user_id)
    return stores


@router.delete("/stores/{store_id}")
async def disconnect_store(store_id: int, db: Session = Depends(get_db)):
    """
    Disconnect a store (delete from database)
    """
    store = store_crud.get_store(db, store_id=store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    store_crud.delete_store(db, store_id=store_id)
    return {"message": "Store disconnected successfully"}