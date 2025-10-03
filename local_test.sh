#!/bin/bash

################################################################################
# Dukira Webhook API - Local Testing Script
#
# This script automates the setup and testing of the API on your local machine.
# It will:
#   1. Check Docker is running
#   2. Start PostgreSQL and Redis in Docker containers
#   3. Set up the database and run migrations
#   4. Activate Python virtual environment
#   5. Start all services (API, Celery worker, Celery beat)
#   6. Run basic health checks
#   7. Log everything to local_test.log
#
# Usage:
#   ./local_test.sh       - Start all services
#   ./local_test.sh stop  - Stop all services (including Docker containers)
################################################################################

# Configuration
LOG_FILE="local_test.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
DB_NAME="dukira_webhook_db"
DB_USER="postgres"
DB_HOST="localhost"
API_PORT=8000

################################################################################
# Logging Functions
################################################################################

# Log message with timestamp and level
log() {
    local level=$1
    shift
    local message="$@"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $message" | tee -a "$LOG_FILE"
}

log_info() {
    log "INFO" "$@"
}

log_error() {
    log "ERROR" "$@"
}

log_success() {
    log "SUCCESS" "$@"
}

log_warning() {
    log "WARNING" "$@"
}

# Print section header
log_section() {
    local title="$1"
    echo "" | tee -a "$LOG_FILE"
    echo "================================================================================" | tee -a "$LOG_FILE"
    log "INFO" "$title"
    echo "================================================================================" | tee -a "$LOG_FILE"
}

################################################################################
# Utility Functions
################################################################################

# Check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check if a port is in use
port_in_use() {
    local port=$1
    if command_exists netstat; then
        # Use case-insensitive grep for Windows/Cygwin compatibility
        netstat -an | grep -i ":$port " | grep -iq "listen"
    elif command_exists lsof; then
        lsof -i ":$port" >/dev/null 2>&1
    else
        log_warning "Cannot check port $port - netstat/lsof not available"
        return 1
    fi
}

# Start PostgreSQL using Docker
start_postgres() {
    log_info "Checking PostgreSQL status..."

    # Check if container already exists
    if docker ps -a --filter "name=dukira-postgres" --format "{{.Names}}" 2>/dev/null | grep -q "dukira-postgres"; then
        log_info "PostgreSQL container exists. Checking status..."

        # Check if it's running
        if docker ps --filter "name=dukira-postgres" --format "{{.Names}}" 2>/dev/null | grep -q "dukira-postgres"; then
            log_success "PostgreSQL container is already running"
            return 0
        else
            # Container exists but not running - start it
            log_info "Starting existing PostgreSQL container..."
            if docker start dukira-postgres >> "$LOG_FILE" 2>&1; then
                log_success "PostgreSQL container started"
                sleep 2  # Give PostgreSQL time to initialize
                return 0
            else
                log_error "Failed to start PostgreSQL container"
                return 1
            fi
        fi
    else
        # Container doesn't exist - create and run it
        log_info "Creating new PostgreSQL container..."
        if docker run -d --name dukira-postgres \
            -e POSTGRES_PASSWORD=postgres \
            -e POSTGRES_USER=postgres \
            -p 5432:5432 \
            postgres:15 >> "$LOG_FILE" 2>&1; then
            log_success "PostgreSQL container created and started"
            log_info "Waiting for PostgreSQL to be ready..."
            sleep 5  # Give PostgreSQL time to initialize
            return 0
        else
            log_error "Failed to create PostgreSQL container"
            log_info "Make sure Docker Desktop is running"
            return 1
        fi
    fi
}

# Start Redis using Docker
start_redis() {
    log_info "Checking Redis status..."

    # Check if container already exists
    if docker ps -a --filter "name=dukira-redis" --format "{{.Names}}" 2>/dev/null | grep -q "dukira-redis"; then
        log_info "Redis container exists. Checking status..."

        # Check if it's running
        if docker ps --filter "name=dukira-redis" --format "{{.Names}}" 2>/dev/null | grep -q "dukira-redis"; then
            log_success "Redis container is already running"
            return 0
        else
            # Container exists but not running - start it
            log_info "Starting existing Redis container..."
            if docker start dukira-redis >> "$LOG_FILE" 2>&1; then
                log_success "Redis container started"
                sleep 1  # Give Redis time to initialize
                return 0
            else
                log_error "Failed to start Redis container"
                return 1
            fi
        fi
    else
        # Container doesn't exist - create and run it
        log_info "Creating new Redis container..."
        if docker run -d --name dukira-redis \
            -p 6379:6379 \
            redis:7 >> "$LOG_FILE" 2>&1; then
            log_success "Redis container created and started"
            sleep 2  # Give Redis time to initialize
            return 0
        else
            log_error "Failed to create Redis container"
            log_info "Make sure Docker Desktop is running"
            return 1
        fi
    fi
}

