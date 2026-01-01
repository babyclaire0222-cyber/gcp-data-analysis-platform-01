import os
from google.cloud import bigquery, storage
from flask import Request

PROJECT_ID = os.environ.get('GCP_PROJECT', 'project-64f58cb2-a1cc-4618-9a0')
BIGQUERY_DATASET = os.environ.get('BIGQUERY_DATASET', 'analysis_dataset')
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'project-64f58cb2-data-analysis')

bq_client = bigquery.Client()
storage_client = storage.Client()

# Define a flexible schema for analysis results (auto-detected from source)
def get_dynamic_schema(table_name):
    """Create schema based on source table structure."""
    try:
        table_ref = bq_client.dataset(BIGQUERY_DATASET).table(table_name)
        table = bq_client.get_table(table_ref)
        return table.schema
    except Exception:
        # Fallback to basic schema if table doesn't exist
        return [
            bigquery.SchemaField("department", "STRING"),
            bigquery.SchemaField("amount", "FLOAT"),
            bigquery.SchemaField("date", "TIMESTAMP"),
            bigquery.SchemaField("expense_type", "STRING")
        ]

def _dataset_location():
    """Read actual dataset location (safer than assuming)."""
    try:
        ds = bq_client.get_dataset(f"{PROJECT_ID}.{BIGQUERY_DATASET}")
        return ds.location or "US"  # Default to US if location is not set
    except Exception as e:
        print(f"Error getting dataset location: {e}")
        return "US"  # Fallback location
    
def create_table_from_csv_if_not_exists(table_name):
    """Creates a BigQuery table from a CSV in GCS if it doesn't exist."""
    table_ref = bq_client.dataset(BIGQUERY_DATASET).table(table_name)
    try:
        bq_client.get_table(table_ref)
        return  # Table already exists
    except Exception:
        print(f"Table {table_name} not found. Searching for CSV in GCS...")

    # Possible CSV paths
    possible_paths = [
        f"{table_name}.csv",
        f"uploads/{table_name}.csv",
        f"data/{table_name}.csv",
        f"raw/{table_name}.csv"
    ]

    bucket = storage_client.bucket(BUCKET_NAME)
    csv_uri = None

    for path in possible_paths:
        blob = bucket.blob(path)
        if blob.exists():
            csv_uri = f"gs://{BUCKET_NAME}/{path}"
            print(f"Found CSV at {path}")
            break

    if not csv_uri:
        raise ValueError(f"No CSV file found in GCS for table {table_name}")

    # Load into BigQuery with autodetect schema
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,
        autodetect=True
    )

    load_job = bq_client.load_table_from_uri(csv_uri, table_ref, job_config=job_config)
    load_job.result()
    print(f"Created BigQuery table {table_name} from CSV: {csv_uri}")

def run_analysis(request: Request):
    table_name = request.args.get('table')

    if not table_name:
        return "Missing 'table' query parameter. Example: ?table=my_table", 400

    # Ensure table exists (create if CSV available)
    create_table_from_csv_if_not_exists(table_name)

    # Query first 10 rows
    query = f"SELECT * FROM `{PROJECT_ID}.{BIGQUERY_DATASET}.{table_name}` LIMIT 10"
    results = bq_client.query(query).result()

    # Save results to CSV in /tmp
    result_file = "/tmp/results.csv"
    with open(result_file, "w") as f:
        headers = [field.name for field in results.schema]
        f.write(",".join(headers) + "\n")
        for row in results:
            f.write(",".join([str(x) for x in row.values()]) + "\n")

    # Upload analysis results to GCS
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(f"analysis_results/{table_name}_results.csv")
    blob.upload_from_filename(result_file)

    # Load into BigQuery analysis table with dynamic schema
    destination_table = f"{PROJECT_ID}.{BIGQUERY_DATASET}.{table_name}_analysis"
    job_config = bigquery.LoadJobConfig(
        schema=get_dynamic_schema(table_name),
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        create_disposition=bigquery.CreateDisposition.CREATE_IF_NEEDED
    )

    with open(result_file, "rb") as source_file:
        load_job = bq_client.load_table_from_file(source_file, destination_table, job_config=job_config)
        load_job.result()

    return (
        f"Analysis complete for table '{table_name}'.\n"
        f"Results saved to GCS and BigQuery table '{table_name}_analysis'.\n"
        f"Connect Looker Studio to: {destination_table}"
    )
