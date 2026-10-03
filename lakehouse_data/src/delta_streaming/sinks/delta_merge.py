from collections.abc import Sequence

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.streaming.query import StreamingQuery

from delta_streaming.core.config import StreamConfig
from delta_streaming.core.sink import ChangeSink

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
        upsert_change_types: Sequence[str] | None = None,
    ):
        self._spark = spark
        self._merge_condition = merge_condition

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

            view = f"_cdf_batch_{batch_id}"
            batch_df.createOrReplaceTempView(view)
            batch_df.sparkSession.sql(
                f"""
                MERGE INTO {target_table} AS target
                USING {view} AS source
                ON {merge_condition}
                WHEN MATCHED AND source._change_type = 'delete'
                    THEN DELETE
                WHEN MATCHED AND source._change_type IN ({upsert_types})
                    THEN UPDATE SET *
                WHEN NOT MATCHED AND source._change_type IN ({upsert_types})
                    THEN INSERT *
                """
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
