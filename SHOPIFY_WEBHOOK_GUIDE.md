# Shopify Webhook Integration Guide

## 🎯 Complete Workflow

Your API automatically:
1. **Receives webhooks** from Shopify when products change
2. **Downloads product images** from Shopify CDN
3. **Runs AI model** (TestModel) to score image quality (0-1.0)
4. **Uploads approved images** (score ≥ 0.7) to Google Cloud Storage

---

## 🚀 Quick Start (5 Minutes)

### Step 1: Start the API
```bash
./local_test.sh
```

### Step 2: Connect Your Shopify Dev Store

**Option A: Via Browser**
1. Visit: http://localhost:8000/docs
2. Find `/auth/shopify/authorize` endpoint
3. Enter your store: `your-store.myshopify.com`
4. Click "Execute" and follow OAuth flow

**Option B: Via cURL**
```bash
curl "http://localhost:8000/auth/shopify/authorize?shop=your-store.myshopify.com"
# Copy the auth_url from response and open in browser
```

### Step 3: Sync Products & Process Images
```bash
# Replace {store_id} with your store ID from OAuth response
curl -X POST "http://localhost:8000/products/sync/{store_id}?job_type=full_sync"
```

### Step 4: Watch the Magic! ✨
```bash
# Watch logs in real-time
tail -f local_test.log
```

You'll see:
- ✅ Images downloaded from Shopify
- 🤖 AI model scoring each image
- ☁️ Approved images uploaded to Google Cloud
- ❌ Rejected images (score < 0.7)

---

## 📊 How It Works

### Image Processing Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                     SHOPIFY WEBHOOK                             │
│  Product Updated → Sends webhook to your API                    │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│               STEP 1: DOWNLOAD & VALIDATE                       │
│  • Download image from Shopify CDN                              │
│  • Validate: min 100x100, max 10MB                              │
│  • Check format (PNG, JPG, etc.)                                │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│               STEP 2: DUPLICATE DETECTION                       │
│  • Calculate SHA-256 hash                                       │
│  • Check if image already exists                                │
│  • Skip duplicates automatically                                │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│               STEP 3: AI MODEL ANALYSIS                         │
│                                                                 │
│  TestModel (current):                                           │
│    • Random 50% pass rate                                       │
│    • Score: 0.0 - 1.0                                           │
│    • Analysis: quality, clarity, lighting, composition          │
│                                                                 │
│  OR Real AI Model (when configured):                            │
│    • Advanced image quality assessment                          │
│    • Product-specific analysis                                  │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
                        ┌────────┴────────┐
                        │                 │
                   Score ≥ 0.7       Score < 0.7
                        │                 │
                        ▼                 ▼
              ┌─────────────────┐  ┌─────────────────┐
              │   APPROVED      │  │   REJECTED      │
              └────────┬────────┘  └─────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│          STEP 4: UPLOAD TO GOOGLE CLOUD STORAGE                 │
│  • Path: products/{product_id}/images/{image_id}.jpg            │
│  • Update database with GCS path                                │
│  • Image available via signed URL                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔧 Configuration

### Current Settings (.env)

```env
# AI Model (Currently using TestModel)
USE_TEST_MODEL=true                    # ✅ TestModel enabled (50% pass rate)

# Google Cloud Storage
GOOGLE_CLOUD_PROJECT_ID=dukira-dev-file
GOOGLE_CLOUD_BUCKET_NAME=dukira-web-hook
GOOGLE_APPLICATION_CREDENTIALS=D:\PROJECTS\Dukira_web_hook\dukira-dev-flie-f5459052090d.json

# Shopify OAuth
SHOPIFY_CLIENT_ID=<your-client-id>
SHOPIFY_CLIENT_SECRET=<your-client-secret>
```

### AI Model Options

**TestModel (Default):**
- ✅ No API key needed
- ✅ Perfect for development/testing
- 🎲 Random 50% pass rate
- 📊 Mock analysis data

**Real AI Model:**
```env
USE_TEST_MODEL=false
AI_MODEL_API_URL=https://your-ai-api.com/analyze
AI_MODEL_API_KEY=your-api-key
```

---

## 🧪 Testing the Complete Flow

### Test Script
```bash
./test_shopify_webhook.sh
```

This shows:
- ✅ API status
- ✅ Configuration check
- ✅ Pipeline explanation
- ✅ Test commands

### Manual Testing Steps

#### 1. Connect Shopify Store
```bash
# Get auth URL
curl "http://localhost:8000/auth/shopify/authorize?shop=your-store.myshopify.com"

# Output:
# {
#   "auth_url": "https://your-store.myshopify.com/admin/oauth/authorize?..."
# }

# Open auth_url in browser → Complete OAuth
```

#### 2. Trigger Product Sync
```bash
# Full sync (all products)
curl -X POST "http://localhost:8000/products/sync/1?job_type=full_sync"

# Incremental sync (recent changes)
curl -X POST "http://localhost:8000/products/sync/1?job_type=incremental"
```

