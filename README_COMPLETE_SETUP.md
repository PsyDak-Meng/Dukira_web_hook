# 🎉 Dukira Webhook API - Complete Setup Guide

## ✅ What You Have

Your API is **fully configured** for the complete Shopify → AI → Google Cloud workflow:

### Architecture Overview

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│   Shopify   │  POST   │  Your API    │  Store  │   Google    │
│ Dev Store   │────────>│  (FastAPI)   │────────>│ Cloud       │
│             │ Webhook │              │ Images  │ Storage     │
└─────────────┘         └──────────────┘         └─────────────┘
                               │
                               │ Analyze
                               ▼
                        ┌──────────────┐
                        │  AI Model    │
                        │ (TestModel)  │
                        │ Score: 0-1.0 │
                        └──────────────┘
```

### Current Configuration

✅ **API Server**: Running on http://localhost:8000
✅ **Database**: PostgreSQL (Docker)
✅ **Cache**: Redis (Docker)
✅ **AI Model**: TestModel (50% pass rate)
✅ **Cloud Storage**: Google Cloud Storage (bucket: `dukira-web-hook`)
✅ **Shopify**: OAuth credentials configured

---

## 🚀 Quick Start Commands

### Essential Scripts

| Script | Purpose | Command |
|--------|---------|---------|
| **local_test.sh** | Start all services | `./local_test.sh` |
| **check_status.sh** | Check service status | `./check_status.sh` |
| **test_shopify_webhook.sh** | View workflow & test commands | `./test_shopify_webhook.sh` |
| **quick_test.sh** | Interactive testing menu | `./quick_test.sh` |

### Stop All Services
```bash
./local_test.sh stop
```

---

## 📋 Complete Workflow Steps

### 1. Start the API
```bash
./local_test.sh
```

This automatically:
- ✅ Starts PostgreSQL & Redis (Docker)
- ✅ Activates Python virtual environment
- ✅ Runs database migrations
- ✅ Starts FastAPI server (port 8000)
- ✅ Starts Celery workers (background jobs)

### 2. Connect Your Shopify Dev Store

**Interactive Mode:**
```bash
./quick_test.sh
# Select option 3: Start Shopify OAuth Flow
```

**Manual Mode:**
```bash
curl "http://localhost:8000/auth/shopify/authorize?shop=YOUR-STORE.myshopify.com"
# Copy the auth_url from response and open in browser
```

**Browser Mode:**
- Visit: http://localhost:8000/docs
- Try `/auth/shopify/authorize` endpoint

### 3. Trigger Product Sync

After OAuth is complete, sync your products:

```bash
# Full sync (all products)
curl -X POST "http://localhost:8000/products/sync/1?job_type=full_sync"

# Or use interactive menu
./quick_test.sh
# Select option 4: Trigger Product Sync
```

### 4. Watch the Processing

```bash
# Real-time logs
tail -f local_test.log

# Or use interactive menu
./quick_test.sh
# Select option 7: View Recent Logs
```

You'll see:
```
[INFO] Downloading image from Shopify CDN...
[INFO] TestModel analyzed image: score=0.85, quality=high
[INFO] Image approved, uploading to GCS...
[SUCCESS] Image uploaded: products/123/images/456.jpg
```

### 5. Check Results

```bash
# View all products
curl "http://localhost:8000/products/store/1"

# View product images
curl "http://localhost:8000/products/1/images"

# Get statistics
curl "http://localhost:8000/products/stats"
```

### 6. Verify Google Cloud Storage

**Via Console:**
https://console.cloud.google.com/storage/browser/dukira-web-hook

**Via CLI (if gcloud installed):**
```bash
gcloud storage ls gs://dukira-web-hook/products/
```

---

## 🔧 How It Works

### Image Processing Pipeline

When a Shopify webhook arrives:

**STEP 1: Download & Validate**
- Downloads image from Shopify CDN
- Validates: min 100x100px, max 10MB
- Checks format (PNG, JPG, etc.)

**STEP 2: Duplicate Detection**
- Calculates SHA-256 hash
- Skips if duplicate exists
- Saves bandwidth & storage

**STEP 3: AI Analysis**
- Runs TestModel (or real AI)
- Scores quality: 0.0 - 1.0
- Generates analysis data

**STEP 4: Decision**
- **Score ≥ 0.7**: ✅ APPROVED → Upload to GCS
- **Score < 0.7**: ❌ REJECTED → No upload

**STEP 5: Cloud Upload** (if approved)
- Uploads to: `products/{product_id}/images/{image_id}.jpg`
- Stores GCS path in database
- Image ready for use!

### AI Model (TestModel)

Currently using **TestModel** for testing:
- 🎲 Random 50% pass rate
- 📊 Mock analysis data (quality, clarity, lighting, etc.)
- ⚡ Fast processing (100ms)
- 🔧 Perfect for development

**Switch to Real AI:**
```env
# In .env file
USE_TEST_MODEL=false
AI_MODEL_API_URL=https://your-ai-api.com/analyze
AI_MODEL_API_KEY=your-api-key
```

---

## 📊 Monitoring & Debugging

### Service Status
```bash
./check_status.sh
```

Shows:
- 📦 Docker containers (PostgreSQL, Redis)
- 🔌 Port status (5432, 6379, 8000)
- ⚙️ Process status (API, Celery)
- 🏥 Health check result

### View Logs

```bash
# All logs
cat local_test.log

# Real-time
tail -f local_test.log

# Errors only
grep ERROR local_test.log

