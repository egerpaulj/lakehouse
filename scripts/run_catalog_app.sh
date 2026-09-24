#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
mode="${1:-write}"
case "$mode" in
  write|read|append|schema|history|time-travel) ;;
  *) echo "Usage: $0 [write|read|append|schema|history|time-travel]" >&2; exit 2 ;;
esac

docker compose run --rm --no-deps spark-worker \
  env SPARK_CONNECT_URL=sc://spark-connect:15002 \
  /opt/conda/bin/python \
  /opt/spark-apps/catalog_io.py "$mode"
