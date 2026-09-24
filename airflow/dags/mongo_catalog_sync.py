"""Generate one Airflow DAG per configured MongoDB-to-catalog sync job.

Each entry in ``mongo_catalog_sync_jobs.yaml`` describes an independently
scheduled instance of ``spark-apps/mongo_catalog_sync.py``: which MongoDB
collection to read, which catalog database/table to append to, and how often
to run. Adding a new instance only requires adding an entry to the YAML file;
no Python changes are needed.
"""

from datetime import datetime
from pathlib import Path

import yaml
from airflow import DAG
from airflow.operators.bash import BashOperator

CONFIG_PATH = Path(__file__).with_name("mongo_catalog_sync_jobs.yaml")

def load_job_configs() -> list:
    with CONFIG_PATH.open() as config_file:
        config = yaml.safe_load(config_file) or {}
    return config.get("jobs", [])


def build_spark_submit_command(job: dict) -> str:
    args = [
        "--mongo-database",
        job["mongo_database"],
        "--mongo-collection",
        job["mongo_collection"],
        "--catalog-database",
        job["catalog_database"],
        "--catalog-table",
        job["catalog_table"],
    ]
    if job.get("mongo_uri"):
        args += ["--mongo-uri", job["mongo_uri"]]
    if job.get("batch_limit"):
        args += ["--batch-limit", str(job["batch_limit"])]
    if job.get("dry_run"):
        args += ["--dry-run"]

    args_str = " ".join(args)
    return (
        "SPARK_CONNECT_URL=sc://spark-connect:15002 "
        "python "
        f"/opt/spark-apps/mongo_catalog_sync.py {args_str}"
    )


def create_dag(job: dict) -> DAG:
    dag_id = f"mongo_catalog_sync_{job['name']}"
    with DAG(
        dag_id=dag_id,
        description=(
            f"Sync {job['mongo_database']}.{job['mongo_collection']} into "
            f"{job['catalog_database']}.{job['catalog_table']}"
        ),
        start_date=datetime(2024, 1, 1),
        schedule=job["schedule"],
        catchup=False,
        max_active_runs=1,
        tags=["spark", "mongo", "catalog"],
    ) as dag:
        BashOperator(
            task_id="sync_mongo_to_catalog",
            bash_command=build_spark_submit_command(job),
        )
    return dag


for job_config in load_job_configs():
    globals()[f"mongo_catalog_sync_{job_config['name']}"] = create_dag(job_config)
