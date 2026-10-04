import time
from collections.abc import Sequence

from pyspark import cloudpickle
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.streaming.query import StreamingQuery

from delta_streaming.core.config import StreamConfig
from delta_streaming.core.sink import ChangeSink
from delta_streaming import metrics as metrics_module
from delta_streaming.metrics import StatsdMetrics

class DeltaCDFMergeSink(ChangeSink):
    """
    Applies Delta CDF records to a target Delta table using
    foreachBatch + MERGE.

    Default behavior:

        insert            -> INSERT
        update_postimage  -> UPDATE / INSERT
        delete            -> DELETE

    update_preimage is ignored.
    """

    DEFAULT_UPSERT_TYPES = (
        "insert",
        "update_postimage",
    )

    def __init__(
        self,
        spark: SparkSession,
        merge_condition: str,
        metrics: StatsdMetrics | None = None,
        upsert_change_types: Sequence[str] | None = None,
    ):
        self._spark = spark
        self._merge_condition = merge_condition
        self._metrics = metrics

        self._upsert_change_types = tuple(
            upsert_change_types
            or self.DEFAULT_UPSERT_TYPES
        )

    def write(
        self,
        df: DataFrame,
        config: StreamConfig,
    ) -> StreamingQuery:
        # Copy to locals: the closure is pickled and must not capture `self`
        # (it holds a SparkSession, which is not picklable under Spark Connect).
        merge_condition = self._merge_condition
        metrics = self._metrics
        if metrics is not None:
            # The foreachBatch worker runs server-side, where this package
            # is not installed: ship the metrics module by value.
            cloudpickle.register_pickle_by_value(metrics_module)
        target_table = config.target_table
        upsert_types = ", ".join(
            f"'{value}'"
            for value in self._upsert_change_types
        )

        def merge_batch(
            batch_df: DataFrame,
            batch_id: int,
        ) -> None:
            if batch_df.isEmpty():
                return

            started_at = time.monotonic()
            view = f"_cdf_batch_{batch_id}"
            try:
                batch_df.createOrReplaceTempView(view)
                if metrics is not None:
                    counts = {
                        row["_change_type"]: row["count"]
                        for row in batch_df.groupBy("_change_type")
                        .count()
                        .collect()
                    }
                    metrics.observe_batch_rows(sum(counts.values()))

                result = batch_df.sparkSession.sql(
                    f"""
                    MERGE INTO {target_table} AS target
                    USING {view} AS source
                    ON {merge_condition}
                    WHEN MATCHED AND source._change_type = 'delete'
                        THEN DELETE
                    WHEN MATCHED
                        AND source._change_type IN ({upsert_types})
                        THEN UPDATE SET *
                    WHEN NOT MATCHED
                        AND source._change_type IN ({upsert_types})
                        THEN INSERT *
                    """
                ).collect()

                if metrics is not None:
                    for change_type, count in counts.items():
                        metrics.processed(change_type, count)
                    row = result[0].asDict() if result else {}
                    metrics.merge_result(
                        inserted=int(row.get("num_inserted_rows") or 0),
                        updated=int(row.get("num_updated_rows") or 0),
                        deleted=int(row.get("num_deleted_rows") or 0),
                    )
                    metrics.batch_succeeded()
            except Exception as exc:
                if metrics is not None:
                    metrics.batch_failed(exc)
                raise
            finally:
                if metrics is not None:
                    metrics.observe_batch_duration(
                        time.monotonic() - started_at
                    )

        writer = (
            df.writeStream
            .foreachBatch(merge_batch)
            .option(
                "checkpointLocation",
                config.checkpoint_location,
            )
            .trigger(availableNow=True)
        )

        if config.query_name:
            writer = writer.queryName(config.query_name)

        return writer.start()
