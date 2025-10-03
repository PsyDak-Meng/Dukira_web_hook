#!/bin/bash
################################################################################
# Quick Status Checker for Dukira Webhook API
# Shows the current status of all services
################################################################################

echo "===================================="
echo " Dukira Webhook API - Service Status"
echo "===================================="
echo ""

# Check Docker containers
echo "📦 Docker Containers:"
echo "------------------------------------"
if docker ps --filter "name=dukira-postgres" --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | grep -q "dukira-postgres"; then
    docker ps --filter "name=dukira" --format "  ✓ {{.Names}}: {{.Status}}"
else
    echo "  ✗ No Docker containers running"
fi
echo ""

# Check ports
echo "🔌 Port Status:"
echo "------------------------------------"
netstat -an | grep -i ":5432 " | grep -iq "listen" && echo "  ✓ PostgreSQL (5432): LISTENING" || echo "  ✗ PostgreSQL (5432): NOT LISTENING"
netstat -an | grep -i ":6379 " | grep -iq "listen" && echo "  ✓ Redis (6379): LISTENING" || echo "  ✗ Redis (6379): NOT LISTENING"
netstat -an | grep -i ":8000 " | grep -iq "listen" && echo "  ✓ API Server (8000): LISTENING" || echo "  ✗ API Server (8000): NOT LISTENING"
echo ""

# Check PID files
echo "⚙️  Application Processes:"
echo "------------------------------------"
if [[ -f .api_server.pid ]]; then
    pid=$(cat .api_server.pid)
    if ps -p $pid > /dev/null 2>&1; then
        echo "  ✓ API Server (PID: $pid): RUNNING"
    else
        echo "  ✗ API Server (PID: $pid): NOT RUNNING"
    fi
else
    echo "  - API Server: No PID file found"
fi

if [[ -f .celery_worker.pid ]]; then
    pid=$(cat .celery_worker.pid)
    if ps -p $pid > /dev/null 2>&1; then
        echo "  ✓ Celery Worker (PID: $pid): RUNNING"
    else
        echo "  ✗ Celery Worker (PID: $pid): NOT RUNNING"
    fi
else
    echo "  - Celery Worker: No PID file found"
fi

if [[ -f .celery_beat.pid ]]; then
    pid=$(cat .celery_beat.pid)
    if ps -p $pid > /dev/null 2>&1; then
        echo "  ✓ Celery Beat (PID: $pid): RUNNING"
    else
        echo "  ✗ Celery Beat (PID: $pid): NOT RUNNING"
    fi
else
    echo "  - Celery Beat: No PID file found"
fi
echo ""

# Test API health
echo "🏥 API Health Check:"
echo "------------------------------------"
response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null)
if [[ "$response" == "200" ]]; then
    echo "  ✓ API Health: OK (HTTP $response)"
    echo "  📄 API Docs: http://localhost:8000/docs"
else
    echo "  ✗ API Health: FAILED (HTTP $response)"
    echo "  💡 Check logs: tail -f local_test.log"
fi
echo ""

echo "===================================="
echo "Recent log entries:"
echo "------------------------------------"
tail -15 local_test.log 2>/dev/null | grep -E "\[INFO\]|\[ERROR\]|\[SUCCESS\]|\[WARNING\]" | tail -10
echo ""
echo "Full logs: cat local_test.log"
echo "===================================="
