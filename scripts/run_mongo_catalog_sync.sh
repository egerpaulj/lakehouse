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
  env SPARK_CONNECT_URL=sc://spark-connect:15002 \
  /opt/conda/bin/python \
  /opt/spark-apps/mongo_catalog_sync.py "$@"
