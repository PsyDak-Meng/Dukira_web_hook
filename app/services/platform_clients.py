import httpx
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod
import json
from datetime import datetime

from ..models import Store, PlatformType


class PlatformClient(ABC):
    """Abstract base class for platform API clients"""
    
    def __init__(self, store: Store):
        self.store = store
        self.access_token = store.access_token
        self.base_url = self._get_base_url()
    
    @abstractmethod
    def _get_base_url(self) -> str:
        pass
    
    @abstractmethod
    async def get_products(self, limit: int = 250, since_id: Optional[str] = None) -> List[Dict[str, Any]]:
        pass
    
    @abstractmethod
    async def get_product(self, product_id: str) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def _get_headers(self) -> Dict[str, str]:
        pass


class ShopifyClient(PlatformClient):
    def _get_base_url(self) -> str:
        return f"https://{self.store.platform_store_id}.myshopify.com/admin/api/2024-01"
    
    def _get_headers(self) -> Dict[str, str]:
        return {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json"
        }
    
    async def get_products(self, limit: int = 250, since_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch products from Shopify"""
        url = f"{self.base_url}/products.json"
        params = {"limit": limit}
        if since_id:
            params["since_id"] = since_id
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("products", [])
    
    async def get_product(self, product_id: str) -> Dict[str, Any]:
        """Fetch a single product from Shopify"""
        url = f"{self.base_url}/products/{product_id}.json"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers())
            response.raise_for_status()
            data = response.json()
            return data.get("product", {})
    
    async def get_product_count(self) -> int:
        """Get total product count"""
        url = f"{self.base_url}/products/count.json"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers())
            response.raise_for_status()
            data = response.json()
            return data.get("count", 0)
    
    async def create_webhook(self, topic: str, address: str) -> Dict[str, Any]:
        """Create a webhook in Shopify"""
        url = f"{self.base_url}/webhooks.json"
        payload = {
            "webhook": {
                "topic": topic,
                "address": address,
                "format": "json"
            }
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=self._get_headers(), json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("webhook", {})


class WooCommerceClient(PlatformClient):
    def _get_base_url(self) -> str:
        return f"{self.store.store_url}/wp-json/wc/v3"
    
    def _get_headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json"
        }
    
    def _get_auth(self) -> tuple:
        """Get WooCommerce consumer key and secret for basic auth"""
        platform_data = self.store.platform_data or {}
        consumer_key = platform_data.get("consumer_key", self.access_token)
        consumer_secret = platform_data.get("consumer_secret", self.store.refresh_token)
        return (consumer_key, consumer_secret)
    
    async def get_products(self, limit: int = 100, page: int = 1) -> List[Dict[str, Any]]:
        """Fetch products from WooCommerce"""
        url = f"{self.base_url}/products"
        params = {
            "per_page": limit,
            "page": page
        }
        
        auth = self._get_auth()
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers(), params=params, auth=auth)
            response.raise_for_status()
            return response.json()
    
    async def get_product(self, product_id: str) -> Dict[str, Any]:
        """Fetch a single product from WooCommerce"""
        url = f"{self.base_url}/products/{product_id}"
        
        auth = self._get_auth()
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers(), auth=auth)
            response.raise_for_status()
            return response.json()
    
    async def create_webhook(self, topic: str, delivery_url: str) -> Dict[str, Any]:
        """Create a webhook in WooCommerce"""
        url = f"{self.base_url}/webhooks"
        payload = {
            "name": f"Dukira {topic}",
            "topic": topic,
            "delivery_url": delivery_url,
            "status": "active"
        }
        
        auth = self._get_auth()
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=self._get_headers(), json=payload, auth=auth)
            response.raise_for_status()
            return response.json()


class WixClient(PlatformClient):
    def _get_base_url(self) -> str:
        return "https://www.wixapis.com"
    
    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
    
    async def get_site_id(self) -> str:
        """Get Wix site ID"""
        url = f"{self.base_url}/site-list/v2/sites"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers())
            response.raise_for_status()
            data = response.json()
            sites = data.get("sites", [])
            if sites:
                return sites[0].get("id", "")
        return ""
    
    async def get_products(self, limit: int = 100, cursor: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch products from Wix"""
        site_id = await self.get_site_id()
        url = f"{self.base_url}/stores/v1/products/query"
        
        payload = {
            "query": {
                "paging": {
                    "limit": limit
                }
            }
        }
        
        if cursor:
            payload["query"]["paging"]["cursor"] = cursor
        
        headers = self._get_headers()
        headers["wix-site-id"] = site_id
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("products", [])
    
    async def get_product(self, product_id: str) -> Dict[str, Any]:
        """Fetch a single product from Wix"""
        site_id = await self.get_site_id()
        url = f"{self.base_url}/stores/v1/products/{product_id}"
        
        headers = self._get_headers()
        headers["wix-site-id"] = site_id
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()


def get_platform_client(store: Store) -> PlatformClient:
    """Factory function to get the appropriate platform client"""
    if store.platform == PlatformType.SHOPIFY:
        return ShopifyClient(store)
    elif store.platform == PlatformType.WOOCOMMERCE:
        return WooCommerceClient(store)
    elif store.platform == PlatformType.WIX:
        return WixClient(store)
    else:
        raise ValueError(f"Unsupported platform: {store.platform}")