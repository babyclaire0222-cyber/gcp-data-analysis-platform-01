#!/bin/bash

# GCP Data Analysis Platform Production Setup Script

echo "🚀 Setting up GCP Data Analysis Platform for Production..."

# Check if service account file exists
if [ ! -f "credentials/service-account.json" ]; then
    echo "❌ Service account file not found!"
    echo "Please download your GCP service account JSON key and place it in credentials/service-account.json"
    echo ""
    echo "Steps:"
    echo "1. Go to https://console.cloud.google.com/"
    echo "2. Navigate to IAM & Admin → Service Accounts"
    echo "3. Select or create a service account"
    echo "4. Download JSON key"
    echo "5. Place it in credentials/service-account.json"
    exit 1
fi

echo "✅ Service account file found"

# Verify GCP project ID
PROJECT_ID=$(grep -o '"project_id": "[^"]*' credentials/service-account.json | cut -d'"' -f4)
echo "📋 Project ID: $PROJECT_ID"

# Verify required GCP services
echo ""
echo "🔍 Checking GCP services..."
gcloud services list --enabled --project=$PROJECT_ID 2>/dev/null

if [ $? -ne 0 ]; then
    echo "❌ GCP authentication failed or services not enabled"
    echo "Please run: gcloud auth login"
    exit 1
fi

echo "✅ GCP authentication successful"

# Check if required services are enabled
REQUIRED_SERVICES=("bigquery.googleapis.com" "storage.googleapis.com" "pubsub.googleapis.com" "run.googleapis.com")

for service in "${REQUIRED_SERVICES[@]}"; do
    if gcloud services list --enabled --project=$PROJECT_ID --filter="config.name=$service" --format="value(config.name)" | grep -q "$service"; then
        echo "✅ $service is enabled"
    else
        echo "⚠️  $service is not enabled. Enabling..."
        gcloud services enable $service --project=$PROJECT_ID
    fi
done

echo ""
echo "🐳 Starting production environment..."
docker-compose -f docker-compose.production.yml up --build

echo ""
echo "✅ Production environment started!"
echo "🌐 Application available at: http://localhost:8080"
echo ""
echo "📋 Useful commands:"
echo "  - View logs: make logs-prod"
echo "  - Stop services: make stop-prod"
echo "  - Restart: make prod-real"
