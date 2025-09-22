# Dukira Webhook API - Test Suite

Comprehensive test suite for the Dukira Webhook API covering all functionality from OAuth authentication through image processing to plugin integration.

## Test Structure

### 📁 Test Files Overview

| Test File | Purpose | Coverage |
|-----------|---------|----------|
| `test_auth.py` | OAuth authentication flows | Shopify, WooCommerce, Wix OAuth, store management |
| `test_webhooks.py` | Webhook processing | Signature verification, event handling, background processing |
| `test_sync_service.py` | Product synchronization | Platform clients, data transformation, Celery tasks |
| `test_image_service.py` | Image processing pipeline | Download, AI processing, GCS upload, deduplication |
| `test_api_endpoints.py` | API endpoints | Product retrieval, search, sync triggers, plugin endpoints |
| `test_crud_operations.py` | Database operations | Create, read, update, delete for all models |
| `test_integration.py` | End-to-end workflows | Complete user journeys and error scenarios |

### 🧪 Test Categories

#### Unit Tests
- **OAuth Authentication** - Individual OAuth provider implementations
- **Webhook Processing** - Platform-specific webhook handling
- **Sync Service** - Product fetching and transformation logic
- **Image Service** - Image processing pipeline components
- **API Endpoints** - Individual FastAPI route handlers
- **CRUD Operations** - Database interaction patterns

#### Integration Tests
- **Complete OAuth Flow** - From authorization to store creation
- **Product Sync Workflow** - End-to-end synchronization process
- **Webhook Processing Flow** - Real-time update handling
- **Image Processing Pipeline** - Complete image workflow
- **Plugin Integration** - Frontend consumption patterns
- **Error Handling** - Failure scenarios and recovery

## Running Tests

### Quick Start

```bash
# Make script executable and run all tests
chmod +x run_tests.sh
./run_tests.sh
```

### Manual Test Execution

```bash
# Install dependencies
pip install -r requirements.txt
pip install -r tests/test_requirements.txt

# Run specific test categories
pytest tests/test_auth.py -v                    # OAuth tests
pytest tests/test_webhooks.py -v                # Webhook tests  
pytest tests/test_sync_service.py -v            # Sync tests
pytest tests/test_image_service.py -v           # Image tests
pytest tests/test_api_endpoints.py -v           # API tests
pytest tests/test_crud_operations.py -v         # Database tests
pytest tests/test_integration.py -v             # Integration tests

# Run all tests with coverage
pytest tests/ --cov=app --cov-report=html
```

### Test Markers

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests  
pytest -m integration

# Skip slow tests
pytest -m "not slow"

# Run only external service tests
pytest -m external
```

## Test Configuration

### Environment Variables

Tests use these environment variables (set automatically by test runner):

```bash
TESTING=true
DATABASE_URL=sqlite:///test.db
REDIS_URL=redis://localhost:6379/1
SECRET_KEY=test_secret_key_for_testing_only
```

### Test Database

Tests use SQLite for fast, isolated testing:
- Each test function gets a fresh database session
- Transactions are rolled back after each test
- No external database dependencies required

### Mocking Strategy

External services are mocked for reliable testing:
- **Platform APIs** (Shopify, WooCommerce, Wix) - Mocked responses
- **AI Service** - Configurable score responses
- **Google Cloud Storage** - Simulated upload/download
- **HTTP Requests** - Controlled network responses

## Test Data & Fixtures

### Key Fixtures

- `created_store` - Pre-created store for testing
- `created_product` - Product with variants and images
- `sample_*_store_data` - Platform-specific store data
- `mock_*_api` - Mocked external service responses

### Test Data Factories

Fixtures create realistic test data:
- Complete product structures with variants
- Platform-specific API response formats
- Image processing scenarios
- OAuth flow simulations

## Key Test Scenarios

### 🔐 OAuth Authentication Tests

```python
def test_complete_shopify_oauth_flow():
    """Test full OAuth journey from auth URL to token storage"""
    # 1. Generate authorization URL
    # 2. Simulate user authorization  
    # 3. Handle callback with token exchange
    # 4. Verify store creation and data storage
```

### 🔄 Webhook Processing Tests

```python
def test_shopify_webhook_with_signature_verification():
    """Test webhook security and processing"""
    # 1. Verify HMAC signature authenticity
    # 2. Parse webhook payload
    # 3. Trigger appropriate sync actions
    # 4. Store webhook event for monitoring
```

### 📦 Product Sync Tests

```python
def test_complete_product_sync_workflow():
    """Test full sync from platform to database"""
    # 1. Fetch products from platform API
    # 2. Transform platform data to internal format
    # 3. Create/update products, variants, images
    # 4. Track sync progress and handle errors
