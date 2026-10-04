from datetime import datetime, timezone

from pyspark.sql import SparkSession

from delta_streaming import (
    CDFStreamingPipeline,
    ChangeTypeFilter,
    DeltaCDFMergeSink,
    DeltaCDFSource,
    IdentityTransformer,
    StatsdMetrics,
    StreamConfig,
)

spark = (
    SparkSession.builder
    .remote("sc://localhost:15002")
    .appName("example-delta-streaming")
    .getOrCreate()
)

database = "notebook_connect"
run_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
source_table = f"{database}.source_{run_id}"
target_table = f"{database}.target_{run_id}"
checkpoint_location = f"s3a://warehouse/notebook_delta_streaming_checkpoints/{run_id}"

spark.sql(
    f"CREATE DATABASE IF NOT EXISTS {database} "
    "LOCATION 's3a://warehouse/notebook_delta_streaming'"
)

initial_data = spark.createDataFrame(
    [(1, "Ada", "engineering"), (2, "Grace", "data")],
    ["id", "name", "team"],
)
(
    initial_data.write
    .format("delta")
    .option("delta.enableChangeDataFeed", "true")
    .mode("overwrite")
    .saveAsTable(source_table)
)
spark.createDataFrame([], initial_data.schema).write.format("delta").saveAsTable(
    target_table
)

print(f"Source: {source_table}")
print(f"Target: {target_table}")
print(f"Checkpoint: {checkpoint_location}")
spark.table(source_table).show()

config = StreamConfig(
    source_table=source_table,
    target_table=target_table,
    checkpoint_location=checkpoint_location,
    query_name=f"customer-cdf-{run_id}",
    starting_version=0,
)

pipeline = CDFStreamingPipeline(
    source=DeltaCDFSource(config),
    transformer=IdentityTransformer(),
    change_filter=ChangeTypeFilter(["insert", "update_postimage"]),
    sink=DeltaCDFMergeSink(
        spark=spark,
        merge_condition="target.id = source.id",
        metrics=StatsdMetrics(
            stream="customer_cdf",
        ),
    ),
)


def run_streaming_step(step_name):
    query = pipeline.start(spark=spark, config=config)
    query.awaitTermination()

    progress = query.lastProgress
    print(f"{step_name} - CDF offsets:")
    if progress:
        for source_progress in progress.get("sources", []):
            print(f"  startOffset: {source_progress.get('startOffset')}")
            print(f"  endOffset: {source_progress.get('endOffset')}")
    else:
        print("  No source progress was reported for this run.")

    print(f"{step_name} - target table:")
    spark.table(target_table).orderBy("id").show()


run_streaming_step("Initial batch")

spark.sql(f"UPDATE {source_table} SET name = 'Ada Lovelace' WHERE id = 1")
spark.createDataFrame(
    [(3, "Linus", "platform")], ["id", "name", "team"]
).write.format("delta").mode("append").saveAsTable(source_table)

print("New source rows:")
spark.table(source_table).orderBy("id").show()

run_streaming_step("Incremental batch")

spark.stop()