# Check if PostgreSQL is running (after starting)
check_postgres() {
    log_info "Verifying PostgreSQL connection..."

    # If psql command not available, just check if port is listening
    if ! command_exists psql; then
        log_warning "psql command not available, checking port only..."
        sleep 3  # Give PostgreSQL time to start
        if port_in_use 5432; then
            log_success "PostgreSQL appears to be running on port 5432"
            return 0
        else
            log_error "Port 5432 is not accessible"
            return 1
        fi
    fi

    # Wait up to 20 seconds for PostgreSQL to be ready (with psql)
    local retries=20
    while [ $retries -gt 0 ]; do
        if psql -U "$DB_USER" -h "$DB_HOST" -lqt >/dev/null 2>&1; then
            log_success "PostgreSQL is accessible"
            return 0
        fi
        retries=$((retries - 1))
        sleep 1
    done

    log_error "PostgreSQL is not accessible after starting"
    return 1
}

# Check if Redis is running (after starting)
check_redis() {
    log_info "Verifying Redis connection..."

    if command_exists redis-cli; then
        if redis-cli ping >/dev/null 2>&1; then
            log_success "Redis is accessible"
            return 0
        fi
    fi

    # Alternative check using port
    if port_in_use 6379; then
        log_success "Redis appears to be running on port 6379"
        return 0
    else
        log_error "Redis is not accessible after starting"
        return 1
    fi
}

# Create database if it doesn't exist
setup_database() {
    log_info "Checking if database '$DB_NAME' exists..."

    if psql -U "$DB_USER" -h "$DB_HOST" -lqt | cut -d \| -f 1 | grep -qw "$DB_NAME"; then
        log_success "Database '$DB_NAME' already exists"
    else
        log_info "Creating database '$DB_NAME'..."
        if psql -U "$DB_USER" -h "$DB_HOST" -c "CREATE DATABASE $DB_NAME;" 2>&1 | tee -a "$LOG_FILE"; then
            log_success "Database '$DB_NAME' created successfully"
        else
            log_error "Failed to create database '$DB_NAME'"
            return 1
        fi
    fi

    return 0
}

# Run database migrations
run_migrations() {
    log_info "Running database migrations..."
    if alembic upgrade head 2>&1 | tee -a "$LOG_FILE"; then
        log_success "Database migrations completed"
        return 0
    else
        log_error "Database migrations failed"
        return 1
    fi
}

# Check if virtual environment is activated
check_venv() {
    log_info "Checking Python virtual environment..."

    if [[ -z "$VIRTUAL_ENV" ]]; then
        log_warning "Virtual environment is not activated"

        if [[ -d "venv" ]]; then
            log_info "Found venv directory. Attempting to activate..."
            source venv/Scripts/activate 2>/dev/null || source venv/bin/activate 2>/dev/null

            if [[ -n "$VIRTUAL_ENV" ]]; then
                log_success "Virtual environment activated: $VIRTUAL_ENV"
            else
                log_error "Failed to activate virtual environment"
                return 1
            fi
        else
            log_error "No venv directory found. Create one with: python -m venv venv"
            return 1
        fi
    else
        log_success "Virtual environment is active: $VIRTUAL_ENV"
    fi

    return 0
}

# Install dependencies
install_dependencies() {
    log_info "Checking dependencies..."

    if ! pip list | grep -q "fastapi"; then
        log_info "Installing dependencies from requirements.txt..."
        if pip install -r requirements.txt 2>&1 | tee -a "$LOG_FILE"; then
            log_success "Dependencies installed successfully"
        else
            log_error "Failed to install dependencies"
            return 1
        fi
    else
        log_success "Dependencies already installed"
    fi

    return 0
}

