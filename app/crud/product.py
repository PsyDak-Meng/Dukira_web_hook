from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List, Optional, Dict, Any
from datetime import datetime

from ..models import Product, ProductVariant, ProductImage, Store
from ..schemas import ProductBase


def get_product(db: Session, product_id: int) -> Optional[Product]:
    return db.query(Product).filter(Product.id == product_id).first()


def get_product_by_platform_id(
    db: Session, platform_product_id: str, store_id: int
) -> Optional[Product]:
    return db.query(Product).filter(
        and_(
            Product.platform_product_id == platform_product_id,
            Product.store_id == store_id
        )
    ).first()


def get_products_by_store(
    db: Session, store_id: int, skip: int = 0, limit: int = 100
) -> List[Product]:
    return db.query(Product).filter(
        Product.store_id == store_id
    ).offset(skip).limit(limit).all()


def create_product(db: Session, product_data: Dict[str, Any], store_id: int) -> Product:
    product_data["store_id"] = store_id
    db_product = Product(**product_data)
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product


def update_product(
    db: Session, product_id: int, product_data: Dict[str, Any]
) -> Optional[Product]:
    db_product = db.query(Product).filter(Product.id == product_id).first()
    if db_product:
        for key, value in product_data.items():
            if hasattr(db_product, key):
                setattr(db_product, key, value)
        db_product.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_product)
    return db_product


def delete_product(db: Session, product_id: int) -> bool:
    db_product = db.query(Product).filter(Product.id == product_id).first()
    if db_product:
        db.delete(db_product)
        db.commit()
        return True
    return False


def get_variant_by_platform_id(
    db: Session, platform_variant_id: str, product_id: int
) -> Optional[ProductVariant]:
    return db.query(ProductVariant).filter(
        and_(
            ProductVariant.platform_variant_id == platform_variant_id,
            ProductVariant.product_id == product_id
        )
    ).first()


def create_variant(db: Session, variant_data: Dict[str, Any], product_id: int) -> ProductVariant:
    variant_data["product_id"] = product_id
    db_variant = ProductVariant(**variant_data)
    db.add(db_variant)
    db.commit()
    db.refresh(db_variant)
    return db_variant


def update_variant(
    db: Session, variant_id: int, variant_data: Dict[str, Any]
) -> Optional[ProductVariant]:
    db_variant = db.query(ProductVariant).filter(ProductVariant.id == variant_id).first()
    if db_variant:
        for key, value in variant_data.items():
            if hasattr(db_variant, key):
                setattr(db_variant, key, value)
        db_variant.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_variant)
    return db_variant


def get_image_by_platform_id(
    db: Session, platform_image_id: str, product_id: int
) -> Optional[ProductImage]:
    return db.query(ProductImage).filter(
        and_(
            ProductImage.platform_image_id == platform_image_id,
            ProductImage.product_id == product_id
        )
    ).first()


def get_image_by_hash(db: Session, image_hash: str) -> Optional[ProductImage]:
    return db.query(ProductImage).filter(ProductImage.image_hash == image_hash).first()


def create_image(db: Session, image_data: Dict[str, Any], product_id: int, variant_id: int = None) -> ProductImage:
    image_data["product_id"] = product_id
    if variant_id:
        image_data["variant_id"] = variant_id
    db_image = ProductImage(**image_data)
    db.add(db_image)
    db.commit()
    db.refresh(db_image)
    return db_image


def update_image(
    db: Session, image_id: int, image_data: Dict[str, Any]
) -> Optional[ProductImage]:
    db_image = db.query(ProductImage).filter(ProductImage.id == image_id).first()
    if db_image:
        for key, value in image_data.items():
            if hasattr(db_image, key):
                setattr(db_image, key, value)
        db_image.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_image)
    return db_image


def get_pending_images(db: Session, limit: int = 100) -> List[ProductImage]:
    """Get images that need AI processing"""
    from ..models import ImageStatus
    return db.query(ProductImage).filter(
        ProductImage.status == ImageStatus.PENDING
    ).limit(limit).all()


def get_approved_images_by_product(db: Session, product_id: int) -> List[ProductImage]:
    """Get all approved images for a product"""
    from ..models import ImageStatus
    return db.query(ProductImage).filter(
        and_(
            ProductImage.product_id == product_id,
            ProductImage.status == ImageStatus.STORED,
            ProductImage.is_duplicate == False
        )
    ).order_by(ProductImage.position).all()


def search_products(
    db: Session, 
    query: str, 
    store_id: Optional[int] = None,
    skip: int = 0, 
    limit: int = 100
) -> List[Product]:
    """Search products by title, description, or tags"""
    search_filter = or_(
        Product.title.ilike(f"%{query}%"),
        Product.description.ilike(f"%{query}%"),
        Product.vendor.ilike(f"%{query}%")
    )
    
    if store_id:
        search_filter = and_(search_filter, Product.store_id == store_id)
    
    return db.query(Product).filter(search_filter).offset(skip).limit(limit).all()