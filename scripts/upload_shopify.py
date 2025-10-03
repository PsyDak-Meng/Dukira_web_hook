import os
import csv
import random

# -------- CONFIG --------
IMG_DIR = "sample_images"  # local folder (for iteration)
CSV_FILE = "shopify_products.csv"

# Sample metadata pools
TITLES = ["Cool Shirt", "Awesome Mug", "Trendy Hat", "Stylish Bag", "Unique Poster"]
VENDORS = ["Brandify", "DakotaCo", "AI Merch", "Shopify Testers", "OpenAI Goods"]
TYPES = ["Clothing", "Accessories", "Home Decor", "Electronics", "Stationery"]

# -------- GENERATE CSV --------
with open(CSV_FILE, "w", newline="", encoding="utf-8") as csvfile:
    writer = csv.writer(csvfile)
    # Shopify CSV header
    writer.writerow(["Title","Body (HTML)","Vendor","Product Type","Variant Price","Image Src"])

    for img_file in os.listdir(IMG_DIR):
        if not img_file.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
            continue

        # Build raw GitHub URL
        img_url = f"https://raw.githubusercontent.com/PsyDak-Meng/Dukira_web_hook/main/sample_images/{img_file}"

        title = random.choice(TITLES) + f" #{random.randint(1000,9999)}"
        vendor = random.choice(VENDORS)
        ptype = random.choice(TYPES)
        price = round(random.uniform(5.0, 50.0), 2)

        writer.writerow([title, f"<strong>Auto product</strong> {title}", vendor, ptype, price, img_url])
        print(f"Added {title} -> {img_url}")

print(f"\n✅ CSV generated at: {CSV_FILE}")
