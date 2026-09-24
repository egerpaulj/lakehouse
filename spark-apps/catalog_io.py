"""Demonstrate Delta Lake operations through the Hive catalog."""

import argparse
import os

from pyspark.sql import SparkSession

DATABASE = "catalog_examples"
TABLE = f"spark_catalog.{DATABASE}.people"
SCHEMA_TABLE = f"spark_catalog.{DATABASE}.people_schema"
TIME_TRAVEL_TABLE = f"spark_catalog.{DATABASE}.people_history"
EXPECTED = [(1, "Ada", "engineering"), (2, "Grace", "data")]


def create_spark() -> SparkSession:
    return (
        SparkSession.builder.appName("delta-catalog-example")
        .remote(os.environ.get("SPARK_CONNECT_URL", "sc://spark-connect:15002"))
        .getOrCreate()
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode",
        choices=("write", "read", "append", "schema", "history", "time-travel"),
    )
    args = parser.parse_args()
    spark = create_spark()
    try:
        spark.sql(
            f"CREATE DATABASE IF NOT EXISTS {DATABASE} "
            f"LOCATION 's3a://warehouse/{DATABASE}'"
        )
        if args.mode == "write":
            spark.createDataFrame(EXPECTED, ["id", "name", "team"]).write.format("delta").mode("overwrite").saveAsTable(TABLE)
            print(f"Wrote Delta table {TABLE}")
        elif args.mode == "read":
            actual = [tuple(row) for row in spark.table(TABLE).orderBy("id").collect()]
            if actual != EXPECTED:
                raise RuntimeError(f"Delta read verification failed: expected {EXPECTED}, got {actual}")
            print(f"Read and verified Delta table: {actual}")
        elif args.mode == "append":
            spark.createDataFrame([(3, "Lin", "platform")], ["id", "name", "team"]).write.format("delta").mode("append").saveAsTable(TABLE)
            count = spark.table(TABLE).count()
            print(f"Appended one row; Delta table now contains {count} rows")
        elif args.mode == "schema":
            spark.createDataFrame([(1, "Ada")], ["id", "name"]).write.format("delta").mode("overwrite").saveAsTable(SCHEMA_TABLE)
            spark.createDataFrame([(2, "Grace", "data")], ["id", "name", "team"]).write.format("delta").option("mergeSchema", "true").mode("append").saveAsTable(SCHEMA_TABLE)
            columns = spark.table(SCHEMA_TABLE).columns
            if columns != ["id", "name", "team"]:
                raise RuntimeError(f"Schema evolution failed: got columns {columns}")
            print(f"Schema evolution succeeded: {columns}")
        elif args.mode == "history":
            history = spark.sql(f"DESCRIBE HISTORY {TABLE}").select("version", "operation").collect()
            print(f"Delta history: {[(row.version, row.operation) for row in history]}")
        else:
            spark.createDataFrame([(1, "before")], ["id", "state"]).write.format("delta").mode("overwrite").saveAsTable(TIME_TRAVEL_TABLE)
            spark.createDataFrame([(2, "after")], ["id", "state"]).write.format("delta").mode("append").saveAsTable(TIME_TRAVEL_TABLE)
            version_zero = [
                tuple(row)
                for row in spark.read.format("delta").option("versionAsOf", 0).table(TIME_TRAVEL_TABLE).collect()
            ]
            if version_zero != [(1, "before")]:
                raise RuntimeError(f"Time travel verification failed: got {version_zero}")
            print(f"Time travel version 0: {version_zero}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
