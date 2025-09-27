#!/bin/bash

# remote_setup.sh - One-click setup script for Dukira Webhook API
# This script automates the entire quickstart process from the README

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Print banner
print_banner() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                  Dukira Webhook API Setup                   ║"
    echo "║                  One-Click Setup Script                     ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    local missing_deps=()
    
    # Check Python 3.11+
    if command_exists python3; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        if [[ $(echo "$PYTHON_VERSION 3.11" | awk '{print ($1 >= $2)}') == 1 ]]; then
            log_success "Python $PYTHON_VERSION found"
        else
            log_warning "Python $PYTHON_VERSION found, but 3.11+ recommended"
        fi
    else
        missing_deps+=("python3")
    fi
    
    # Check pip
    if ! command_exists pip3 && ! command_exists pip; then
        missing_deps+=("pip")
    fi
    
    # Check Docker
    if command_exists docker; then
        log_success "Docker found"
        SETUP_MODE="docker"
    else
        log_warning "Docker not found, will use local setup"
        SETUP_MODE="local"
        
        # For local setup, check PostgreSQL and Redis
        if ! command_exists psql; then
            missing_deps+=("postgresql")
        fi
        if ! command_exists redis-cli; then
            missing_deps+=("redis")
        fi
    fi
    
    # Check Git
    if ! command_exists git; then
        missing_deps+=("git")
    fi
    
    if [ ${#missing_deps[@]} -ne 0 ]; then
        log_error "Missing dependencies: ${missing_deps[*]}"
        log_info "Please install the missing dependencies and run this script again."
        exit 1
    fi
    
    log_success "All prerequisites satisfied"
}

# Setup environment file
setup_environment() {
    log_info "Setting up environment configuration..."
    
    if [ ! -f ".env" ]; then
        cp .env.example .env
        log_success "Created .env file from template"
        
        # Generate a random secret key
        SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
        
        # Update .env with generated values
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            sed -i '' "s/your-secret-key-here/$SECRET_KEY/" .env
        else
            # Linux
            sed -i "s/your-secret-key-here/$SECRET_KEY/" .env
        fi
        
        log_success "Generated random SECRET_KEY"
        
        # Set test model to true for easy testing
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s/USE_TEST_MODEL=false/USE_TEST_MODEL=true/" .env
        else
            sed -i "s/USE_TEST_MODEL=false/USE_TEST_MODEL=true/" .env
        fi
        
        log_success "Enabled TestModel for easy testing"
        
        log_warning "Please update .env with your actual credentials:"
        log_warning "  - Database URL (if not using Docker)"
        log_warning "  - Google Cloud Storage settings"
        log_warning "  - OAuth client credentials"
        log_warning "  - AI Model API settings (optional, TestModel is enabled)"
        
    else
        log_info ".env file already exists, skipping..."
    fi
}

# Docker setup
setup_docker() {
    log_info "Setting up with Docker..."
    
    # Check if docker-compose exists
    if command_exists docker-compose; then
        COMPOSE_CMD="docker-compose"
    elif command_exists docker && docker compose version >/dev/null 2>&1; then
        COMPOSE_CMD="docker compose"
    else
        log_error "Neither docker-compose nor 'docker compose' found"
        exit 1
    fi
    
    log_info "Building Docker images..."
    $COMPOSE_CMD build
    
    log_info "Starting services..."
    $COMPOSE_CMD up -d postgres redis
    
    # Wait for services to be ready
    log_info "Waiting for database to be ready..."
    sleep 10
    
    # Run migrations
    log_info "Running database migrations..."
    $COMPOSE_CMD run --rm web alembic upgrade head
    
    # Start all services
    log_info "Starting all services..."
    $COMPOSE_CMD up -d
    
    log_success "Docker setup completed!"
    log_info "Services running:"
    log_info "  - API Server: http://localhost:8000"
    log_info "  - Celery Flower: http://localhost:5555"
    log_info "  - PostgreSQL: localhost:5432"
    log_info "  - Redis: localhost:6379"
}

# Local setup
setup_local() {
    log_info "Setting up for local development..."
    
    # Install Python dependencies
    log_info "Installing Python dependencies..."
    if command_exists pip3; then
        pip3 install -r requirements.txt
    else
        pip install -r requirements.txt
    fi
    
    # Check if PostgreSQL is running
    if ! pg_isready -h localhost -p 5432 >/dev/null 2>&1; then
        log_warning "PostgreSQL doesn't seem to be running on localhost:5432"
        log_warning "Please start PostgreSQL and ensure database 'dukira_webhook_db' exists"
        log_info "You can create it with: createdb dukira_webhook_db"
    fi
    
    # Check if Redis is running
    if ! redis-cli ping >/dev/null 2>&1; then
        log_warning "Redis doesn't seem to be running on localhost:6379"
        log_warning "Please start Redis service"
    fi
    
    # Run migrations
    log_info "Running database migrations..."
    alembic upgrade head
    
    log_success "Local setup completed!"
    log_info "To start the services manually:"
    log_info "  1. Start API: uvicorn app.main:app --reload"
    log_info "  2. Start Celery worker: celery -A app.services.sync_service worker --loglevel=info"
    log_info "  3. Start Celery beat: celery -A app.services.sync_service beat --loglevel=info"
}

# Start services helper
start_services() {
    if [ "$SETUP_MODE" = "docker" ]; then
        log_info "Services are already running via Docker"
        log_info "Use '$COMPOSE_CMD logs' to view logs"
        log_info "Use '$COMPOSE_CMD down' to stop services"
    else
        log_info "Starting API server in background..."
        nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > api.log 2>&1 &
        API_PID=$!
        echo $API_PID > api.pid
        
        sleep 3
        
        if kill -0 $API_PID 2>/dev/null; then
            log_success "API server started (PID: $API_PID)"
            log_info "API server logs: tail -f api.log"
        else
            log_error "Failed to start API server"
            return 1
        fi
    fi
}

# Health check
health_check() {
    log_info "Performing health check..."
    
    # Wait a bit for services to fully start
    sleep 5
    
    # Check API health
    if curl -s http://localhost:8000/health >/dev/null; then
        log_success "API health check passed"
    else
        log_warning "API health check failed - service might still be starting"
    fi
    
    # Check if we can reach the API info endpoint
    if curl -s http://localhost:8000/info >/dev/null; then
        log_success "API info endpoint accessible"
    else
        log_warning "API info endpoint not accessible"
    fi
}

# Cleanup function
cleanup() {
    if [ -f "api.pid" ]; then
        PID=$(cat api.pid)
        if kill -0 $PID 2>/dev/null; then
            log_info "Stopping API server..."
            kill $PID
            rm api.pid
        fi
    fi
}

# Main execution
main() {
    print_banner
    
    # Set up signal handling for cleanup
    trap cleanup EXIT INT TERM
    
    # Check if we're in the right directory
    if [ ! -f "app/main.py" ]; then
        log_error "This script must be run from the project root directory"
        log_error "Make sure you're in the dukira_web_hook directory"
        exit 1
    fi
    
    check_prerequisites
    setup_environment
    
    if [ "$SETUP_MODE" = "docker" ]; then
        setup_docker
    else
        setup_local
        
        # Ask if user wants to start services
        read -p "Start API server now? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            start_services
        fi
    fi
    
    health_check
    
    echo
    log_success "Setup completed successfully!"
    echo
    log_info "Next steps:"
    log_info "1. Update .env with your actual credentials"
    log_info "2. Access the API at: http://localhost:8000"
    log_info "3. View API docs at: http://localhost:8000/docs"
    log_info "4. Check health at: http://localhost:8000/health"
    
    if [ "$SETUP_MODE" = "docker" ]; then
        log_info "5. Monitor Celery at: http://localhost:5555"
        log_info "6. View logs: $COMPOSE_CMD logs -f"
    else
        log_info "5. Start Celery worker: celery -A app.services.sync_service worker --loglevel=info"
        log_info "6. Start Celery beat: celery -A app.services.sync_service beat --loglevel=info"
    fi
    
    echo
    log_info "The TestModel is enabled for easy testing of the image processing pipeline."
    log_info "To test image processing, upload product images - 50% will pass randomly."
    echo
}

# Check if script is being sourced or executed
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi