"""Run the existing catalog IO Spark app once per hour."""

from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator


with DAG(
    dag_id="catalog_io_hourly",
    description="Append the next catalog_io record to the Delta catalog",
    start_date=datetime(2024, 1, 1),
    schedule="@hourly",
    catchup=False,
    max_active_runs=1,
    tags=["spark", "catalog"],
) as dag:
    append_catalog_data = BashOperator(
        task_id="append_catalog_data",
        bash_command=(
            "SPARK_CONNECT_URL=sc://spark-connect:15002 "
            "python "
            "/opt/spark-apps/catalog_io.py append"
        ),
    )
