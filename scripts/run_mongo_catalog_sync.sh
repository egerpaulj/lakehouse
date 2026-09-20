#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

usage() {
  cat >&2 <<'EOF'
Usage: run_mongo_catalog_sync.sh --mongo-database DB --mongo-collection COLL \
       --catalog-database CATALOG_DB --catalog-table CATALOG_TABLE \
       [--mongo-uri URI] [--batch-limit N] [--dry-run]
EOF
  exit 2
}

[ "$#" -ge 1 ] || usage

docker compose run --rm --no-deps spark-worker \
  /opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 \
  --conf spark.jars.ivy=/tmp/.ivy2 \
  --packages io.delta:delta-spark_2.12:3.2.0,org.apache.hadoop:hadoop-aws:3.3.4,org.mongodb.spark:mongo-spark-connector_2.12:10.4.1 \
  /opt/spark-apps/mongo_catalog_sync.py "$@"
