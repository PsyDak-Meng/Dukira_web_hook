import os
import random
import requests

# ====== CONFIG ======
SHOP = "your-dev-store.myshopify.com"   # replace with your dev store URL
TOKEN = "your-access-token"             # from Shopify admin -> Apps -> API credentials
API_VERSION = "2025-01"                 # use latest stable version
IMG_DIR = r"D:\PROJECTS\Dukira_web_hook\sample_images"

# ====== SAMPLE METADATA POOLS ======
TITLES = ["Cool Shirt", "Awesome Mug", "Trendy Hat", "Stylish Bag", "Unique Poster"]
VENDORS = ["Brandify", "DakotaCo", "AI Merch", "Shopify Testers", "OpenAI Goods"]
TYPES = ["Clothing", "Accessories", "Home Decor", "Electronics", "Stationery"]

# ====== API URL ======
PRODUCTS_URL = f"https://{SHOP}/admin/api/{API_VERSION}/products.json"

if __name__ == "__main__":
    # ====== LOOP THROUGH IMAGES ======
    for img_file in os.listdir(IMG_DIR):
        if not img_file.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
            continue

        file_path = os.path.join(IMG_DIR, img_file)

        # Generate random product data
        title = random.choice(TITLES) + f" #{random.randint(1000,9999)}"
        vendor = random.choice(VENDORS)
        ptype = random.choice(TYPES)
        price = round(random.uniform(5.0, 50.0), 2)

        # Read image as base64-encoded data
        with open(file_path, "rb") as f:
            img_bytes = f.read()
        import base64
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")

        # Create product payload
        data = {
            "product": {
                "title": title,
                "body_html": f"<strong>Auto-generated product</strong> with image {img_file}",
                "vendor": vendor,
                "product_type": ptype,
                "variants": [
                    {"price": str(price)}
                ],
                "images": [
                    {"attachment": img_b64, "filename": img_file}
                ]
            }
        }

        # Upload to Shopify
        resp = requests.post(PRODUCTS_URL, json=data, headers={
            "X-Shopify-Access-Token": TOKEN,
            "Content-Type": "application/json"
        })

        if resp.status_code == 201:
            product = resp.json()["product"]
            print(f"✅ Created: {product['title']} (ID: {product['id']})")
        else:
            print(f"❌ Error uploading {img_file}: {resp.status_code} - {resp.text}")
