from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy.orm import Session
import logging

from .config import settings
from .database import engine, get_db
from .models import Base
from .routers import auth, webhooks, products
from .services.gcs_service import GCSService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="Webhook API for connecting to Shopify, WooCommerce, and Wix",
    version="1.0.0",
    debug=settings.debug
)

# Add security middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"] if settings.debug else ["yourdomain.com", "*.yourdomain.com"]
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else ["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(webhooks.router)
app.include_router(products.router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Dukira Webhook API",
        "version": "1.0.0",
        "status": "operational"
    }


@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint"""
    health_status = {
        "status": "healthy",
        "database": "connected",
        "gcs": "unknown"
    }
    
    # Check database connection
    try:
        db.execute("SELECT 1")
        health_status["database"] = "connected"
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        health_status["database"] = "disconnected"
        health_status["status"] = "unhealthy"
    
    # Check GCS connection
    try:
        gcs_service = GCSService()
        if gcs_service.health_check():
            health_status["gcs"] = "connected"
        else:
            health_status["gcs"] = "disconnected"
    except Exception as e:
        logger.error(f"GCS health check failed: {str(e)}")
        health_status["gcs"] = "error"
    
    if health_status["status"] == "unhealthy":
        raise HTTPException(status_code=503, detail=health_status)
    
    return health_status


@app.get("/info")
async def app_info():
    """Application information"""
    return {
        "app_name": settings.app_name,
        "version": "1.0.0",
        "supported_platforms": ["shopify", "woocommerce", "wix"],
        "features": {
            "oauth_authentication": True,
            "webhook_processing": True,
            "product_sync": True,
            "image_processing": True,
            "ai_filtering": bool(settings.ai_model_api_url),
            "cloud_storage": True
        },
        "endpoints": {
            "auth": "/auth",
            "webhooks": "/webhooks",
            "products": "/products",
            "docs": "/docs"
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info"
    )