# Test API health endpoint
test_health() {
    log_info "Testing API health endpoint..."
    sleep 3  # Give the server time to start

    local response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$API_PORT/health)

    if [[ "$response" == "200" ]]; then
        log_success "API health check passed (HTTP $response)"
        curl -s http://localhost:$API_PORT/health | tee -a "$LOG_FILE"
        echo "" | tee -a "$LOG_FILE"
        return 0
    else
        log_error "API health check failed (HTTP $response)"
        return 1
    fi
}

# Start API server in background
start_api_server() {
    log_info "Starting FastAPI server on port $API_PORT..."

    if port_in_use $API_PORT; then
        log_warning "Port $API_PORT is already in use. Skipping API server start."
        return 0
    fi

    # Use absolute path to venv python to ensure correct environment
    local python_path="$PWD/venv/Scripts/python"
    if [[ ! -f "$python_path" ]]; then
        python_path="$PWD/venv/bin/python"
    fi

    nohup "$python_path" -m uvicorn app.main:app --host 0.0.0.0 --port $API_PORT >> "$LOG_FILE" 2>&1 &
    local pid=$!
    echo $pid > .api_server.pid

    log_success "FastAPI server started (PID: $pid)"
    log_info "API Documentation: http://localhost:$API_PORT/docs"
    log_info "API ReDoc: http://localhost:$API_PORT/redoc"

    return 0
}

# Start Celery worker in background
start_celery_worker() {
    log_info "Starting Celery worker..."

    # Use absolute path to venv python to ensure correct environment
    local python_path="$PWD/venv/Scripts/python"
    if [[ ! -f "$python_path" ]]; then
        python_path="$PWD/venv/bin/python"
    fi

    nohup "$python_path" -m celery -A app.celery_config worker --loglevel=info --pool=solo >> "$LOG_FILE" 2>&1 &
    local pid=$!
    echo $pid > .celery_worker.pid

    log_success "Celery worker started (PID: $pid)"

    return 0
}

# Start Celery beat scheduler in background
start_celery_beat() {
    log_info "Starting Celery beat scheduler..."

    # Use absolute path to venv python to ensure correct environment
    local python_path="$PWD/venv/Scripts/python"
    if [[ ! -f "$python_path" ]]; then
        python_path="$PWD/venv/bin/python"
    fi

    nohup "$python_path" -m celery -A app.celery_config beat --loglevel=info >> "$LOG_FILE" 2>&1 &
    local pid=$!
    echo $pid > .celery_beat.pid

    log_success "Celery beat scheduler started (PID: $pid)"

    return 0
}

# Stop all services
stop_services() {
    log_section "Stopping Services"

    # Stop API server
    if [[ -f .api_server.pid ]]; then
        local pid=$(cat .api_server.pid)
        log_info "Stopping API server (PID: $pid)..."
        kill $pid 2>/dev/null && log_success "API server stopped" || log_warning "API server process not found"
        rm -f .api_server.pid
    fi

    # Stop Celery worker
    if [[ -f .celery_worker.pid ]]; then
        local pid=$(cat .celery_worker.pid)
        log_info "Stopping Celery worker (PID: $pid)..."
        kill $pid 2>/dev/null && log_success "Celery worker stopped" || log_warning "Celery worker process not found"
        rm -f .celery_worker.pid
    fi

    # Stop Celery beat
    if [[ -f .celery_beat.pid ]]; then
        local pid=$(cat .celery_beat.pid)
        log_info "Stopping Celery beat (PID: $pid)..."
        kill $pid 2>/dev/null && log_success "Celery beat stopped" || log_warning "Celery beat process not found"
        rm -f .celery_beat.pid
    fi

    # Stop Docker containers
    log_info "Stopping Docker containers..."

    if docker ps --filter "name=dukira-postgres" --format "{{.Names}}" 2>/dev/null | grep -q "dukira-postgres"; then
        log_info "Stopping PostgreSQL container..."
        docker stop dukira-postgres >/dev/null 2>&1 && log_success "PostgreSQL container stopped"
    fi

    if docker ps --filter "name=dukira-redis" --format "{{.Names}}" 2>/dev/null | grep -q "dukira-redis"; then
        log_info "Stopping Redis container..."
        docker stop dukira-redis >/dev/null 2>&1 && log_success "Redis container stopped"
    fi
}

