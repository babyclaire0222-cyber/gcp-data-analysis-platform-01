"""
Development version of the web application with emulator support.
This file can be used instead of main.py for local development.
"""

import os
import json
import csv
import pandas as pd
import logging
import time
from functools import wraps
from flask import Flask, request, render_template, send_file, jsonify, g
import redis
from google.cloud import storage, bigquery
from google.cloud import pubsub_v1
import re
import io
from google.api_core.exceptions import NotFound

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'local-dev-secret-key')

# ===============================
# 🔹 Development Configuration
# ===============================
IS_DEVELOPMENT = os.environ.get('FLASK_ENV') == 'development'

# Redis client for rate limiting
try:
    redis_client = redis.from_url(os.environ.get('REDIS_URL', 'redis://localhost:6379/0'))
    redis_client.ping()
    logger.info("Connected to Redis")
except:
    logger.warning("Redis not available, using in-memory rate limiting")
    redis_client = None

# GCP Clients with emulator support
def get_gcs_client():
    """Get GCS client with emulator support."""
    if os.environ.get('STORAGE_EMULATOR_HOST'):
        # For local development with emulator
        client = storage.Client(
            project=os.environ.get('GCP_PROJECT', 'local-development'),
            client_options={'api_endpoint': os.environ.get('STORAGE_EMULATOR_HOST')}
        )
        return client
    return storage.Client()

def get_bq_client():
    """Get BigQuery client with emulator support."""
    if os.environ.get('BIGQUERY_EMULATOR_HOST'):
        # For local development with emulator
        client = bigquery.Client(
            project=os.environ.get('GCP_PROJECT', 'local-development'),
            client_options={'api_endpoint': os.environ.get('BIGQUERY_EMULATOR_HOST')}
        )
        return client
    return bigquery.Client()

def get_pubsub_client():
    """Get Pub/Sub client with emulator support."""
    if os.environ.get('PUBSUB_EMULATOR_HOST'):
        # For local development with emulator
        client = pubsub_v1.PublisherClient(
            client_options={'api_endpoint': os.environ.get('PUBSUB_EMULATOR_HOST')}
        )
        return client
    return pubsub_v1.PublisherClient()

# Initialize clients
storage_client = get_gcs_client()
bq_client = get_bq_client()
publisher = get_pubsub_client()

# GCP Configuration
PROJECT_ID = os.environ.get('GCP_PROJECT', 'local-development')
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'local-bucket')
PUBSUB_TOPIC_FOR_SQL_IMPORT = os.environ.get('PUBSUB_TOPIC_FOR_SQL_IMPORT', 'sql-import-topic')
BIGQUERY_DATASET = os.environ.get('BIGQUERY_DATASET', 'analysis_dataset')

# ===============================
# 🔹 Security Middleware
# ===============================
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses."""
    if not IS_DEVELOPMENT:
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self'; connect-src 'self'"
    return response

# Rate limiting with Redis or in-memory
def rate_limit(max_requests=10, window_seconds=60):
    """Rate limiting decorator with Redis fallback."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
            now = time.time()
            key = f"rate_limit:{client_ip}"
            
            if redis_client:
                # Redis-based rate limiting
                try:
                    current = redis_client.get(key)
                    if current and int(current) >= max_requests:
                        return jsonify({"error": "Rate limit exceeded. Please try again later."}), 429
                    
                    pipe = redis_client.pipeline()
                    pipe.incr(key)
                    pipe.expire(key, window_seconds)
                    pipe.execute()
                except redis.RedisError:
                    logger.warning("Redis error, falling back to in-memory rate limiting")
                    # Fallback to in-memory
                    return _in_memory_rate_limit(client_ip, max_requests, window_seconds, f)
            else:
                # In-memory rate limiting
                return _in_memory_rate_limit(client_ip, max_requests, window_seconds, f)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# In-memory rate limiting fallback
rate_limit_storage = {}

def _in_memory_rate_limit(client_ip, max_requests, window_seconds, func):
    """In-memory rate limiting fallback."""
    now = time.time()
    
    # Clean old entries
    rate_limit_storage[client_ip] = [
        req_time for req_time in rate_limit_storage.get(client_ip, [])
        if now - req_time < window_seconds
    ]
    
    # Check rate limit
    if len(rate_limit_storage[client_ip]) >= max_requests:
        logger.warning(f"Rate limit exceeded for IP: {client_ip}")
        return jsonify({"error": "Rate limit exceeded. Please try again later."}), 429
    
    # Add current request
    rate_limit_storage.setdefault(client_ip, []).append(now)
    
    return func()

