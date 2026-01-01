"""
Simple development version that works without GCP credentials.
"""

import os
import json
import csv
import pandas as pd
import logging
import time
from functools import wraps
from flask import Flask, request, render_template, send_file, jsonify, g
import re
import io

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'local-dev-secret-key')

# ===============================
# 🔹 Development Configuration
# ===============================
IS_DEVELOPMENT = True

# ===============================
# 🔹 Mock Authentication
# ===============================
@app.before_request
def mock_auth():
    """Mock authentication for development."""
    g.user_email = "dev-user@example.com"

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
# 🔹 Mock GCP Operations
# ===============================
class MockGCS:
    def bucket(self, name):
        return MockBucket(name)

class MockBucket:
    def __init__(self, name):
        self.name = name
    
    def blob(self, name):
        return MockBlob(name)

class MockBlob:
    def __init__(self, name):
        self.name = name
    
    def upload_from_filename(self, filename):
        logger.info(f"Mock GCS: Uploaded {filename} to {self.name}")

class MockBigQuery:
    def dataset(self, dataset_id):
        return MockDataset(dataset_id)

class MockDataset:
    def __init__(self, dataset_id):
        self.dataset_id = dataset_id
    
    def table(self, table_name):
        return MockTable(table_name)

class MockTable:
    def __init__(self, table_name):
        self.table_name = table_name
    
    def get_schema(self):
        return [
            {"name": "department", "type": "STRING"},
            {"name": "amount", "type": "FLOAT"},
            {"name": "date", "type": "TIMESTAMP"},
            {"name": "expense_type", "type": "STRING"}
        ]

class MockPubSub:
    def topic_path(self, project_id, topic):
        return f"projects/{project_id}/topics/{topic}"
    
    def publish(self, topic, data):
        logger.info(f"Mock Pub/Sub: Published to {topic}: {data.decode()}")

# Initialize mock clients
storage_client = MockGCS()
bq_client = MockBigQuery()
publisher = MockPubSub()

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
    return response

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

def load_to_bigquery(file_path, filename, table_name):
    """Mock BigQuery loading for development."""
    logger.info(f"Mock BigQuery: Loading {filename} into table {table_name}")
    
    # Read and validate the file
    ext = os.path.splitext(filename)[1].lower()
    
    if ext in [".xls", ".xlsx"]:
        df = pd.read_excel(file_path)
        logger.info(f"Mock: Processed Excel file with {len(df)} rows")
    elif ext == ".csv":
        df = pd.read_csv(file_path)
        logger.info(f"Mock: Processed CSV file with {len(df)} rows")
    elif ext == ".json":
        df = pd.read_json(file_path, lines=True)
        logger.info(f"Mock: Processed JSON file with {len(df)} rows")
    else:
        raise ValueError("Unsupported file type. Use CSV, Excel, or JSON.")
    
    # Mock upload to GCS
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(f"uploads/{filename}")
    blob.upload_from_filename(file_path)
    
    return True

# ===============================
# 🔹 Routes
# ===============================
@app.route('/', methods=['GET', 'POST'])
@require_user
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
                # Mock SQL processing
                bucket = storage_client.bucket(BUCKET_NAME)
                blob = bucket.blob(f"uploads/{uploaded_file.filename}")
                blob.upload_from_filename(file_path)
                logger.info(f"Mock: SQL file uploaded to GCS: {uploaded_file.filename}")

                message_data = {'name': uploaded_file.filename, 'bucket': BUCKET_NAME}
                publisher.publish(publisher.topic_path(PROJECT_ID, PUBSUB_TOPIC_FOR_SQL_IMPORT), 
                                data=json.dumps(message_data).encode('utf-8'))
                logger.info(f"Mock: Pub/Sub message published for SQL file: {uploaded_file.filename}")

            elif file_ext in ['.xlsx', '.xls', '.csv', '.json']:
                load_to_bigquery(file_path, uploaded_file.filename, table_name)

            else:
                return jsonify({"success": False, "error": "Unsupported file format. Supported: CSV, Excel, JSON, SQL"}), 400

            return jsonify({
                "success": True,
                "message": f"✅ Uploaded {uploaded_file.filename} successfully (Mock Mode)",
                "table": table_name,
                "user": user_email,
                "development_mode": True,
                "mock_mode": True
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
    return jsonify({"success": True, "email": current_user_email(), "development_mode": IS_DEVELOPMENT, "mock_mode": True})

@app.route("/dev-info")
@require_user
def dev_info():
    """Development information endpoint."""
    return jsonify({
        "development_mode": True,
        "mock_mode": True,
        "gcp_project": PROJECT_ID,
        "bucket_name": BUCKET_NAME,
        "bigquery_dataset": BIGQUERY_DATASET,
        "pubsub_topic": PUBSUB_TOPIC_FOR_SQL_IMPORT,
        "message": "Running in mock mode - no real GCP operations"
    })

# ===============================
# 🔹 Start Flask App
# ===============================
if __name__ == '__main__':
    if IS_DEVELOPMENT:
        app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=True)
    else:
        app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
