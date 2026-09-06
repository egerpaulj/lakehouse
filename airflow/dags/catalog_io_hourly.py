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
            "spark-submit "
            "--master spark://spark-master:7077 "
            "--conf spark.jars.ivy=/tmp/.ivy2 "
            "--conf spark.driver.bindAddress=0.0.0.0 "
            "--conf spark.driver.host=airflow "
            "--jars /opt/spark-jars/delta-spark_2.12-3.2.0.jar,"
            "/opt/spark-jars/delta-storage-3.2.0.jar,"
            "/opt/spark-jars/hadoop-aws-3.3.4.jar,"
            "/opt/spark-jars/aws-java-sdk-bundle-1.12.262.jar,"
            "/opt/spark-jars/wildfly-openssl-1.0.7.Final.jar "
            "/opt/spark-apps/catalog_io.py append"
        ),
    )
