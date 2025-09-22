from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional, Dict, Any
from datetime import datetime

from ..models import Store, PlatformType
from ..schemas import StoreCreate, StoreUpdate


def get_store(db: Session, store_id: int) -> Optional[Store]:
    return db.query(Store).filter(Store.id == store_id).first()


def get_store_by_platform_id(
    db: Session, platform_store_id: str, platform: PlatformType
) -> Optional[Store]:
    return db.query(Store).filter(
        and_(
            Store.platform_store_id == platform_store_id,
            Store.platform == platform
        )
    ).first()


def get_stores_by_user(db: Session, user_id: str, skip: int = 0, limit: int = 100) -> List[Store]:
    return db.query(Store).filter(Store.user_id == user_id).offset(skip).limit(limit).all()


def get_stores_by_platform(db: Session, platform: PlatformType) -> List[Store]:
    return db.query(Store).filter(Store.platform == platform).all()


def create_store(db: Session, store_data: Dict[str, Any]) -> Store:
    db_store = Store(**store_data)
    db.add(db_store)
    db.commit()
    db.refresh(db_store)
    return db_store


def update_store(db: Session, store_id: int, store_data: Dict[str, Any]) -> Optional[Store]:
    db_store = db.query(Store).filter(Store.id == store_id).first()
    if db_store:
        for key, value in store_data.items():
            if hasattr(db_store, key):
                setattr(db_store, key, value)
        db_store.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_store)
    return db_store


def update_store_sync_time(db: Session, store_id: int) -> Optional[Store]:
    db_store = db.query(Store).filter(Store.id == store_id).first()
    if db_store:
        db_store.last_sync = datetime.utcnow()
        db_store.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_store)
    return db_store


def delete_store(db: Session, store_id: int) -> bool:
    db_store = db.query(Store).filter(Store.id == store_id).first()
    if db_store:
        db.delete(db_store)
        db.commit()
        return True
    return False


def get_stores_for_auto_sync(db: Session) -> List[Store]:
    """Get all stores that have auto_sync enabled"""
    return db.query(Store).filter(Store.auto_sync == True).all()


def refresh_token(db: Session, store_id: int, new_access_token: str, new_refresh_token: str = None) -> Optional[Store]:
    """Update store tokens after refresh"""
    db_store = db.query(Store).filter(Store.id == store_id).first()
    if db_store:
        db_store.access_token = new_access_token
        if new_refresh_token:
            db_store.refresh_token = new_refresh_token
        db_store.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_store)
    return db_store