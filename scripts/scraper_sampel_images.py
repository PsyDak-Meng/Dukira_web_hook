from selenium import webdriver
from selenium.webdriver.common.by import By
import time
import requests
import os

# -------- Settings --------
SEARCH_TERM = "puppies"
NUM_IMAGES = 100
SAVE_DIR = os.path.join(os.getcwd(), "sample_images")

# -------- Setup --------
if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

options = webdriver.ChromeOptions()
options.add_argument("--headless")  # run in background
driver = webdriver.Chrome(options=options)

SEARCH_URL = f"https://www.google.com/search?q={SEARCH_TERM}&tbm=isch"
driver.get(SEARCH_URL)
time.sleep(2)

# -------- Scroll and collect --------
if __name__ == "__main__":   
    images = set()
    last_height = driver.execute_script("return document.body.scrollHeight")

    while len(images) < NUM_IMAGES:
        # Find all <img> elements
        new_images = driver.find_elements(By.CSS_SELECTOR, "img")
        for img in new_images:
            src = img.get_attribute("src")
            if src and "http" in src:
                images.add(src)
                if len(images) >= NUM_IMAGES:
                    break

        # Scroll to load more
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:  # no more images loaded
            break
        last_height = new_height

    print(f"Collected {len(images)} image URLs. Downloading...")

    # -------- Download --------
    for i, src in enumerate(list(images)[:NUM_IMAGES]):
        try:
            img_data = requests.get(src, timeout=5).content
            file_path = os.path.join(SAVE_DIR, f"img_{i+1}.jpg")
            with open(file_path, "wb") as f:
                f.write(img_data)
            print(f"Saved {file_path}")
        except Exception as e:
            print(f"Failed to save image {i+1}: {e}")

    driver.quit()