# AI scores
grep "TestModel analyzed" local_test.log
```

### API Documentation

Interactive docs: http://localhost:8000/docs
Alternative docs: http://localhost:8000/redoc

---

## 🧪 Testing Checklist

Use this checklist to verify everything works:

- [ ] **Start services**: `./local_test.sh`
- [ ] **Check status**: `./check_status.sh` (all green?)
- [ ] **View API docs**: http://localhost:8000/docs
- [ ] **Connect Shopify**: OAuth flow completes successfully
- [ ] **Sync products**: Products appear in database
- [ ] **Process images**: Images downloaded and analyzed
- [ ] **AI scoring**: Some approved (≥0.7), some rejected (<0.7)
- [ ] **GCS upload**: Approved images in bucket
- [ ] **Webhook test**: Create/update product in Shopify → webhook received

---

## 📁 Project Structure

```
Dukira_web_hook/
├── 📄 local_test.sh              # Start all services
├── 📄 check_status.sh            # Check service status
├── 📄 test_shopify_webhook.sh    # E2E test guide
├── 📄 quick_test.sh              # Interactive test menu
│
├── 📚 SHOPIFY_WEBHOOK_GUIDE.md   # Complete workflow guide
├── 📚 QUICK_START.md             # Basic usage guide
├── 📚 README.md                  # Main documentation
│
├── 📁 app/
│   ├── main.py                   # FastAPI application
│   ├── config.py                 # Settings & environment
│   ├── models.py                 # Database models
│   │
│   ├── 📁 services/
│   │   ├── image_service.py      # Image processing pipeline
│   │   ├── test_model.py         # AI model (TestModel)
│   │   ├── gcs_service.py        # Google Cloud Storage
│   │   └── sync_service.py       # Celery background jobs
│   │
│   ├── 📁 routers/
│   │   ├── auth.py               # OAuth endpoints
│   │   ├── products.py           # Product endpoints
│   │   └── webhooks.py           # Webhook endpoints
│   │
│   └── 📁 crud/
│       ├── store.py              # Store operations
│       └── product.py            # Product operations
│
├── 📁 sample_images/             # Test images
├── 📄 .env                       # Configuration (DO NOT COMMIT)
├── 📄 requirements.txt           # Python dependencies
└── 📄 docker-compose.yml         # Docker services
```

---

## 🔐 Security & Environment

### Environment Variables (.env)

**Required:**
```env
DATABASE_URL=postgresql://postgres:postgres@localhost/dukira_webhook_db
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-secret-key-here

GOOGLE_CLOUD_PROJECT_ID=dukira-dev-file
GOOGLE_CLOUD_BUCKET_NAME=dukira-web-hook
GOOGLE_APPLICATION_CREDENTIALS=D:\PROJECTS\Dukira_web_hook\dukira-dev-flie-f5459052090d.json

SHOPIFY_CLIENT_ID=your_client_id
SHOPIFY_CLIENT_SECRET=your_client_secret
SHOPIFY_REDIRECT_URI=http://localhost:8000/auth/shopify/callback
```

**Optional (for real AI):**
```env
USE_TEST_MODEL=false
AI_MODEL_API_URL=https://your-ai-api.com/analyze
AI_MODEL_API_KEY=your-api-key
```

### Google Cloud Credentials

Your service account JSON is at:
```
D:\PROJECTS\Dukira_web_hook\dukira-dev-flie-f5459052090d.json
```

**Verify it has:**
- ✅ Storage Object Admin role
- ✅ Access to bucket: `dukira-web-hook`

---

## 🐛 Troubleshooting

### API won't start
```bash
# Check Docker
docker ps

# Check logs
cat local_test.log | grep ERROR

# Verify .env file
cat .env
```

### Images not processing
```bash
# Check Celery workers
tail -f local_test.log | grep celery

# Manually trigger sync
curl -X POST "http://localhost:8000/products/sync/1"

# Check image stats
curl "http://localhost:8000/products/stats"
```

### Google Cloud upload fails
```bash
# Verify bucket exists
gcloud storage ls gs://dukira-web-hook

# Check service account permissions
cat dukira-dev-flie-f5459052090d.json

# View upload errors
grep "GCS" local_test.log | grep ERROR
```

### All images rejected
- **TestModel**: 50% rejection is normal (random)
- **Lower threshold**: Edit `app/services/image_service.py` line 72
- **Skip AI**: Set `USE_TEST_MODEL=false` and leave `AI_MODEL_API_URL` empty

---

## 🎯 Next Steps

### For Development:
1. ✅ Test with sample products from Shopify dev store
2. ✅ Verify images appear in Google Cloud bucket
3. ✅ Adjust AI score threshold if needed (line 72 in image_service.py)
4. ✅ Monitor logs to understand the flow

### For Production:
1. 🔐 Set production environment variables
2. 🌐 Deploy to cloud (AWS, GCP, or Azure)
3. 📡 Update Shopify redirect URIs
4. 🤖 Switch to real AI model API
5. 📊 Set up monitoring & alerts

---

## 📚 Documentation

- **[SHOPIFY_WEBHOOK_GUIDE.md](SHOPIFY_WEBHOOK_GUIDE.md)** - Complete workflow explanation
- **[QUICK_START.md](QUICK_START.md)** - Basic usage guide
- **[README.md](README.md)** - Main project documentation

---

## 🎉 You're All Set!

Your complete Shopify webhook workflow is ready:

```
Shopify → Webhook → Download Images → AI Analysis → Upload to GCS ✅
```

### Quick Test Now:
```bash
./quick_test.sh
```

### Or Step-by-Step:
```bash
# 1. Start
./local_test.sh

# 2. Check
./check_status.sh

# 3. Connect Shopify & sync
curl "http://localhost:8000/auth/shopify/authorize?shop=YOUR-STORE.myshopify.com"

# 4. Watch magic happen
tail -f local_test.log
```

**Questions?** Check the logs or API docs: http://localhost:8000/docs
