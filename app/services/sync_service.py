from celery import Celery
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
import asyncio
from datetime import datetime
import logging

from ..database import SessionLocal
from ..models import Store, Product, ProductVariant, ProductImage, SyncJob, SyncStatus, ImageStatus
from ..crud import store as store_crud, product as product_crud
from .platform_clients import get_platform_client
from .image_service import ImageService

# Initialize Celery
celery_app = Celery('dukira_sync')
celery_app.config_from_object('app.celery_config')

logger = logging.getLogger(__name__)


class SyncService:
    def __init__(self, db: Session):
        self.db = db
        self.image_service = ImageService()
    
    async def sync_store_products(self, store_id: int, job_type: str = "full_sync") -> SyncJob:
        """Sync all products for a store"""
        store = store_crud.get_store(self.db, store_id)
        if not store:
            raise ValueError(f"Store {store_id} not found")
        
        # Create sync job
        sync_job = SyncJob(
            store_id=store_id,
            job_type=job_type,
            status=SyncStatus.IN_PROGRESS,
            started_at=datetime.utcnow()
        )
        self.db.add(sync_job)
        self.db.commit()
        self.db.refresh(sync_job)
        
        try:
            client = get_platform_client(store)
            
            # Get product count for progress tracking
            if hasattr(client, 'get_product_count'):
                total_products = await client.get_product_count()
                sync_job.total_products = total_products
                self.db.commit()
            
            # Sync products in batches
            processed = 0
            failed = 0
            since_id = None
            
            while True:
                try:
                    products = await client.get_products(limit=50, since_id=since_id)
                    if not products:
                        break
                    
                    for product_data in products:
                        try:
                            await self._sync_single_product(store, product_data)
                            processed += 1
                        except Exception as e:
                            logger.error(f"Failed to sync product {product_data.get('id')}: {str(e)}")
                            failed += 1
                        
                        # Update progress
                        sync_job.processed_products = processed
                        sync_job.failed_products = failed
                        self.db.commit()
                    
                    # Update since_id for pagination
                    since_id = products[-1].get('id')
                    
                except Exception as e:
                    logger.error(f"Batch sync error: {str(e)}")
                    failed += len(products) if 'products' in locals() else 0
                    break
            
            # Complete sync job
            sync_job.status = SyncStatus.COMPLETED
            sync_job.completed_at = datetime.utcnow()
            
            # Update store last sync time
            store_crud.update_store_sync_time(self.db, store_id)
            
        except Exception as e:
            logger.error(f"Sync job {sync_job.id} failed: {str(e)}")
            sync_job.status = SyncStatus.FAILED
            sync_job.error_message = str(e)
            sync_job.completed_at = datetime.utcnow()
        
        self.db.commit()
        return sync_job
    
    async def _sync_single_product(self, store: Store, product_data: Dict[str, Any]):
        """Sync a single product and its variants/images"""
        platform_product_id = str(product_data.get('id'))
        
        # Check if product already exists
        existing_product = product_crud.get_product_by_platform_id(
            self.db, platform_product_id, store.id
        )
        
        # Prepare product data
        product_update_data = self._extract_product_data(product_data, store.platform)
        
        if existing_product:
            # Update existing product
            product = product_crud.update_product(
                self.db, existing_product.id, product_update_data
            )
        else:
            # Create new product
            product = product_crud.create_product(
                self.db, product_update_data, store.id
            )
        
        # Sync variants
        variants_data = product_data.get('variants', [])
        for variant_data in variants_data:
            await self._sync_product_variant(product, variant_data, store.platform)
        
        # Sync images
        images_data = product_data.get('images', [])
        for image_data in images_data:
            await self._sync_product_image(product, image_data, store.platform)
    
    async def _sync_product_variant(self, product: Product, variant_data: Dict[str, Any], platform: str):
        """Sync a single product variant"""
        platform_variant_id = str(variant_data.get('id'))
        
        existing_variant = product_crud.get_variant_by_platform_id(
            self.db, platform_variant_id, product.id
        )
        
        variant_update_data = self._extract_variant_data(variant_data, platform)
        
        if existing_variant:
            product_crud.update_variant(self.db, existing_variant.id, variant_update_data)
        else:
            product_crud.create_variant(self.db, variant_update_data, product.id)
    
    async def _sync_product_image(self, product: Product, image_data: Dict[str, Any], platform: str):
        """Sync a single product image"""
        platform_image_id = str(image_data.get('id', ''))
        image_url = image_data.get('src') or image_data.get('url')
        
        if not image_url:
            return
        
        existing_image = product_crud.get_image_by_platform_id(
            self.db, platform_image_id, product.id
        )
        
        image_update_data = self._extract_image_data(image_data, platform)
        
        if existing_image:
            product_crud.update_image(self.db, existing_image.id, image_update_data)
        else:
            # Create new image and queue for processing
            image = product_crud.create_image(self.db, image_update_data, product.id)
            
            # Queue image for AI processing
            process_image_task.delay(image.id)
    
    def _extract_product_data(self, product_data: Dict[str, Any], platform: str) -> Dict[str, Any]:
        """Extract and normalize product data based on platform"""
        if platform == "shopify":
            return {
                "platform_product_id": str(product_data.get('id')),
                "title": product_data.get('title'),
                "description": product_data.get('body_html'),
                "vendor": product_data.get('vendor'),
                "product_type": product_data.get('product_type'),
                "tags": product_data.get('tags', '').split(', ') if product_data.get('tags') else [],
                "handle": product_data.get('handle'),
                "status": product_data.get('status'),
                "published": product_data.get('status') == 'active',
                "platform_data": product_data
            }
        elif platform == "woocommerce":
            return {
                "platform_product_id": str(product_data.get('id')),
                "title": product_data.get('name'),
                "description": product_data.get('description'),
                "product_type": product_data.get('type'),
                "tags": [tag.get('name') for tag in product_data.get('tags', [])],
                "handle": product_data.get('slug'),
                "status": product_data.get('status'),
                "published": product_data.get('status') == 'publish',
                "platform_data": product_data
            }
        elif platform == "wix":
            return {
                "platform_product_id": str(product_data.get('id')),
                "title": product_data.get('name'),
                "description": product_data.get('description'),
                "product_type": product_data.get('productType'),
                "status": 'active',  # Wix doesn't have explicit status
                "published": True,
                "platform_data": product_data
            }
        
        return {}
    
    def _extract_variant_data(self, variant_data: Dict[str, Any], platform: str) -> Dict[str, Any]:
        """Extract and normalize variant data based on platform"""
        if platform == "shopify":
            return {
                "platform_variant_id": str(variant_data.get('id')),
                "title": variant_data.get('title'),
                "sku": variant_data.get('sku'),
                "barcode": variant_data.get('barcode'),
                "price": variant_data.get('price'),
                "compare_at_price": variant_data.get('compare_at_price'),
                "inventory_quantity": variant_data.get('inventory_quantity'),
                "weight": variant_data.get('weight'),
                "option1": variant_data.get('option1'),
                "option2": variant_data.get('option2'),
                "option3": variant_data.get('option3'),
                "platform_data": variant_data
            }
        elif platform == "woocommerce":
            return {
                "platform_variant_id": str(variant_data.get('id')),
                "title": variant_data.get('name'),
                "sku": variant_data.get('sku'),
                "price": variant_data.get('price'),
                "inventory_quantity": variant_data.get('stock_quantity'),
                "weight": variant_data.get('weight'),
                "platform_data": variant_data
            }
        elif platform == "wix":
            return {
                "platform_variant_id": str(variant_data.get('id', '')),
                "title": variant_data.get('choices', {}).get('title'),
                "sku": variant_data.get('variant', {}).get('sku'),
                "price": str(variant_data.get('variant', {}).get('price', 0)),
                "platform_data": variant_data
            }
        
        return {}
    
    def _extract_image_data(self, image_data: Dict[str, Any], platform: str) -> Dict[str, Any]:
        """Extract and normalize image data based on platform"""
        if platform == "shopify":
            return {
                "platform_image_id": str(image_data.get('id')),
                "src": image_data.get('src'),
                "alt_text": image_data.get('alt'),
                "position": image_data.get('position'),
                "width": image_data.get('width'),
                "height": image_data.get('height'),
                "status": ImageStatus.PENDING
            }
        elif platform == "woocommerce":
            return {
                "platform_image_id": str(image_data.get('id')),
                "src": image_data.get('src'),
                "alt_text": image_data.get('alt'),
                "position": image_data.get('position'),
                "status": ImageStatus.PENDING
            }
        elif platform == "wix":
            return {
                "src": image_data.get('url'),
                "alt_text": image_data.get('alt_text'),
                "status": ImageStatus.PENDING
            }
        
        return {}


# Celery tasks
@celery_app.task
def sync_store_task(store_id: int, job_type: str = "full_sync"):
    """Celery task to sync store products"""
    db = SessionLocal()
    try:
        sync_service = SyncService(db)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(sync_service.sync_store_products(store_id, job_type))
        return result.id
    finally:
        db.close()


@celery_app.task
def process_image_task(image_id: int):
    """Celery task to process a single image"""
    db = SessionLocal()
    try:
        image_service = ImageService()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(image_service.process_image(db, image_id))
    finally:
        db.close()


@celery_app.task
def auto_sync_all_stores():
    """Celery task to auto-sync all stores with auto_sync enabled"""
    db = SessionLocal()
    try:
        stores = store_crud.get_stores_for_auto_sync(db)
        for store in stores:
            sync_store_task.delay(store.id, "incremental")
    finally:
        db.close()