#### 3. Check Results
```bash
# View all products for your store
curl "http://localhost:8000/products/store/1"

# View specific product images
curl "http://localhost:8000/products/1/images"

# Get image stats
curl "http://localhost:8000/products/stats"
```

#### 4. Verify in Google Cloud
Visit: https://console.cloud.google.com/storage/browser/dukira-web-hook

You should see uploaded images under:
```
products/
  ├── {product_id}/
  │   └── images/
  │       ├── {image_id_1}.jpg  ✅ (score ≥ 0.7)
  │       ├── {image_id_2}.jpg  ✅ (score ≥ 0.7)
  │       └── ...
```

---

## 📡 Webhook Setup (Production)

### Register Webhooks on Shopify

Once OAuth is complete, register webhooks:

```bash
curl -X POST "http://localhost:8000/webhooks/{store_id}/setup"
```

This creates webhooks for:
- `products/create` - New products
- `products/update` - Product changes
- `products/delete` - Product deletion

### Webhook Endpoint

Shopify will send POST requests to:
```
POST http://localhost:8000/webhooks/shopify/{store_id}
```

The API automatically:
1. Verifies HMAC signature
2. Parses product data
3. Queues images for processing
4. Returns 200 OK

---

## 📊 Monitoring & Logs

### Real-time Logs
```bash
# All logs
tail -f local_test.log

# Only errors
tail -f local_test.log | grep ERROR

# Only AI scoring
tail -f local_test.log | grep "TestModel analyzed"
```

### Check Service Status
```bash
./check_status.sh
```

### View Processing Stats
```bash
# Total images by status
curl "http://localhost:8000/products/stats"

# Example output:
# {
#   "pending": 0,
#   "processing": 2,
#   "approved": 15,
#   "rejected": 8,
#   "stored": 15
# }
```

---

## 🔍 Understanding Results

### Image Status Flow

1. **PENDING** → Image downloaded, waiting for processing
2. **PROCESSING** → Currently being analyzed by AI
3. **APPROVED** → AI score ≥ 0.7, ready for upload
4. **REJECTED** → AI score < 0.7 OR validation failed
5. **STORED** → Successfully uploaded to Google Cloud

### AI Analysis Data

Each processed image has:
```json
{
  "ai_score": "0.85",
  "ai_analysis": {
    "quality": "high",
    "clarity": 0.92,
    "lighting": 0.88,
    "composition": 0.79,
    "background": "clean",
    "product_focus": true,
    "model_used": "TestModel",
    "confidence": 0.95
  },
  "gcs_path": "products/123/images/456.jpg"
}
```

---

## 🐛 Troubleshooting

### Images Not Processing?

1. **Check API is running:**
   ```bash
   ./check_status.sh
   ```

2. **Check Celery workers:**
   ```bash
   tail -f local_test.log | grep celery
   ```

3. **Manually trigger processing:**
   ```bash
   curl -X POST "http://localhost:8000/products/sync/{store_id}"
   ```

### Images Not Uploading to GCS?

1. **Verify GCS credentials:**
   ```bash
   cat dukira-dev-flie-f5459052090d.json
   ```

2. **Check bucket permissions:**
   - Go to: https://console.cloud.google.com/storage/browser/dukira-web-hook
   - Ensure service account has "Storage Object Admin" role

3. **Test GCS manually:**
   ```bash
   # If you have gcloud CLI
   gcloud storage ls gs://dukira-web-hook
   ```

### All Images Rejected?

- **Using TestModel:** 50% random pass rate is normal
- **Change threshold:** Edit `image_service.py` line 72 (score >= 0.7)
- **Force approve:** Set `USE_TEST_MODEL=false` and `AI_MODEL_API_URL=` (empty) in .env

---

## 📚 API Endpoints Reference

### Authentication
- `GET /auth/shopify/authorize` - Start OAuth flow
- `GET /auth/shopify/callback` - OAuth callback
- `GET /auth/stores/{user_id}` - List connected stores

### Products & Images
- `POST /products/sync/{store_id}` - Sync products from Shopify
- `GET /products/store/{store_id}` - Get all products
- `GET /products/{product_id}` - Get single product
- `GET /products/{product_id}/images` - Get product images
- `GET /products/stats` - Image processing statistics

### Webhooks
- `POST /webhooks/shopify/{store_id}` - Receive Shopify webhook
- `POST /webhooks/{store_id}/setup` - Register webhooks on Shopify
- `GET /webhooks/{store_id}/events` - View webhook history

---

## 🎉 You're All Set!

Your complete workflow is ready:

✅ **Shopify** → Sends webhooks on product updates
✅ **API** → Downloads images automatically
✅ **AI Model** → Scores image quality (TestModel or real AI)
✅ **Google Cloud** → Stores approved images
✅ **Database** → Tracks everything

### Next Steps:

1. **Connect your Shopify dev store** (if not done)
2. **Trigger a product sync** to test the flow
3. **Check Google Cloud Storage** for uploaded images
4. **Switch to real AI model** when ready

**Interactive Testing:** http://localhost:8000/docs
