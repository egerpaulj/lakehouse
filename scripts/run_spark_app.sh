#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
mode="${1:-write}"
case "$mode" in
  write|read|append|schema|history|time-travel) ;;
  *) echo "Usage: $0 [write|read|append|schema|history|time-travel]" >&2; exit 2 ;;
esac

docker compose run --rm --no-deps spark-worker \
  /opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 \
  --conf spark.jars.ivy=/tmp/.ivy2 \
  --packages io.delta:delta-spark_2.12:3.2.0,org.apache.hadoop:hadoop-aws:3.3.4 \
  /opt/spark-apps/delta_io.py "$mode"
