import httpx
import secrets
from typing import Dict, Any, Optional
from urllib.parse import urlencode, parse_qs, urlparse
from ..config import settings


class OAuthProvider:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
    
    def generate_auth_url(self, scopes: list = None, state: str = None) -> str:
        raise NotImplementedError
    
    async def exchange_code_for_token(self, code: str, **kwargs) -> Dict[str, Any]:
        raise NotImplementedError


class ShopifyOAuth(OAuthProvider):
    def __init__(self):
        super().__init__(
            settings.shopify_client_id,
            settings.shopify_client_secret,
            settings.shopify_redirect_uri
        )
        self.base_url = "https://{shop}.myshopify.com"
    
    def generate_auth_url(self, shop: str, scopes: list = None, state: str = None) -> str:
        if not scopes:
            scopes = ["read_products", "read_product_listings", "write_products"]
        
        if not state:
            state = secrets.token_urlsafe(32)
        
        params = {
            "client_id": self.client_id,
            "scope": ",".join(scopes),
            "redirect_uri": self.redirect_uri,
            "state": state
        }
        
        shop_url = f"https://{shop}.myshopify.com"
        return f"{shop_url}/admin/oauth/authorize?{urlencode(params)}"
    
    async def exchange_code_for_token(self, code: str, shop: str, **kwargs) -> Dict[str, Any]:
        token_url = f"https://{shop}.myshopify.com/admin/oauth/access_token"
        
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(token_url, data=data)
            response.raise_for_status()
            return response.json()
    
    async def verify_webhook(self, payload: bytes, signature: str, secret: str) -> bool:
        import hmac
        import hashlib
        import base64
        
        calculated_hmac = base64.b64encode(
            hmac.new(secret.encode('utf-8'), payload, hashlib.sha256).digest()
        ).decode()
        
        return hmac.compare_digest(calculated_hmac, signature)


class WooCommerceOAuth(OAuthProvider):
    def __init__(self):
        super().__init__(
            settings.woocommerce_client_id,
            settings.woocommerce_client_secret,
            settings.woocommerce_redirect_uri
        )
    
    def generate_auth_url(self, store_url: str, scopes: list = None, state: str = None) -> str:
        if not scopes:
            scopes = ["read", "write"]
        
        if not state:
            state = secrets.token_urlsafe(32)
        
        params = {
            "app_name": "Dukira Webhook Integration",
            "scope": ",".join(scopes),
            "user_id": state,
            "return_url": self.redirect_uri,
            "callback_url": self.redirect_uri
        }
        
        return f"{store_url}/wc-auth/v1/authorize?{urlencode(params)}"
    
    async def exchange_code_for_token(self, **kwargs) -> Dict[str, Any]:
        # WooCommerce uses a different flow - tokens are provided in the callback
        # This method handles the callback data
        return kwargs


class WixOAuth(OAuthProvider):
    def __init__(self):
        super().__init__(
            settings.wix_client_id,
            settings.wix_client_secret,
            settings.wix_redirect_uri
        )
        self.auth_url = "https://www.wix.com/oauth/authorize"
        self.token_url = "https://www.wix.com/oauth/access_token"
    
    def generate_auth_url(self, scopes: list = None, state: str = None) -> str:
        if not scopes:
            scopes = ["offline_access"]
        
        if not state:
            state = secrets.token_urlsafe(32)
        
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(scopes),
            "state": state
        }
        
        return f"{self.auth_url}?{urlencode(params)}"
    
    async def exchange_code_for_token(self, code: str, **kwargs) -> Dict[str, Any]:
        data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(self.token_url, data=data)
            response.raise_for_status()
            return response.json()


# OAuth provider instances
shopify_oauth = ShopifyOAuth()
woocommerce_oauth = WooCommerceOAuth()
wix_oauth = WixOAuth()