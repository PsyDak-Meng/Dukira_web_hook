#!/bin/bash

# Dukira Webhook API Test Runner
# This script runs the complete test suite with proper configuration

set -e  # Exit on any error

echo "🧪 Starting Dukira Webhook API Test Suite"
echo "========================================"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "⚠️  Virtual environment not found. Creating one..."
    python -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install test dependencies
echo "📦 Installing test dependencies..."
pip install -r tests/test_requirements.txt
pip install -r requirements.txt

# Set test environment variables
export TESTING=true
export DATABASE_URL="sqlite:///test.db"
export REDIS_URL="redis://localhost:6379/1"
export SECRET_KEY="test_secret_key_for_testing_only"

# Create test database directory if needed
mkdir -p tests/data

echo ""
echo "🔍 Running Tests"
echo "==============="

# Run different test categories
echo "Unit Tests - OAuth & Authentication:"
pytest tests/test_auth.py -v --tb=short

echo ""
echo "Unit Tests - Webhook Processing:"
pytest tests/test_webhooks.py -v --tb=short

echo ""
echo "Unit Tests - Sync Service:"
pytest tests/test_sync_service.py -v --tb=short

echo ""
echo "Unit Tests - Image Processing:"
pytest tests/test_image_service.py -v --tb=short

echo ""
echo "Unit Tests - API Endpoints:"
pytest tests/test_api_endpoints.py -v --tb=short

echo ""
echo "Unit Tests - CRUD Operations:"
pytest tests/test_crud_operations.py -v --tb=short

echo ""
echo "Integration Tests:"
pytest tests/test_integration.py -v --tb=short

echo ""
echo "📊 Full Test Suite with Coverage:"
pytest tests/ \
    --cov=app \
    --cov-report=term-missing \
    --cov-report=html:htmlcov \
    --cov-fail-under=80 \
    -v

echo ""
echo "✅ Test Suite Complete!"
echo "📈 Coverage report saved to htmlcov/index.html"
echo ""

# Optional: Run linting
if command -v flake8 &> /dev/null; then
    echo "🔍 Running code quality checks..."
    flake8 app/ --max-line-length=100 --ignore=E203,W503
    echo "✅ Code quality checks passed!"
fi

echo "🎉 All tests completed successfully!"