```

### 🖼️ Image Processing Tests

```python
def test_complete_image_processing_pipeline():
    """Test full image workflow"""
    # 1. Download and validate image
    # 2. Calculate hash for deduplication
    # 3. Process with AI for quality assessment
    # 4. Upload approved images to GCS
    # 5. Update database with processing results
```

### 🔌 Plugin Integration Tests

```python
def test_complete_plugin_integration_workflow():
    """Test API consumption by frontend plugins"""
    # 1. Get user's connected stores
    # 2. Retrieve products with approved images
    # 3. Generate signed URLs for image display
    # 4. Format data for plugin consumption
```

## Coverage Goals

### Target Coverage Levels

- **Overall**: 85%+
- **Core Services**: 90%+
- **API Endpoints**: 95%+
- **Database Operations**: 90%+

### Coverage Reports

```bash
# Generate HTML coverage report
pytest tests/ --cov=app --cov-report=html

# View in browser
open htmlcov/index.html
```

## Error Testing

### Failure Scenarios Tested

- **Network Failures** - API timeouts, connection errors
- **Authentication Errors** - Invalid tokens, expired credentials  
- **Data Validation** - Malformed payloads, missing fields
- **Service Outages** - AI service unavailable, GCS failures
- **Rate Limiting** - Platform API limits, throttling
- **Partial Failures** - Some products fail, others succeed

### Recovery Testing

- **Retry Logic** - Automatic retry of failed operations
- **Graceful Degradation** - Fallback when services unavailable
- **Data Consistency** - Maintaining integrity during failures
- **Error Logging** - Proper error tracking and reporting

## Performance Testing

### Load Scenarios

- **Large Product Catalogs** - 1000+ products per store
- **High Image Volume** - Multiple images per product
- **Concurrent Operations** - Simultaneous sync and webhook processing
- **API Pagination** - Efficient handling of large result sets

### Performance Assertions

```python
def test_large_product_catalog_performance():
    """Ensure API remains responsive with large datasets"""
    # Create 1000 products
    # Test paginated retrieval
    # Verify response times under load
```

## Debugging Tests

### Verbose Output

```bash
# Maximum verbosity
pytest tests/ -vvv --tb=long

# Show print statements
pytest tests/ -s

# Drop into debugger on failure
pytest tests/ --pdb
```

### Test Isolation

```bash
# Run single test
pytest tests/test_auth.py::TestShopifyOAuth::test_generate_auth_url

# Run test class
pytest tests/test_auth.py::TestShopifyOAuth
```

## Continuous Integration

### GitHub Actions Integration

```yaml
# .github/workflows/test.yml
name: Test Suite
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.11
      - name: Run tests
        run: ./run_tests.sh
```

### Pre-commit Hooks

```bash
# Install pre-commit
pip install pre-commit
pre-commit install

# Run on all files
pre-commit run --all-files
```

## Test Maintenance

### Adding New Tests

1. **Follow Naming Convention**: `test_<functionality>_<scenario>`
2. **Use Descriptive Docstrings**: Explain what the test verifies
3. **Mock External Services**: Keep tests isolated and fast
4. **Test Both Success and Failure**: Cover happy path and edge cases
5. **Update Coverage Goals**: Maintain high coverage standards

### Updating Existing Tests

1. **Preserve Test Intent**: Keep original test purpose clear
2. **Update Mocks**: Ensure mocks match current external APIs
3. **Verify Backwards Compatibility**: Don't break existing functionality
4. **Document Changes**: Update test docstrings when behavior changes

## Troubleshooting

### Common Issues

**Import Errors**
```bash
# Ensure app module is in Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

**Database Issues**
```bash
# Clear test database
rm -f test.db tests/test.db
```

**Coverage Not Updating**
```bash
# Clear coverage cache
rm -rf .coverage htmlcov/
```

**Async Test Issues**
```bash
# Ensure pytest-asyncio is installed
pip install pytest-asyncio
```

### Getting Help

1. **Check Test Logs**: Look for specific error messages
2. **Run Individual Tests**: Isolate failing tests
3. **Verify Environment**: Ensure all dependencies installed
4. **Check Mocks**: Verify external service mocks are correct

## Best Practices

### Test Writing Guidelines

- **Clear Test Names**: Describe what is being tested
- **Single Responsibility**: One test, one behavior
- **Arrange-Act-Assert**: Structure tests clearly
- **Independent Tests**: No dependencies between tests
- **Realistic Data**: Use data that matches production scenarios

### Performance Guidelines

- **Fast Execution**: Unit tests should run in milliseconds
- **Parallel Safe**: Tests can run concurrently
- **Minimal Setup**: Only create necessary test data
- **Clean Teardown**: Properly clean up after tests

This comprehensive test suite ensures the Dukira Webhook API is robust, reliable, and ready for production deployment.