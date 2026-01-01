# Docker Setup for GCP Data Analysis Platform

This guide shows how to run the GCP Data Analysis Platform locally using Docker for development and testing.

## 🐳 Prerequisites

- Docker Desktop installed
- Docker Compose
- Make (optional, for convenience commands)

## 🚀 Quick Start

### 1. Initial Setup

```bash
# Clone the repository
git clone https://github.com/babyclaire0222-cyber/gcp-data-analysis-platform-01.git
cd gcp-data-analysis-platform-01

# Run initial setup
make setup
```

### 2. Start Development Environment

```bash
# Start all services with hot reload
make dev

# Or manually:
docker-compose -f docker-compose.dev.yml up --build
```

### 3. Access the Application

- **Web Application**: http://localhost:8080
- **Redis**: localhost:6379
- **GCS Emulator**: http://localhost:4443
- **BigQuery Emulator**: http://localhost:9050
- **Pub/Sub Emulator**: http://localhost:8432

## 📋 Available Services

### Development Environment (`docker-compose.dev.yml`)

- **Web App**: Flask application with hot reload
- **Redis**: Caching and rate limiting
- **GCS Emulator**: Local Google Cloud Storage
- **BigQuery Emulator**: Local BigQuery database
- **Pub/Sub Emulator**: Local Pub/Sub messaging

### Production Environment (`docker-compose.yml`)

- **Web App**: Production-optimized Flask app
- **Redis**: Production caching
- **Optional Emulators**: For testing without GCP

## 🛠️ Development Commands

```bash
# Start development environment
make dev

# Build images
make build

# Run tests
make test

# View logs
make logs

# Stop services
make stop

# Clean up everything
make clean

# Access webapp container shell
make shell

# Create sample data
make sample-data
```

## 🔧 Configuration

### Environment Variables

Copy `.env.example` to `.env` and customize:

```bash
cp .env.example .env
```

Key variables:
- `GCP_PROJECT`: Your GCP project ID
- `GOOGLE_APPLICATION_CREDENTIALS`: Path to service account JSON
- `FLASK_SECRET_KEY`: Secret key for Flask sessions
- `REDIS_URL`: Redis connection string

### Service Account Setup

1. Create a service account in GCP
2. Download the JSON key file
3. Place it in `credentials/service-account.json`

For local development without GCP:
```bash
# Mock service account file
echo '{"type": "service_account", "project_id": "local-development"}' > credentials/service-account.json
```

## 📊 Testing the Application

### 1. Upload Sample Data

```bash
# Create sample data
make sample-data

# Upload via web interface
# Visit http://localhost:8080 and upload sample-data/sample_finance.csv
```

### 2. Test API Endpoints

```bash
# Health check
curl http://localhost:8080/healthz

# User info (if authenticated)
curl http://localhost:8080/whoami

# List reports
curl http://localhost:8080/reports
```

## 🐛 Debugging

### View Logs

```bash
# All services
make logs

# Specific service
docker-compose -f docker-compose.dev.yml logs -f webapp
```

### Access Container Shell

```bash
make shell
# or
docker-compose -f docker-compose.dev.yml exec webapp bash
```

### Restart Services

```bash
make restart
# or
docker-compose -f docker-compose.dev.yml restart webapp
```

## 🔄 Hot Reload

The development environment includes hot reload for:
- Python code changes
- Template changes
- Static file changes

Changes are automatically reflected without restarting containers.

## 📦 Production Deployment

### Build Production Image

```bash
# Build production image
docker build -f webapp/Dockerfile -t gcp-data-analysis-platform ./webapp

# Run production container
docker run -p 8080:8080 \
  -e GCP_PROJECT=your-project \
  -e FLASK_SECRET_KEY=your-secret \
  gcp-data-analysis-platform
```

### Production Compose

```bash
# Start production environment
make prod

# Or manually
docker-compose up --build
```

## 🔒 Security Considerations

- Change `FLASK_SECRET_KEY` in production
- Use proper service account credentials
- Enable HTTPS in production
- Configure firewall rules
- Set up proper IAM permissions

## 🌐 Network Configuration

All services communicate via the `data-analysis-network` Docker network. External access is only available through exposed ports.

## 📈 Monitoring

### Health Checks

- Web App: `/healthz` endpoint
- Redis: Built-in health monitoring
- Emulators: Admin interfaces on respective ports

### Logs

All services log to stdout/stderr and can be viewed with `make logs`.

## 🧪 Testing

```bash
# Run unit tests
make test

# Run with coverage
docker-compose -f docker-compose.dev.yml run --rm webapp pytest --cov=.

# Run specific test
docker-compose -f docker-compose.dev.yml run --rm webapp pytest tests/test_upload.py
```

## 🚨 Troubleshooting

### Common Issues

1. **Port conflicts**: Check if ports 8080, 6379, 4443, 9050, 8432 are available
2. **Permission issues**: Ensure Docker has proper file permissions
3. **Service account**: Verify credentials file exists and is valid
4. **Memory**: Increase Docker memory allocation if needed

### Reset Environment

```bash
# Complete reset
make clean
docker system prune -f
make setup
make dev
```

## 📝 Development Workflow

1. Make code changes
2. Test locally with `make dev`
3. Run tests with `make test`
4. Commit changes
5. Deploy to staging/production

## 🤝 Contributing

When contributing:
1. Use the development environment
2. Add tests for new features
3. Update documentation
4. Follow the existing code style
