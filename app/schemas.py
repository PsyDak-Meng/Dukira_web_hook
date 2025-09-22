from pydantic import BaseModel, HttpUrl
from typing import Optional, Dict, Any, List
from datetime import datetime
from .models import PlatformType, SyncStatus, ImageStatus


class StoreBase(BaseModel):
    user_id: str
    platform: PlatformType
    store_name: str
    store_url: Optional[str] = None
    auto_sync: bool = True


class StoreCreate(StoreBase):
    access_token: str
    refresh_token: Optional[str] = None
    platform_store_id: Optional[str] = None
    platform_data: Optional[Dict[str, Any]] = None


class StoreUpdate(BaseModel):
    store_name: Optional[str] = None
    store_url: Optional[str] = None
    auto_sync: Optional[bool] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None


class Store(StoreBase):
    id: int
    platform_store_id: Optional[str]
    last_sync: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class ProductVariantBase(BaseModel):
    platform_variant_id: str
    title: Optional[str] = None
    sku: Optional[str] = None
    price: Optional[str] = None
    inventory_quantity: Optional[int] = None


class ProductVariant(ProductVariantBase):
    id: int
    product_id: int
    barcode: Optional[str]
    compare_at_price: Optional[str]
    weight: Optional[str]
    option1: Optional[str]
    option2: Optional[str]
    option3: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ProductImageBase(BaseModel):
    platform_image_id: Optional[str]
    src: str
    alt_text: Optional[str] = None
    position: Optional[int] = None


class ProductImage(ProductImageBase):
    id: int
    product_id: int
    variant_id: Optional[int]
    status: ImageStatus
    ai_score: Optional[str]
    gcs_path: Optional[str]
    width: Optional[int]
    height: Optional[int]
    is_duplicate: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ProductBase(BaseModel):
    platform_product_id: str
    title: str
    description: Optional[str] = None
    vendor: Optional[str] = None
    product_type: Optional[str] = None
    tags: Optional[List[str]] = None


class Product(ProductBase):
    id: int
    store_id: int
    handle: Optional[str]
    status: Optional[str]
    published: bool
    variants: List[ProductVariant] = []
    images: List[ProductImage] = []
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class SyncJobBase(BaseModel):
    job_type: str
    status: SyncStatus = SyncStatus.PENDING


class SyncJob(SyncJobBase):
    id: int
    store_id: int
    total_products: int
    processed_products: int
    failed_products: int
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class WebhookEventCreate(BaseModel):
    store_id: int
    platform: PlatformType
    event_type: str
    platform_event_id: Optional[str]
    payload: Dict[str, Any]
    headers: Optional[Dict[str, str]] = None


class WebhookEvent(WebhookEventCreate):
    id: int
    processed: bool
    processed_at: Optional[datetime]
    error_message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class OAuthCallback(BaseModel):
    code: str
    state: Optional[str] = None
    shop: Optional[str] = None  # Shopify specific


class ImageProcessingResult(BaseModel):
    approved: bool
    score: float
    analysis: Dict[str, Any]
    gcs_path: Optional[str] = None


class ProductDisplayResponse(BaseModel):
    product: Product
    approved_images: List[ProductImage]
    store: Store