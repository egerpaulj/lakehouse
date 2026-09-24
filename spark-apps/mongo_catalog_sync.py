"""Sync documents from a MongoDB collection into the Delta catalog.

The job is intentionally generic and driven entirely by CLI arguments so that
a single script can back many independently scheduled Airflow DAGs, each
pointing at a different MongoDB collection and catalog table.

Processing steps, per run:

1. Ensure the target catalog database exists (created if missing).
2. Read all documents currently in the configured MongoDB collection.
3. Append the documents to the target Delta catalog table (created if
   missing, otherwise appended to).
4. Delete the documents that were successfully added from MongoDB, using the
   exact `_id` values that were read, so documents inserted after the read
   started are left untouched for the next run.
"""

import argparse
import os
import sys

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import NullType

from bson import ObjectId
from pymongo import MongoClient


def create_spark(app_name: str) -> SparkSession:
    return (
        SparkSession.builder.appName(app_name)
        .remote(os.environ.get("SPARK_CONNECT_URL", "sc://spark-connect:15002"))
        .getOrCreate()
    )


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mongo-uri",
        default=os.environ.get("MONGO_URI", "mongodb://mongo:27017"),
        help="MongoDB connection URI (default: %(default)s, or $MONGO_URI)",
    )
    parser.add_argument("--mongo-database", required=True, help="Source MongoDB database")
    parser.add_argument("--mongo-collection", required=True, help="Source MongoDB collection")
    parser.add_argument("--catalog-database", required=True, help="Target Hive catalog database")
    parser.add_argument("--catalog-table", required=True, help="Target Delta catalog table")
    parser.add_argument(
        "--warehouse-root",
        default="s3a://warehouse",
        help="Root S3A path under which catalog databases are created (default: %(default)s)",
    )
    parser.add_argument(
        "--batch-limit",
        type=int,
        default=None,
        help="Optional cap on the number of documents processed in one run",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Read and catalog documents but skip deleting them from MongoDB",
    )
    return parser.parse_args(argv)


def ensure_catalog_database(spark: SparkSession, catalog_database: str, warehouse_root: str) -> None:
    spark.sql(
        f"CREATE DATABASE IF NOT EXISTS {catalog_database} "
        f"LOCATION '{warehouse_root}/{catalog_database}'"
    )


def delete_synced_documents(mongo_uri: str, mongo_database: str, mongo_collection: str, ids: list) -> int:
    """Delete the given MongoDB _id values now that they are in the catalog."""

    client = MongoClient(mongo_uri)
    try:
        collection = client[mongo_database][mongo_collection]
        string_ids = [str(oid) for oid in ids]
        # Chunk deletes to keep the $in filter list a reasonable size.
        deleted = 0
        chunk_size = 1000
        for start in range(0, len(string_ids), chunk_size):
            chunk = string_ids[start : start + chunk_size]
            result = collection.delete_many({"_id": {"$in": chunk}})
            deleted += result.deleted_count
        return deleted
    finally:
        client.close()


def main(argv=None) -> None:
    args = parse_args(argv)
    # Hive/Delta table identifiers only allow letters, numbers, and
    # underscores (even when quoted), so dots in a configured catalog table
    # name (e.g. "crawler.responses.raw", used for readability) are
    # normalized to underscores for the actual table name.
    table_name = args.catalog_table.replace(".", "_")
    app_name = f"mongo-catalog-sync-{args.mongo_collection}-{table_name}"
    spark = create_spark(app_name)
    try:
        ensure_catalog_database(spark, args.catalog_database, args.warehouse_root)

        read_df = (
            spark.read.format("mongodb")
            .option("connection.uri", args.mongo_uri)
            .option("database", args.mongo_database)
            .option("collection", args.mongo_collection)
            .load()
        )

        if args.batch_limit:
            read_df = read_df.limit(args.batch_limit)

        read_df = read_df.withColumn("_synced_at", F.current_timestamp()).cache()
        total = read_df.count()
        if total == 0:
            print(f"No documents found in {args.mongo_database}.{args.mongo_collection}; nothing to sync")
            return

        for field in read_df.schema.fields:
            if isinstance(field.dataType, NullType):
                read_df = read_df.withColumn(
                    field.name,
                    F.lit(None).cast("string")
                )

        # The connector infers "_id" as a plain hex string by default (not a
        # struct with an "oid" field), so read it directly.
        source_ids = [row["id"] for row in read_df.select(F.col("_id").alias("id")).collect()]

        full_table_name = f"spark_catalog.{args.catalog_database}.{table_name}"
        if spark.catalog.tableExists(full_table_name):
            read_df.write.format("delta").mode("append").saveAsTable(full_table_name)
        else:
            read_df.write.format("delta").mode("overwrite").saveAsTable(full_table_name)
        print(f"Wrote {total} document(s) from {args.mongo_collection} to {full_table_name}")

        read_df.unpersist()

        if args.dry_run:
            print("Dry run: skipping deletion of synced documents from MongoDB")
            return

        deleted = delete_synced_documents(
            args.mongo_uri, args.mongo_database, args.mongo_collection, source_ids
        )
        print(f"Deleted {deleted} synced document(s) from {args.mongo_database}.{args.mongo_collection}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main(sys.argv[1:])
