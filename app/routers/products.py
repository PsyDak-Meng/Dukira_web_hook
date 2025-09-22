from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from ..database import get_db
from ..models import Store, Product, ProductImage, ImageStatus
from ..schemas import Product as ProductSchema, ProductDisplayResponse
from ..crud import store as store_crud, product as product_crud
from ..services.sync_service import sync_store_task
from ..services.gcs_service import GCSService

router = APIRouter(prefix="/products", tags=["products"])
logger = logging.getLogger(__name__)


@router.post("/sync/{store_id}")
async def sync_store_products(
    store_id: int,
    background_tasks: BackgroundTasks,
    job_type: str = Query("full_sync", description="Type of sync: full_sync or incremental"),
    db: Session = Depends(get_db)
):
    """
    Trigger product sync for a store
    """
    store = store_crud.get_store(db, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    # Queue sync job
    background_tasks.add_task(sync_store_task.delay, store_id, job_type)
    
    return {
        "message": f"Sync job queued for store {store.store_name}",
        "store_id": store_id,
        "job_type": job_type
    }


@router.get("/store/{store_id}")
async def get_store_products(
    store_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """
    Get all products for a store
    """
    store = store_crud.get_store(db, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    products = product_crud.get_products_by_store(db, store_id, skip, limit)
    
    return {
        "store": store,
        "products": products,
        "total": len(products),
        "skip": skip,
        "limit": limit
    }


@router.get("/{product_id}")
async def get_product(product_id: int, db: Session = Depends(get_db)):
    """
    Get a single product with all its variants and approved images
    """
    product = product_crud.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Get approved images
    approved_images = product_crud.get_approved_images_by_product(db, product_id)
    
    # Get store info
    store = store_crud.get_store(db, product.store_id)
    
    return ProductDisplayResponse(
        product=product,
        approved_images=approved_images,
        store=store
    )


@router.get("/{product_id}/images")
async def get_product_images(
    product_id: int,
    include_urls: bool = Query(False, description="Include signed URLs for images"),
    db: Session = Depends(get_db)
):
    """
    Get all approved images for a product with optional signed URLs
    """
    product = product_crud.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    approved_images = product_crud.get_approved_images_by_product(db, product_id)
    
    if include_urls:
        gcs_service = GCSService()
        
        # Add signed URLs to images
        for image in approved_images:
            if image.gcs_path:
                signed_url = await gcs_service.get_image_url(image.gcs_path)
                image.signed_url = signed_url
            else:
                image.signed_url = None
    
    return {
        "product_id": product_id,
        "images": approved_images,
        "total_images": len(approved_images)
    }


@router.get("/search")
async def search_products(
    q: str = Query(..., min_length=2, description="Search query"),
    store_id: Optional[int] = Query(None, description="Filter by store ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """
    Search products by title, description, or vendor
    """
    products = product_crud.search_products(db, q, store_id, skip, limit)
    
    return {
        "query": q,
        "products": products,
        "total": len(products),
        "skip": skip,
        "limit": limit
    }


@router.get("/user/{user_id}")
async def get_user_products(
    user_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    include_images: bool = Query(False, description="Include approved images"),
    db: Session = Depends(get_db)
):
    """
    Get all products for all stores belonging to a user
    """
    # Get user's stores
    stores = store_crud.get_stores_by_user(db, user_id)
    if not stores:
        return {
            "user_id": user_id,
            "products": [],
            "total": 0
        }
    
    # Get products from all stores
    all_products = []
    for store in stores:
        store_products = product_crud.get_products_by_store(db, store.id, 0, 1000)
        
        # Add store info to each product
        for product in store_products:
            product.store_info = {
                "id": store.id,
                "name": store.store_name,
                "platform": store.platform
            }
            
            # Add approved images if requested
            if include_images:
                product.approved_images = product_crud.get_approved_images_by_product(db, product.id)
        
        all_products.extend(store_products)
    
    # Apply pagination
    paginated_products = all_products[skip:skip + limit]
    
    return {
        "user_id": user_id,
        "products": paginated_products,
        "total": len(all_products),
        "skip": skip,
        "limit": limit,
        "stores": len(stores)
    }


@router.get("/display/{product_id}")
async def get_product_for_display(
    product_id: int,
    variant_id: Optional[int] = Query(None, description="Specific variant ID"),
    image_size: str = Query("original", description="Image size preference"),
    db: Session = Depends(get_db)
):
    """
    Get product data optimized for plugin display
    """
    product = product_crud.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Get store info
    store = store_crud.get_store(db, product.store_id)
    
    # Get approved images
    approved_images = product_crud.get_approved_images_by_product(db, product_id)
    
    # Filter images by variant if specified
    if variant_id:
        variant_images = [img for img in approved_images if img.variant_id == variant_id]
        if variant_images:
            approved_images = variant_images
    
    # Generate signed URLs for images
    gcs_service = GCSService()
    image_urls = []
    
    for image in approved_images:
        if image.gcs_path:
            signed_url = await gcs_service.get_image_url(image.gcs_path)
            if signed_url:
                image_urls.append({
                    "id": image.id,
                    "url": signed_url,
                    "alt_text": image.alt_text,
                    "position": image.position,
                    "width": image.width,
                    "height": image.height
                })
    
    # Get specific variant if requested
    selected_variant = None
    if variant_id:
        selected_variant = next((v for v in product.variants if v.id == variant_id), None)
    
    return {
        "product": {
            "id": product.id,
            "title": product.title,
            "description": product.description,
            "vendor": product.vendor,
            "product_type": product.product_type,
            "tags": product.tags,
            "handle": product.handle
        },
        "store": {
            "id": store.id,
            "name": store.store_name,
            "platform": store.platform
        },
        "variant": selected_variant,
        "variants": product.variants,
        "images": image_urls,
        "total_images": len(image_urls)
    }


@router.get("/stats/{store_id}")
async def get_store_product_stats(store_id: int, db: Session = Depends(get_db)):
    """
    Get product and image statistics for a store
    """
    from sqlalchemy import func
    
    store = store_crud.get_store(db, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    # Product counts
    total_products = db.query(func.count(Product.id)).filter(Product.store_id == store_id).scalar()
    published_products = db.query(func.count(Product.id)).filter(
        Product.store_id == store_id,
        Product.published == True
    ).scalar()
    
    # Image counts by status
    image_stats = db.query(
        ProductImage.status,
        func.count(ProductImage.id).label('count')
    ).join(Product).filter(
        Product.store_id == store_id
    ).group_by(ProductImage.status).all()
    
    image_counts = {status.value: count for status, count in image_stats}
    
    # Variant count
    total_variants = db.query(func.count(Product.id)).join(Product).filter(
        Product.store_id == store_id
    ).scalar()
    
    return {
        "store_id": store_id,
        "store_name": store.store_name,
        "products": {
            "total": total_products,
            "published": published_products,
            "draft": total_products - published_products
        },
        "variants": {
            "total": total_variants
        },
        "images": image_counts,
        "last_sync": store.last_sync
    }