# Cleanup function for script exit
cleanup() {
    log_section "Script Interrupted - Cleaning Up"
    stop_services
    exit 1
}

################################################################################
# Main Execution
################################################################################

main() {
    # Initialize log file
    echo "################################################################################" > "$LOG_FILE"
    echo "# Dukira Webhook API - Local Test Log" >> "$LOG_FILE"
    echo "# Started: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
    echo "################################################################################" >> "$LOG_FILE"

    log_section "Dukira Webhook API - Local Test Execution"
    log_info "Log file: $LOG_FILE"

    # Set up trap for cleanup on exit
    trap cleanup SIGINT SIGTERM

    # Step 1: Check prerequisites
    log_section "Step 1: Checking Prerequisites"

    if ! command_exists python && ! command_exists python3; then
        log_error "Python is not installed"
        exit 1
    fi

    if ! command_exists docker; then
        log_error "Docker is not installed or not in PATH"
        log_info "Install Docker Desktop from: https://www.docker.com/products/docker-desktop"
        exit 1
    fi

    # Check if Docker daemon is running
    if ! docker ps >/dev/null 2>&1; then
        log_error "Docker daemon is not running"
        log_info "Please start Docker Desktop and try again"
        exit 1
    fi

    log_success "Docker is running and accessible"

    if ! command_exists psql; then
        log_warning "psql client not found - will rely on port checks for verification"
    fi

    # Step 1.5: Start Docker containers for PostgreSQL and Redis
    log_section "Step 1.5: Starting PostgreSQL and Redis"

    if ! start_postgres; then
        log_error "Failed to start PostgreSQL. Please check Docker and try again."
        exit 1
    fi

    if ! start_redis; then
        log_error "Failed to start Redis. Please check Docker and try again."
        exit 1
    fi

    # Verify services are accessible
    if ! check_postgres; then
        log_error "PostgreSQL started but is not accessible. Check logs with: docker logs dukira-postgres"
        exit 1
    fi

    if ! check_redis; then
        log_error "Redis started but is not accessible. Check logs with: docker logs dukira-redis"
        exit 1
    fi

    # Step 2: Setup Python environment
    log_section "Step 2: Setting Up Python Environment"

    if ! check_venv; then
        exit 1
    fi

    if ! install_dependencies; then
        exit 1
    fi

    # Step 3: Setup database
    log_section "Step 3: Setting Up Database"

    if ! setup_database; then
        exit 1
    fi

    if ! run_migrations; then
        exit 1
    fi

    # Step 4: Start services
    log_section "Step 4: Starting Services"

    start_api_server
    start_celery_worker
    start_celery_beat

    # Step 5: Run tests
    log_section "Step 5: Running Health Checks"

    if test_health; then
        log_success "All health checks passed!"
    else
        log_warning "Some health checks failed. Check the logs for details."
    fi

    # Final summary
    log_section "Test Execution Complete"
    log_success "All services are running!"
    echo "" | tee -a "$LOG_FILE"
    log_info "API Server: http://localhost:$API_PORT"
    log_info "API Docs: http://localhost:$API_PORT/docs"
    log_info "Log file: $LOG_FILE"
    echo "" | tee -a "$LOG_FILE"
    log_info "To stop all services, run: ./local_test.sh stop"
    echo "" | tee -a "$LOG_FILE"

    # Show running processes
    log_info "Running services:"
    if [[ -f .api_server.pid ]]; then
        log_info "  - API Server (PID: $(cat .api_server.pid))"
    fi
    if [[ -f .celery_worker.pid ]]; then
        log_info "  - Celery Worker (PID: $(cat .celery_worker.pid))"
    fi
    if [[ -f .celery_beat.pid ]]; then
        log_info "  - Celery Beat (PID: $(cat .celery_beat.pid))"
    fi

    log_info "Services are running in the background. Check $LOG_FILE for ongoing logs."
}

################################################################################
# Script Entry Point
################################################################################

# Check if running with "stop" argument
if [[ "$1" == "stop" ]]; then
    stop_services
    log_info "All services stopped"
    exit 0
fi

# Run main function
main
