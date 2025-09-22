from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    database_url: str
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # JWT
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Google Cloud Storage
    google_cloud_project_id: str
    google_cloud_bucket_name: str
    google_application_credentials: Optional[str] = None
    
    # Shopify OAuth
    shopify_client_id: str
    shopify_client_secret: str
    shopify_redirect_uri: str
    
    # WooCommerce OAuth
    woocommerce_client_id: str
    woocommerce_client_secret: str
    woocommerce_redirect_uri: str
    
    # Wix OAuth
    wix_client_id: str
    wix_client_secret: str
    wix_redirect_uri: str
    
    # AI Model
    ai_model_api_url: Optional[str] = None
    ai_model_api_key: Optional[str] = None
    
    # App Settings
    app_name: str = "Dukira Webhook API"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    class Config:
        env_file = ".env"


settings = Settings()