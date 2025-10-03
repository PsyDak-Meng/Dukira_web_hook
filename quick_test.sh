#!/bin/bash

################################################################################
# Quick Test Helper for Shopify Webhook API
# Run common test commands easily
################################################################################

API_URL="http://localhost:8000"

show_menu() {
    echo ""
    echo "========================================="
    echo "   Shopify Webhook API - Quick Test"
    echo "========================================="
    echo ""
    echo "1. Check API Status"
    echo "2. View API Documentation (browser)"
    echo "3. Start Shopify OAuth Flow"
    echo "4. Trigger Product Sync"
    echo "5. View Products & Images"
    echo "6. Check Image Stats"
    echo "7. View Recent Logs"
    echo "8. Check Google Cloud Storage"
    echo "9. Run Full E2E Test"
    echo "0. Exit"
    echo ""
    echo -n "Select option [0-9]: "
}

# 1. Check API Status
check_status() {
    echo ""
    echo "Checking API status..."
    ./check_status.sh
}

# 2. Open API Docs
open_docs() {
    echo ""
    echo "Opening API documentation..."
    if command -v start >/dev/null 2>&1; then
        start "$API_URL/docs"
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$API_URL/docs"
    elif command -v open >/dev/null 2>&1; then
        open "$API_URL/docs"
    else
        echo "Please open: $API_URL/docs"
    fi
}

# 3. Start OAuth
start_oauth() {
    echo ""
    echo -n "Enter your Shopify store (e.g., dukira-test or dukira-test.myshopify.com): "
    read shop

    if [ -z "$shop" ]; then
        echo "Error: Store domain required"
        return
    fi

    # Remove .myshopify.com if user included it
    shop=$(echo "$shop" | sed 's/\.myshopify\.com$//')

    echo ""
    echo -n "Enter user ID (default: test-user-1): "
    read user_id
    user_id=${user_id:-test-user-1}

    echo ""
    echo "Generating OAuth URL for shop: $shop, user: $user_id..."
    response=$(curl -s "$API_URL/auth/shopify/authorize?shop=$shop&user_id=$user_id")

    echo ""
    echo "Response:"
    echo "$response" | jq '.' 2>/dev/null || echo "$response"

    auth_url=$(echo "$response" | jq -r '.auth_url' 2>/dev/null)

    if [ -n "$auth_url" ] && [ "$auth_url" != "null" ]; then
        echo ""
        echo "Opening OAuth URL in browser..."
        echo "Note: You may see 'Not Secure' warning - this is normal for localhost"
        echo "Click 'Proceed anyway' or 'Advanced' → 'Continue to localhost'"
        echo ""
        if command -v start >/dev/null 2>&1; then
            start "$auth_url"
        elif command -v xdg-open >/dev/null 2>&1; then
            xdg-open "$auth_url"
        elif command -v open >/dev/null 2>&1; then
            open "$auth_url"
        else
            echo "Please open: $auth_url"
        fi
    fi
}

# 4. Trigger Sync
trigger_sync() {
    echo ""
    echo -n "Enter Store ID (default: 1): "
    read store_id
    store_id=${store_id:-1}

    echo ""
    echo "Select sync type:"
    echo "  1. Full Sync (all products)"
    echo "  2. Incremental Sync (recent changes)"
    echo -n "Choice [1-2]: "
    read sync_choice

    job_type="full_sync"
    if [ "$sync_choice" == "2" ]; then
        job_type="incremental"
    fi

    echo ""
    echo "Triggering $job_type for store $store_id..."
    curl -X POST "$API_URL/products/sync/$store_id?job_type=$job_type" | jq '.' 2>/dev/null

    echo ""
    echo "✅ Sync job queued! Watch logs with: tail -f local_test.log"
}

# 5. View Products
view_products() {
    echo ""
    echo -n "Enter Store ID (default: 1): "
    read store_id
    store_id=${store_id:-1}

    echo ""
    echo "Fetching products for store $store_id..."
    curl -s "$API_URL/products/store/$store_id" | jq '.' 2>/dev/null || echo "No products found or API error"

    echo ""
    echo -n "View images for a specific product? (y/n): "
    read view_images

    if [ "$view_images" == "y" ]; then
        echo -n "Enter Product ID: "
        read product_id

        if [ -n "$product_id" ]; then
            echo ""
            echo "Fetching images for product $product_id..."
            curl -s "$API_URL/products/$product_id/images" | jq '.' 2>/dev/null
        fi
    fi
}

# 6. Check Stats
check_stats() {
    echo ""
    echo "Fetching image processing statistics..."
    curl -s "$API_URL/products/stats" | jq '.' 2>/dev/null || curl -s "$API_URL/products/stats"

    echo ""
}

# 7. View Logs
view_logs() {
    echo ""
    echo "Select log view:"
    echo "  1. Last 50 lines"
    echo "  2. Follow live logs (Ctrl+C to stop)"
    echo "  3. Errors only"
    echo "  4. AI scoring only"
    echo -n "Choice [1-4]: "
    read log_choice

    echo ""
    case $log_choice in
        1)
            tail -50 local_test.log
            ;;
        2)
            echo "Following logs (Ctrl+C to stop)..."
            tail -f local_test.log
            ;;
        3)
            echo "Recent errors:"
            grep ERROR local_test.log | tail -20
            ;;
        4)
            echo "AI scoring results:"
            grep "TestModel analyzed" local_test.log | tail -20
            ;;
        *)
            echo "Invalid choice"
            ;;
    esac
}

# 8. Check GCS
check_gcs() {
    echo ""
    bucket=$(grep "GOOGLE_CLOUD_BUCKET_NAME" .env | cut -d= -f2)

    echo "Google Cloud Storage bucket: $bucket"
    echo ""

    if command -v gcloud >/dev/null 2>&1; then
        echo "Listing bucket contents..."
        gcloud storage ls "gs://$bucket" || echo "Cannot access bucket (check credentials)"
    else
        echo "gcloud CLI not installed"
        echo "View bucket in console: https://console.cloud.google.com/storage/browser/$bucket"
    fi
}

# 9. Full E2E Test
run_e2e_test() {
    echo ""
    echo "Running full end-to-end test..."
    ./test_shopify_webhook.sh
}

# Main menu loop
main() {
    # Check if jq is available
    if ! command -v jq >/dev/null 2>&1; then
        echo "Note: Install 'jq' for prettier JSON output"
        echo ""
    fi

    while true; do
        show_menu
        read choice

        case $choice in
            1) check_status ;;
            2) open_docs ;;
            3) start_oauth ;;
            4) trigger_sync ;;
            5) view_products ;;
            6) check_stats ;;
            7) view_logs ;;
            8) check_gcs ;;
            9) run_e2e_test ;;
            0) echo "Goodbye!"; exit 0 ;;
            *) echo "Invalid option" ;;
        esac

        echo ""
        echo -n "Press Enter to continue..."
        read
    done
}

main
