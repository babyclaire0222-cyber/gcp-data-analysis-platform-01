#!/bin/bash

# GCP Data Analysis Platform Docker Setup Script

echo "🐳 Setting up GCP Data Analysis Platform with Docker..."

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p credentials
mkdir -p sample-data
mkdir -p logs

# Create environment file
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "✅ .env file created. Please edit it with your configuration."
fi

# Create mock service account file for local development
if [ ! -f credentials/service-account.json ]; then
    echo "🔑 Creating mock service account file..."
    cat > credentials/service-account.json << EOF
{
  "type": "service_account",
  "project_id": "local-development",
  "private_key_id": "mock-key-id",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMOCK_PRIVATE_KEY_FOR_LOCAL_DEVELOPMENT\n-----END PRIVATE KEY-----\n",
  "client_email": "dev-service-account@local-development.iam.gserviceaccount.com",
  "client_id": "123456789012345678901",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token"
}
EOF
    echo "✅ Mock service account created at credentials/service-account.json"
fi

# Create sample data
if [ ! -f sample-data/sample_finance.csv ]; then
    echo "📊 Creating sample data..."
    cat > sample-data/sample_finance.csv << EOF
department,amount,date,expense_type
Engineering,5000,2024-01-15,Software
Marketing,3000,2024-01-16,Advertising
Sales,4500,2024-01-17,Travel
Engineering,6000,2024-01-18,Hardware
HR,2000,2024-01-19,Training
Finance,3500,2024-01-20,Consulting
Engineering,5500,2024-01-21,Cloud Services
Marketing,2500,2024-01-22,Social Media
Sales,4000,2024-01-23,Conference
Operations,3000,2024-01-24,Office Supplies
EOF
    echo "✅ Sample data created at sample-data/sample_finance.csv"
fi

# Build and start services
echo "🚀 Building and starting development environment..."
docker-compose -f docker-compose.dev.yml up --build -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 10

# Check if services are running
echo "🔍 Checking service status..."
docker-compose -f docker-compose.dev.yml ps

echo ""
echo "✅ Setup complete!"
echo ""
echo "🌐 Access the application at: http://localhost:8080"
echo ""
echo "📋 Available services:"
echo "  - Web App: http://localhost:8080"
echo "  - Redis: localhost:6379"
echo "  - GCS Emulator: http://localhost:4443"
echo "  - BigQuery Emulator: http://localhost:9050"
echo "  - Pub/Sub Emulator: http://localhost:8432"
echo ""
echo "🔧 Useful commands:"
echo "  - View logs: make logs"
echo "  - Stop services: make stop"
echo "  - Restart services: make restart"
echo "  - Access shell: make shell"
echo "  - Clean up: make clean"
echo ""
echo "📊 To test the application:"
echo "  1. Visit http://localhost:8080"
echo "  2. Upload sample-data/sample_finance.csv"
echo "  3. View the uploaded data and analysis results"
