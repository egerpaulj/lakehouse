"""Stream Delta Change Data Feed changes from the bronze (b0) table to silver (s0).

On the first run the s0 table is created from a snapshot of b0, extended with
the decorator columns (summary, ner_nel, text_embedding, summary_embedding).
Afterwards the Change Data Feed of b0 is merged into s0 by key. Only the b0
columns are written, so values added by the decorator jobs are preserved.
Columns named like the decorator columns are never copied from b0.
The stream uses ``availableNow`` triggers and a checkpoint, so each run
processes only the changes since the previous one.
"""

import argparse
import os
import sys

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from delta_streaming import (
    CDFStreamingPipeline,
    ChangeTypeFilter,
    DeltaCDFMergeSink,
    DeltaCDFSource,
    IdentityTransformer,
    StatsdMetrics,
    StreamConfig,
)

DECORATOR_COLUMNS = {
    "summary": "string",
    "ner_nel": "string",
    "text_embedding": "array<float>",
    "summary_embedding": "array<float>",
}


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-table", required=True, help="Bronze table, e.g. crawler.responses_b0")
    parser.add_argument("--target-table", required=True, help="Silver table, e.g. crawler.responses_s0")
    parser.add_argument("--checkpoint-location", required=True)
    parser.add_argument("--merge-key", default="_id")
    return parser.parse_args(argv)


def latest_version(spark: SparkSession, table: str) -> int:
    return int(spark.sql(f"DESCRIBE HISTORY {table} LIMIT 1").collect()[0]["version"])


def main(argv=None) -> None:
    args = parse_args(argv)
    spark = (
        SparkSession.builder.appName(f"cdf-{args.source_table}-to-{args.target_table}")
        .remote(os.environ.get("SPARK_CONNECT_URL", "sc://spark-connect:15002"))
        .getOrCreate()
    )
    try:
        props = spark.sql(f"SHOW TBLPROPERTIES {args.source_table}").collect()
        if not any(
            r["key"] == "delta.enableChangeDataFeed" and r["value"] == "true"
            for r in props
        ):
            spark.sql(
                f"ALTER TABLE {args.source_table} "
                "SET TBLPROPERTIES (delta.enableChangeDataFeed = true)"
            )

        starting_version = None
        if not spark.catalog.tableExists(args.target_table):
            # CDF only exists from the moment it was enabled, so seed s0 with
            # a snapshot of b0 and stream the changes after that version.
            starting_version = latest_version(spark, args.source_table)
            snapshot = spark.sql(
                f"SELECT * FROM {args.source_table} VERSION AS OF {starting_version}"
            )
            for name, data_type in DECORATOR_COLUMNS.items():
                # Replaces any same-named b0 column with the decorator column.
                snapshot = snapshot.withColumn(name, F.lit(None).cast(data_type))
            snapshot.write.format("delta").saveAsTable(args.target_table)
            seeded = spark.table(args.target_table).count()
            seed_metrics = StatsdMetrics(stream=args.target_table)
            seed_metrics.processed("insert", seeded)
            seed_metrics.merge_result(inserted=seeded, updated=0, deleted=0)
            print(f"Created {args.target_table} from {args.source_table} @ version {starting_version}")

        # Decorator columns are owned by s0 (b0 may have a same-named, empty one).
        source_columns = [
            c for c in spark.table(args.source_table).columns
            if c not in DECORATOR_COLUMNS
        ]
        config = StreamConfig(
            source_table=args.source_table,
            target_table=args.target_table,
            checkpoint_location=args.checkpoint_location,
            query_name=f"cdf-{args.target_table}",
            starting_version=starting_version,
        )
        key = args.merge_key
        pipeline = CDFStreamingPipeline(
            source=DeltaCDFSource(config),
            transformer=IdentityTransformer(),
            change_filter=ChangeTypeFilter(["insert", "update_postimage", "delete"]),
            sink=DeltaCDFMergeSink(
                spark=spark,
                merge_condition=f"target.`{key}` = source.`{key}`",
                metrics=StatsdMetrics(stream=args.target_table),
                columns=source_columns,
            ),
        )
        query = pipeline.start(spark=spark, config=config)
        query.awaitTermination()
        print(f"CDF stream {args.source_table} -> {args.target_table} finished")
    finally:
        spark.stop()


if __name__ == "__main__":
    main(sys.argv[1:])
