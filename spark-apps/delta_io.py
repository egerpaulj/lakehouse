"""Demonstrate common Delta Lake operations in MinIO through Spark."""

import argparse

from pyspark.sql import SparkSession

TARGET = "s3a://warehouse/examples/people"
SCHEMA_TARGET = "s3a://warehouse/examples/people_schema"
TIME_TRAVEL_TARGET = "s3a://warehouse/examples/people_history"
EXPECTED = [(1, "Ada", "engineering"), (2, "Grace", "data")]


def create_spark() -> SparkSession:
    builder = (
        SparkSession.builder.appName("delta-minio-example")
        .master("spark://spark-master:7077")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .config("spark.hadoop.hive.metastore.uris", "thrift://hive-metastore:9083")
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000")
        .config("spark.hadoop.fs.s3a.access.key", "minioadmin")
        .config("spark.hadoop.fs.s3a.secret.key", "minioadmin")
        .config("spark.hadoop.fs.s3a.aws.credentials.provider", "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider")
        .config("spark.hadoop.fs.s3a.endpoint.region", "us-east-1")
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
    )
    return builder.enableHiveSupport().getOrCreate()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode",
        choices=("write", "read", "append", "schema", "history", "time-travel"),
    )
    args = parser.parse_args()
    spark = create_spark()
    try:
        if args.mode == "write":
            spark.createDataFrame(EXPECTED, ["id", "name", "team"]).write.format("delta").mode("overwrite").save(TARGET)
            print(f"Wrote Delta table to {TARGET}")
        elif args.mode == "read":
            actual = [tuple(row) for row in spark.read.format("delta").load(TARGET).orderBy("id").collect()]
            if actual != EXPECTED:
                raise RuntimeError(f"Delta read verification failed: expected {EXPECTED}, got {actual}")
            print(f"Read and verified Delta table: {actual}")
        elif args.mode == "append":
            spark.createDataFrame([(3, "Lin", "platform")], ["id", "name", "team"]).write.format("delta").mode("append").save(TARGET)
            count = spark.read.format("delta").load(TARGET).count()
            print(f"Appended one row; Delta table now contains {count} rows")
        elif args.mode == "schema":
            spark.createDataFrame([(1, "Ada")], ["id", "name"]).write.format("delta").mode("overwrite").save(SCHEMA_TARGET)
            spark.createDataFrame([(2, "Grace", "data")], ["id", "name", "team"]).write.format("delta").option("mergeSchema", "true").mode("append").save(SCHEMA_TARGET)
            columns = spark.read.format("delta").load(SCHEMA_TARGET).columns
            if columns != ["id", "name", "team"]:
                raise RuntimeError(f"Schema evolution failed: got columns {columns}")
            print(f"Schema evolution succeeded: {columns}")
        elif args.mode == "history":
            history = spark.sql(f"DESCRIBE HISTORY '{TARGET}'").select("version", "operation").collect()
            print(f"Delta history: {[(row.version, row.operation) for row in history]}")
        else:
            spark.createDataFrame([(1, "before")], ["id", "state"]).write.format("delta").mode("overwrite").save(TIME_TRAVEL_TARGET)
            spark.createDataFrame([(2, "after")], ["id", "state"]).write.format("delta").mode("append").save(TIME_TRAVEL_TARGET)
            version_zero = [tuple(row) for row in spark.read.format("delta").option("versionAsOf", 0).load(TIME_TRAVEL_TARGET).collect()]
            if version_zero != [(1, "before")]:
                raise RuntimeError(f"Time travel verification failed: got {version_zero}")
            print(f"Time travel version 0: {version_zero}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
