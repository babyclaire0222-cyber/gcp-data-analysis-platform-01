.PHONY: help build dev prod test clean logs

# Default target
help:
	@echo "Available commands:"
	@echo "  make dev      - Start development environment with hot reload"
	@echo "  make prod     - Start production environment"
	@echo "  make build    - Build Docker images"
	@echo "  make test     - Run tests"
	@echo "  make logs     - Show logs"
	@echo "  make clean    - Clean up containers and volumes"
	@echo "  make setup    - Initial setup"

# Initial setup
setup:
	@echo "Setting up development environment..."
	@mkdir -p credentials
	@echo "Please place your service account JSON file in credentials/service-account.json"
	@echo "Or create a mock file for local development"
	@touch credentials/service-account.json
	@echo '{"type": "service_account", "project_id": "local-development"}' > credentials/service-account.json

# Development environment
dev:
	@echo "Starting development environment..."
	docker-compose -f docker-compose.dev.yml up --build

# Production environment
prod:
	@echo "Starting production environment..."
	docker-compose up --build

# Build images
build:
	@echo "Building Docker images..."
	docker-compose -f docker-compose.dev.yml build
	docker-compose build

# Run tests
test:
	@echo "Running tests..."
	docker-compose -f docker-compose.dev.yml run --rm webapp pytest

# Show logs
logs:
	docker-compose -f docker-compose.dev.yml logs -f

# Clean up
clean:
	@echo "Cleaning up..."
	docker-compose -f docker-compose.dev.yml down -v
	docker-compose down -v
	docker system prune -f

# Stop services
stop:
	@echo "Stopping services..."
	docker-compose -f docker-compose.dev.yml stop
	docker-compose stop

# Restart services
restart:
	@echo "Restarting services..."
	docker-compose -f docker-compose.dev.yml restart

# Shell access to webapp
shell:
	docker-compose -f docker-compose.dev.yml exec webapp bash

# Database operations
db-setup:
	@echo "Setting up local BigQuery dataset..."
	@echo "This would typically be done via the BigQuery web UI or API"

# Create sample data
sample-data:
	@echo "Creating sample data..."
	@mkdir -p sample-data
	@echo "department,amount,date,expense_type" > sample-data/sample_finance.csv
	@echo "Engineering,5000,2024-01-15,Software" >> sample-data/sample_finance.csv
	@echo "Marketing,3000,2024-01-16,Advertising" >> sample-data/sample_finance.csv
	@echo "Sales,4500,2024-01-17,Travel" >> sample-data/sample_finance.csv
	@echo "Engineering,6000,2024-01-18,Hardware" >> sample-data/sample_finance.csv
	@echo "HR,2000,2024-01-19,Training" >> sample-data/sample_finance.csv
