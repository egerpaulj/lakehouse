"""Ingest new books/files from inbox folders into Delta tables hourly."""

from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator


with DAG(
    dag_id="books_ingest_hourly",
    description="Convert books to markdown, split chapters, append to Delta",
    start_date=datetime(2024, 1, 1),
    schedule="@hourly",
    catchup=False,
    max_active_runs=1,
    tags=["spark", "books"],
) as dag:
    ingest_books = BashOperator(
        task_id="ingest_books",
        bash_command=(
            "SPARK_CONNECT_URL=sc://spark-connect:15002 "
            "/opt/books-venv/bin/python /opt/spark-apps/ingest_files.py "
            "--folder /opt/airflow/data/books/inbox "
            "--catalog crawler --table books_b0 --scan-type book"
        ),
    )

    ingest_files = BashOperator(
        task_id="ingest_files",
        bash_command=(
            "SPARK_CONNECT_URL=sc://spark-connect:15002 "
            "/opt/books-venv/bin/python /opt/spark-apps/ingest_files.py "
            "--folder /opt/airflow/data/files/inbox "
            "--catalog crawler --table documents_b0 --scan-type generic"
        ),
    )
