# Dukira Webhook API

A comprehensive FastAPI-based webhook system for connecting to Shopify, WooCommerce, and Wix e-commerce platforms. This backend handles OAuth authentication, product synchronization, image processing with AI filtering, and cloud storage integration.

## Features

- **Multi-Platform OAuth**: Connect to Shopify, WooCommerce, and Wix stores
- **Real-time Webhooks**: Keep product data synchronized with platform changes
- **Image Processing Pipeline**: AI-powered image filtering and quality assessment
- **Cloud Storage**: Automated image upload to Google Cloud Storage
- **Background Jobs**: Celery-based async processing for heavy operations
- **RESTful API**: Clean endpoints for frontend integration

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   E-commerce    │    │  Dukira Webhook  │    │   Frontend/     │
│   Platforms     │───▶│      API         │◀───│    Plugin       │
│ (Shopify/Woo/  │    │                  │    │                 │
│     Wix)        │    │  ┌─────────────┐ │    │                 │
└─────────────────┘    │  │   FastAPI   │ │    └─────────────────┘
                       │  │   Server    │ │
                       │  └─────────────┘ │
                       │  ┌─────────────┐ │    ┌─────────────────┐
                       │  │   Celery    │ │    │   PostgreSQL    │
                       │  │   Workers   │ │───▶│   Database      │
                       │  └─────────────┘ │    └─────────────────┘
                       │  ┌─────────────┐ │
                       │  │ Image AI &  │ │    ┌─────────────────┐
                       │  │ GCS Upload  │ │───▶│ Google Cloud    │
                       │  └─────────────┘ │    │    Storage      │
                       └──────────────────┘    └─────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL
- Redis
- Google Cloud Storage account
- Docker (optional)

### Environment Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd dukira_web_hook
```

2. Copy environment file:
```bash
cp .env.example .env
```

3. Update `.env` with your configuration:
```env
DATABASE_URL=postgresql://username:password@localhost/dukira_webhook_db
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-secret-key-here

# Google Cloud Storage
GOOGLE_CLOUD_PROJECT_ID=your-project-id
GOOGLE_CLOUD_BUCKET_NAME=your-bucket-name
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json

# Platform OAuth credentials
SHOPIFY_CLIENT_ID=your-shopify-client-id
SHOPIFY_CLIENT_SECRET=your-shopify-client-secret
# ... (add other platform credentials)
```

### Installation

#### Option 1: Docker (Recommended)

```bash
# Start all services
docker-compose up -d

# Run database migrations
docker-compose exec web alembic upgrade head
```

#### Option 2: Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL and Redis locally

# Run database migrations
alembic upgrade head

# Start FastAPI server
uvicorn app.main:app --reload

# Start Celery worker (in separate terminal)
celery -A app.services.sync_service worker --loglevel=info

# Start Celery beat (in separate terminal)
celery -A app.services.sync_service beat --loglevel=info
```

## API Endpoints

### Authentication
- `GET /auth/{platform}/authorize` - Generate OAuth URL
- `GET /auth/{platform}/callback` - Handle OAuth callback
- `GET /auth/stores/{user_id}` - Get user's connected stores

### Webhooks
- `POST /webhooks/{platform}/{store_id}` - Receive platform webhooks
- `GET /webhooks/{store_id}/events` - Get webhook event history
- `POST /webhooks/{store_id}/setup` - Set up webhooks on platform

### Products
- `POST /products/sync/{store_id}` - Trigger product sync
- `GET /products/store/{store_id}` - Get store products
- `GET /products/{product_id}` - Get single product
- `GET /products/{product_id}/images` - Get product images
- `GET /products/display/{product_id}` - Get product for plugin display

### System
- `GET /health` - Health check
- `GET /info` - Application information

## OAuth Integration

### Shopify
```python
# Generate auth URL
auth_url = await shopify_oauth.generate_auth_url(
    shop="your-shop",
    scopes=["read_products", "write_products"]
)
```

### WooCommerce
```python
# Generate auth URL
auth_url = woocommerce_oauth.generate_auth_url(
    store_url="https://your-store.com",
    scopes=["read", "write"]
)
```

### Wix
```python
# Generate auth URL
auth_url = wix_oauth.generate_auth_url(
    scopes=["offline_access"]
)
```

## Webhook Processing

The system automatically processes webhooks from connected platforms:

1. **Verification**: Validates webhook signatures
2. **Storage**: Stores webhook events in database
3. **Processing**: Triggers appropriate sync actions
4. **Background Jobs**: Handles heavy processing asynchronously

## Image Processing Pipeline

1. **Download**: Fetch images from platform URLs
2. **Validation**: Check image format, size, and quality
3. **Deduplication**: Calculate hash to prevent duplicates
4. **AI Processing**: Send to AI model for quality assessment
5. **Filtering**: Approve/reject based on AI score
6. **Storage**: Upload approved images to Google Cloud Storage

## Sync Jobs

### Full Sync
```bash
# Trigger full product sync for a store
curl -X POST "http://localhost:8000/products/sync/1?job_type=full_sync"
```

### Incremental Sync
```bash
# Trigger incremental sync (auto-scheduled)
curl -X POST "http://localhost:8000/products/sync/1?job_type=incremental"
```

## Monitoring

### Celery Flower
Access the Celery monitoring dashboard at `http://localhost:5555`

### Health Check
```bash
curl http://localhost:8000/health
```

### Database Migrations
```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head
```

## Configuration

### AI Model Integration
Configure your AI model endpoint in `.env`:
```env
AI_MODEL_API_URL=https://your-ai-api.com/analyze
AI_MODEL_API_KEY=your-api-key
```

### Google Cloud Storage
1. Create a GCS bucket
2. Create a service account with Storage Admin role
3. Download service account JSON key
4. Update `.env` with bucket name and credentials path

### Platform Webhooks
After connecting a store, set up webhooks:
```bash
curl -X POST "http://localhost:8000/webhooks/{store_id}/setup"
```

## Development

### Running Tests
```bash
pytest
```

### Code Formatting
```bash
black app/
isort app/
```

### Database Console
```bash
# Access PostgreSQL
docker-compose exec postgres psql -U postgres -d dukira_webhook_db
```

## Production Deployment

1. **Environment Variables**: Set production values in `.env`
2. **Database**: Use managed PostgreSQL service
3. **Redis**: Use managed Redis service
4. **SSL**: Configure HTTPS with reverse proxy
5. **Monitoring**: Set up logging and error tracking
6. **Scaling**: Scale Celery workers based on load

## Troubleshooting

### Common Issues

1. **OAuth Callback Errors**: Check redirect URI configuration
2. **Webhook Verification Failed**: Verify webhook secrets
3. **Image Processing Fails**: Check AI model API credentials
4. **GCS Upload Errors**: Verify service account permissions

### Logs
```bash
# View application logs
docker-compose logs web

# View Celery worker logs
docker-compose logs celery_worker
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License.