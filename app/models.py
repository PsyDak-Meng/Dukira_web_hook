from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, JSON, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum as PyEnum
from .database import Base


class PlatformType(PyEnum):
    SHOPIFY = "shopify"
    WOOCOMMERCE = "woocommerce"
    WIX = "wix"


class SyncStatus(PyEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ImageStatus(PyEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    APPROVED = "approved"
    REJECTED = "rejected"
    STORED = "stored"


class Store(Base):
    __tablename__ = "stores"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    platform = Column(Enum(PlatformType), nullable=False)
    store_name = Column(String, nullable=False)
    store_url = Column(String)
    
    # OAuth tokens
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text)
    token_expires_at = Column(DateTime)
    
    # Platform-specific data
    platform_store_id = Column(String)
    platform_data = Column(JSON)
    
    # Sync settings
    auto_sync = Column(Boolean, default=True)
    last_sync = Column(DateTime)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    products = relationship("Product", back_populates="store")
    sync_jobs = relationship("SyncJob", back_populates="store")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    
    # Platform product data
    platform_product_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    vendor = Column(String)
    product_type = Column(String)
    tags = Column(JSON)
    handle = Column(String)
    
    # Product status
    status = Column(String)
    published = Column(Boolean, default=True)
    
    # SEO
    seo_title = Column(String)
    seo_description = Column(Text)
    
    # Platform-specific data
    platform_data = Column(JSON)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    store = relationship("Store", back_populates="products")
    variants = relationship("ProductVariant", back_populates="product")
    images = relationship("ProductImage", back_populates="product")


class ProductVariant(Base):
    __tablename__ = "product_variants"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    
    # Platform variant data
    platform_variant_id = Column(String, nullable=False, index=True)
    title = Column(String)
    sku = Column(String, index=True)
    barcode = Column(String)
    
    # Pricing
    price = Column(String)
    compare_at_price = Column(String)
    cost_per_item = Column(String)
    
    # Inventory
    inventory_quantity = Column(Integer)
    inventory_management = Column(String)
    inventory_policy = Column(String)
    
    # Physical properties
    weight = Column(String)
    weight_unit = Column(String)
    
    # Options
    option1 = Column(String)
    option2 = Column(String)
    option3 = Column(String)
    
    # Platform-specific data
    platform_data = Column(JSON)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    product = relationship("Product", back_populates="variants")
    images = relationship("ProductImage", back_populates="variant")


class ProductImage(Base):
    __tablename__ = "product_images"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    variant_id = Column(Integer, ForeignKey("product_variants.id"), nullable=True)
    
    # Platform image data
    platform_image_id = Column(String, index=True)
    src = Column(String, nullable=False)
    alt_text = Column(String)
    position = Column(Integer)
    
    # Processing status
    status = Column(Enum(ImageStatus), default=ImageStatus.PENDING)
    ai_score = Column(String)
    ai_analysis = Column(JSON)
    
    # Storage
    gcs_path = Column(String)
    local_path = Column(String)
    
    # Image properties
    width = Column(Integer)
    height = Column(Integer)
    file_size = Column(Integer)
    content_type = Column(String)
    
    # Deduplication
    image_hash = Column(String, index=True)
    is_duplicate = Column(Boolean, default=False)
    original_image_id = Column(Integer, ForeignKey("product_images.id"))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    product = relationship("Product", back_populates="images")
    variant = relationship("ProductVariant", back_populates="images")


class SyncJob(Base):
    __tablename__ = "sync_jobs"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    
    # Job details
    job_type = Column(String, nullable=False)  # 'full_sync', 'incremental', 'webhook'
    status = Column(Enum(SyncStatus), default=SyncStatus.PENDING)
    
    # Progress tracking
    total_products = Column(Integer, default=0)
    processed_products = Column(Integer, default=0)
    failed_products = Column(Integer, default=0)
    
    # Error handling
    error_message = Column(Text)
    error_details = Column(JSON)
    
    # Timing
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    store = relationship("Store", back_populates="sync_jobs")


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    
    # Event details
    platform = Column(Enum(PlatformType), nullable=False)
    event_type = Column(String, nullable=False)  # 'product/create', 'product/update', etc.
    platform_event_id = Column(String, index=True)
    
    # Payload
    payload = Column(JSON, nullable=False)
    headers = Column(JSON)
    
    # Processing
    processed = Column(Boolean, default=False)
    processed_at = Column(DateTime)
    error_message = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    store = relationship("Store")