# ===============================
# 🔹 Mock Authentication (Development)
# ===============================
@app.before_request
def mock_auth():
    """Mock authentication for development."""
    if IS_DEVELOPMENT:
        g.user_email = "dev-user@example.com"
    else:
        # Use real IAP authentication
        raw = request.headers.get("X-Goog-Authenticated-User-Email", "") or ""
        g.user_email = raw.split(":", 1)[1] if raw.startswith("accounts.google.com:") else None

def current_user_email():
    """Return the authenticated user's email."""
    return getattr(g, 'user_email', None)

def require_user(fn):
    """Decorator that ensures the request is authenticated."""
    @wraps(fn)
    def _wrap(*args, **kwargs):
        email = current_user_email()
        if not email:
            return jsonify({"success": False, "error": "Unauthorized"}), 401
        return fn(*args, **kwargs)
    return _wrap

# ===============================
# 🔹 Helper Functions
# ===============================
def validate_table_name(table_name):
    """Strict table name validation to prevent SQL injection."""
    if not table_name:
        raise ValueError("Table name cannot be empty")
    
    # Only allow alphanumeric characters and underscores
    if not re.match(r'^[a-zA-Z0-9_]{1,128}$', table_name):
        raise ValueError("Invalid table name. Only letters, numbers, and underscores allowed (max 128 chars)")
    
    # Prevent SQL keywords
    sql_keywords = {'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 'EXEC', 'UNION', 'WHERE', 'JOIN'}
    if table_name.upper() in sql_keywords:
        raise ValueError("Table name cannot be a SQL keyword")
    
    return table_name

def ensure_dataset_exists(dataset_id):
    """Create dataset if it doesn't already exist."""
    if IS_DEVELOPMENT and os.environ.get('BIGQUERY_EMULATOR_HOST'):
        # Skip dataset creation in emulator mode
        return
    
    dataset_ref = bq_client.dataset(dataset_id)
    try:
        bq_client.get_dataset(dataset_ref)
    except Exception:
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "asia-southeast1"
        bq_client.create_dataset(dataset)

def load_to_bigquery(file_path, filename, table_name):
    """Loads supported file types into BigQuery with autodetect schema."""
    ensure_dataset_exists(BIGQUERY_DATASET)

    ext = os.path.splitext(filename)[1].lower()
    tmp_path = file_path

    # Convert Excel to CSV before loading
    if ext in [".xls", ".xlsx"]:
        df = pd.read_excel(file_path)
        tmp_path = f"/tmp/{table_name}.csv"
        df.to_csv(tmp_path, index=False)
        source_format = bigquery.SourceFormat.CSV
        skip_rows = 1
    elif ext == ".csv":
        source_format = bigquery.SourceFormat.CSV
        skip_rows = 1
    elif ext == ".json":
        source_format = bigquery.SourceFormat.NEWLINE_DELIMITED_JSON
        skip_rows = 0
    elif ext == ".parquet":
        source_format = bigquery.SourceFormat.PARQUET
        skip_rows = 0
    else:
        raise ValueError("Unsupported file type. Use CSV, Excel, JSON, or Parquet.")

    # Upload to GCS
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(f"uploads/{filename}")
    blob.upload_from_filename(tmp_path)

    # Load into BigQuery
    table_id = f"{PROJECT_ID}.{BIGQUERY_DATASET}.{table_name}"
    job_config = bigquery.LoadJobConfig(
        autodetect=True,
        source_format=source_format,
        skip_leading_rows=skip_rows,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )

    with open(tmp_path, "rb") as source_file:
        load_job = bq_client.load_table_from_file(source_file, table_id, job_config=job_config)

    load_job.result()

# ===============================
# 🔹 Routes
# ===============================
@app.route('/', methods=['GET', 'POST'])
@require_user
@rate_limit(max_requests=5, window_seconds=60)
def index():
    user_email = current_user_email()
    logger.info(f"Request from user: {user_email}")

    if request.method == 'POST':
        uploaded_file = request.files.get('file')
        if not uploaded_file:
            return jsonify({"success": False, "error": "No file uploaded"}), 400
            
        if uploaded_file.filename == '':
            return jsonify({"success": False, "error": "No file selected"}), 400

        file_ext = os.path.splitext(uploaded_file.filename)[1].lower()
        file_path = f"/tmp/{uploaded_file.filename}"
        
        try:
            uploaded_file.save(file_path)
            logger.info(f"File saved: {uploaded_file.filename}")

            table_name = os.path.splitext(uploaded_file.filename)[0].replace(" ", "_").lower()
            table_name = validate_table_name(table_name)
            
            logger.info(f"Processing file: {uploaded_file.filename}, table: {table_name}")

            if file_ext == '.sql':
                # Upload raw SQL to GCS then notify Pub/Sub
                bucket = storage_client.bucket(BUCKET_NAME)
                blob = bucket.blob(f"uploads/{uploaded_file.filename}")
                blob.upload_from_filename(file_path)
                logger.info(f"SQL file uploaded to GCS: {uploaded_file.filename}")

                message_data = {'name': uploaded_file.filename, 'bucket': BUCKET_NAME}
                if os.environ.get('PUBSUB_EMULATOR_HOST'):
                    # Mock Pub/Sub for development
                    logger.info(f"Mock Pub/Sub message: {message_data}")
                else:
                    publisher.publish(publisher.topic_path(PROJECT_ID, PUBSUB_TOPIC_FOR_SQL_IMPORT), 
                                    data=json.dumps(message_data).encode('utf-8'))
                    logger.info(f"Pub/Sub message published for SQL file: {uploaded_file.filename}")

            elif file_ext in ['.xlsx', '.xls']:
                # Convert Excel to CSV first
                csv_path = f"/tmp/{table_name}.csv"
                df = pd.read_excel(file_path)
                df.to_csv(csv_path, index=False)
                logger.info(f"Excel file converted to CSV: {uploaded_file.filename}")
                load_to_bigquery(csv_path, f"{table_name}.csv", table_name)

            elif file_ext in ['.csv', '.json', '.parquet']:
                load_to_bigquery(file_path, uploaded_file.filename, table_name)

            else:
                return jsonify({"success": False, "error": "Unsupported file format. Supported: CSV, Excel, JSON, Parquet, SQL"}), 400

            return jsonify({
                "success": True,
                "message": f"✅ Uploaded {uploaded_file.filename} successfully",
                "table": table_name,
                "user": user_email,
                "development_mode": True
            })

        except ValueError as ve:
            logger.error(f"Validation error for {uploaded_file.filename}: {str(ve)}")
            return jsonify({"success": False, "error": str(ve)}), 400
        except Exception as e:
            logger.error(f"Error processing {uploaded_file.filename}: {str(e)}", exc_info=True)
            return jsonify({"success": False, "error": f"Error processing file: {str(e)}"}), 500
        finally:
            # Clean up temporary files
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                csv_path = f"/tmp/{table_name}.csv"
                if os.path.exists(csv_path):
                    os.remove(csv_path)
            except Exception as cleanup_error:
                logger.warning(f"Error cleaning up temporary files: {cleanup_error}")

    return render_template('index.html')

@app.route("/healthz")
def healthz():
    """Health check endpoint."""
    return "ok", 200

@app.route("/whoami")
@require_user
def whoami():
    """Return the authenticated user's email."""
    return jsonify({"success": True, "email": current_user_email(), "development_mode": IS_DEVELOPMENT})

@app.route("/dev-info")
@require_user
def dev_info():
    """Development information endpoint."""
    if not IS_DEVELOPMENT:
        return jsonify({"error": "Not available in production"}), 404
    
    return jsonify({
        "development_mode": True,
        "gcp_project": PROJECT_ID,
        "bucket_name": BUCKET_NAME,
        "bigquery_dataset": BIGQUERY_DATASET,
        "pubsub_topic": PUBSUB_TOPIC_FOR_SQL_IMPORT,
        "redis_connected": redis_client is not None,
        "emulators": {
            "storage": os.environ.get('STORAGE_EMULATOR_HOST'),
            "bigquery": os.environ.get('BIGQUERY_EMULATOR_HOST'),
            "pubsub": os.environ.get('PUBSUB_EMULATOR_HOST')
        }
    })

# ===============================
# 🔹 Start Flask App
# ===============================
if __name__ == '__main__':
    if IS_DEVELOPMENT:
        app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=True)
    else:
        app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
