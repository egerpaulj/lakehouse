"""Generate independent bronze -> silver Airflow DAGs per configured pipeline.

Per pipeline entry in ``responses_s0_pipeline.yaml`` four DAGs are created:

* ``responses_s0_<name>_cdf``       - Delta CDF stream from b0 into s0
* ``responses_s0_<name>_summary``   - llm-summary -> ``summary``
* ``responses_s0_<name>_ner_nel``   - llm-ner-nel -> ``ner_nel`` (JSON)
* ``responses_s0_<name>_embedding`` - embedding API -> ``text_embedding`` and
  ``summary_embedding`` (only rows that already have a summary)

The DAGs are not chained; each has its own schedule, pause state and limit.
Every decorator only processes rows that are still missing its value, so they
can run in any order or concurrently with the CDF stream.
The CDF stream runs in the Airflow Python environment; the decorators run in
``/opt/decorators-venv`` which holds the LLM client dependencies.
"""

from datetime import datetime
from pathlib import Path
from shlex import quote

import yaml
from airflow import DAG
from airflow.operators.bash import BashOperator

CONFIG_PATH = Path(__file__).with_name("responses_s0_pipeline.yaml")
SPARK_CONNECT = "SPARK_CONNECT_URL=sc://spark-connect:15002"
DECORATOR_PYTHON = "/opt/decorators-venv/bin/python"
JOBS = ("cdf", "summary", "ner_nel", "embedding")
# Job name -> decorate_s0.py --decorator value
DECORATOR_NAMES = {"summary": "summary", "ner_nel": "ner_nel", "embedding": "embeddings"}


def load_pipelines() -> list:
    with CONFIG_PATH.open() as config_file:
        return (yaml.safe_load(config_file) or {}).get("pipelines", [])


def command(python: str, script: str, args: list) -> str:
    return " ".join(
        [SPARK_CONNECT, python, f"/opt/spark-apps/{script}"] + [quote(str(a)) for a in args]
    )


def cdf_command(p: dict) -> str:
    checkpoint = p.get("checkpoint_location") or (
        f"s3a://warehouse/checkpoints/{p['target_table'].replace('.', '_')}"
    )
    args = [
        "--source-table", p["source_table"],
        "--target-table", p["target_table"],
        "--checkpoint-location", checkpoint,
        "--merge-key", p.get("merge_key", "_id"),
    ]
    return command("PYTHONPATH=/opt/lakehouse_data/src python", "cdf_b0_to_s0.py", args)


def decorator_command(p: dict, job: str) -> str:
    section = p.get(job) or {}
    args = [
        "--decorator", DECORATOR_NAMES[job],
        "--table", p["target_table"],
        "--key-column", p.get("merge_key", "_id"),
        "--text-column", p.get("text_column", "text"),
        "--limit", section.get("limit", 100),
    ]
    if job == "embedding":
        args += ["--embedding-api-url", section.get("api_url", "http://embedding-api:8000")]
    else:
        if section.get("model"):
            args += ["--model", section["model"]]
        args += ["--strategy", section.get("strategy", "ollama")]
        args += ["--ollama-host", p.get("ollama_host", "http://ollama:11434")]
    return command(
        f"PYTHONPATH=/opt/lakehouse_data/src {DECORATOR_PYTHON}", "decorate_s0.py", args
    )


def create_dag(p: dict, job: str) -> DAG:
    section = p.get(job) or {}
    bash = cdf_command(p) if job == "cdf" else decorator_command(p, job)
    with DAG(
        dag_id=f"responses_s0_{p['name']}_{job}",
        description=f"{job}: {p['source_table']} -> {p['target_table']}",
        start_date=datetime(2024, 1, 1),
        schedule=section.get("schedule", p.get("schedule", "@hourly")),
        catchup=False,
        max_active_runs=1,
        is_paused_upon_creation=bool(section.get("paused", False)),
        tags=["spark", "silver", job],
    ) as dag:
        BashOperator(task_id=job, bash_command=bash)
    return dag


for pipeline in load_pipelines():
    for job_name in JOBS:
        dag_obj = create_dag(pipeline, job_name)
        globals()[dag_obj.dag_id] = dag_obj
