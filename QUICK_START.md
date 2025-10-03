# Dukira Webhook API - Quick Start Guide

## ✅ Your API is Running!

### Access Your API

- **API Documentation**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc
- **Health Endpoint**: http://localhost:8000/health

## 📋 Status Check

Run this anytime to see if services are running:
```bash
./check_status.sh
```

## 🚀 Start/Stop Commands

```bash
# Start all services (PostgreSQL, Redis, API, Celery)
./local_test.sh

# Stop all services
./local_test.sh stop
```

## 📊 Current Status

✅ **Running**:
- PostgreSQL (Docker container, port 5432)
- Redis (Docker container, port 6379)
- FastAPI server (port 8000)

⚠️ **Minor Issues** (API still works):
- Database health check SQL syntax warning
- Celery workers need celery_config fix (non-critical for API testing)

## 🧪 Test the API

### Via Browser
1. Open http://localhost:8000/docs
2. Try the interactive API documentation

### Via cURL
```bash
# Test health endpoint
curl http://localhost:8000/health

# Get API info
curl http://localhost:8000/info

# Generate Shopify auth URL (requires Shopify credentials in .env)
curl "http://localhost:8000/auth/shopify/authorize?shop=your-store.myshopify.com"
```

## 📝 View Logs

```bash
# View all logs
cat local_test.log

# Follow logs in real-time
tail -f local_test.log

# View recent errors
grep ERROR local_test.log
```

## 🔧 Configuration

Edit `.env` file for your settings:

```env
# Database (already configured)
DATABASE_URL=postgresql://postgres:postgres@localhost/dukira_webhook_db

# Add your Shopify credentials here:
SHOPIFY_CLIENT_ID=your_actual_client_id
SHOPIFY_CLIENT_SECRET=your_actual_client_secret

# Other platforms
WOOCOMMERCE_CLIENT_ID=...
WIX_CLIENT_ID=...
```

## 🗄️ Database Access

```bash
# Access PostgreSQL via Docker
docker exec dukira-postgres psql -U postgres -d dukira_webhook_db

# Example queries:
# \dt              - List tables
# SELECT * FROM stores;
# \q               - Quit
```

## 📦 Running Services

| Service | Port | Status Command |
|---------|------|----------------|
| PostgreSQL | 5432 | `docker ps \| grep postgres` |
| Redis | 6379 | `docker ps \| grep redis` |
| FastAPI | 8000 | Check http://localhost:8000/docs |

## 🐛 Troubleshooting

### API won't start
1. Check Docker is running: `docker ps`
2. Check logs: `cat local_test.log`
3. Verify .env has correct DATABASE_URL

### Port already in use
```bash
# Find what's using port 8000
netstat -ano | findstr :8000

# Kill the process or change port in script
```

### Database connection issues
```bash
# Restart PostgreSQL
docker restart dukira-postgres

# Check it's running
docker logs dukira-postgres
```

## 📚 Next Steps

1. **Add your Shopify credentials** to `.env`
2. **Test OAuth flow** at http://localhost:8000/docs
3. **Connect your store** using the /auth endpoints
4. **Sync products** using /products/sync endpoints

## 🎉 You're Ready!

Your Dukira Webhook API is now running locally. Visit http://localhost:8000/docs to start exploring!
